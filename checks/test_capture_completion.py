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
    def test_optional_missing_and_pending_resources_warn_without_blocking(self):
        optional='https://bg.izzi.digital/app.js.map'
        completion.watch(optional,'GET',self.lesson,'optional');self.settled()
        result=completion.status(self.lesson,[],self.mapping,self.archive)
        self.assertTrue(result['available']);self.assertEqual([],result['pending'])
        self.assertEqual(optional,result['warnings'][0]['url'])
        self.assertEqual('warning',result['warnings'][0]['severity'])
        required='https://bg.izzi.digital/exercise.js'
        result=completion.status(self.lesson,[required],self.mapping,self.archive)
        self.assertFalse(result['available']);self.assertEqual(required,result['missing'][0]['url'])
        self.add(optional,b'{"version":3}')
        self.assertEqual([],completion.status(self.lesson,[],self.mapping,self.archive)['warnings'])

    def test_linked_apps_share_optional_policy_but_root_is_required(self):
        import external_links
        optional='https://example.org/app.js.map';script='https://example.org/exercise.js'
        entry={'resources':[self.lesson,optional]}
        with patch.object(external_links,'state',return_value={'data':{self.lesson:entry}}):
            result=external_links.status(self.lesson,self.mapping,self.archive)
            self.assertTrue(result['available']);self.assertEqual(optional,result['warnings'][0]['url'])
            entry['resources'].append(script)
            self.assertEqual([script],external_links.status(self.lesson,self.mapping,self.archive)['missing'])
        with patch.object(external_links,'state',return_value={'data':{}}):
            self.assertFalse(external_links.status(optional,self.mapping,self.archive)['available'])
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
    def test_bundled_fonts_and_mathlive_sound_work_in_capture_for_all_books(self):
        import bundled_assets
        paths=['components/fonts/KaTeX_'+name+'.woff' for name in ('AMS-Regular','Main-Regular','Math-Italic')]+['components/js/sounds/plonk.wav']
        for book in ('887348','777'):
            for path in paths:
                url='https://bg.izzi.digital/DOS/'+book+'/'+path
                self.add(url,b'<html>origin missing</html>',404)
                flow=SimpleNamespace(id=url,metadata={},request=http.Request.make('GET',url,headers={'Referer':self.lesson}),response=None)
                with patch.object(capture_addon,'load_json',return_value=self.mapping),patch.object(capture_addon,'ARCHIVE_DIR',self.archive),patch.object(capture_addon,'update_entry') as update:
                    capture_addon.request(flow)
                    self.assertEqual(200,flow.response.status_code)
                    self.assertEqual(bundled_assets.asset('bg.izzi.digital','/DOS/'+book+'/'+path).read_bytes(),flow.response.content)
                    capture_addon.response(flow);update.assert_not_called()
                    status=SimpleNamespace(request=http.Request.make('GET','https://bg.izzi.digital/__offline_capture__/image_status?url='+url),response=None)
                    capture_addon.request(status)
                    self.assertTrue(json.loads(status.response.content)['available'])
                self.assertEqual(404,self.mapping[url][0]['status'])
        self.settled()
        self.assertTrue(completion.status(self.lesson,list(self.mapping),self.mapping,self.archive)['available'])
        missing='https://bg.izzi.digital/DOS/777/components/fonts/KaTeX_Unknown.woff'
        self.assertFalse(completion.status(self.lesson,[missing],self.mapping,self.archive)['available'])
        self.assertIsNone(bundled_assets.asset('outside.example','/DOS/777/components/js/sounds/plonk.wav'))
        self.assertIsNone(bundled_assets.asset('bg.izzi.digital','/DOS/777/components/js/sounds/../plonk.wav'))

    def test_post_background_requests_old_lesson_and_analytics_are_excluded(self):
        self.assertFalse(completion.watch('https://bg.izzi.digital/api/sync','POST',self.lesson,'write'))
        self.assertFalse(completion.watch('https://api.izzi.digital/api/data','GET','https://bg.izzi.digital/DOS/2/9.html','other'))
        self.assertFalse(completion.watch('https://www.google-analytics.com/log','GET',self.lesson,'analytics'))
        self.settled();self.assertTrue(completion.status(self.lesson,[],self.mapping,self.archive)['available'])
        self.assertFalse(completion.status('https://bg.izzi.digital/DOS/1/9.html',[],self.mapping,self.archive)['tracked'])
        with self.assertRaises(ValueError):completion.status(self.lesson,['x']*(completion.LIMIT+1),self.mapping,self.archive)
    def test_declared_api_app_is_tracked_with_an_origin_only_referer(self):
        app='https://api.izzi.digital/datastore/blocks/657825/index.html'
        script='https://api.izzi.digital/datastore/blocks/657825/variables.js'
        self.assertFalse(completion.watch(app,'GET','https://bg.izzi.digital/','unrelated'))
        self.assertFalse(completion.expect(app,'https://bg.izzi.digital/DOS/2/9.html'))
        from urllib.parse import urlencode
        control=SimpleNamespace(request=http.Request.make('GET','https://bg.izzi.digital/__offline_capture__/event?'+urlencode({'kind':'link-register','url':self.lesson,'asset':app})),response=None)
        with patch.object(capture_addon.external_links,'register') as register,patch.object(capture_addon,'event'):
            capture_addon.request(control)
            register.assert_called_once_with(app)
        self.assertEqual(204,control.response.status_code)
        self.assertIn(app,completion.CURRENT['urls'])
        self.assertTrue(completion.watch(app+'?__izzi_offline_recover=retry','GET','https://bg.izzi.digital/','app'))
        self.assertTrue(completion.watch(script,'GET',app,'script'))
        self.add(app,b'<html>app</html>');self.add(script,b'window.test=true;')
        completion.finish('app');self.settled()
        self.assertFalse(completion.status(self.lesson,[],self.mapping,self.archive)['available'])
        completion.finish('script');self.settled()
        self.assertTrue(completion.status(self.lesson,[],self.mapping,self.archive)['available'])

    def test_failed_datastore_assets_retry_api_and_wait_for_usable_archive(self):
        import external_links
        source='https://bg.izzi.digital/DOS/888413/datastore/blocks/657825/jquery-3.2.1.min.js'
        target='https://api.izzi.digital/datastore/blocks/657825/jquery-3.2.1.min.js'
        app=source.rsplit('/',1)[0]+'/index.html'
        self.add(app,b'<html>app</html>')
        completion.expect(app,self.lesson)
        completion.watch(source,'GET',app,'original')
        flow=SimpleNamespace(id='original',request=http.Request.make('GET',source,headers={'Referer':app}),response=http.Response.make(503,b'origin unavailable',{'Content-Type':'text/plain'}))
        def committed(path,key,mutate,default):mutate(self.mapping.setdefault(key,default))
        with patch.multiple(capture_addon,ARCHIVE_DIR=self.archive,STATE_DIR=self.archive,URL_MAP_FILE=self.archive/'url_map.json'),patch.object(capture_addon,'observe'),patch.object(capture_addon,'update_entry',side_effect=committed),patch.multiple(external_links,FILE=self.archive/'links.json',INDEX=None):
            external_links.register(app);external_links.associate(source,app)
            capture_addon.response(flow)
            self.assertEqual(503,self.mapping[source][0]['status'],'preserve the real origin error')
            self.assertEqual(307,flow.response.status_code)
            self.assertEqual(target,flow.response.headers['Location'])
            self.assertIn(target,completion.CURRENT['urls'])
            self.assertTrue(completion.watch(target,'GET','https://bg.izzi.digital/','api'))
            self.settled();self.assertFalse(completion.status(self.lesson,[],self.mapping,self.archive)['available'])
            flow=SimpleNamespace(id='api',request=http.Request.make('GET',target),response=http.Response.make(200,b'window.recovered=true;',{'Content-Type':'application/javascript'}))
            capture_addon.response(flow)
            self.settled();self.assertTrue(completion.status(self.lesson,[],self.mapping,self.archive)['available'])
            self.assertTrue(external_links.status(app,self.mapping,self.archive)['available'])

    def test_picture_retry_requires_real_api_image_and_keeps_origin_error(self):
        import base64,external_links
        source='https://bg.izzi.digital/datastore/15/publication/449863/pictures/2023/01/03/0b8e656a120a406585bf71e1bccb5dc0_extracted.png'
        target=source.replace('bg.izzi.digital','api.izzi.digital')
        completion.watch(source,'GET',self.lesson,'original-image')
        flow=SimpleNamespace(id='original-image',request=http.Request.make('GET',source,headers={'Referer':self.lesson}),response=http.Response.make(404,b'<html>not found</html>',{'Content-Type':'text/html'}))
        def committed(path,key,mutate,default):mutate(self.mapping.setdefault(key,default))
        with patch.multiple(capture_addon,ARCHIVE_DIR=self.archive,STATE_DIR=self.archive,URL_MAP_FILE=self.archive/'url_map.json'),patch.object(capture_addon,'observe'),patch.object(capture_addon,'update_entry',side_effect=committed),patch.multiple(external_links,FILE=self.archive/'links.json',INDEX=None):
            capture_addon.response(flow)
            self.assertEqual(404,self.mapping[source][0]['status'])
            self.assertEqual(307,flow.response.status_code)
            self.assertEqual(target,flow.response.headers['Location'])
            self.assertTrue(completion.watch(target,'GET','https://bg.izzi.digital/','api-image'))
            self.settled();self.assertFalse(completion.status(self.lesson,[],self.mapping,self.archive)['available'])
            # Even HTTP 200 must not let a login/error HTML page stand in for a PNG.
            api=SimpleNamespace(id='api-image',request=http.Request.make('GET',target),response=http.Response.make(200,b'<html>login</html>',{'Content-Type':'text/html'}))
            capture_addon.response(api)
            self.settled();self.assertFalse(completion.status(self.lesson,[],self.mapping,self.archive)['available'])
            png=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aS1cAAAAASUVORK5CYII=')
            self.assertTrue(completion.watch(target,'GET','https://bg.izzi.digital/','api-retry'))
            api=SimpleNamespace(id='api-retry',request=http.Request.make('GET',target),response=http.Response.make(200,png,{'Content-Type':'image/png'}))
            capture_addon.response(api)
            self.settled();self.assertTrue(completion.status(self.lesson,[],self.mapping,self.archive)['available'])
            self.assertEqual(404,self.mapping[source][0]['status'])

    def test_empty_datastore_address_warns_but_real_files_remain_required(self):
        from resource_policy import optional_reason
        placeholders=['https://bg.izzi.digital/DOS/449863/datastore/','https://bg.izzi.digital/datastore/','https://api.izzi.digital/datastore/']
        for index,url in enumerate(placeholders):
            self.assertTrue(optional_reason(url))
            completion.watch(url,'GET',self.lesson,'placeholder-'+str(index))
        self.settled();result=completion.status(self.lesson,[],self.mapping,self.archive)
        self.assertTrue(result['available']);self.assertEqual(3,len(result['warnings']))
        required='https://bg.izzi.digital/datastore/15/publication/449863/pictures/missing.png'
        self.assertFalse(optional_reason(required))
        self.assertFalse(optional_reason('https://other.example/DOS/449863/datastore/'))
        result=completion.status(self.lesson,[required],self.mapping,self.archive)
        self.assertFalse(result['available']);self.assertEqual([required],[row['url'] for row in result['missing']])

    def test_datastore_fallback_scope_and_api_failure_are_not_hidden(self):
        paths=['/datastore/blocks/657825/GeoGebra/deployggb.js','/DOS/888413/datastore/blocks/657825/assets/style.css','/DOS/9/datastore/blocks/657825/images/loading-icon.gif','/datastore/15/publication/30521/files/2021/01/11/1610382881_b7_u5_lin_ur.ggb',
            '/datastore/15/publication/449863/pictures/2023/01/03/0b8e656a120a406585bf71e1bccb5dc0_extracted.png',
            '/DOS/449863/datastore/15/publication/449863/pictures/example.PNG',
            '/datastore/15/shared/pictures/example.svg']
        for path in paths:
            source='https://bg.izzi.digital'+path+'?v=2&__izzi_offline_recover=test'
            target=capture_addon.datastore_fallback_url(source)
            self.assertTrue(target.startswith('https://api.izzi.digital/datastore/'))
            self.assertTrue(target.endswith('?v=2&__izzi_offline_recover=test'))
        for source in ['https://evil.example/datastore/blocks/1/a.js','https://bg.izzi.digital/api/login','https://bg.izzi.digital/datastore/blocks/1/%2e%2e/api','https://bg.izzi.digital/datastore/blocks/1/a%5cb','https://bg.izzi.digital/datastore/15/publication/1/files/test.exe',
            'https://bg.izzi.digital/datastore/15/publication/1/pictures/test.js',
            'https://bg.izzi.digital/datastore/15/publication/1/pictures/%2e%2e/other.png',
            'https://bg.izzi.digital/DOS/449863/datastore/']:
            self.assertIsNone(capture_addon.datastore_fallback_url(source))
        url='https://bg.izzi.digital/datastore/blocks/657825/variables.js'
        with patch.object(capture_addon.external_links,'associate'):
            for method,status,url in [('GET',200,url),('GET',403,url),('POST',404,url),('GET',404,'https://api.izzi.digital/datastore/blocks/657825/variables.js')]:
                flow=SimpleNamespace(request=http.Request.make(method,url),response=http.Response.make(status,b'original'))
                capture_addon.recover_datastore_response(flow)
                self.assertEqual(status,flow.response.status_code)
                self.assertEqual(b'original',flow.response.content)
        api='https://api.izzi.digital/datastore/blocks/657825/variables.js'
        self.add(api,b'unavailable',503);completion.expect(api,self.lesson);self.settled()
        self.assertFalse(completion.status(self.lesson,[],self.mapping,self.archive)['available'])

    def test_api_queries_do_not_use_another_cached_response(self):
        other='https://api.izzi.digital/api/info?id=2';wanted='https://api.izzi.digital/api/info?id=1'
        self.add(other,b'{}');self.settled()
        self.assertFalse(completion.status(self.lesson,[wanted],self.mapping,self.archive)['available'])
        self.add(wanted,b'{}')
        self.assertTrue(completion.status(self.lesson,[wanted],self.mapping,self.archive)['available'])
    def test_exact_asset_confirmation_does_not_accept_another_host_alias(self):
        from urllib.parse import urlencode
        bg='https://bg.izzi.digital/DOS/888413/datastore/blocks/657825/index.html'
        api='https://api.izzi.digital/datastore/blocks/657825/index.html'
        self.add(bg,b'<html>old app</html>')
        def confirmed(exact):
            query=urlencode({'url':api,**({'exact':'1'} if exact else {})})
            flow=SimpleNamespace(request=http.Request.make('GET','https://bg.izzi.digital/__offline_capture__/image_status?'+query),response=None)
            with patch.object(capture_addon,'load_json',return_value=self.mapping),patch.object(capture_addon,'ARCHIVE_DIR',self.archive):capture_addon.request(flow)
            return json.loads(flow.response.content)['available']
        self.assertTrue(confirmed(False));self.assertFalse(confirmed(True))
        self.add(api,b'<html>origin missing</html>',404)
        self.assertFalse(confirmed(True))
        self.add(api,b'<html>real API app</html>')
        self.assertTrue(confirmed(True))

    def test_proxy_serves_current_runtime_without_upstream_or_archive(self):
        url='https://bg.izzi.digital/__offline_capture__/book_capture.js?t=123'
        flow=SimpleNamespace(request=http.Request.make('GET',url),response=None)
        with patch.object(capture_addon,'load_json',side_effect=AssertionError('Runtime must not scan archive')):
            capture_addon.request(flow)
        self.assertEqual(200,flow.response.status_code)
        self.assertEqual('no-store',flow.response.headers['Cache-Control'])
        self.assertEqual('nosniff',flow.response.headers['X-Content-Type-Options'])
        self.assertEqual(Path(capture_addon.__file__).with_name('capture_book_runtime.js').read_bytes(),flow.response.content)
        flow.request=http.Request.make('POST',url);flow.response=None;capture_addon.request(flow)
        self.assertEqual(405,flow.response.status_code)
        flow.request=http.Request.make('GET',url);flow.response=None
        with patch.object(Path,'read_bytes',side_effect=FileNotFoundError):capture_addon.request(flow)
        self.assertEqual(503,flow.response.status_code)

    def test_proxy_status_endpoint_confirms_archive_and_rejects_invalid_request(self):
        flow=SimpleNamespace(request=http.Request.make('POST','https://bg.izzi.digital/__offline_capture__/lesson_status',content=json.dumps({'lesson':self.lesson,'assets':[]}).encode()),response=None)
        self.settled()
        with patch.object(capture_addon,'load_json',return_value=self.mapping),patch.object(capture_addon,'ARCHIVE_DIR',self.archive):capture_addon.request(flow)
        self.assertEqual(200,flow.response.status_code);self.assertTrue(json.loads(flow.response.content)['available'])
        flow.request.content=b'not-json';flow.response=None;capture_addon.request(flow)
        self.assertEqual(503,flow.response.status_code)
if __name__=='__main__':unittest.main()
