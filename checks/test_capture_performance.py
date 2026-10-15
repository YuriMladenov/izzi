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
