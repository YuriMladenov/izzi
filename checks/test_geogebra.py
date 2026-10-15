"""Runtime ZIP installation, GeoGebra replay and capture on private fixtures."""
import gzip,io,json,shutil,subprocess,sys,unittest,zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import geogebra_runtime as runtime,install_geogebra,server,capture_addon,capture_completion
from replay_resolver import usable_body
from checks import test_library_workflow as fixtures
from mitmproxy import http

class GeoGebra(unittest.TestCase):
    tearDown=fixtures.LibraryWorkflow.tearDown
    add=fixtures.LibraryWorkflow.add
    write=fixtures.LibraryWorkflow.write
    start_server=fixtures.LibraryWorkflow.start_server
    stop_server=fixtures.LibraryWorkflow.stop_server
    request=fixtures.LibraryWorkflow.request
    def setUp(self):
        fixtures.LibraryWorkflow.setUp(self)
        directory=self.root/'vendor/geogebra/HTML5/5.0'
        item=patch.object(runtime,'DIRECTORY',directory);self.patches.append(item);item.start()
        self.write('books.json',{});self.write('url_map.json',{})
    def bundle(self,body=None,extra=None):
        file=self.root/'official-fixture.zip'
        with zipfile.ZipFile(file,'w') as package:
            package.writestr('bundle/HTML5/5.0/web3d/web3d.nocache.js',body or b'/*'+b'x'*2048+b'*/window.ggbFixture=true;')
            package.writestr('bundle/HTML5/5.0/web3d/A.cache.js',b'window.permutation=true;')
            package.writestr('bundle/LICENSE.txt','Fixture notice')
            if extra:
                for name,value in extra.items():package.writestr(name,value)
        return file
    def install(self):return install_geogebra.install(self.bundle(),runtime.DIRECTORY.parent.parent)
    def test_install_preserves_notices_hashes_and_previous_version(self):
        self.assertEqual(2,self.install());self.assertTrue(runtime.installed())
        base=runtime.DIRECTORY.parent.parent
        manifest=json.loads((base/'installation.json').read_text(encoding='utf8'))
        self.assertEqual(2,len(manifest['files']));self.assertTrue(list((base/'package-notices').iterdir()))
        previous=(runtime.DIRECTORY/'web3d/web3d.nocache.js').read_bytes()
        with self.assertRaisesRegex(ValueError,'Unsafe ZIP'):install_geogebra.install(self.bundle(extra={'../escape':b'bad'}),base)
        self.assertEqual(previous,(runtime.DIRECTORY/'web3d/web3d.nocache.js').read_bytes());self.assertFalse((self.root/'escape').exists())
        install_geogebra.install(self.bundle(body=b'window.updated=true;'),base)
        self.assertTrue(list((base.parent/'geogebra-backups').iterdir()))
        self.assertEqual(b'window.updated=true;',(runtime.DIRECTORY/'web3d/web3d.nocache.js').read_bytes())
        other=self.root/'web-only.zip'
        with zipfile.ZipFile(other,'w') as package:package.writestr('web/web.nocache.js','web')
        with self.assertRaisesRegex(ValueError,'compatible web3d'):install_geogebra.install(other,base)
    def test_runtime_routes_gzip_archive_precedence_and_traversal(self):
        self.install();self.start_server()
        for prefix in (runtime.PREFIX,'/DOS/887348'+runtime.PREFIX):
            status,headers,body=self.request(prefix+'web3d/web3d.nocache.js',headers={'Accept-Encoding':'gzip'})
            self.assertEqual(200,status);self.assertIn('javascript',headers['Content-Type'])
            self.assertIn(b'ggbFixture',gzip.decompress(body));self.assertEqual('gzip',headers['Content-Encoding'])
        for path in ('web3d/%2e%2e/%2e%2e/installation.json','web3d/%5c..%5csecret','web3d/missing.cache.js'):
            self.assertEqual(404,self.request(runtime.PREFIX+path)[0])
        self.assertIsNone(runtime.asset('evil.example',runtime.PREFIX+'web3d/web3d.nocache.js'))
        self.add(runtime.PREFIX+'web3d/web3d.nocache.js',b'/* archived original */',content_type='application/javascript')
        self.assertEqual(b'/* archived original */',self.request(runtime.PREFIX+'web3d/web3d.nocache.js')[2])
    def test_ggb_is_a_real_geogebra_zip_and_replays_with_correct_mime(self):
        buffer=io.BytesIO()
        with zipfile.ZipFile(buffer,'w') as package:package.writestr('geogebra.xml','<?xml version="1.0"?><geogebra format="5.0"></geogebra>')
        good=self.add('/datastore/15/publication/1/files/demo.ggb',buffer.getvalue(),content_type='application/octet-stream')
        self.assertTrue(usable_body(good,self.archive,'.ggb'))
        for name,body in [('login.ggb',b'<html>Login</html>'),('truncated.ggb',buffer.getvalue()[:30])]:
            row=self.add('/datastore/15/publication/1/files/'+name,body)
            self.assertFalse(usable_body(row,self.archive,'.ggb'))
        self.start_server()
        status,headers,body=self.request('/DOS/1/datastore/15/publication/1/files/demo.ggb')
        self.assertEqual(200,status);self.assertEqual('application/vnd.geogebra.file',headers['Content-Type']);self.assertEqual(buffer.getvalue(),body)
        self.assertEqual(404,self.request('/datastore/15/publication/1/files/login.ggb')[0])
    def test_capture_proxy_and_strict_barrier_recognize_installed_runtime(self):
        self.install();lesson='https://bg.izzi.digital/DOS/1/2.html'
        self.add(lesson,b'<html>lesson</html>')
        url='https://bg.izzi.digital'+runtime.PREFIX+'web3d/web3d.nocache.js'
        flow=SimpleNamespace(id='ggb',request=http.Request.make('GET',url,headers={'Referer':lesson}),response=None)
        with patch.multiple(capture_addon,URL_MAP_FILE=self.state/'url_map.json',ARCHIVE_DIR=self.archive),patch.object(capture_completion,'CURRENT',None):
            capture_completion.start(lesson);capture_addon.request(flow)
            self.assertEqual(200,flow.response.status_code);self.assertEqual('1',flow.response.headers['X-IZZI-Archive'])
            capture_addon.response(flow);capture_completion.CURRENT['activity']-=2
            self.assertTrue(capture_completion.status(lesson,[],self.mapping,self.archive)['available'])
            (runtime.DIRECTORY/'web3d/web3d.nocache.js').unlink()
            self.assertFalse(capture_completion.status(lesson,[],self.mapping,self.archive)['available'])
    @unittest.skipUnless(shutil.which('node'),'Node.js required for capture runtime check')
    def test_hidden_ggb_capture(self):
        result=subprocess.run(['node',str(Path(__file__).with_name('test_geogebra_capture.js'))],capture_output=True,text=True,encoding='utf8',timeout=10)
        self.assertEqual(0,result.returncode,result.stdout+result.stderr)

if __name__=='__main__':unittest.main()
