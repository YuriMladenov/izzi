"""Per-book export/import: selection, shared assets, merge safety and conflicts."""
import hashlib,json,sys,tempfile,unittest,zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import archive_db,book_transfer
from archive_storage import blob_key

class BookTransfer(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.source=self.build('source')
        self.target=self.build('target')

    def tearDown(self):self.tmp.cleanup()

    def build(self,name):
        root=self.root/name;state=root/'state';archive=root/'archive'
        state.mkdir(parents=True);archive.mkdir()
        mapping={}
        def put(data,ext):
            key=blob_key(hashlib.sha256(data).hexdigest(),ext)
            path=archive/key;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
            return key
        def record(key,data,kind):
            return {'key':key,'body_available':True,'status':200,'method':'GET',
                    'size':len(data),'decoded':True,'content_type':kind}
        if name=='source':
            css=b'body{color:red}';css_key=put(css,'.css')
            for lesson in (11,12):
                body=b'<html>lesson '+str(lesson).encode()+b'</html>';key=put(body,'.html')
                mapping[f'https://bg.izzi.digital/DOS/1/{lesson}.html']=[record(key,body,'text/html')]
            image=b'\x89PNG\r\n\x1a\n'+b'0'*64
            mapping['https://bg.izzi.digital/DOS/1/datastore/cover.png']=[record(put(image,'.png'),image,'image/png')]
            mapping['https://bg.izzi.digital/DOS/1/site.css']=[record(css_key,css,'text/css')]
            other=b'<html>other book</html>'
            mapping['https://bg.izzi.digital/DOS/2/21.html']=[record(put(other,'.html'),other,'text/html')]
            books={'1':{'id':'1','title':'Book One','lessons':{'11':{'id':'11'},'12':{'id':'12'}}},
                   '2':{'id':'2','title':'Book Two','lessons':{'21':{'id':'21'}}}}
            catalog={'1':{'order':['11','12']},'2':{'order':['21']}}
            media={'lessons':{'1/11':{'book':'1','lesson':'11','media':[]},
                              '2/21':{'book':'2','lesson':'21','media':[]}}}
            links={'https://bg.izzi.digital/DOS/1/11.html':{'resources':['https://bg.izzi.digital/DOS/1/11.html','https://bg.izzi.digital/DOS/1/site.css','https://bg.izzi.digital/DOS/1/datastore/cover.png']},
                   'https://bg.izzi.digital/DOS/1/12.html':{'resources':['https://bg.izzi.digital/DOS/1/12.html','https://bg.izzi.digital/DOS/1/site.css']},
                   'https://bg.izzi.digital/DOS/2/21.html':{'resources':['https://bg.izzi.digital/DOS/2/21.html']}}
        else:
            body=b'<html>nine</html>'
            mapping['https://bg.izzi.digital/DOS/9/91.html']=[record(put(body,'.html'),body,'text/html')]
            books={'9':{'id':'9','title':'Book Nine','lessons':{'91':{'id':'91'}}}}
            catalog={'9':{'order':['91']}}
            media={'lessons':{'9/91':{'book':'9','lesson':'91','media':[]}}}
            links={'https://bg.izzi.digital/DOS/9/91.html':{'resources':['https://bg.izzi.digital/DOS/9/91.html']}}
        (state/'url_map.json').write_text(json.dumps(mapping))
        (state/'books.json').write_text(json.dumps(books))
        (state/'library_catalog.json').write_text(json.dumps(catalog))
        (state/'media_map.json').write_text(json.dumps(media))
        (state/'lesson_links.json').write_text(json.dumps(links))
        archive_db.initialize(state)
        return state,archive

    def export_one(self):
        self.package=self.root/'one.zip'
        return book_transfer.export(['1'],*self.source,self.package)

    def urls(self,state):return set(book_transfer.read_index(state)[0])

    def test_export_contains_only_selected_book_and_its_shared_assets(self):
        result=self.export_one()
        self.assertEqual({'1':'Book One'},result['books'])
        with zipfile.ZipFile(self.package) as package:
            names=package.namelist()
            manifest=json.loads(package.read(book_transfer.MANIFEST))
            index=json.loads(package.read('state/index.json'))
        self.assertNotIn('https://bg.izzi.digital/DOS/2/21.html',index['url_map'])
        self.assertEqual(4,len(manifest['files']))
        self.assertIn('state/lesson_links.json',names)
        for entry in manifest['files']:
            self.assertIn('archive/'+entry['key'],names)
        # The shared stylesheet must travel even though it is a book-level URL.
        self.assertTrue(any(name.endswith('.css') for name in names))

    def test_import_merges_without_touching_other_books(self):
        self.export_one()
        report=book_transfer.preview(self.package,*self.target)
        self.assertEqual(['1'],report['adding'])
        self.assertEqual([],report['conflicts'])
        book_transfer.import_books(self.package,*self.target)
        state=self.target[0]
        self.assertEqual({'9','1'},set(book_transfer.known_books(state)))
        urls=self.urls(state)
        self.assertIn('https://bg.izzi.digital/DOS/1/11.html',urls)
        self.assertIn('https://bg.izzi.digital/DOS/9/91.html',urls)
        catalog=json.loads((state/'library_catalog.json').read_text())
        self.assertEqual({'9','1'},set(catalog))
        media=json.loads((state/'media_map.json').read_text())['lessons']
        self.assertEqual({'9/91','1/11'},set(media))

    def test_reimport_requires_replace_and_is_idempotent(self):
        self.export_one()
        book_transfer.import_books(self.package,*self.target)
        with self.assertRaises(book_transfer.TransferError):
            book_transfer.import_books(self.package,*self.target)
        result=book_transfer.import_books(self.package,*self.target,replace=True)
        self.assertEqual(0,result['copied'])
        self.assertEqual(4,result['restored'])
        self.assertEqual({'9','1'},set(book_transfer.known_books(self.target[0])))

    def test_conflicting_local_file_is_reported_and_blocks_import(self):
        self.export_one()
        source_archive=self.source[1]
        key=next(iter(sorted(source_archive.glob('blobs/*/*/*.css'))))
        relative=key.relative_to(source_archive)
        broken=self.target[1]/relative
        broken.parent.mkdir(parents=True,exist_ok=True);broken.write_bytes(b'tampered')
        report=book_transfer.preview(self.package,*self.target)
        self.assertEqual([str(relative)],report['conflicts'])
        with self.assertRaises(book_transfer.TransferError):
            book_transfer.import_books(self.package,*self.target)

    def test_export_refuses_missing_bodies_and_unknown_books(self):
        state,archive=self.source
        (archive/next(iter(sorted(archive.glob('blobs/*/*/*.html'))))).unlink()
        with self.assertRaises(book_transfer.TransferError):
            book_transfer.export(['1'],state,archive,self.root/'broken.zip')
        self.assertFalse((self.root/'broken.zip').exists())
        state2,archive2=self.build('second')
        with self.assertRaises(book_transfer.TransferError):
            book_transfer.export(['777'],state2,archive2,self.root/'none.zip')

    def test_selection_accepts_ids_and_partial_titles(self):
        books=book_transfer.known_books(self.source[0])
        self.assertEqual(['1'],book_transfer.parse_selection(['Book One'],books))
        self.assertEqual(['1'],book_transfer.parse_selection(['one'],books))
        self.assertEqual(['1','2'],book_transfer.parse_selection(None,books))
        with self.assertRaises(book_transfer.TransferError):
            book_transfer.parse_selection(['missing'],books)

if __name__=='__main__':unittest.main()
