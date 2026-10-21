"""Large dependency indexes and archive I/O must not stall proxy networking."""
import asyncio,inspect,json,sys,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import external_links as links
import capture_addon as capture
from import_har import save
from mitmproxy import http
from mitmproxy.test import tflow

class DependencyIndex(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.file=Path(self.tmp.name)/'lesson_links.json'
        self.patch=patch.object(links,'FILE',self.file);self.patch.start();links.INDEX=None
    def tearDown(self):
        self.patch.stop();links.INDEX=None;self.tmp.cleanup()
    def test_discovery_batches_writes_and_reuses_index(self):
        root='https://resources.example.org/app/index.html'
        save(self.file,{root:{'resources':[root]}})
        with patch.object(links,'load',wraps=links.load) as read,patch.object(links,'save',wraps=links.save) as write:
            links.hosts()
            for _ in range(20):links.hosts();links.associate(root,root)
            self.assertEqual(1,read.call_count);self.assertEqual(0,write.call_count)
            links.discover(root,(''.join('<img src="image%d.png">'%i for i in range(30))).encode(),'text/html')
            self.assertEqual(1,write.call_count);self.assertEqual(1,read.call_count)
            links.associate(root+'?__izzi_offline_recover=123',root)
            self.assertEqual(1,write.call_count)
        self.assertEqual(31,len(json.loads(self.file.read_text()) [root]['resources']))
        data=json.loads(self.file.read_text());data['https://new.example.org/']={'resources':[]};save(self.file,data)
        self.assertIn('new.example.org',links.hosts())
    def test_link_dependencies_honor_the_first_html_base(self):
        root='https://bg.izzi.digital/DOS/888413/datastore/blocks/657825/index.html'
        links.register(root)
        links.discover(root,b'<base href="/datastore/blocks/657825/"><base href="/ignored/"><script src="variables.js"></script><link rel="stylesheet" href="assets/style.css">','text/html')
        data=json.loads(self.file.read_text())[root]['resources']
        self.assertIn('https://bg.izzi.digital/datastore/blocks/657825/variables.js',data)
        self.assertIn('https://bg.izzi.digital/datastore/blocks/657825/assets/style.css',data)
        self.assertNotIn('https://bg.izzi.digital/DOS/888413/datastore/blocks/657825/variables.js',data)
        links.discover('https://bg.izzi.digital/datastore/blocks/657825/assets/style.css',b'body{background:url(../images/loading-icon.gif)}','text/css')
        data=json.loads(self.file.read_text())[root]['resources']
        self.assertIn('https://bg.izzi.digital/datastore/blocks/657825/images/loading-icon.gif',data)

    def test_css_tokens_skip_embedded_svg_strings_comments_and_local_fragments(self):
        from css_dependencies import external_targets
        root='https://api.izzi.digital/datastore/blocks/657825/assets/style.css'
        css=r'''/* url(comment.png) */
        .x{content:'url(string.png)';background:url("data:image/svg+xml,%3Csvg%3Eurl(%23SVGID_4_)%3C/svg%3E");
        filter:url(#mask);mask:url('\23 mask');border-image:url(DATA:image/svg+xml,svg(url(%23nested)));}
        @import /* note */ "theme.css";
        .y{background:URL('../real.svg#symbol');mask:url(%23actual.svg);src:url(font.woff2?v=1#face)}
        '''
        targets=external_targets(css,root)
        self.assertEqual({root.rsplit('/',1)[0]+'/theme.css',
            'https://api.izzi.digital/datastore/blocks/657825/real.svg#symbol',
            root.rsplit('/',1)[0]+'/%23actual.svg',root.rsplit('/',1)[0]+'/font.woff2?v=1#face'},targets)

    def test_old_embedded_svg_dependencies_are_repaired_but_real_files_still_block(self):
        import capture_completion as completion
        from css_dependencies import legacy_targets
        root='https://api.izzi.digital/datastore/blocks/657825/index.html'
        css=root.rsplit('/',1)[0]+'/assets/style.css'
        text='.x{background:url("data:image/svg+xml,%3Csvg%3Eurl(%23first)url(%23SVGID_4_)%3C/svg%3E")} .y{mask:url(%23actual.svg)}'
        archive=self.file.parent/'archive';archive.mkdir();mapping={}
        def add(url,body,content_type):
            name=str(len(mapping))+'.bin';(archive/name).write_bytes(body)
            mapping[url]=[{'key':name,'body_available':True,'status':200,'method':'GET','size':len(body),'decoded':True,'content_type':content_type}]
        add(root,b'<html>app</html>','text/html');add(css,text.encode(),'text/css')
        fake=css.rsplit('/',1)[0]+'/%23SVGID_4_';real=css.rsplit('/',1)[0]+'/%23actual.svg'
        save(self.file,{root:{'resources':[root,css,*sorted(legacy_targets(text,css))]}})
        with patch.object(links,'CSS_CACHE',links.OrderedDict()):
            result=links.status(root,mapping,archive)
            self.assertEqual([real],result['missing']);self.assertFalse(result['available'])
            self.assertNotIn(fake,json.loads(self.file.read_text())[root]['resources'])
            self.assertNotIn(fake,links.state()['owners'])
            with patch.object(links,'save',side_effect=AssertionError('Repeated migration write')):
                self.assertEqual([real],links.status(root,mapping,archive)['missing'])
            lesson='https://bg.izzi.digital/DOS/888413/888428.html';add(lesson,b'<html>lesson</html>','text/html')
            with patch.object(completion,'CURRENT',None):
                completion.start(lesson)
                for url in (root,css,fake,real):completion.expect(url,lesson)
                completion.CURRENT['activity']-=2
                self.assertEqual([real], [row['url'] for row in completion.status(lesson,[],mapping,archive)['missing']])
                add(real,b'<svg xmlns="http://www.w3.org/2000/svg"></svg>','image/svg+xml')
                self.assertTrue(links.status(root,mapping,archive)['available'])
                self.assertTrue(completion.status(lesson,[],mapping,archive)['available'])
            # The archived content is read once, then cache reused until changed.
            with patch.object(Path,'read_text',side_effect=AssertionError('Unexpected reread')):
                self.assertIn(fake,links.false_css_dependencies([css],mapping,archive))
            text+='.z{mask:url(%23SVGID_4_)}'
            (archive/mapping[css][0]['key']).write_bytes(text.encode())
            mapping[css][0]['size']=len(text.encode())
            self.assertNotIn(fake,links.false_css_dependencies([css],mapping,archive))

    def test_script_redirect_landing_does_not_pollute_app_and_repairs_old_index(self):
        root='https://api.izzi.digital/datastore/blocks/9/index.html'
        script='https://tests.school.bg/broken.js';redirect='https://klett.bg/broken.js';landing='https://klett.bg/'
        junk='https://klett.bg/menu.png';needed='https://klett.bg/needed.svg'
        links.register(root);links.associate(script,root)
        links.associate_redirect(redirect,script);links.associate_redirect(landing,redirect)
        links.discover(landing,b'<img src="/menu.png">','text/html')
        self.assertNotIn(junk,links.state()['data'][root]['resources'])
        # The same landing page remains a valid independently registered page.
        links.register(landing);links.discover(landing,b'<img src="/menu.png">','text/html')
        self.assertIn(junk,links.state()['data'][landing]['resources'])
        self.assertNotIn(junk,links.state()['data'][root]['resources'])
        archive=self.file.parent/'bodies';archive.mkdir();mapping={}
        def add(url,body,ct='text/html',status=200,location=None):
            key=str(len(mapping));(archive/key).write_bytes(body)
            row={'key':key,'size':len(body),'body_available':True,'method':'GET','status':status,'content_type':ct}
            if location:row['location']=location
            mapping[url]=[row]
        add(root,('<html><script src="'+script+'"></script><img src="'+needed+'"></html>').encode())
        add(script,b'redirect',status=301,location=redirect);add(redirect,b'redirect',status=302,location=landing)
        add(landing,b'<html><img src="/menu.png"><img src="/needed.svg"></html>')
        save(self.file,{root:{'resources':[root,script,redirect,landing,junk,needed]}});links.INDEX=None
        report=links.status(root,mapping,archive)
        self.assertNotIn(junk,report['missing']);self.assertNotIn(landing,report['missing'])
        self.assertIn(script,report['missing']);self.assertIn(needed,report['missing'])
        self.assertNotIn(junk,links.state()['data'][root]['resources'])
        # A server may return the unrelated landing HTML directly at a .js URL.
        mapping[script][0].update(status=200,content_type='text/html')
        body=b'<html><img src="https://klett.bg/menu.png"></html>'
        (archive/mapping[script][0]['key']).write_bytes(body);mapping[script][0]['size']=len(body)
        mapping[script][0].pop('location',None)
        save(self.file,{root:{'resources':[root,script,junk,needed]}});links.INDEX=None
        report=links.status(root,mapping,archive)
        self.assertIn(script,report['missing']);self.assertNotIn(junk,report['missing'])

    def test_platform_home_does_not_attach_unrelated_catalog(self):
        root='https://bg.izzi.digital/explanation.html'
        links.register(root)
        links.associate('https://bg.izzi.digital/api/online-bookshelf-publications','https://bg.izzi.digital/')
        self.assertEqual([root],json.loads(self.file.read_text())[root]['resources'])
        links.register('https://external.example.org/app/')
        links.associate('https://cdn.example.org/image.png','https://external.example.org/')
        self.assertIn('cdn.example.org',links.hosts())

class ProxyWorkers(unittest.IsolatedAsyncioTestCase):
    async def test_network_hooks_continue_while_archive_worker_is_busy(self):
        entered=threading.Event();release=threading.Event();threads=[]
        def archive(flow):
            threads.append(threading.get_ident());entered.set()
            if not release.wait(5):raise RuntimeError('worker did not resume')
        flow=tflow.tflow(resp=True);flow.request=http.Request.make('GET','https://bg.izzi.digital/app.js')
        with patch.object(capture,'response_sync',side_effect=archive),patch.object(links,'hosts',return_value=frozenset()):
            task=asyncio.create_task(capture.response(flow))
            try:
                self.assertTrue(await asyncio.to_thread(entered.wait,2))
                other=tflow.tflow(resp=True);other.request=http.Request.make('GET','https://unrelated.example.org/')
                self.assertIsNone(capture.request(other));self.assertIsNone(capture.response(other))
                page=tflow.tflow();page.request=http.Request.make('GET','https://bg.izzi.digital/app.css')
                self.assertIsNone(capture.request(page));self.assertEqual('no-cache',page.request.headers['cache-control'])
                self.assertFalse(task.done());self.assertNotEqual(threading.get_ident(),threads[0])
            finally:
                release.set();await task
                capture.done()
    async def test_control_hook_runs_off_network_thread(self):
        thread=threading.get_ident();seen=[]
        flow=tflow.tflow();flow.request=http.Request.make('GET','https://bg.izzi.digital/__offline_capture__/image_status')
        with patch.object(capture,'request_sync',side_effect=lambda f:seen.append(threading.get_ident())):
            result=capture.request(flow);self.assertTrue(inspect.isawaitable(result));await result
        self.assertNotEqual(thread,seen[0]);capture.done()

if __name__=='__main__':unittest.main()
