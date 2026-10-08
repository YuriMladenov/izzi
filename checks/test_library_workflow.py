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
import import_har

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
    def test_latest_incomplete_capture_overrides_old_done(self):
        self.completed(1)
        session=json.loads((self.state/'capture_session.json').read_text())
        session['visits'].append(dict(kind='lesson-incomplete',book='1',lesson='0'))
        self.write('capture_session.json',session)
        self.assertEqual(self.report()['label'],'INCOMPLETE')
        self.assertEqual(self.report()['done'],[])
        session['visits'].append(dict(kind='lesson-done',book='1',lesson='0'))
        self.write('capture_session.json',session)
        self.assertEqual(self.report()['done'],['0'])

    def test_catalogue_order_rename_hide_and_persistence(self):
        books={'1':{'title':'Book','lessons':{'9':{'id':'9','title':'Nine','path':'/DOS/1/9.html'},'2':{'id':'2','title':'Two','path':'/DOS/1/2.html'},'5':{'id':'5','title':'Five','path':'/DOS/1/5.html'}}}}
        self.write('books.json',books)
        self.write('capture_session.json',{'visits':[{'kind':'lesson-start','book':'1','lesson':'2'},{'kind':'lesson-start','book':'1','lesson':'9'}]})
        self.start_server()
        page=self.request('/__book__/1')[2].decode()
        self.assertLess(page.index('Two'),page.index('Nine'))
        self.assertLess(page.index('Nine'),page.index('Five'))
        from urllib.parse import urlencode
        body=urlencode({'order_9':'1','order_2':'3','order_5':'2','name_9':'Renamed <lesson>','hidden_2':'on'}).encode()
        conn=http.client.HTTPConnection('127.0.0.1',self.httpd.server_port)
        conn.request('POST','/__catalog__/1',body,{'Content-Type':'application/x-www-form-urlencoded'})
        response=conn.getresponse();self.assertEqual(response.status,303);response.read();conn.close()
        self.assertEqual(json.loads((self.state/'books.json').read_text()),books)
        self.assertFalse((self.state/'progress').exists())
        self.stop_server();self.start_server()
        page=self.request('/__book__/1')[2].decode()
        self.assertIn('Renamed &lt;lesson&gt;',page);self.assertNotIn('Two',page)
        self.assertLess(page.index('Renamed'),page.index('Five'))
        edit=self.request('/__book__/1?edit=1')[2].decode()
        self.assertIn('name_2',edit);self.assertIn('checked',edit)
        self.assertEqual(self.request('/__catalog__/1',body,{'Content-Type':'application/x-www-form-urlencoded','Origin':'https://other.example'})[0],403)

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
    def test_full_single206_html_replays_but_partial_or_wrong_size_does_not(self):
        self.completed(1)
        path='/DOS/1/0.html';url='https://bg.izzi.digital'+path
        body=b'<html>verified full range</html>'
        self.mapping.pop(url)
        self.add(path,body,status=206,content_range=f'bytes 0-{len(body)-1}/{len(body)}')
        self.assertEqual('READY',self.report()['label'])
        self.start_server()
        status,headers,got=self.request(path)
        self.assertEqual(200,status);self.assertIn(b'verified full range',got)
        record=self.mapping[url][0]
        record['content_range']=f'bytes 0-{len(body)-1}/{len(body)+1}'
        self.write('url_map.json',self.mapping)
        self.assertEqual(404,self.request(path)[0]);self.assertEqual('INCOMPLETE',self.report()['label'])
        record['content_range']=f'bytes 0-{len(body)-1}/{len(body)}'
        record['size']=len(body)+1;self.write('url_map.json',self.mapping)
        self.assertEqual(404,self.request(path)[0])
    def test_full_single206_mp4_supports_range_without_assembly_flag(self):
        video=bytes(range(256))*8
        self.add('/datastore/full.mp4',video,status=206,content_type='video/mp4',
                 content_range='bytes 0-2047/2048')
        self.start_server()
        status,headers,body=self.request('/datastore/full.mp4',headers={'Range':'bytes=0-1023'})
        self.assertEqual(206,status);self.assertEqual('bytes 0-1023/2048',headers['Content-Range'])
        self.assertEqual(video[:1024],body)
    def test_atomic_json_save_keeps_previous_map_if_replacement_fails(self):
        path=self.state/'url_map.json'
        import_har.save(path,{'old':[]})
        with patch.object(import_har.os,'replace',side_effect=OSError('replace failed')):
            with self.assertRaises(OSError):import_har.save(path,{'new':[]})
        self.assertEqual({'old':[]},import_har.load(path,{}))
        self.assertEqual([],list(self.state.glob('*.tmp')))
        import_har.save(path,{'new':[]})
        self.assertEqual({'new':[]},import_har.load(path,{}))
        path.write_text('{broken')
        with self.assertRaises(ValueError):import_har.load(path,{})
    def test_bad_urlmap_returns503_instead_of_mass_false_misses(self):
        (self.state/'url_map.json').write_text('{broken')
        self.start_server()
        self.assertEqual(503,self.request('/DOS/1/0.html')[0])
        self.assertFalse((self.state/'missing_resources.jsonl').exists())
    def test_current_missing_excludes_recovered_and_separates_warnings(self):
        self.add('/DOS/1/restored.png',b'\x89PNGfixture',content_type='image/png')
        self.add('/DOS/1/upstream.png',b'<html>404</html>',status=404,content_type='text/html')
        events=[{'host':'bg.izzi.digital','path':p,'query':''} for p in
                ['/DOS/1/restored.png','/DOS/1/upstream.png','/DOS/1/missing.png','/favicon.ico','/DOS/1/style.css.map']]
        missing,warnings,resolved=server.current_missing(events,self.mapping)
        self.assertEqual(1,resolved);self.assertEqual(1,len(missing));self.assertEqual(3,len(warnings))
        self.assertIn('missing.png',missing[0][1])
        self.start_server()
        (self.state/'missing_resources.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events))
        text=self.request('/__missing__')[2].decode()
        self.assertNotIn('restored.png',text);self.assertIn('UPSTREAM 404 WARNING',text)
        self.assertEqual(5,len((self.state/'missing_resources.jsonl').read_text().splitlines()))
        self.assertIn('https://bg.izzi.digital/DOS/1/missing.png?__izzi_offline_recover=',text)
        self.assertEqual(4,text.count('>Изтегли</a>'))
        self.assertIn('rel="noopener noreferrer"',text)
    def test_attachment_replay_preserves_bytes_and_forces_download(self):
        bodies={'exe':b'MZbinary\x00file','sb3':b'PK\x03\x04scratch-fixture'}
        for ext,body in bodies.items():self.add('/DOS/1/datastore/15/publication/1/files/demo.'+ext,body,content_type='application/octet-stream')
        self.add('/DOS/1/datastore/15/publication/1/files/bad.sb3',b'<html>login</html>',content_type='text/html')
        self.start_server()
        for ext,body in bodies.items():
            code,headers,result=self.request('/DOS/1/datastore/15/publication/1/files/demo.'+ext+'?v=123')
            self.assertEqual(code,200);self.assertEqual(result,body)
            self.assertIn('attachment;',headers['Content-Disposition'])
        self.assertEqual(self.request('/DOS/1/datastore/15/publication/1/files/bad.sb3')[0],404)

    def test_operations_local_control_and_fixed_actions(self):
        import operations
        self.start_server()
        status=self.request('/__ops__/status')
        self.assertEqual(status[0],200)
        self.assertIn('capture',json.loads(status[2]))
        self.assertEqual(self.request('/__ops__/status',headers={'Host':'192.168.1.20'})[0],403)
        page=self.request('/__operations__',headers={'Host':'192.168.1.20'})[2].decode()
        self.assertNotIn(operations.tasks.token,page)
        payload=json.dumps({'task':'checks','action':'start'}).encode()
        headers={'Content-Type':'application/json','X-IZZI-Control':operations.tasks.token}
        with patch.object(operations.tasks,'start') as start:
            self.assertEqual(self.request('/__ops__/action',payload,{'Content-Type':'application/json'})[0],403)
            self.assertEqual(self.request('/__ops__/action',payload,{**headers,'Origin':'https://external.example'})[0],403)
            self.assertEqual(self.request('/__ops__/action',payload,{**headers,'Host':'192.168.1.20'})[0],403)
            start.assert_not_called()
            self.assertEqual(self.request('/__ops__/action',payload,headers)[0],200)
            start.assert_called_once_with('checks')
        self.assertEqual(self.request('/__ops__/action',b'{"task":"shell","action":"start"}',headers)[0],400)

    def test_operations_owned_process_lifecycle_and_log(self):
        import operations,time
        tasks=operations.Tasks()
        try:
            tasks.start('checks',[sys.executable,'-u','-c','import time;print("TASK OUTPUT",flush=True);time.sleep(30)'])
            with self.assertRaises(ValueError):tasks.start('checks')
            for _ in range(100):
                if 'TASK OUTPUT' in tasks.snapshot()['checks']['log']:break
                time.sleep(.02)
            self.assertEqual(tasks.snapshot()['checks']['state'],'running')
            self.assertIn('TASK OUTPUT',tasks.snapshot()['checks']['log'])
            tasks.stop('checks')
            self.assertEqual(tasks.snapshot()['checks']['state'],'stopped')
            tasks.start('checks',[sys.executable,'-u','-c','print("FINISHED")'])
            for _ in range(100):
                if tasks.snapshot()['checks']['state']!='running':break
                time.sleep(.02)
            self.assertEqual(tasks.snapshot()['checks']['state'],'success')
            self.assertEqual(tasks.snapshot()['checks']['exit_code'],0)
        finally:tasks.close()

    def test_webui_assets_help_and_empty_library(self):
        self.start_server()
        page=self.request('/')[2].decode()
        self.assertIn('lang="bg"',page);self.assertIn('Библиотеката е празна',page)
        self.assertIn('/__ui__/app.css',page);self.assertIn('/__ui__/app.js',page)
        for path,mime in [('/__ui__/app.css','text/css'),('/__ui__/app.js','application/javascript'),('/__ui__/operations.js','application/javascript')]:
            code,headers,body=self.request(path)
            self.assertEqual(code,200);self.assertTrue(headers['Content-Type'].startswith(mime));self.assertTrue(body)
        self.assertIn('capture_mode.bat',self.request('/__help__')[2].decode())
        # UI assets stay available when private archive state is malformed.
        (self.state/'url_map.json').write_text('{broken')
        self.assertEqual(self.request('/__ui__/app.css')[0],200)

    def test_home_uses_only_available_original_cover_for_matching_book(self):
        self.write('books.json',{'1':{'title':'Математика за 4. клас','lessons':{}},'2':{'title':'Математика за 6. клас','lessons':{}}})
        picture=b'\x89PNG\r\n\x1a\ncover'
        self.add('/DOS/group-images/math.png',picture,content_type='image/png')
        catalog={'data':{'grouped':[{'thumbs':{'image1':'/DOS/group-images/math.png'},'publications':[{'dos_id':1,'grade':{'number':4},'thumbs':{'image1':'/DOS/1/missing.png'}}]}],'ungrouped':{'publications':[]}}}
        self.add('/api/online-bookshelf-publications',json.dumps(catalog).encode(),content_type='application/json')
        self.start_server();page=self.request('/')[2].decode()
        self.assertIn('Начален етап',page);self.assertIn('Прогимназиален етап',page)
        self.assertEqual(1,page.count('class="original-cover"'))
        self.assertNotIn('/DOS/1/missing.png',page)
        self.assertIn('src="/__host__/bg.izzi.digital/DOS/group-images/math.png"',page)
        self.assertEqual(picture,self.request('/__host__/bg.izzi.digital/DOS/group-images/math.png')[2])
        self.assertNotIn('catalog-intro',page);self.assertNotIn('Съдържание на архива',page)

    def test_webui_journal_shows_counts_without_private_bodies(self):
        progress_journal.append(self.state/'progress','POST','/api/sync','http://localhost/DOS/1/9.html',b'{"secret":"PRIVATE_BODY"}','application/json')
        self.start_server()
        code,_,body=self.request('/__journal__')
        self.assertEqual(code,200)
        page=body.decode();self.assertIn('POST /api/sync',page);self.assertNotIn('PRIVATE_BODY',page)
        self.assertIn('aria-current="page"',page)

    def test_download_status_checks_actual_archive_and_rejects_external_host(self):
        self.add('/datastore/test.png',b'\x89PNGfixture',content_type='image/png')
        self.start_server()
        from urllib.parse import urlencode
        def status(url):return self.request('/__offline__/asset-status?'+urlencode({'url':url}))
        self.assertTrue(json.loads(status('https://api.izzi.digital/datastore/test.png')[2])['available'])
        self.assertFalse(json.loads(status('https://api.izzi.digital/datastore/missing.png')[2])['available'])
        self.assertEqual(status('https://external.example/test.png')[0],400)
        page=self.request('/__missing__')[2].decode()
        self.assertIn('id="download-all"',page);self.assertIn('id="download-stop"',page)
        self.assertIn('Налични в архива:',page)

    def test_equal_book_titles_stay_separate_and_page_counts_use_bodies(self):
        self.write('books.json',{'1':{'title':'Same title','lessons':{'10':{'id':'10','path':'/DOS/1/10.html','title':'Page'}}},
            '2':{'title':'Same title','lessons':{'20':{'id':'20','path':'/DOS/2/20.html','title':'Page'}}}})
        self.add('/DOS/1/10.html')
        self.start_server();text=self.request('/')[2].decode()
        self.assertEqual(2,text.count('<h3>Same title</h3>'))
        self.assertIn('ID 1',text);self.assertIn('ID 2',text)
        self.assertIn('1 с наличен HTML',self.request('/__book__/1')[2].decode());self.assertIn('0 с наличен HTML',self.request('/__book__/2')[2].decode())
        self.assertIn('data:,',text)
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
    def test_older_publication_assets_replay_under_new_lesson_book(self):
        self.write('books.json',{'412693':{'title':'География','lessons':{'10':{'id':'10','path':'/DOS/412693/10.html','title':'Урок'}}}})
        source='/datastore/15/publication/3931/video/test.mp4'
        self.add(source,b'full older video',content_type='video/mp4')
        url='https://bg.izzi.digital'+source
        self.assertTrue(media_mapping.add_media(url,'https://bg.izzi.digital/DOS/412693/10.html'))
        self.assertEqual(url,media_mapping.lesson_media('412693','10')[0]['url'])
        picture='/DOS/412693/datastore/15/publication/3931/pictures/test.png'
        self.add(picture,b'\x89PNG\r\n\x1a\nold image',content_type='image/png')
        self.start_server()
        request='/DOS/412693'+source
        self.assertEqual(b'full older video',self.request(request)[2])
        code,headers,body=self.request(request,headers={'Range':'bytes=0-3'})
        self.assertEqual(206,code);self.assertEqual(b'full',body);self.assertEqual('bytes 0-3/16',headers['Content-Range'])
        self.assertEqual(200,self.request(picture)[0])
        target='https://bg.izzi.digital'+request
        status=json.loads(self.request('/__offline__/asset-status?url='+urllib.parse.quote(target,safe=''))[2])
        self.assertTrue(status['available'])
        self.assertEqual([],self.report()['bad_mapping'])
        before=(self.state/'missing_resources.jsonl').read_text() if (self.state/'missing_resources.jsonl').exists() else ''
        probe=json.loads(self.request('/__offline_capture__/image_status')[2])
        self.assertFalse(probe['capture'])
        after=(self.state/'missing_resources.jsonl').read_text() if (self.state/'missing_resources.jsonl').exists() else ''
        self.assertEqual(before,after)

    def test_video_login_page_is_not_reported_as_captured_media(self):
        path='/datastore/15/publication/3931/video/login.mp4'
        self.add(path,b'<html>Login required</html>',content_type='text/html')
        self.start_server()
        target=urllib.parse.quote('https://bg.izzi.digital'+path,safe='')
        result=json.loads(self.request('/__offline__/asset-status?url='+target)[2])
        self.assertFalse(result['available'])
        self.assertEqual(404,self.request('/DOS/412693'+path)[0])

    def test_cross_book_media_is_not_mapped_or_injected(self):
        wrong='https://bg.izzi.digital/DOS/2/datastore/15/publication/2/video/test.mp4'
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
