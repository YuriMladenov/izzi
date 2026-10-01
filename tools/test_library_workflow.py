"""Readiness, journal durability and multi-book regression tests on private temp data."""
import base64
import concurrent.futures
import hashlib
import http.client
import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch
from http.server import ThreadingHTTPServer

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import readiness
import server
import assembled_media
import media_mapping
import progress_journal

class LibraryWorkflow(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='izzi-library-test-')
        self.root=Path(self.tmp.name);self.archive=self.root/'archive';self.state=self.root/'state'
        self.archive.mkdir();self.state.mkdir();self.mapping={};self.httpd=None
        self.patches=[patch.multiple(server,ARCHIVE_DIR=self.archive,STATE_DIR=self.state,
            URL_MAP_FILE=self.state/'url_map.json',BOOKS_FILE=self.state/'books.json',PROGRESS_DIR=self.state/'progress'),
            patch.multiple(assembled_media,ARCHIVE_DIR=self.archive,URL_MAP_FILE=self.state/'url_map.json'),
            patch.object(media_mapping,'P',self.state/'media_map.json')]
        for p in self.patches:p.start()
        self.opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    def tearDown(self):
        self.stop_server()
        for p in reversed(self.patches):p.stop()
        self.tmp.cleanup()
    def write(self,name,data):
        (self.state/name).write_text(json.dumps(data))
    def add(self,path,body=b'<html>lesson</html>',**extra):
        key=hashlib.sha256(body).hexdigest();(self.archive/key).write_bytes(body)
        record=dict(key=key,body_available=True,status=200,method='GET',size=len(body),decoded=True,content_type='text/html')
        record.update(extra);url=path if path.startswith('http') else 'https://bg.izzi.digital'+path
        self.mapping.setdefault(url,[]).append(record);self.write('url_map.json',self.mapping)
        return record
    def start_server(self):
        self.httpd=ThreadingHTTPServer(('127.0.0.1',0),server.H)
        self.thread=threading.Thread(target=self.httpd.serve_forever,daemon=True);self.thread.start()
        self.base=f'http://127.0.0.1:{self.httpd.server_port}'
    def stop_server(self):
        if self.httpd:
            self.httpd.shutdown();self.httpd.server_close();self.thread.join();self.httpd=None
    def request(self,path,body=None,headers=None,method=None):
        req=urllib.request.Request(self.base+path,data=body,headers=headers or {},method=method)
        try:response=self.opener.open(req,timeout=5)
        except urllib.error.HTTPError as error:response=error
        with response:return response.code,response.headers,response.read()
    def completed(self,count=2):
        # Metadata misses two historical lessons; visits+map restore the union.
        self.write('books.json',{'1':{'lessons':{str(i):{} for i in range(max(0,count-2))}}})
        visits=[]
        for i in range(count):
            self.add(f'/DOS/1/{i}.html')
            visits.extend([dict(kind='lesson-start',book=1,lesson=str(i)),
                           dict(kind='lesson-done',book='1',lesson=str(i))])
        self.write('capture_session.json',{'visits':visits})
    def report(self):return readiness.assess(self.root)['books'][0]

    def test_27_lesson_union_and_nine_origin404_are_warnings(self):
        self.completed(27)
        obs={}
        for i in range(9):
            u=f'https://api.izzi.digital/datastore/15/publication/1/pictures/{i}_extracted.png'
            obs[u]={'statuses':[404]}
        self.write('capture_observed.json',{'requests':obs})
        result=self.report()
        self.assertEqual('READY WITH WARNINGS',result['label'])
        self.assertEqual(27,len(result['lessons']));self.assertEqual(27,len(result['done']))
        self.assertEqual(9,len(result['warnings']));self.assertEqual([],result['gaps'])
    def test_traversal_subset_cannot_claim_ready(self):
        self.completed(2)
        self.write('capture_session.json',{'visits':[dict(book=1,lesson='0',kind='lesson-done')]})
        self.assertEqual('INCOMPLETE',self.report()['label'])
        self.assertEqual(['1'],self.report()['unfinished'])
    def test_304_gap_disappears_after_canonical_body_recovery(self):
        self.completed()
        url='https://bg.izzi.digital/DOS/1/profil/app.js?old=1'
        api='https://api.izzi.digital/api/userdata'
        self.write('capture_observed.json',{'requests':{url:{'statuses':[304]},
            api:{'statuses':[200],'referers':['https://bg.izzi.digital/DOS/1/0.html'],'content_types':['application/json']}}})
        self.assertEqual([url],self.report()['only304'])
        self.add('/profil/app.js',b'window.fixture=true;',content_type='application/javascript')
        self.assertEqual([],self.report()['only304']);self.assertIn(api,self.report()['gaps'])
        self.add(api,b'{"fixture":true}',content_type='application/json')
        self.assertEqual('READY',self.report()['label'])
    def test_missing_blob_and_incomplete206_fail_readiness(self):
        self.completed()
        r=self.add('/DOS/1/missing.js',b'fixture',content_type='application/javascript')
        (self.archive/r['key']).unlink()
        url='https://bg.izzi.digital/datastore/15/publication/1/video/test.mp4'
        self.add(url,b'chunk',status=206,content_type='video/mp4')
        self.write('media_map.json',{'lessons':{'1/0':{'media':[{'url':url,'strict':True}]}}})
        result=self.report();self.assertEqual('INCOMPLETE',result['label'])
        self.assertEqual([url],result['incomplete_media'])
        self.add(url,b'complete body',source='assembled_ranges',complete=True,content_type='video/mp4')
        self.assertEqual([],self.report()['incomplete_media'])
    def test_corrupt_state_and_missing_lesson_do_not_claim_ready(self):
        self.completed()
        record=self.mapping['https://bg.izzi.digital/DOS/1/1.html'][0]
        (self.archive/record['key']).unlink()
        (self.state/'media_map.json').write_text('{broken')
        report=readiness.assess(self.root)
        self.assertTrue(report['errors']);self.assertEqual('INCOMPLETE',report['books'][0]['label'])
        self.assertTrue(report['books'][0]['missing_lessons'])
    def test_empty_archive_has_no_ready_result(self):
        self.assertEqual([],readiness.assess(self.root)['books'])
    def test_two_books_private_aliases_and_unscoped_ambiguity(self):
        self.add('/DOS/1/profil/app.js',b'book one',content_type='application/javascript')
        self.add('/DOS/2/profil/app.js',b'book two',content_type='application/javascript')
        self.start_server()
        self.assertEqual(b'book one',self.request('/DOS/1/profil/app.js')[2])
        self.assertEqual(b'book two',self.request('/profil/app.js',headers={'Referer':self.base+'/DOS/2/20.html'})[2])
        self.assertEqual(404,self.request('/DOS/3/profil/app.js')[0])
        self.assertEqual(404,self.request('/profil/app.js')[0])
        self.assertEqual(b'book one',self.request('/DOS/1/profil/app.js',headers={'Referer':self.base+'/DOS/2/20.html'})[2])
        self.add('/DOS/2/20.html',b'<html>second book</html>')
        self.assertIn(b'second book',self.request('/DOS/2/20.html',headers={'Referer':self.base+'/DOS/1/10.html'})[2])
    def test_cross_book_media_is_not_mapped_or_injected(self):
        wrong='https://bg.izzi.digital/datastore/15/publication/2/video/test.mp4'
        self.assertFalse(media_mapping.add_media(wrong,'https://bg.izzi.digital/DOS/1/10.html'))
        self.write('media_map.json',{'lessons':{'1/10':{'media':[{'url':wrong,'strict':True}]}}})
        self.assertEqual([],media_mapping.lesson_media('1','10'))
        self.completed();report=self.report()
        self.write('media_map.json',{'lessons':{'1/0':{'media':[{'url':wrong,'strict':True}]}}})
        self.assertEqual([wrong],self.report()['bad_mapping'])
    def test_journal_full_bytes_two_books_and_server_restart(self):
        self.start_server();payload=b'x'*100005+b'\xff\x00'
        self.assertEqual(200,self.request('/__host__/api.izzi.digital/api/write',payload,
            {'Referer':self.base+'/DOS/1/10.html?secret=never-log-ref-query'})[0])
        self.assertEqual(200,self.request('/api/write',b'{"bookmark":1}',{'Referer':self.base+'/DOS/2/20.html'})[0])
        row=json.loads((self.state/'progress/1.jsonl').read_text())
        self.assertEqual(payload,base64.b64decode(row['body_base64']))
        self.assertEqual(len(payload),row['size']);self.assertNotIn('secret=',row['referer'])
        self.stop_server();self.start_server()
        summary=json.loads(self.request('/__offline__/progress')[2])
        self.assertEqual(2,summary['records']);self.assertEqual({'1','2'},{r['book'] for r in summary['books']})
        self.assertNotIn('body',summary);self.assertEqual(0,summary['invalid_lines'])
    def test_concurrent_writes_and_bad_lines_diagnostic(self):
        self.start_server()
        def write(i):return self.request('/api/write',str(i).encode(),{'Referer':self.base+'/DOS/1/10.html'})[0]
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            self.assertEqual([200]*12,list(pool.map(write,range(12))))
        self.assertEqual(12,progress_journal.summarize(self.state/'progress')['records'])
        with (self.state/'progress/1.jsonl').open('a') as f:f.write('{truncated\n')
        self.assertEqual(1,progress_journal.summarize(self.state/'progress')['invalid_lines'])
    def test_write_failure_never_reports_saved(self):
        self.start_server()
        with patch.object(progress_journal,'append',side_effect=OSError('disk full')):
            status,headers,body=self.request('/api/write',b'{}')
        self.assertEqual(500,status);self.assertFalse(json.loads(body)['saved'])
    def test_invalid_lengths_rejected_without_reading_body(self):
        self.start_server()
        for size,status in [('-1',400),(str(progress_journal.MAX_WRITE+1),413),('invalid',400)]:
            connection=http.client.HTTPConnection('127.0.0.1',self.httpd.server_port,timeout=5)
            connection.request('POST','/api/write',headers={'Content-Length':size})
            response=connection.getresponse();response.read();self.assertEqual(status,response.status);connection.close()

if __name__=='__main__':unittest.main()
