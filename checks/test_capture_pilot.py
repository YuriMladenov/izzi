"""Interactive coverage survives restarts, but never bypasses missing resources."""
import base64,hashlib,io,json,sys,tempfile,unittest,zipfile,subprocess,shutil
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import capture_pilot as pilot,capture_addon
from mitmproxy import http

class Pilot(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.archive=self.root/'archive';self.archive.mkdir();self.state=self.root/'state';self.mapping={}
        self.lesson='https://bg.izzi.digital/DOS/1/8.html';self.version='123456789abc'
        self.html=b'<body data-page-template="pdf_page"><izzi-block block-id="10" block-type="objects-slider"><izzi-block block-id="11" block-type="fill-in"></izzi-block><izzi-block block-id="12" block-type="geogebra"></izzi-block></izzi-block></body>'
        self.add(self.lesson,self.html)
    def tearDown(self):self.tmp.cleanup()
    def add(self,url,body,status=200):
        key=hashlib.sha256(body).hexdigest();(self.archive/key).write_bytes(body)
        self.mapping[url]=[{'key':key,'status':status,'method':'GET','size':len(body),'body_available':True,'decoded':True}]
        return key
    def begin(self):return pilot.begin(self.state,self.lesson,self.version,self.mapping,self.archive)
    def item(self,key,status='verified',**proof):
        return pilot.record(self.state,{'lesson':self.lesson,'revision':self.session['revision'],'key':key,'state':status,'proof':{'assets':[self.lesson],**proof}},self.mapping,self.archive)
    def test_inventory_and_restart_revalidation_and_changed_content(self):
        self.session=self.begin();rows=self.session['inventory']
        self.assertEqual(['block:10','block:11','block:12'],[r['key'] for r in rows]);self.assertEqual('10',rows[2]['panel']);self.assertEqual('block:10',rows[2]['parent'])
        image='https://bg.izzi.digital/datastore/example.png';key=self.add(image,b'PNG fixture')
        self.item('block:11',assets=[self.lesson,image]);self.item('slide:10:1')
        resumed=self.begin();self.assertIn('block:11',resumed['verified']);self.assertIn('slide:10:1',resumed['verified'])
        (self.archive/key).unlink();self.assertNotIn('block:11',self.begin()['verified'])
        self.add(image,b'new image');self.session=self.begin();self.item('block:11',assets=[self.lesson,image])
        self.add(image,b'different image body');self.assertNotIn('block:11',self.begin()['verified'])
        self.add(self.lesson,self.html+b'changed');fresh=self.begin();self.assertNotEqual(self.session['revision'],fresh['revision']);self.assertFalse(fresh['verified'])
        self.version='abcdef123456';self.assertNotEqual(fresh['revision'],self.begin()['revision'])
    def test_geogebra_requires_ready_and_valid_file_and_finish_checks_all_items(self):
        self.session=self.begin()
        with self.assertRaisesRegex(ValueError,'готовност'):self.item('block:12')
        ggb='https://bg.izzi.digital/datastore/test.ggb'
        self.add(ggb,b'<html>login</html>')
        with self.assertRaises(ValueError):self.item('block:12',ready=True,assets=[self.lesson,ggb])
        buffer=io.BytesIO()
        with zipfile.ZipFile(buffer,'w') as z:z.writestr('geogebra.xml','<geogebra format="5.0"></geogebra>')
        self.add(ggb,buffer.getvalue());self.item('block:12',ready=True,assets=[self.lesson,ggb])
        finish=lambda:pilot.finish(self.state,{'lesson':self.lesson,'revision':self.session['revision']},self.mapping,self.archive)
        self.assertFalse(finish()['available'])
        self.item('block:11');self.item('block:10');self.item('slide:10:1');self.assertTrue(finish()['available'])
        self.assertFalse(pilot.report(self.state)['offline_tested'])
        self.add(self.lesson,self.html+b'new capture')
        with self.assertRaisesRegex(ValueError,'променен'):finish()
    def test_blank_page_requires_paper_images_and_viewer(self):
        self.add(self.lesson,b'<body data-page-template="pdf_page"></body>')
        viewer='https://bg.izzi.digital/DOS/1/99.html'
        image='https://bg.izzi.digital/datastore/page8.png'
        self.session=pilot.begin(self.state,self.lesson,self.version,self.mapping,self.archive,page_number=8,viewer=viewer,page_assets=[image])
        finish=lambda:pilot.finish(self.state,{'lesson':self.lesson,'revision':self.session['revision']},self.mapping,self.archive)
        self.assertFalse(finish()['available'])
        self.add(viewer,b'<html>viewer</html>');self.add(image,b'page image')
        self.assertTrue(finish()['available'])
        self.assertEqual({'/DOS/1/8.html':'/DOS/1/99.html?page=8&centrespread=0'},pilot.display_links(self.state,'1'))
        with self.assertRaisesRegex(ValueError,'another book'):
            pilot.begin(self.state,self.lesson,self.version,self.mapping,self.archive,viewer='https://bg.izzi.digital/DOS/2/99.html')

    def test_unknown_components_and_unsafe_data_cannot_be_marked_complete(self):
        self.add(self.lesson,b'<body data-page-template="pdf_page"><izzi-block block-id="90" block-type="unknown-game"></izzi-block></body>');self.session=self.begin()
        self.item('block:90','manual')
        with self.assertRaisesRegex(ValueError,'Непознат'):self.item('block:90')
        with self.assertRaises(ValueError):self.item('block:999')
        with self.assertRaises(ValueError):self.item('slide:999:1')
        self.assertIsNone(pilot.safe_asset('https://bg.izzi.digital/a.png?jwt=private'))
        self.assertIsNone(pilot.safe_asset('https://user:password@example.org/a'))
        with self.assertRaises(ValueError):pilot.begin(self.state,'https://other.example/DOS/1/8.html',self.version,self.mapping,self.archive)
    def test_control_endpoint_never_forwards_invalid_requests(self):
        def call(method,data=None,origin=None):
            request=http.Request.make(method,'https://bg.izzi.digital/__offline_capture__/pilot?book=1',json.dumps(data).encode() if data else b'')
            if origin:request.headers['Origin']=origin
            flow=SimpleNamespace(request=request,response=None)
            with patch.multiple(capture_addon,STATE_DIR=self.state,ARCHIVE_DIR=self.archive),patch.object(capture_addon,'load_json',return_value=self.mapping):capture_addon.request(flow)
            return flow.response
        self.assertEqual(200,call('GET').status_code)
        self.assertEqual(405,call('PUT').status_code)
        self.assertEqual(403,call('POST',{'action':'begin'},'https://other.example').status_code)
        self.assertEqual(400,call('POST',{'action':'arbitrary'}).status_code)
        response=call('POST',{'action':'begin','lesson':self.lesson,'version':self.version})
        self.assertEqual(200,response.status_code);self.assertTrue(json.loads(response.content)['capture'])
    def test_report_does_not_store_headers_or_answers_and_no_db_is_needed_to_read_empty_report(self):
        self.assertEqual([],pilot.report(self.state)['pages']);self.assertFalse(self.state.exists())
        self.session=self.begin();self.item('block:11')
        report=pilot.report(self.state,'1');self.assertEqual(1,len(report['pages']))
        self.assertNotIn('proof',report['pages'][0]['items'][0])
        self.assertFalse(report['offline_tested'])

    @unittest.skipUnless(shutil.which('node'),'Node.js required')
    def test_browser_readiness_and_resume(self):
        result=subprocess.run(['node',str(Path(__file__).with_name('test_capture_pilot.js'))],capture_output=True,text=True,encoding='utf8',timeout=15)
        self.assertEqual(0,result.returncode,result.stdout+result.stderr)

if __name__=='__main__':unittest.main()
