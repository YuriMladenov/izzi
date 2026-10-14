"""Incomplete MP4 inspection, range resume, access control and session scope."""
import hashlib,json,sys,unittest,urllib.error
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import archive_db,video_resume,range_assembler,capture_addon,operations
from mitmproxy import http
from checks import test_library_workflow as fixtures

class Resume(unittest.TestCase):
    setUp=fixtures.LibraryWorkflow.setUp
    tearDown=fixtures.LibraryWorkflow.tearDown
    write=fixtures.LibraryWorkflow.write
    start_server=fixtures.LibraryWorkflow.start_server
    stop_server=fixtures.LibraryWorkflow.stop_server
    request=fixtures.LibraryWorkflow.request
    def setUp(self):
        fixtures.LibraryWorkflow.setUp(self)
        self.write('url_map.json',{});self.write('books.json',{});archive_db.initialize(self.state)
        self.url='https://api.izzi.digital/datastore/15/publication/1/video/test.mp4'
        self.body=b'\x00\x00\x00\x18ftypmp42'+bytes(range(116))
        self.extra=[patch.multiple(video_resume,ARCHIVE_DIR=self.archive,STATE_DIR=self.state,URL_MAP_FILE=self.state/'url_map.json'),patch.multiple(range_assembler,ARCHIVE_DIR=self.archive,STATE_DIR=self.state,STATE=self.state/'range_assembly',URL_MAP_FILE=self.state/'url_map.json'),patch.multiple(capture_addon,ARCHIVE_DIR=self.archive,STATE_DIR=self.state,URL_MAP_FILE=self.state/'url_map.json',BOOKS_FILE=self.state/'books.json',VIDEO_HEADERS={}),patch.object(capture_addon,'observe'),patch.object(capture_addon,'add_media'),patch.object(capture_addon.external_links,'associate'),patch.object(capture_addon.external_links,'discover')]
        # Real OrderedDict behavior is needed for the bounded in-memory session cache.
        from collections import OrderedDict
        self.extra[2]=patch.multiple(capture_addon,ARCHIVE_DIR=self.archive,STATE_DIR=self.state,URL_MAP_FILE=self.state/'url_map.json',BOOKS_FILE=self.state/'books.json',VIDEO_HEADERS=OrderedDict())
        for p in self.extra:p.start()
    def tearDown(self):
        for p in reversed(self.extra):p.stop()
        fixtures.LibraryWorkflow.tearDown(self)
    def flow(self,start,end,url=None,resume=False,cookie=None,etag='"v1"'):
        url=url or self.url;headers={'Range':f'bytes={start}-{end}'}
        if resume:headers['X-IZZI-Resume']='1'
        if cookie:headers['Cookie']=cookie
        return SimpleNamespace(request=http.Request.make('GET',url,headers=headers),response=http.Response.make(206,self.body[start:end+1],{'Content-Type':'video/mp4','Content-Range':f'bytes {start}-{end}/{len(self.body)}','ETag':etag}),metadata={},client_conn=SimpleNamespace(peername=('127.0.0.1',12345)))
    def partial(self,start,end):capture_addon.response(self.flow(start,end))
    def test_missing_ranges_are_requested_once_and_video_becomes_playable(self):
        self.partial(0,19);self.partial(60,79)
        report=video_resume.inspect();self.assertEqual([[20,59],[80,127]],report['videos'][0]['missing'])
        calls=[]
        def fetch(client,url,start,end):
            calls.append((start,end));flow=self.flow(start,end,resume=True);flow.response=None;capture_addon.request(flow)
            if flow.response is None:flow.response=self.flow(start,end).response
            capture_addon.response(flow);return end-start+1
        jobs=video_resume.Jobs();jobs.state='running'
        with patch.object(video_resume,'opener',return_value=object()),patch.object(video_resume,'fetch',side_effect=fetch):jobs.run(report['videos'])
        self.assertEqual([(20,59),(80,127)],calls);self.assertEqual('success',jobs.snapshot()['state']);self.assertEqual([],video_resume.inspect()['videos'])
        self.start_server();status,headers,data=self.request('/__host__/api.izzi.digital/datastore/15/publication/1/video/test.mp4',headers={'Range':'bytes=14-39'})
        self.assertEqual(206,status);self.assertEqual(self.body[14:40],data)
    def test_missing_manifest_parts_and_moved_windows_paths_are_recovered(self):
        self.partial(0,19)
        manifest=range_assembler.manifest_path(self.url);data=json.loads(manifest.read_text(encoding='utf-8'));identity=range_assembler.uid(self.url)
        data['ranges'][0][2]='D:\\old\\izzi\\state\\range_assembly\\'+identity+'\\0-19.part';manifest.write_text(json.dumps(data),encoding='utf-8')
        self.assertEqual(20,video_resume.inspect()['videos'][0]['covered'])
        (self.state/'range_assembly'/identity/'0-19.part').unlink()
        # The separate archived body can repopulate the missing .part.
        range_assembler.restore_archived(self.url)
        self.assertEqual(20,video_resume.inspect()['videos'][0]['covered'])
        self.assertTrue((self.state/'range_assembly'/identity/'0-19.part').is_file())
    def test_authorization_is_exact_url_memory_only_and_lan_resume_is_rejected(self):
        self.partial(0,19)
        authenticated=self.flow(0,19,cookie='fixture-private-cookie');authenticated.request.headers['Authorization']='Bearer fixture-private-token';capture_addon.response(authenticated)
        flow=self.flow(20,39,resume=True);flow.response=None;capture_addon.request(flow)
        self.assertEqual('fixture-private-cookie',flow.request.headers['Cookie']);self.assertEqual('Bearer fixture-private-token',flow.request.headers['Authorization']);self.assertNotIn('X-IZZI-Resume',flow.request.headers)
        other=self.flow(20,39,url=self.url.replace('test.mp4','other.mp4'),resume=True);other.response=None;capture_addon.request(other)
        self.assertNotIn('Cookie',other.request.headers)
        remote=self.flow(20,39,resume=True);remote.client_conn.peername=('10.0.0.61',4567);remote.response=None;capture_addon.request(remote)
        self.assertEqual(403,remote.response.status_code)
        for path in self.state.rglob('*'):
            if path.is_file():self.assertNotIn(b'fixture-private',path.read_bytes())
    def test_version_change_discards_prior_coverage_and_replaces_same_sized_part(self):
        self.partial(0,19);self.partial(60,79)
        changed=self.flow(0,19,etag='"v2"');changed.response.content=b'\x00\x00\x00\x18ftypmp42'+b'z'*8
        capture_addon.response(changed)
        row=video_resume.inspect()['videos'][0];self.assertEqual(20,row['covered']);self.assertEqual([[20,127]],row['missing'])
        path=self.state/'range_assembly'/range_assembler.uid(self.url)/'0-19.part';self.assertEqual(changed.response.content,path.read_bytes())
    def test_permission_failure_preserves_parts_and_stop_preserves_queue(self):
        self.partial(0,19);report=video_resume.inspect();jobs=video_resume.Jobs();jobs.state='running'
        error=urllib.error.HTTPError(self.url,403,'Denied',{},None)
        with patch.object(video_resume,'opener',return_value=object()),patch.object(video_resume,'fetch',side_effect=error):jobs.run(report['videos'])
        self.assertEqual('failed',jobs.snapshot()['state']);self.assertIn('правилния профил',jobs.snapshot()['log']);self.assertEqual(20,video_resume.inspect()['videos'][0]['covered'])
        jobs=video_resume.Jobs();jobs.cancel.set()
        with patch.object(video_resume,'opener',return_value=object()),patch.object(video_resume,'fetch') as fetch:jobs.run(report['videos']);fetch.assert_not_called()
        self.assertEqual('stopped',jobs.snapshot()['state'])
    def test_unknown_size_full_response_and_compressed_range_rejection(self):
        from import_har import load,save
        error_body=b'<html>missing</html>';key='missing.html';(self.archive/key).write_bytes(error_body)
        mapping=load(self.state/'url_map.json',{});mapping[self.url]=[{'key':key,'status':404,'body_available':True,'size':len(error_body),'method':'GET','content_type':'text/html'}];save(self.state/'url_map.json',mapping)
        report=video_resume.inspect();self.assertIsNone(report['videos'][0]['total'])
        calls=[]
        def full(client,url,start,end):
            calls.append((start,end));flow=self.flow(0,len(self.body)-1,resume=True);flow.metadata={'izzi_resume':True}
            flow.response=http.Response.make(200,self.body,{'Content-Type':'video/mp4'});capture_addon.response(flow)
        jobs=video_resume.Jobs();jobs.state='running'
        with patch.object(video_resume,'opener',return_value=object()),patch.object(video_resume,'fetch',side_effect=full):jobs.run(report['videos'])
        self.assertEqual([(0,video_resume.CHUNK-1)],calls);self.assertEqual('success',jobs.snapshot()['state']);self.assertEqual([],video_resume.inspect()['videos'])
        flow=self.flow(0,19,resume=True);flow.metadata={'izzi_resume':True};flow.response.headers['Content-Encoding']='gzip'
        capture_addon.response(flow);self.assertEqual(502,flow.response.status_code)

    def test_video_page_and_actions_require_local_control(self):
        self.partial(0,19);self.start_server()
        self.assertIn('Недовършени видеа'.encode(),self.request('/__videos__')[2])
        self.assertIn(b'/__videos__/action',self.request('/__ui__/videos.js')[2])
        self.assertEqual(403,self.request('/__videos__',headers={'Host':'10.0.0.2'})[0])
        self.assertEqual(403,self.request('/__videos__/status',headers={'Host':'10.0.0.2'})[0])
        self.assertEqual(403,self.request('/__videos__/action',body=b'{"action":"start"}',headers={'Content-Type':'application/json'})[0])
        headers={'Content-Type':'application/json','X-IZZI-Control':operations.tasks.token}
        with patch.object(operations,'capture_port_busy',return_value=False):self.assertEqual(400,self.request('/__videos__/action',body=b'{"action":"start"}',headers=headers)[0])
        with patch.object(video_resume.jobs,'start') as start:
            self.assertEqual(200,self.request('/__videos__/action',body=b'{"action":"start","id":"all"}',headers=headers)[0]);start.assert_called_once_with('all')
        self.assertEqual(403,self.request('/__videos__/action',body=b'{"action":"stop"}',headers={**headers,'Origin':'https://example.org'})[0])
        self.assertFalse(video_resume.safe_url('https://example.org/video.mp4'));self.assertFalse(video_resume.safe_url('https://api.izzi.digital@127.0.0.1/video.mp4'))
if __name__=='__main__':unittest.main()
