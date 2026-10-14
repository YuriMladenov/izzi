"""Strict capture waits for current-lesson GET bodies, not traversal markers."""
import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import capture_completion as completion
import capture_addon,capture_observed
from mitmproxy import http
class Completion(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.archive=Path(self.tmp.name);self.lesson='https://bg.izzi.digital/DOS/1/8.html'
        self.mapping={};self.patch=patch.object(completion,'CURRENT',None);self.patch.start();completion.start(self.lesson)
        self.add(self.lesson,b'<html>lesson</html>')
    def tearDown(self):self.patch.stop();self.tmp.cleanup()
    def add(self,url,body,status=200,content_range=None):
        key=str(len(self.mapping))+'.bin';(self.archive/key).write_bytes(body)
        row={'key':key,'status':status,'body_available':bool(body),'size':len(body),'method':'GET','content_type':'text/html' if body.startswith(b'<html') else 'application/octet-stream'}
        if content_range:row['content_range']=content_range
        self.mapping[url]=[row]
    def settled(self):completion.CURRENT['activity']-=2
    def test_pending_nested_requests_and_missing_files_prevent_done(self):
        css='https://bg.izzi.digital/profil/style.css';font='https://api.izzi.digital/fonts/font.woff2'
        self.assertTrue(completion.watch(css,'GET',self.lesson,'css'))
        self.assertTrue(completion.watch(font,'GET',css,'font'))
        self.add(css,b'body{}');self.add(font,b'wOF2font');self.settled()
        self.assertFalse(completion.status(self.lesson,[],self.mapping,self.archive)['available'])
        completion.finish('css');completion.finish('font');self.settled()
        self.assertTrue(completion.status(self.lesson,[],self.mapping,self.archive)['available'])
        (self.archive/self.mapping[font][0]['key']).unlink()
        result=completion.status(self.lesson,[],self.mapping,self.archive)
        self.assertFalse(result['available']);self.assertEqual(font,result['missing'][0]['url'])

    def test_proxy_completes_request_only_after_body_and_index_commit(self):
        asset='https://bg.izzi.digital/style.css';identifier='response-flow'
        completion.watch(asset,'GET',self.lesson,identifier)
        flow=SimpleNamespace(id=identifier,request=http.Request.make('GET',asset),response=http.Response.make(200,b'body{}',{'Content-Type':'text/css'}))
        def committed(path,key,mutate,default):
            self.assertIn(identifier,completion.CURRENT['pending'])
            mutate(default)
            self.assertTrue((self.archive/default[0]['key']).is_file())
        with patch.multiple(capture_addon,ARCHIVE_DIR=self.archive,STATE_DIR=self.archive,URL_MAP_FILE=self.archive/'url_map.json'),patch.object(capture_addon,'observe'),patch.object(capture_addon.external_links,'discover'),patch.object(capture_addon,'update_entry',side_effect=committed):
            capture_addon.response(flow)
        self.assertNotIn(identifier,completion.CURRENT['pending'])

    def test_observation_batch_is_atomic_flushed_and_respects_diagnostic_reset(self):
        path=self.archive/'observed.json'
        with patch.multiple(capture_observed,P=path,CACHED=None,DIRTY=False,LAST_FLUSH=0),patch.object(capture_observed.time,'monotonic',return_value=100),patch.object(capture_observed,'save',wraps=capture_observed.save) as saved:
            for i in range(100):capture_observed.observe(self.lesson,200,'text/html',size=i)
            self.assertEqual(1,saved.call_count,'do not rewrite a large JSON for every response')
            capture_addon.done()
            data=json.loads(path.read_text(encoding='utf8'))
            self.assertEqual(100,data['requests'][self.lesson]['seen']);self.assertEqual(99,data['requests'][self.lesson]['max_size'])
            self.assertEqual(2,saved.call_count)
            capture_observed.observe(self.lesson,404)
            capture_observed.atomic_save(path,{'requests':{}})
            capture_observed.flush()
            self.assertEqual({},json.loads(path.read_text(encoding='utf8'))['requests'])
            capture_observed.observe(self.lesson,206);capture_observed.flush()
            data=json.loads(path.read_text(encoding='utf8'))
            self.assertEqual([206],data['requests'][self.lesson]['statuses'])
    def test_partial_video_and_performance_assets_are_checked(self):
        url='https://api.izzi.digital/datastore/video.mp4';self.add(url,b'\x00\x00\x00\x18ftyp',206,'bytes 0-7/100')
        self.settled();result=completion.status(self.lesson,[url],self.mapping,self.archive)
        self.assertFalse(result['available']);self.assertEqual(url,result['missing'][0]['url'])
        self.add(url,b'\x00\x00\x00\x18ftyp'+b'0'*92)
        self.assertTrue(completion.status(self.lesson,[url],self.mapping,self.archive)['available'])
    def test_post_background_requests_old_lesson_and_analytics_are_excluded(self):
        self.assertFalse(completion.watch('https://bg.izzi.digital/api/sync','POST',self.lesson,'write'))
        self.assertFalse(completion.watch('https://api.izzi.digital/api/data','GET','https://bg.izzi.digital/DOS/2/9.html','other'))
        self.assertFalse(completion.watch('https://www.google-analytics.com/log','GET',self.lesson,'analytics'))
        self.settled();self.assertTrue(completion.status(self.lesson,[],self.mapping,self.archive)['available'])
        self.assertFalse(completion.status('https://bg.izzi.digital/DOS/1/9.html',[],self.mapping,self.archive)['tracked'])
        with self.assertRaises(ValueError):completion.status(self.lesson,['x']*(completion.LIMIT+1),self.mapping,self.archive)
    def test_api_queries_do_not_use_another_cached_response(self):
        other='https://api.izzi.digital/api/info?id=2';wanted='https://api.izzi.digital/api/info?id=1'
        self.add(other,b'{}');self.settled()
        self.assertFalse(completion.status(self.lesson,[wanted],self.mapping,self.archive)['available'])
        self.add(wanted,b'{}')
        self.assertTrue(completion.status(self.lesson,[wanted],self.mapping,self.archive)['available'])
    def test_proxy_status_endpoint_confirms_archive_and_rejects_invalid_request(self):
        flow=SimpleNamespace(request=http.Request.make('POST','https://bg.izzi.digital/__offline_capture__/lesson_status',content=json.dumps({'lesson':self.lesson,'assets':[]}).encode()),response=None)
        self.settled()
        with patch.object(capture_addon,'load_json',return_value=self.mapping),patch.object(capture_addon,'ARCHIVE_DIR',self.archive):capture_addon.request(flow)
        self.assertEqual(200,flow.response.status_code);self.assertTrue(json.loads(flow.response.content)['available'])
        flow.request.content=b'not-json';flow.response=None;capture_addon.request(flow)
        self.assertEqual(503,flow.response.status_code)
if __name__=='__main__':unittest.main()
