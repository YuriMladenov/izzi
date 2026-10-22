"""Repeated validation saves disk reads without hiding changed/missing bodies."""
import json,os,sys,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from replay_resolver import usable_body,_valid_content
import book_covers

class ValidationCache(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.file=self.root/'body';self.file.write_bytes(b'<html>lesson</html>')
        self.record={'key':'body','body_available':True,'status':200,'size':self.file.stat().st_size}
        _valid_content.cache_clear()
    def tearDown(self):self.tmp.cleanup();_valid_content.cache_clear()
    def test_repeated_html_checks_read_once(self):
        self.assertTrue(usable_body(self.record,self.root,'.html'))
        with patch.object(Path,'open',side_effect=AssertionError('unnecessary body read')):
            for _ in range(20):self.assertTrue(usable_body(self.record,self.root,'.html'))
        self.assertEqual(20,_valid_content.cache_info().hits)
    def test_modified_replaced_deleted_and_repaired_body(self):
        self.assertTrue(usable_body(self.record,self.root,'.html'))
        original=self.file.stat()
        self.file.write_bytes(b'\0'*original.st_size)
        os.utime(self.file,ns=(original.st_atime_ns,original.st_mtime_ns+1000000))
        self.assertFalse(usable_body(self.record,self.root,'.html'))
        replacement=self.root/'replacement';replacement.write_bytes(b'x'*original.st_size)
        os.utime(replacement,ns=(original.st_atime_ns,original.st_mtime_ns+1000000))
        os.replace(replacement,self.file)
        self.assertTrue(usable_body(self.record,self.root,'.html'))
        self.file.unlink();self.assertFalse(usable_body(self.record,self.root,'.html'))
    def test_record_changes_and_content_type_are_not_cached(self):
        self.file.write_bytes(b'audio');self.record['size']=5
        self.assertTrue(usable_body(self.record,self.root,'.mp3'))
        self.record['content_type']='text/html';self.assertFalse(usable_body(self.record,self.root,'.mp3'))
        self.record.pop('content_type');self.record['status']=206
        self.assertFalse(usable_body(self.record,self.root,'.mp3'))
        self.record['content_range']='bytes 0-4/5';self.assertTrue(usable_body(self.record,self.root,'.mp3'))
        self.record['size']=6;self.assertFalse(usable_body(self.record,self.root,'.mp3'))
    def test_extension_is_part_of_cache_key(self):
        self.assertTrue(usable_body(self.record,self.root,'.html'))
        self.assertFalse(usable_body(self.record,self.root,'.js'))
    def test_geogebra_validation_reuses_zip_check(self):
        with zipfile.ZipFile(self.file,'w') as z:z.writestr('geogebra.xml','<geogebra/>')
        self.record['size']=self.file.stat().st_size
        self.assertTrue(usable_body(self.record,self.root,'.ggb'))
        with patch('replay_resolver.zipfile.ZipFile',side_effect=AssertionError('reopened ZIP')):
            self.assertTrue(usable_body(self.record,self.root,'.ggb'))
    def test_thumbnail_lookup_reused_only_within_one_catalog_render(self):
        url='https://bg.izzi.digital/cover.png';catalog='https://bg.izzi.digital/api/online-bookshelf-publications'
        payload={'data':{'grouped':[{'thumbs':{'image1':url},'publications':[{'dos_id':str(i)} for i in range(3)]}]}}
        (self.root/'catalog').write_text(json.dumps(payload),encoding='utf8')
        mapping={catalog:[{'key':'catalog','body_available':True,'status':200}],url:[self.record]}
        self.file.write_bytes(b'image');self.record['size']=5
        books={str(i):{'title':'5. клас'} for i in range(3)}
        with patch.object(book_covers,'find',wraps=book_covers.find) as lookup:
            covers=book_covers.catalog_covers(mapping,self.root,books)
            self.assertEqual(2,lookup.call_count);self.assertTrue(all(row['src'] for row in covers.values()))
        self.file.unlink()
        self.assertFalse(any(row['src'] for row in book_covers.catalog_covers(mapping,self.root,books).values()))

if __name__=='__main__':unittest.main()
