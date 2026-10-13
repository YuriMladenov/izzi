"""Strict capture waits for current-lesson GET bodies, not traversal markers."""
import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import capture_completion as completion
import capture_addon
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
