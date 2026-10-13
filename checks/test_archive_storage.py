"""SQLite migration, indexed replay, concurrent edits and archive redistribution."""
import concurrent.futures,hashlib,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import archive_db,archive_state,archive_cleanup,import_har,migrate_archive,server,assembled_media,range_assembler
from archive_storage import blob_key,assembled_key
from replay_resolver import find,usable_body
from checks import test_library_workflow as fixtures

class Storage(unittest.TestCase):
    setUp=fixtures.LibraryWorkflow.setUp
    tearDown=fixtures.LibraryWorkflow.tearDown
    write=fixtures.LibraryWorkflow.write
    start_server=fixtures.LibraryWorkflow.start_server
    stop_server=fixtures.LibraryWorkflow.stop_server
    request=fixtures.LibraryWorkflow.request
    # Reuse the HTTP fixture helpers, without rerunning inherited regression cases.
    def prepare(self):
        self.body=b'<html><body>offline lesson</body></html>'
        self.old='blobs/'+hashlib.sha256(self.body).hexdigest()+'.html'
        (self.archive/self.old).parent.mkdir(parents=True,exist_ok=True);(self.archive/self.old).write_bytes(self.body)
        self.url='https://bg.izzi.digital/DOS/1/2.html'
        self.rec={'key':self.old,'body_available':True,'status':200,'method':'GET','size':len(self.body),'decoded':True,'content_type':'text/html'}
        self.write('url_map.json',{self.url:[self.rec]})
        self.write('books.json',{'1':{'title':'Book for 5. class','lessons':{'2':{'title':'Lesson','path':'/DOS/1/2.html'}}},'3':{'title':'Other','lessons':{}}})
        archive_db.initialize(self.state)
    def test_sqlite_import_replay_invalidation_and_independent_writers(self):
        self.prepare();original=(self.state/'url_map.json').read_bytes()
        archive_db.initialize(self.state)
        value=archive_state.load(self.state/'url_map.json',{})
        self.assertEqual(self.rec,find(value,'bg.izzi.digital','/DOS/1/2.html',''))
        a=import_har.load(self.state/'url_map.json',{});b=import_har.load(self.state/'url_map.json',{})
        a['https://api.izzi.digital/datastore/new.png']=[self.rec];b['https://bg.izzi.digital/other.png']=[self.rec]
        import_har.save(a.path,a);import_har.save(b.path,b)
        new=archive_state.load(a.path,{})
        self.assertIsNot(value,new);self.assertEqual(3,len(new))
        self.assertEqual(original,(self.state/'url_map.json').read_bytes())
        c=import_har.load(a.path,{});d=import_har.load(a.path,{})
        c[self.url][0]['status']=404;d[self.url][0]['size']=999
        import_har.save(c.path,c)
        with self.assertRaisesRegex(ValueError,'concurrently'):import_har.save(d.path,d)
        self.assertEqual(404,import_har.load(c.path,{})[self.url][0]['status'])
        with archive_db.connect(archive_db.database(a.path)) as conn:
            detail=conn.execute('EXPLAIN QUERY PLAN SELECT url,data FROM resources WHERE canonical=?',('/DOS/1/2.html',)).fetchall()
            self.assertIn('resource_paths',str(detail))
        with patch.object(archive_db.Index,'items',side_effect=AssertionError('Resolver must use SQL index')):
            self.assertIsNotNone(find(new,'api.izzi.digital','/DOS/1/datastore/new.png',''))
        self.assertEqual('blobs/ab/cd/'+'abcd'+'0'*60+'.png',blob_key('abcd'+'0'*60,'.png'))
    def test_sqlite_http_layout_migration_cleanup_and_delete(self):
        self.prepare();self.write('extra.json',{'key':self.old})
        plan=migrate_archive.report(self.archive,self.state)
        self.assertEqual(1,plan['count']);self.assertEqual(self.old,plan['files'][0]['old'])
        self.start_server();self.assertEqual(200,self.request('/DOS/1/2.html')[0]);self.stop_server()
        result=migrate_archive.apply(self.archive,self.state,plan['fingerprint'])
        key=blob_key(hashlib.sha256(self.body).hexdigest(),'.html')
        self.assertEqual(1,result['moved']);self.assertEqual(self.body,(self.archive/key).read_bytes())
        self.assertTrue((self.archive/self.old).is_file())
        self.assertEqual(key,import_har.load(self.state/'url_map.json',{})[self.url][0]['key'])
        self.assertEqual(key,json.loads((self.state/'extra.json').read_text())['key'])
        self.assertTrue((Path(result['backup'])/'library.sqlite3').is_file())
        with patch.object(archive_cleanup,'now',return_value=__import__('time').time()+600):
            cleanup=archive_cleanup.report(self.archive,self.state)
        self.assertIn(self.old,[row['path'] for row in cleanup['files']]);self.assertNotIn(key,[row['path'] for row in cleanup['files']])
        self.start_server();self.assertEqual(200,self.request('/DOS/1/2.html')[0])
        self.assertIn(b'Book for',self.request('/')[2]);self.stop_server()
        # Resuming never overwrites; mismatch rejects all changes.
        plan=migrate_archive.report(self.archive,self.state)
        (self.archive/key).write_bytes(b'conflict')
        with self.assertRaises(ValueError):migrate_archive.apply(self.archive,self.state,plan['fingerprint'])
        (self.archive/key).write_bytes(self.body)
        import delete_book
        delete_book.remove('1',self.state,self.archive)
        self.assertNotIn('1',import_har.load(self.state/'books.json',{}));self.assertIn('3',import_har.load(self.state/'books.json',{}))
        self.assertFalse((self.archive/key).exists())
    def test_sqlite_range_assembly_and_capture(self):
        self.prepare();url='https://api.izzi.digital/datastore/video.mp4';body=b'\x00\x00\x00\x18ftypmp42'+b'video'*20
        with patch.multiple(range_assembler,ARCHIVE_DIR=self.archive,STATE=self.state/'range_assembly',URL_MAP_FILE=self.state/'url_map.json'):
            self.assertIsNone(range_assembler.add_range(url,f'bytes 0-19/{len(body)}',body[:20]))
            final=range_assembler.add_range(url,f'bytes 20-{len(body)-1}/{len(body)}',body[20:]);range_assembler.register_complete(url,final)
        self.assertEqual(assembled_key(range_assembler.uid(url)),final.relative_to(self.archive).as_posix())
        row=find(import_har.load(self.state/'url_map.json',{}),'api.izzi.digital','/datastore/video.mp4','',lambda r:usable_body(r,self.archive,'.mp4'))
        self.assertEqual(len(body),row['size'])
        self.start_server();status,headers,data=self.request('/__host__/api.izzi.digital/datastore/video.mp4',headers={'Range':'bytes=10-29'})
        self.assertEqual(206,status);self.assertEqual(body[10:30],data);self.stop_server()
    def test_sqlite_corruption_and_failed_import_preserve_originals(self):
        self.write('url_map.json',{'u':'invalid'});self.write('books.json',{})
        with self.assertRaises(ValueError):archive_db.initialize(self.state)
        self.assertEqual({'u':'invalid'},json.loads((self.state/'url_map.json').read_text()))
        self.prepare();(self.state/'library.sqlite3').write_bytes(b'broken sqlite')
        with self.assertRaises(ValueError):archive_state.load(self.state/'url_map.json',{})
        self.start_server();self.assertEqual(503,self.request('/')[0]);self.stop_server()
    def test_har_import_and_proxy_use_sqlite_and_sharded_bodies(self):
        self.prepare()
        data=b'<html><title>Imported lesson</title></html>'
        url='https://bg.izzi.digital/DOS/3/4.html'
        har=self.root/'fixture.har'
        har.write_text(json.dumps({'log':{'entries':[{'request':{'url':url,'method':'GET','headers':[]},'response':{'status':200,'headers':[],'content':{'mimeType':'text/html','text':data.decode()}}}]}}))
        with patch.multiple(import_har,ARCHIVE_DIR=self.archive,STATE_DIR=self.state,CAPTURES_DIR=self.root/'captures',URL_MAP_FILE=self.state/'url_map.json',BOOKS_FILE=self.state/'books.json',IMPORTS_FILE=self.state/'imports.json'),patch.object(sys,'argv',['import_har.py',str(har)]):
            import_har.main()
        mapping=import_har.load(self.state/'url_map.json',{})
        self.assertEqual(blob_key(hashlib.sha256(data).hexdigest(),'.html'),mapping[url][0]['key'])
        self.assertIn('4',import_har.load(self.state/'books.json',{})['3']['lessons'])
        import capture_addon
        from mitmproxy import http
        from types import SimpleNamespace
        flow=SimpleNamespace(request=http.Request.make('GET','https://bg.izzi.digital/DOS/1/5.html'),response=http.Response.make(200,b'<html><title>Captured</title></html>',{'Content-Type':'text/html'}))
        with patch.multiple(capture_addon,ARCHIVE_DIR=self.archive,STATE_DIR=self.state,URL_MAP_FILE=self.state/'url_map.json',BOOKS_FILE=self.state/'books.json'),patch.object(capture_addon,'observe'),patch.object(capture_addon.external_links,'discover'):
            capture_addon.running();capture_addon.response(flow);capture_addon.response(flow)
        mapping=import_har.load(self.state/'url_map.json',{})
        self.assertEqual(1,len(mapping[flow.request.pretty_url]))
        self.assertEqual(4,len(Path(mapping[flow.request.pretty_url][0]['key']).parts))
        self.assertIn('5',import_har.load(self.state/'books.json',{})['1']['lessons'])

    def test_layout_can_resume_after_interrupted_metadata_update(self):
        self.prepare();self.write('extra.json',{'key':self.old})
        plan=migrate_archive.report(self.archive,self.state)
        original_save=migrate_archive.save
        def interrupted(path,value):
            if Path(path).name=='extra.json':raise OSError('simulated interruption')
            return original_save(path,value)
        with patch.object(migrate_archive,'save',side_effect=interrupted):
            with self.assertRaises(OSError):migrate_archive.apply(self.archive,self.state,plan['fingerprint'])
        self.assertTrue((self.archive/self.old).is_file())
        self.assertEqual(self.old,json.loads((self.state/'extra.json').read_text())['key'])
        self.start_server();self.assertEqual(200,self.request('/DOS/1/2.html')[0]);self.stop_server()
        plan=migrate_archive.report(self.archive,self.state)
        self.assertEqual(0,plan['copy_bytes'])
        done=migrate_archive.apply(self.archive,self.state,plan['fingerprint'])
        key=blob_key(hashlib.sha256(self.body).hexdigest(),'.html')
        self.assertEqual(key,json.loads((self.state/'extra.json').read_text())['key'])
        self.assertEqual(1,done['moved'])

    def test_sqlite_thread_writers(self):
        self.prepare()
        def write(i):
            mapping=import_har.load(self.state/'url_map.json',{});mapping[f'https://bg.izzi.digital/{i}.png']=[self.rec];import_har.save(mapping.path,mapping)
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:list(pool.map(write,range(40)))
        self.assertEqual(41,len(import_har.load(self.state/'url_map.json',{})))
        def append(i):
            import_har.update_entry(self.state/'url_map.json',self.url,lambda rows:rows.append({**self.rec,'size':i}),[])
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:list(pool.map(append,range(40)))
        rows=import_har.load(self.state/'url_map.json',{})[self.url]
        self.assertEqual(41,len(rows))
        self.assertEqual(set(range(40)),{r['size'] for r in rows[1:]})

if __name__=='__main__':unittest.main()
