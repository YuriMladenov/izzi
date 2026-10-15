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
        (self.state/name).write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
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

    def test_prepared_static_cache_invalidates_modified_and_deleted_sources(self):
        row=self.add('/DOS/1/profil/test.js',b'const value=1;',content_type='application/javascript')
        self.start_server()
        with patch.object(server,'rewrite',wraps=server.rewrite) as rewrite:
            status,headers,data=self.request('/DOS/1/profil/test.js')
            self.assertEqual(200,status);self.assertEqual(b'const value=1;',data)
            self.assertEqual(304,self.request('/DOS/1/profil/test.js',headers={'If-None-Match':headers['ETag']})[0])
            self.assertEqual(200,self.request('/DOS/1/profil/test.js')[0]);self.assertEqual(1,rewrite.call_count)
            (self.archive/row['key']).write_bytes(b'const value=2;')
            status,new_headers,data=self.request('/DOS/1/profil/test.js',headers={'If-None-Match':headers['ETag']})
            self.assertEqual(200,status);self.assertEqual(b'const value=2;',data)
            self.assertNotEqual(headers['ETag'],new_headers['ETag']);self.assertEqual(2,rewrite.call_count)
            (self.archive/row['key']).unlink()
            self.assertEqual(404,self.request('/DOS/1/profil/test.js')[0])

    def test_parallel_cache_builds_share_same_file_without_blocking_other_files(self):
        import replay_cache
        one=self.archive/'one.js';two=self.archive/'two.js'
        one.write_bytes(b'one');two.write_bytes(b'two')
        entered=threading.Event();release=threading.Event();calls=[]
        def build():
            calls.append(1);entered.set()
            if not release.wait(3):raise TimeoutError('cache build not released')
            return one.read_bytes()
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            futures=[pool.submit(replay_cache.prepared,one,(),build) for _ in range(6)]
            try:
                self.assertTrue(entered.wait(3))
                self.assertEqual(b'two',replay_cache.prepared(two,(),two.read_bytes)[0])
            finally:release.set()
            for future in futures:self.assertEqual(b'one',future.result(timeout=3)[0])
        self.assertEqual(1,len(calls))
        one.write_bytes(b'bad')
        def broken():raise UnicodeDecodeError('utf8',b'\xff',0,1,'invalid source')
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            futures=[pool.submit(replay_cache.prepared,one,(),broken) for _ in range(4)]
            for future in futures:
                with self.assertRaises(UnicodeDecodeError):future.result(timeout=3)
        self.assertFalse(replay_cache.BUILDING,'failed builds must release waiting requests')

    def test_keepalive_response_framing_for_range_error_head_and_revalidation(self):
        self.add('/test.mp4',b'\x00\x00\x00\x18ftypmp42'+b'video'*20,content_type='video/mp4')
        self.start_server()
        connection=http.client.HTTPConnection('127.0.0.1',self.httpd.server_port,timeout=3)
        try:
            socket=None
            for method,headers,status in [('GET',{},200),('HEAD',{},200),('GET',{'Range':'bytes=9999-'},416),('GET',{'Range':'bytes=2-5'},206)]:
                connection.request(method,'/test.mp4',headers=headers)
                response=connection.getresponse();self.assertEqual(status,response.status);response.read()
                if socket is None:socket=connection.sock
                self.assertIs(socket,connection.sock)
                etag=response.getheader('ETag') or etag
            connection.request('GET','/test.mp4',headers={'If-None-Match':etag})
            response=connection.getresponse();self.assertEqual(304,response.status);self.assertEqual(b'',response.read())
            connection.request('GET','/missing.png');response=connection.getresponse()
            self.assertEqual(404,response.status);response.read();self.assertIs(socket,connection.sock)
        finally:connection.close()
    def test_bundled_katex_fallback_cache_and_archive_precedence(self):
        from urllib.parse import quote
        path='/DOS/888827/components/fonts/KaTeX_Main-Regular.woff'
        self.add(path,b'<html>Not found</html>',status=404)
        self.write('books.json',{})
        self.start_server()
        for name in ('KaTeX_Main-Regular','KaTeX_Math-Italic','KaTeX_Size3-Regular'):
            for ext,magic in (('.woff',b'wOFF'),('.woff2',b'wOF2')):
                target='/DOS/888827/components/fonts/'+name+ext
                status,headers,body=self.request(target+'?v=1',headers={'Host':'192.168.1.20'})
                self.assertEqual(200,status);self.assertEqual(magic,body[:4])
                self.assertEqual('font/woff2' if ext=='.woff2' else 'font/woff',headers['Content-Type'])
                self.assertEqual(304,self.request(target,headers={'If-None-Match':headers['ETag']})[0])
        self.assertEqual(200,self.request('/__host__/bg.izzi.digital'+path)[0])
        probe='/__offline__/asset-status?url='+quote('https://bg.izzi.digital'+path,safe='')
        self.assertTrue(json.loads(self.request(probe)[2])['available'])
        missing,warnings,resolved=server.current_missing([{'host':'bg.izzi.digital','path':path}],self.mapping)
        self.assertEqual(([],[],1),(missing,warnings,resolved))
        original=b'wOFF'+b'archived original font'*10
        self.add(path,original,content_type='font/woff')
        self.assertEqual(original,self.request(path)[2])
        self.assertIsNone(server.bundled_font('external.example',path))
        self.assertIsNone(server.bundled_font('bg.izzi.digital','/DOS/888827/components/fonts/../LICENSE'))
        self.assertEqual(404,self.request('/DOS/888827/components/fonts/KaTeX_Unknown.woff')[0])
    def test_bundled_text_icon_fonts_and_alternate_katex_path(self):
        paths=(
            '/DOS/888827/profil/dist/common/katex/fonts/KaTeX_Size3-Regular.woff2',
            '/DOS/412693/profil/dist/izzi/fonts/IBMPlexSans/IBMPlexSans-BoldItalic.woff2',
            '/DOS/888827/profil/dist/common/icons/material/MaterialIcons.woff',
            '/DOS/888827/datastore/blocks/12507701/assets/fonts/Open_Sans/OpenSans-Regular.woff',
        )
        for path in paths:self.add(path,b'<html>404</html>',status=404)
        self.write('books.json',{});self.start_server()
        for path in paths:
            status,headers,body=self.request(path,headers={'Host':'192.168.1.20'})
            self.assertEqual(200,status);self.assertIn(body[:4],(b'wOFF',b'wOF2'))
            self.assertEqual(304,self.request(path,headers={'If-None-Match':headers['ETag']})[0])
            self.assertEqual(([],[],1),server.current_missing([{'host':'bg.izzi.digital','path':path}],self.mapping))
            original=b'wOFF'+b'archived font'*20
            self.add(path,original,content_type='font/woff')
            self.assertEqual(original,self.request(path)[2])
        self.assertIsNone(server.bundled_font('bg.izzi.digital','/DOS/888827/profil/dist/izzi/fonts/IBMPlexSansHB/IBMPlexSans-Regular.woff2'))
        self.assertIsNone(server.bundled_font('bg.izzi.digital','/DOS/888827/datastore/blocks/12507701/assets/fonts/Open_Sans/MyriadPro-Regular.woff'))
    def test_latest_incomplete_capture_overrides_old_done(self):
        self.completed(1)
        session=json.loads((self.state/'capture_session.json').read_text(encoding='utf-8'))
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
        self.assertEqual(json.loads((self.state/'books.json').read_text(encoding='utf-8')),books)
        self.assertFalse((self.state/'progress').exists())
        self.stop_server();self.start_server()
        page=self.request('/__book__/1')[2].decode()
        self.assertIn('Renamed &lt;lesson&gt;',page);self.assertNotIn('Two',page)
        self.assertLess(page.index('Renamed'),page.index('Five'))
        edit=self.request('/__book__/1?edit=1')[2].decode()
        self.assertIn('name_2',edit);self.assertIn('checked',edit)
        self.assertEqual(self.request('/__catalog__/1',body,{'Content-Type':'application/x-www-form-urlencoded','Origin':'https://other.example'})[0],403)

    def test_original_numbers_survive_rename_and_reordering(self):
        from library_catalog import ordered_lessons
        book={'lessons':{'9':{'title':'Nine'},'2':{'title':'Two'}}}
        session={'visits':[{'kind':'lesson-start','book':'1','lesson':'2','extra':{'title':'Земята','number':'3.1.'}},
                           {'kind':'lesson-start','book':'1','lesson':'9','extra':{'title':'3.2. Строеж','number':'3.2.'}}]}
        rows=ordered_lessons('1',book,session,{})
        self.assertEqual([r['title'] for r in rows],['3.1. Земята','3.2. Строеж'])
        rows=ordered_lessons('1',book,session,{'1':{'order':['9','2'],'names':{'9':'Ново име'},'hidden':['2']}})
        self.assertEqual([r['title'] for r in rows],['3.2. Ново име','3.1. Земята'])
        self.assertTrue(rows[1]['hidden'])

    def test_lesson_list_shows_captured_module_and_escapes_its_name(self):
        self.write('books.json',{'1':{'title':'Book','lessons':{
            '2':{'title':'Earth','path':'/DOS/1/2.html'},
            '3':{'title':'Structure','path':'/DOS/1/3.html'},
            '4':{'title':'Older lesson','path':'/DOS/1/4.html'}}}})
        self.write('capture_session.json',{'visits':[{'kind':'lesson-start','book':'1','lesson':'2',
            'extra':{'module':'Планетата <Земя>','number':'3.1.'}},
            {'kind':'lesson-start','book':'1','lesson':'3','extra':{'module':'Планетата <Земя>','number':'3.2.'}},
            {'kind':'lesson-start','book':'1','lesson':'2','extra':{}}]})
        self.start_server()
        page=self.request('/__book__/1')[2].decode()
        self.assertIn('3.1. Earth',page)
        self.assertIn('<h2>Планетата &lt;Земя&gt;</h2>',page)
        self.assertLess(page.index('<h2>Планетата'),page.index('3.1. Earth'))
        self.assertNotIn('Планетата <Земя>',page)
        self.assertEqual(page.count('<h2>Планетата'),1)
        self.assertLess(page.index('3.1. Earth'),page.index('3.2. Structure'))
        self.assertEqual(page.count('class="lesson-section"'),2)
        self.assertIn('<h2>Уроци без записан раздел</h2>',page)
        self.assertIn('Older lesson',page)

    def test_manual_section_and_original_number_and_automatic_preview(self):
        import html
        self.write('books.json',{'1':{'title':'Book','lessons':{
            '10':{'title':'Chapter','path':'/DOS/1/10.html'},'2':{'title':'Old title','path':'/DOS/1/2.html'}}}})
        breadcrumbs=html.escape(json.dumps([{'id':10,'name':'Земята','systemType':'module','prettyPosition':'3'}]),quote=True)
        unit=html.escape(json.dumps({'id':2,'name':'Форма на Земята'}),quote=True)
        self.add('/DOS/1/10.html',('<breadcrumbs :items="'+breadcrumbs+'"></breadcrumbs><units-list-item :item="'+unit+'" position="3.1." title="Форма на Земята"></units-list-item>').encode())
        self.start_server()
        preview=self.request('/__book__/1?edit=1&auto=1')[2].decode()
        self.assertIn('value="Земята"',preview);self.assertIn('value="3.1."',preview)
        self.assertIn('Форма на Земята',preview)
        self.assertFalse((self.state/'library_catalog.json').exists())
        from urllib.parse import urlencode
        body=urlencode({'name_2':'Нов урок','module_2':'Първи срок','number_2':'2.1.','order_2':'1'}).encode()
        self.assertEqual(self.request('/__catalog__/1',body,{'Content-Type':'application/x-www-form-urlencoded'})[0],200)  # follows redirect
        page=self.request('/__book__/1')[2].decode()
        self.assertIn('<h2>Първи срок</h2>',page);self.assertIn('2.1. Нов урок',page)
        self.assertEqual(self.request('/__book__/1?edit=1&auto=1',headers={'Host':'192.168.1.20'})[0],403)

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
        (self.state/'media_map.json').write_text('{broken',encoding='utf-8')
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
        path.write_text('{broken',encoding='utf-8')
        with self.assertRaises(ValueError):import_har.load(path,{})
    def test_bad_urlmap_returns503_instead_of_mass_false_misses(self):
        (self.state/'url_map.json').write_text('{broken',encoding='utf-8')
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
        (self.state/'missing_resources.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events),encoding='utf-8')
        text=self.request('/__missing__')[2].decode()
        self.assertNotIn('restored.png',text);self.assertIn('UPSTREAM 404 WARNING',text)
        self.assertEqual(5,len((self.state/'missing_resources.jsonl').read_text(encoding='utf-8').splitlines()))
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

    def test_capture_finds_python_scripts_without_path_entry(self):
        import operations,os
        scripts=self.root/'Scripts';scripts.mkdir()
        executable=scripts/('mitmdump.exe' if os.name=='nt' else 'mitmdump');executable.touch()
        with patch.object(operations.sys,'executable',str(self.root/'python.exe')), patch.object(operations.sysconfig,'get_path',return_value=str(scripts)), patch.object(operations.shutil,'which',return_value=None):
            self.assertEqual(operations.find_mitmdump(),str(executable))

    def test_capture_reports_external_port_before_searching_executable(self):
        import operations,config,socket
        tasks=operations.Tasks()
        with socket.socket() as listener:
            listener.bind(('127.0.0.1',0));listener.listen()
            with patch.object(config,'CAPTURE_PROXY_PORT',listener.getsockname()[1]), patch.object(operations,'find_mitmdump') as find, patch.object(operations.subprocess,'Popen') as spawn:
                self.assertEqual(tasks.snapshot()['capture']['state'],'external')
                with self.assertRaisesRegex(ValueError,'capture_mode.bat'):tasks.start('capture')
                find.assert_not_called();spawn.assert_not_called()
                tasks.stop('capture')
                self.assertEqual(tasks.snapshot()['capture']['state'],'external')

    def test_capture_unavailable_executable_gives_actionable_error(self):
        import operations
        with patch.object(operations.sys,'executable',str(self.root/'absent/python.exe')), patch.object(operations.sysconfig,'get_path',return_value=str(self.root/'absent/Scripts')), patch.object(operations.shutil,'which',return_value=None):
            with self.assertRaisesRegex(ValueError,'рестартирай библиотеката'):operations.find_mitmdump()

    def test_link_dependencies_and_external_replay(self):
        import external_links
        with patch.object(external_links,'FILE',self.state/'lesson_links.json'):
            root='https://resources.example.org/app/index.html'
            external_links.register(root)
            external_links.associate('https://resources.example.org/assets/app.js',root)
            external_links.associate('https://cdn.example.org/data.json','https://resources.example.org/assets/app.js')
            self.assertEqual(external_links.hosts(),{'resources.example.org','cdn.example.org'})
            external_links.discover(root,b'<script src="/assets/app.js"></script>', 'text/html')
            external_links.associate('https://origin-cdn.example.org/library.css','https://resources.example.org/')
            self.add('https://origin-cdn.example.org/library.css',b'body{}',content_type='text/css')
            self.assertIn('origin-cdn.example.org',external_links.hosts())
            self.add(root,b'<html><script src="/assets/app.js"></script><a href="https://cdn.example.org/data.json">data</a></html>')
            self.add('https://resources.example.org/assets/app.js',b'fetch("/data.json")',content_type='application/javascript')
            self.assertFalse(external_links.status(root,self.mapping,self.archive)['available'])
            self.add('https://cdn.example.org/data.json',b'{}',content_type='application/json')
            self.assertTrue(external_links.status(root,self.mapping,self.archive)['available'])
            self.start_server()
            page=self.request('/__host__/resources.example.org/app/index.html')[2].decode()
            self.assertIn('src="/__host__/resources.example.org/assets/app.js"',page)
            self.assertIn('href="/__host__/cdn.example.org/data.json"',page)
            self.assertEqual(self.request('/__host__/resources.example.org/assets/app.js')[2],b'fetch("/__host__/resources.example.org/data.json")')
            redirect='https://resources.example.org/start'
            external_links.register(redirect)
            self.add(redirect,b'',status=302,location='/app/index.html')
            self.assertTrue(external_links.status(redirect,self.mapping,self.archive)['available'])
            self.assertEqual(self.request('/__host__/resources.example.org/start')[0],200)  # urllib follows the local redirect
            for url in ('http://127.0.0.1/admin','http://localhost/admin','https://www.google-analytics.com/collect','file:///secret'):
                with self.assertRaises(ValueError):external_links.register(url)

    def test_capture_proxy_records_external_app_dependencies(self):
        import external_links
        try:
            import capture_addon
            from mitmproxy import http
        except ImportError:self.skipTest('capture dependencies not installed')
        from types import SimpleNamespace
        root='https://resources.example.org/app/index.html'
        with patch.object(external_links,'FILE',self.state/'lesson_links.json'), patch.multiple(capture_addon,ARCHIVE_DIR=self.archive,STATE_DIR=self.state,URL_MAP_FILE=self.state/'url_map.json'), patch.object(capture_addon,'observe'), patch.object(capture_addon,'event'):
            external_links.register(root)
            flow=SimpleNamespace(request=http.Request.make('GET',root),response=http.Response.make(200,b'<script src="https://cdn.example.org/app.js"></script>',{'Content-Type':'text/html'}))
            capture_addon.request(flow);capture_addon.response(flow)
            self.assertIn('cdn.example.org',external_links.hosts())
            script=SimpleNamespace(request=http.Request.make('GET','https://cdn.example.org/app.js',headers={'Referer':'https://resources.example.org/'}),response=http.Response.make(200,b'console.log("app")',{'Content-Type':'application/javascript'}))
            capture_addon.request(script);capture_addon.response(script)
            mapping=json.loads((self.state/'url_map.json').read_text(encoding='utf-8'))
            self.assertTrue(external_links.status(root,mapping,self.archive)['available'])
            private=SimpleNamespace(request=http.Request.make('POST','https://resources.example.org/api/save',content=b'private'),response=http.Response.make(200,b'private'))
            capture_addon.response(private)
            self.assertNotIn(private.request.pretty_url,json.loads((self.state/'url_map.json').read_text(encoding='utf-8')))

    def test_missing_only_reuses_complete_assets_and_requests_missing_ones(self):
        try:
            import capture_addon
            from mitmproxy import http
        except ImportError:self.skipTest('capture dependencies not installed')
        import external_links,time
        from types import SimpleNamespace
        self.add('/DOS/1/app.js',b'archived()',content_type='application/javascript')
        with patch.multiple(capture_addon,MISSING_ONLY=True,UPDATE_BOOK='1',UPDATE_UNTIL=time.monotonic()+60,ARCHIVE_DIR=self.archive,URL_MAP_FILE=self.state/'url_map.json'), patch.object(external_links,'FILE',self.state/'lesson_links.json'):
            def request(path):
                flow=SimpleNamespace(request=http.Request.make('GET','https://bg.izzi.digital'+path),response=None)
                capture_addon.request(flow);return flow.response
            self.assertEqual(request('/DOS/1/app.js').content,b'archived()')
            self.assertIsNone(request('/DOS/1/missing.js'))
            self.assertIsNone(request('/DOS/2/app.js'))
            self.assertIsNone(request('/api/account.json'))
            with patch.object(capture_addon,'UPDATE_UNTIL',0):self.assertIsNone(request('/DOS/1/app.js'))

    def test_null_padded_html_is_not_reused(self):
        from replay_resolver import usable_body
        record=self.add('/DOS/1/2.html',b'<html>partial'+b'\x00'*100000)
        self.assertFalse(usable_body(record,self.archive,'.html'))
        record=self.add('/DOS/1/2.html',b'<html>complete</html>')
        self.assertTrue(usable_body(record,self.archive,'.html'))

    def test_delete_book_is_local_confirmed_and_preserves_shared_content(self):
        import operations,delete_book
        self.write('books.json',{'1':{'title':'Delete me','lessons':{'2':{'title':'Lesson','path':'/DOS/1/2.html'}}},'3':{'title':'Keep me','lessons':{}}})
        own=self.add('/DOS/1/2.html',b'<html>unique</html>')
        shared=self.add('/DOS/1/picture.png',b'shared bytes',content_type='image/png')
        self.add('/DOS/3/picture.png',b'shared bytes',content_type='image/png')
        self.write('capture_session.json',{'visits':[{'book':'1','lesson':'2','kind':'lesson-start'},{'book':'3','lesson':'4','kind':'lesson-start'}]})
        self.start_server()
        preview=self.request('/__delete_book__/1')
        self.assertEqual(preview[0],200);self.assertIn('Delete me',preview[2].decode())
        self.assertTrue((self.archive/own['key']).exists())
        self.assertEqual(self.request('/__delete_book__/1',headers={'Host':'192.168.1.20'})[0],403)
        headers={'Content-Type':'application/x-www-form-urlencoded'}
        self.assertEqual(self.request('/__delete_book__/1',b'token=wrong',headers)[0],403)
        from urllib.parse import urlencode
        body=urlencode({'token':operations.tasks.token}).encode()
        with patch.object(operations,'capture_port_busy',return_value=True):self.assertEqual(self.request('/__delete_book__/1',body,headers)[0],400)
        with patch.object(operations,'capture_port_busy',return_value=False):self.assertEqual(self.request('/__delete_book__/1',body,headers)[0],200)
        self.assertNotIn('1',json.loads((self.state/'books.json').read_text(encoding='utf-8')))
        self.assertFalse((self.archive/own['key']).exists())
        self.assertTrue((self.archive/shared['key']).exists())
        self.assertEqual(json.loads((self.state/'capture_session.json').read_text(encoding='utf-8'))['visits'][0]['book'],'3')
        self.assertEqual(self.request('/__book__/1')[0],404)

    def test_youtube_links_play_local_video_and_reuse_download(self):
        import youtube_download
        identifier='abcdefghijk'
        self.assertEqual(youtube_download.video_id('https://youtu.be/'+identifier),identifier)
        self.assertEqual(youtube_download.video_id('https://www.youtube.com/watch?v='+identifier+'&feature=share'),identifier)
        self.assertIsNone(youtube_download.video_id('https://evil.example/watch?v='+identifier))
        escaped='https:\\/\\/www.youtube.com\\/embed\\/'+identifier
        self.assertIn('/__offline__/external-media/'+identifier,server.rewrite(escaped.encode()).decode())
        with patch.object(youtube_download,'ARCHIVE_DIR',self.archive),patch.object(youtube_download,'STATE_DIR',self.state),patch.object(youtube_download,'worker') as worker:
            folder=self.archive/'youtube';folder.mkdir();video=folder/(identifier+'.mp4')
            video.write_bytes(b'\x00\x00\x00\x18ftypisom'+b'x'*32)
            self.assertTrue(youtube_download.status(identifier,start=True)['available']);worker.assert_not_called()
            self.assertIn('/__offline__/external-media/'+identifier,server.rewrite(('<a href="https://www.youtube.com/watch?v='+identifier+'">video</a>').encode()).decode())
            component=server.rewrite(('<youtube-player title="Пояснение" video-id="'+identifier+'" :player-vars="{}"></youtube-player>').encode()).decode()
            self.assertNotIn('<youtube-player',component)
            self.assertIn('<iframe',component)
            self.assertIn('data-youtube-id="'+identifier+'"',component)
            self.start_server()
            page=self.request('/__offline__/external-media/'+identifier)[2].decode()
            self.assertIn('<video controls',page)
            self.assertEqual(self.request('/__offline__/youtube-video/'+identifier)[2],video.read_bytes())
            self.assertEqual(self.request('/__offline__/youtube-video/'+identifier,headers={'Range':'bytes=0-7'})[0],206)

    def test_replay_cache_refreshes_changed_state_and_preserves_alias_scope(self):
        import archive_state
        from replay_resolver import find
        self.add('/DOS/1/profil/app.js',b'one',content_type='application/javascript')
        self.add('/DOS/2/profil/app.js',b'two',content_type='application/javascript')
        path=self.state/'url_map.json'
        first=archive_state.load(path,{})
        self.assertIs(first,archive_state.load(path,{}))
        self.assertIsNone(find(first,'bg.izzi.digital','/profil/app.js',''))
        self.assertEqual(find(first,'bg.izzi.digital','/profil/app.js','',book='1')['key'],self.mapping['https://bg.izzi.digital/DOS/1/profil/app.js'][0]['key'])
        self.add('/DOS/1/new.js',b'new',content_type='application/javascript')
        updated=archive_state.load(path,{})
        self.assertIsNot(first,updated)
        self.assertIsNotNone(find(updated,'bg.izzi.digital','/DOS/1/new.js',''))
        path.write_text('{bad json',encoding='utf-8')
        with self.assertRaises(ValueError):archive_state.load(path,{})
        path.unlink();self.assertEqual(archive_state.load(path,{}),{})

    def test_static_browser_cache_revalidates_changes_and_removals(self):
        path='/DOS/1/profil/app.css'
        self.add(path,b'body{color:red}',content_type='text/css')
        self.start_server()
        code,headers,body=self.request(path)
        self.assertEqual(code,200);self.assertIn('must-revalidate',headers['Cache-Control'])
        tag=headers['ETag']
        response=self.request(path,headers={'If-None-Match':tag})
        self.assertEqual(response[0],304);self.assertEqual(response[2],b'')
        self.assertEqual(self.request(path,headers={'If-None-Match':'W/'+tag})[0],304)
        self.assertEqual(self.request(path,headers={'If-None-Match':tag},method='HEAD')[0],304)
        self.add(path,b'body{color:blue}',content_type='text/css')
        changed=self.request(path,headers={'If-None-Match':tag})
        self.assertEqual(changed[0],200);self.assertNotEqual(changed[1]['ETag'],tag)
        self.assertEqual(changed[2],b'body{color:blue}')
        self.mapping.pop('https://bg.izzi.digital'+path);self.write('url_map.json',self.mapping)
        self.assertEqual(self.request(path,headers={'If-None-Match':changed[1]['ETag']})[0],404)
        self.assertEqual(self.request('/')[1]['Cache-Control'],'no-store')
        self.assertEqual(self.request('/__ui__/app.css',headers={'If-None-Match':self.request('/__ui__/app.css')[1]['ETag']})[0],304)

    def test_media_etag_and_if_range_preserve_seek_behavior(self):
        path='/DOS/1/video.mp4';data=b'0123456789'
        self.add(path,data,content_type='video/mp4')
        self.start_server()
        tag=self.request(path)[1]['ETag']
        response=self.request(path,headers={'Range':'bytes=2-5','If-Range':tag})
        self.assertEqual(response[0],206);self.assertEqual(response[2],b'2345')
        self.assertEqual(self.request(path,headers={'Range':'bytes=2-5','If-Range':'"old-version"'})[2],data)
        self.assertEqual(self.request(path,headers={'If-None-Match':tag})[0],304)

    def test_cleanup_preserves_shared_files_and_incomplete_parts_and_restores(self):
        import archive_cleanup,time
        clock=patch.object(archive_cleanup,'now',return_value=time.time()+600);clock.start();self.patches.append(clock)
        self.write('books.json',{})
        video=b'\x00\x00\x00\x18ftypisom'+b'x'*40
        url='https://bg.izzi.digital/DOS/1/movie.mp4'
        record=self.add(url,video,content_type='video/mp4',complete=True)
        self.add('/DOS/2/movie.mp4',video,content_type='video/mp4',complete=True)
        blobs=self.archive/'blobs';blobs.mkdir()
        orphan=blobs/(hashlib.sha256(b'orphan').hexdigest()+'.bin');orphan.write_bytes(b'orphan')
        def ranges(target,total,body):
            identity=hashlib.sha256(target.encode()).hexdigest();folder=self.state/'range_assembly'/identity;folder.mkdir(parents=True)
            part=folder/('0-'+str(len(body)-1)+'.part');part.write_bytes(body)
            self.write('range_assembly/'+identity+'.json',{'url':target,'total':total,'ranges':[[0,len(body)-1,str(part)]]})
            return part
        completed=ranges(url,len(video),video)
        unfinished=ranges('https://bg.izzi.digital/DOS/1/unfinished.mp4',100,b'abc')
        result=archive_cleanup.report(self.archive,self.state)
        paths={entry['path'] for entry in result['files']}
        self.assertIn(orphan.relative_to(self.archive).as_posix(),paths)
        self.assertIn(completed.relative_to(self.state).as_posix(),paths)
        self.assertNotIn(unfinished.relative_to(self.state).as_posix(),paths)
        self.write('library_catalog.json',{})
        with self.assertRaisesRegex(ValueError,'променен'):archive_cleanup.quarantine(self.archive,self.state,result['fingerprint'])
        result=archive_cleanup.report(self.archive,self.state)
        batch=archive_cleanup.quarantine(self.archive,self.state,result['fingerprint'])
        self.assertFalse(orphan.exists());self.assertFalse(completed.exists());self.assertTrue(unfinished.exists())
        self.assertTrue((self.archive/record['key']).exists())
        orphan.write_bytes(b'new content')
        with self.assertRaisesRegex(ValueError,'Вече има файл'):archive_cleanup.restore(self.archive,self.state,batch)
        self.assertFalse(completed.exists())
        orphan.unlink()
        archive_cleanup.restore(self.archive,self.state,batch)
        self.assertTrue(orphan.exists());self.assertTrue(completed.exists())
        trash=archive_cleanup.trash_report(self.state,batch)
        manifest=json.loads((self.state/'cleanup_trash'/batch/'manifest.json').read_text(encoding='utf-8'));manifest['changed']=True
        self.write('cleanup_trash/'+batch+'/manifest.json',manifest)
        with self.assertRaisesRegex(ValueError,'променена'):archive_cleanup.purge(self.state,batch,trash['fingerprint'])
        trash=archive_cleanup.trash_report(self.state,batch)
        archive_cleanup.purge(self.state,batch,trash['fingerprint'])
        self.assertFalse((self.state/'cleanup_trash'/batch).exists())
        self.assertIn(unfinished.relative_to(self.state).as_posix(),{e['path'] for e in archive_cleanup.report(self.archive,self.state,True)['files']})

    def test_cleanup_is_local_and_requires_review_and_valid_indexes(self):
        import archive_cleanup,operations,time
        clock=patch.object(archive_cleanup,'now',return_value=time.time()+600);clock.start();self.patches.append(clock)
        self.write('books.json',{});self.write('url_map.json',{})
        blobs=self.archive/'blobs';blobs.mkdir()
        orphan=blobs/('a'*64+'.bin');orphan.write_bytes(b'orphan')
        self.start_server()
        page=self.request('/__cleanup__')[2].decode()
        self.assertIn('Предварителен отчет',page);self.assertTrue(orphan.exists())
        self.assertIn('Почистване на архива',self.request('/')[2].decode())
        self.assertEqual(self.request('/__cleanup__',headers={'Host':'192.168.1.20'})[0],403)
        headers={'Content-Type':'application/x-www-form-urlencoded'}
        self.assertEqual(self.request('/__cleanup__',b'action=clean',headers)[0],403)
        result=archive_cleanup.report(self.archive,self.state)
        from urllib.parse import urlencode
        body=urlencode({'action':'clean','review':result['fingerprint'],'token':operations.tasks.token}).encode()
        with patch.object(operations,'capture_port_busy',return_value=True):self.assertEqual(self.request('/__cleanup__',body,headers)[0],400)
        with patch.object(operations,'capture_port_busy',return_value=False):self.assertEqual(self.request('/__cleanup__',body,headers)[0],200)
        self.assertFalse(orphan.exists())
        (self.state/'url_map.json').write_text('{bad',encoding='utf-8')
        with self.assertRaises(ValueError):archive_cleanup.report(self.archive,self.state)
        blocked=self.request('/__cleanup__')[2].decode()
        self.assertIn('Почистването е блокирано',blocked);self.assertIn('Възстанови',blocked)
        self.assertNotIn('Потвърди преместването',blocked)

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
        (self.state/'url_map.json').write_text('{broken',encoding='utf-8')
        self.assertEqual(self.request('/__ui__/app.css')[0],200)

    def test_explicit_class_in_title_overrides_conflicting_catalogue_number(self):
        from book_covers import grade_number
        for title in ('География за 5. клас','География за пети клас','География за V клас','География за <b>5.&nbsp;клас</b>'):
            self.assertEqual(grade_number(title,{'grade':{'number':1}}),5)
        self.assertEqual(grade_number('Учебник',{'grade':{'number':'7'}}),7)
        self.assertEqual(grade_number('Учебник'),0)
        self.write('books.json',{'1':{'title':'География за 5. клас','lessons':{}}})
        self.add('/api/online-bookshelf-publications',json.dumps({'data':{'ungrouped':{'publications':[{'dos_id':1,'grade':{'number':1}}]}}}).encode(),content_type='application/json')
        self.start_server();page=self.request('/')[2].decode()
        self.assertIn('<h2>5. клас</h2>',page)
        self.assertNotIn('<h2>1. клас</h2>',page)

    def test_home_uses_only_available_original_cover_for_matching_book(self):
        self.write('books.json',{'1':{'title':'Математика за 4. клас','lessons':{}},'2':{'title':'Математика за 6. клас','lessons':{}}})
        picture=b'\x89PNG\r\n\x1a\ncover'
        self.add('/DOS/group-images/math.png',picture,content_type='image/png')
        catalog={'data':{'grouped':[{'thumbs':{'image1':'/DOS/group-images/math.png'},'publications':[{'dos_id':1,'grade':{'number':4},'thumbs':{'image1':'/DOS/1/missing.png'}}]}],'ungrouped':{'publications':[]}}}
        self.add('/api/online-bookshelf-publications',json.dumps(catalog).encode(),content_type='application/json')
        self.start_server();page=self.request('/')[2].decode()
        self.assertIn('<h2>4. клас</h2>',page);self.assertIn('<h2>6. клас</h2>',page)
        self.assertLess(page.index('<h2>4. клас</h2>'),page.index('<h2>6. клас</h2>'))
        self.assertNotIn('Начален етап',page);self.assertNotIn('Прогимназиален етап',page)
        self.assertEqual(1,page.count('class="original-cover"'))
        self.assertNotIn('/DOS/1/missing.png',page)
        self.assertIn('src="/__host__/bg.izzi.digital/DOS/group-images/math.png"',page)
        self.assertEqual(picture,self.request('/__host__/bg.izzi.digital/DOS/group-images/math.png')[2])
        self.assertNotIn('catalog-intro',page);self.assertNotIn('Съдържание на архива',page)

    def test_covers_keep_original_palette_and_second_image(self):
        import book_covers
        self.write('books.json',{'1':{'title':'Book','lessons':{}}})
        for filename in ('front','back'):
            self.add('/DOS/1/'+filename+'.png',b'\x89PNG\r\n\x1a\n'+filename.encode(),content_type='image/png')
        payload={'data':{'ungrouped':{'publications':[{'dos_id':1,'dos_class':'palette3',
            'thumbs':{'image1':'/DOS/1/front.png','image2':'/DOS/1/back.png'}}]}}}
        self.add('/api/online-bookshelf-publications',json.dumps(payload).encode(),content_type='application/json')
        self.start_server()
        page=self.request('/')[2].decode()
        self.assertIn('book-thumbnail palette3',page)
        self.assertIn('class="cover-tile"',page)
        self.assertIn('class="cover-decoration" src="/__host__/bg.izzi.digital/DOS/1/back.png"',page)
        self.assertIn('class="original-cover" src="/__host__/bg.izzi.digital/DOS/1/front.png"',page)

    def test_lan_is_reader_only_even_with_direct_admin_urls(self):
        self.write('books.json',{'1':{'title':'Book','lessons':{'2':{'title':'Lesson','path':'/DOS/1/2.html'}}}})
        self.add('/DOS/1/2.html')
        self.start_server()
        headers={'Host':'192.168.1.20'}
        for path in ('/','/__book__/1'):
            code,_,body=self.request(path,headers=headers)
            self.assertEqual(code,200)
            self.assertNotIn('library-menu',body.decode())
            self.assertNotIn('Подреди / преименувай / скрий',body.decode())
        self.assertEqual(self.request('/DOS/1/2.html',headers=headers)[0],200)
        for path in ('/__book__/1?edit=1','/__missing__','/__journal__','/__help__','/__operations__','/__ops__/status'):
            self.assertEqual(self.request(path,headers=headers)[0],403,path)
        body=b'order_2=1&hidden_2=on'
        self.assertEqual(self.request('/__catalog__/1',body,{**headers,'Content-Type':'application/x-www-form-urlencoded'})[0],403)
        self.assertFalse((self.state/'library_catalog.json').exists())
        self.assertIn('library-menu',self.request('/')[2].decode())
        self.assertEqual(self.request('/__book__/1?edit=1')[0],200)
        handler=object.__new__(server.H)
        handler.client_address=('192.168.1.30',1234)
        handler.headers={'Host':'localhost','X-Forwarded-For':'127.0.0.1'}
        self.assertFalse(handler.control_local())

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

    def test_lesson_list_checks_files_without_reading_all_lesson_html(self):
        import archive_db
        book={'title':'Book','lessons':{}}
        records=[]
        for lid,extra in [('10',{}),('11',{}),('12',{'size':999999}),('13',{'status':404}),('14',{'status':206,'content_range':'bytes 0-29/999999'})]:
            path=f'/DOS/1/{lid}.html';book['lessons'][lid]={'title':'Page '+lid,'path':path}
            records.append(self.add('https://bg.izzi.digital:443'+path,('<html>'+lid+'x'*100000+'</html>').encode(),**extra))
        # A removed body must never remain available because of a cached count.
        (self.archive/records[1]['key']).unlink()
        books={'1':book};other_records={}
        for bid in ('42888','888827','887348'):
            path=f'/DOS/{bid}/20.html'
            books[bid]={'title':'Book '+bid,'lessons':{'20':{'title':'Page','path':path}}}
            other_records[bid]=self.add(path,('<html>'+bid+'</html>').encode())
        self.write('books.json',books);archive_db.initialize(self.state)
        original_open=Path.open
        def metadata_only(path,*args,**kwargs):
            if path.parent==self.archive:raise AssertionError('Listing must not open lesson HTML bodies')
            return original_open(path,*args,**kwargs)
        self.start_server()
        with patch.object(Path,'open',metadata_only),patch.object(archive_db.Index,'items',side_effect=AssertionError('Listing must not scan the resource index')):
            status,_,body=self.request('/__book__/1')
            self.assertEqual(200,status);self.assertIn('1 с наличен HTML',body.decode())
            for bid,row in other_records.items():
                with self.subTest(book=bid):
                    status,_,body=self.request('/__book__/'+bid)
                    self.assertEqual(200,status);self.assertIn('1 с наличен HTML',body.decode())
                    (self.archive/row['key']).unlink()
                    self.assertIn('0 с наличен HTML',self.request('/__book__/'+bid)[2].decode())
            (self.archive/records[0]['key']).unlink()
            self.assertIn('0 с наличен HTML',self.request('/__book__/1')[2].decode())

    def test_lesson_list_optimization_keeps_full_replay_html_validation(self):
        self.write('books.json',{'1':{'title':'Book','lessons':{'2':{'title':'Page','path':'/DOS/1/2.html'}}}})
        self.add('/DOS/1/2.html',b'<html>'+b'x'*65536+b'\x00'+b'</html>')
        self.start_server()
        self.assertEqual(200,self.request('/__book__/1')[0])
        self.assertEqual(404,self.request('/DOS/1/2.html')[0],'HTML with a NUL after the first chunk must remain rejected during replay')
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
        before=(self.state/'missing_resources.jsonl').read_text(encoding='utf-8') if (self.state/'missing_resources.jsonl').exists() else ''
        probe=json.loads(self.request('/__offline_capture__/image_status')[2])
        self.assertFalse(probe['capture'])
        after=(self.state/'missing_resources.jsonl').read_text(encoding='utf-8') if (self.state/'missing_resources.jsonl').exists() else ''
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
        row=json.loads((self.state/'progress/1.jsonl').read_text(encoding='utf-8'))
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
        with (self.state/'progress/1.jsonl').open('a',encoding='utf-8') as f:f.write('{truncated\n')
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
