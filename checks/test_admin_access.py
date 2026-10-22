"""LAN administration authentication on isolated temporary archives."""
import http.client
import json
import re
import sys
import unittest
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import urlencode
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import admin_account
import server
import test_library_workflow as fixtures

class AdminAccess(unittest.TestCase):
    setUp=fixtures.LibraryWorkflow.setUp
    tearDown=fixtures.LibraryWorkflow.tearDown
    stop_server=fixtures.LibraryWorkflow.stop_server
    def start(self):
        self.state.joinpath('books.json').write_text('{}')
        self.state.joinpath('url_map.json').write_text('{}')
        fixtures.LibraryWorkflow.start_server(self)
    def request(self,path,form=None,cookie='',host='192.168.1.20',origin=None,method=None):
        connection=http.client.HTTPConnection('127.0.0.1',self.httpd.server_port,timeout=5)
        headers={'Host':host,'Cookie':cookie}
        if form is not None:headers['Content-Type']='application/x-www-form-urlencoded'
        if origin:headers['Origin']=origin
        connection.request(method or ('POST' if form is not None else 'GET'),path,urlencode(form) if form is not None else None,headers)
        response=connection.getresponse();result=response.status,dict(response.getheaders()),response.read().decode('utf8')
        connection.close();return result
    def form(self,purpose,cookie='',host='192.168.1.20'):
        status,headers,body=self.request('/__admin__/'+purpose,cookie=cookie,host=host)
        self.assertEqual(200,status)
        nonce=re.search(r'name="csrf" value="([^"]+)"',body).group(1)
        return nonce,'; '.join(filter(None,[cookie,headers['Set-Cookie'].split(';')[0]]))
    def login(self,password='izzi'):
        nonce,cookie=self.form('login')
        return self.request('/__admin__/login',{'csrf':nonce,'username':'admin','password':password},cookie)
    def test_default_account_and_access_boundaries(self):
        self.start()
        status,_,body=self.request('/')
        self.assertEqual(200,status);self.assertIn('/__admin__/login',body);self.assertNotIn('<details',body)
        self.assertEqual(200,self.request('/__operations__',host='localhost')[0])
        self.assertEqual(403,self.request('/__operations__')[0])
        self.assertEqual(403,self.request('/__admin__/account',{'username':'admin','password':'evil'})[0])
        status,headers,_=self.login();self.assertEqual(303,status)
        self.assertIn('HttpOnly',headers['Set-Cookie']);self.assertIn('SameSite=Strict',headers['Set-Cookie'])
        cookie=headers['Set-Cookie'].split(';')[0]
        for path in ['/','/__operations__','/__missing__','/__journal__','/__cleanup__','/__videos__']:
            status,_,body=self.request(path,cookie=cookie);self.assertEqual(200,status,path)
        self.assertIn('<details',self.request('/',cookie=cookie)[2])
        self.assertEqual(403,self.request('/__operations__',cookie=cookie,host='other.local')[0])
        record=json.loads((self.state/'admin_account.json').read_text(encoding='utf8'))
        self.assertNotIn('password',record);self.assertNotIn('izzi',record.values())
    def test_video_page_opens_without_synchronous_archive_scan(self):
        self.start()
        with patch('video_resume.inspect',side_effect=AssertionError('Page must defer archive inspection')):
            status,_,body=self.request('/__videos__',host='localhost')
        self.assertEqual(200,status)
        self.assertIn('data-video="all" disabled',body)
        self.assertIn('/__ui__/videos.js',body)
        self.assertIn('Проверка на архива',body)
    def test_csrf_wrong_credentials_and_logout(self):
        self.start()
        self.assertEqual(401,self.login('wrong')[0])
        nonce,cookie=self.form('login')
        fields={'csrf':nonce,'username':'admin','password':'izzi'}
        self.assertEqual(403,self.request('/__admin__/login',fields,cookie,origin='http://evil.example')[0])
        self.assertEqual(403,self.request('/__admin__/login',fields)[0])
        status,headers,_=self.request('/__admin__/login',fields,cookie);self.assertEqual(303,status)
        self.assertEqual(403,self.request('/__admin__/login',fields,cookie)[0])
        session=headers['Set-Cookie'].split(';')[0]
        nonce,cookie=self.form('logout',session)
        self.assertEqual(200,self.request('/__operations__',cookie=session)[0])
        self.assertEqual(303,self.request('/__admin__/logout',{'csrf':nonce},cookie)[0])
        self.assertEqual(403,self.request('/__operations__',cookie=session)[0])
        self.assertEqual(200,self.request('/__operations__',host='localhost')[0])
    def test_password_change_requires_current_password_and_revokes_sessions(self):
        self.start();_,headers,_=self.login();session=headers['Set-Cookie'].split(';')[0]
        nonce,cookie=self.form('account',session)
        fields={'csrf':nonce,'username':'admin','password':'new password','confirm':'new password','current_password':'wrong'}
        self.assertEqual(400,self.request('/__admin__/account',fields,cookie)[0])
        nonce,cookie=self.form('account',session);fields.update(csrf=nonce,current_password='izzi')
        self.assertEqual(303,self.request('/__admin__/account',fields,cookie)[0])
        self.assertEqual(403,self.request('/__operations__',cookie=session)[0])
        self.assertEqual(401,self.login()[0]);self.assertEqual(303,self.login('new password')[0])
        # Recreating a server-side manager preserves credentials, never resets to izzi.
        account=admin_account.AdminAccount(self.state)
        self.assertIsNone(account.login('admin','izzi','test','host'))
        self.assertIsNotNone(account.login('admin','new password','test','host'))
    def test_session_expiry_restart_rate_limit_and_local_reset(self):
        account=admin_account.AdminAccount(self.state)
        token=account.login('admin','izzi','test','host');cookie=admin_account.COOKIE+'='+token
        self.assertIsNotNone(account.session(cookie,'host'))
        with patch.object(admin_account.time,'monotonic',return_value=account.sessions[account.key(token)]['expires']+1):
            self.assertIsNone(account.session(cookie,'host'))
        self.assertIsNone(admin_account.AdminAccount(self.state).session(cookie,'host'))
        for _ in range(5):self.assertIsNone(account.login('admin','wrong','attacker','host'))
        with self.assertRaises(admin_account.LoginThrottled):account.login('admin','izzi','attacker','host')
        account.set_account('admin','reset password',local=True)
        self.assertIsNotNone(account.login('admin','reset password','owner','host'))
    def test_lan_catalog_write_requires_session_token_and_same_origin(self):
        self.start()
        self.state.joinpath('books.json').write_text(json.dumps({'1':{'title':'Book','lessons':{'2':{'title':'Lesson','path':'/DOS/1/2.html'}}}}))
        fields={'name_2':'Renamed','token':server.operations.tasks.token}
        self.assertEqual(403,self.request('/__catalog__/1',fields)[0])
        _,headers,_=self.login();session=headers['Set-Cookie'].split(';')[0]
        self.assertEqual(403,self.request('/__catalog__/1',{'name_2':'Renamed'},session)[0])
        self.assertEqual(403,self.request('/__catalog__/1',fields,session,origin='http://evil.example')[0])
        self.assertEqual(303,self.request('/__catalog__/1',fields,session,origin='http://192.168.1.20')[0])
        self.assertIn('Renamed',self.request('/__book__/1',cookie=session)[2])

    def test_auth_write_methods_do_not_enter_progress_journal(self):
        self.start()
        for method in ('PUT','PATCH','DELETE'):
            self.assertEqual(405,self.request('/__admin__/login',{'password':'private'},method=method)[0])
        self.assertFalse((self.state/'progress').exists())

    def maintenance_request(self,action,cookie='',token='',origin=None,host='192.168.1.20'):
        connection=http.client.HTTPConnection('127.0.0.1',self.httpd.server_port,timeout=5)
        headers={'Host':host,'Cookie':cookie,'Content-Type':'application/json','X-IZZI-Control':token}
        if origin:headers['Origin']=origin
        connection.request('POST','/__maintenance__/action',json.dumps({'action':action}),headers)
        response=connection.getresponse();result=response.status,response.read();connection.close();return result
    def test_maintenance_requires_administrator_token_and_same_origin(self):
        self.start()
        self.assertEqual(403,self.request('/__maintenance__')[0]);self.assertEqual(403,self.request('/__maintenance__/status')[0])
        _,headers,_=self.login();cookie=headers['Set-Cookie'].split(';')[0];token=server.operations.tasks.token
        self.assertEqual(200,self.request('/__maintenance__',cookie=cookie)[0])
        with patch.object(server.project_maintenance.updates,'start') as start:
            self.assertEqual(403,self.maintenance_request('update',cookie)[0])
            self.assertEqual(403,self.maintenance_request('update',cookie,token,origin='http://evil.example')[0])
            self.assertEqual(403,self.maintenance_request('update',token=token)[0]);start.assert_not_called()
            self.assertEqual(200,self.maintenance_request('update',cookie,token,origin='http://192.168.1.20')[0]);start.assert_called_once()
        with patch.object(server.project_maintenance,'launch_startup_setup') as setup:
            self.assertEqual(403,self.maintenance_request('startup',cookie,token)[0]);setup.assert_not_called()
        with patch.dict(server.os.environ,{'IZZI_MANAGED_LAUNCH':'0'}):
            self.assertEqual(400,self.maintenance_request('restart',cookie,token)[0])
        self.assertEqual(400,self.maintenance_request('arbitrary-command',cookie,token)[0])
        self.assertEqual(405,self.request('/__maintenance__/action',{'action':'update'},method='PUT')[0])
        self.assertFalse((self.state/'progress').exists())

if __name__=='__main__':unittest.main()
