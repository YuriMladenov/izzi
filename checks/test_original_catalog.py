"""Public catalogue import, local book filtering and dependency fallback."""
import hashlib,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import original_catalog,import_catalog
from import_har import load

class OriginalCatalogue(unittest.TestCase):
    def test_local_books_keep_groups_and_link_to_local_lessons(self):
        keep={'dos_id':1,'dos_url':'https://bg.izzi.digital/DOS/1/index.html','is_locked':True}
        other={'dos_id':2,'dos_url':'https://bg.izzi.digital/DOS/2/index.html'}
        source={'data':{'grouped':[{'id':10,'publications':[keep,other]},{'id':11,'publications':[other]}],'ungrouped':{'publications':[other,keep]}}}
        result=original_catalog.local_shelf(source,{'1':{}})['data']
        self.assertEqual([10],[g['id'] for g in result['grouped']])
        self.assertEqual('/__book__/1',result['grouped'][0]['publications'][0]['dos_url'])
        self.assertTrue(result['grouped'][0]['publications'][0]['is_locked'])
        self.assertEqual([1],[p['dos_id'] for p in result['ungrouped']['publications']])
        self.assertEqual(2,len(source['data']['grouped'][0]['publications']))

    def test_import_excludes_account_bodies_and_requires_main_scripts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);archive=root/'archive';mapping=root/'state/map.json';har=root/'input.har'
            entries=[]
            for path,text in [('/', '<html><head></head><body><script src="/_nuxt/app.js"></script></body></html>'),('/_nuxt/app.js','/* app */'),('/api/online-bookshelf-publications','{"data":{"grouped":[],"ungrouped":{}}}'),('/api/userdata','PRIVATE_ACCOUNT'),('/api/p/authapi/device-slots','PRIVATE_DEVICES')]:
                entries.append({'request':{'url':'https://bg.izzi.digital'+path,'method':'GET','headers':[{'name':'Authorization','value':'PRIVATE_TOKEN'}]},'response':{'status':200,'content':{'mimeType':'text/html' if path=='/' else 'application/json','text':text}}})
            har.write_text(json.dumps({'log':{'entries':entries}}))
            with patch.object(import_catalog,'ARCHIVE_DIR',archive),patch.object(import_catalog,'URL_MAP_FILE',mapping),patch.object(sys,'argv',['import_catalog.py',str(har)]):self.assertEqual(0,import_catalog.main())
            rows=load(mapping,{})
            self.assertEqual(3,len(rows));self.assertNotIn('PRIVATE',mapping.read_text())
            self.assertFalse(any('PRIVATE' in p.read_text() for p in archive.rglob('*') if p.is_file()))
            self.assertTrue(original_catalog.ready(rows,archive))
            del rows['https://bg.izzi.digital/_nuxt/app.js']
            self.assertIsNone(original_catalog.ready(rows,archive))

    def test_local_adaptation_preserves_router_host_and_removes_tracking(self):
        source=b't.domain==window.location.host;x={}[window.location.hostname];r.i18n.defaultLocale=We.j;window.location.host.split(".")'
        result=original_catalog.adapt_script(source).decode()
        self.assertIn('defaultLocale="bg"',result);self.assertIn('window.location.host.split',result)
        html=original_catalog.inject('<html><head><script src="https://example.test/delivery/cmp.js"></script></head></html>')
        self.assertNotIn('cmp.js',html);self.assertIn('/__ui__/original.js',html)

if __name__=='__main__':unittest.main()
