"""One local-library administrator; password hashes on disk, bounded sessions in RAM."""
import argparse,hashlib,hmac,json,os,re,secrets,tempfile,threading,time
from http.cookies import SimpleCookie,CookieError
from pathlib import Path

COOKIE='izzi_admin'
NONCE_COOKIE='izzi_admin_form'
SESSION_TTL=8*3600
NONCE_TTL=600
class LoginThrottled(ValueError):pass

class AdminAccount:
    def __init__(self,state):
        self.path=Path(state)/'admin_account.json';self.lock=threading.RLock()
        self.sessions={};self.nonces={};self.attempts={};self.global_attempts=[]
        # Initialize once; never replace a customized account on restart/update.
        if not self.path.exists():self.set_account('admin','izzi',local=True)
    def record(self):
        try:record=json.loads(self.path.read_text(encoding='utf8'))
        except FileNotFoundError:return None
        if (not isinstance(record,dict) or record.get('version')!=1 or not isinstance(record.get('username'),str) or not re.fullmatch(r'[A-Za-z0-9_.@-]{3,64}',record.get('username',''))
            or not re.fullmatch(r'[a-f0-9]{32}',str(record.get('salt','')))
            or not re.fullmatch(r'[a-f0-9]{64}',str(record.get('password_hash','')))
            or not re.fullmatch(r'[a-f0-9]{32}',str(record.get('generation','')))):
            raise ValueError('Admin account configuration is invalid')
        return record
    @staticmethod
    def digest(password,salt):
        return hashlib.scrypt(password.encode('utf8'),salt=bytes.fromhex(salt),n=16384,r=8,p=1,dklen=32).hex()
    @staticmethod
    def valid_authority(authority):
        return bool(re.fullmatch(r'(?:[A-Za-z0-9.-]+|\[[a-fA-F0-9:]+\])(?::[0-9]{1,5})?',authority or ''))
    @staticmethod
    def cookie_value(header,name):
        if not header or len(header)>8192:return ''
        try:
            cookies=SimpleCookie();cookies.load(header)
            return cookies[name].value if name in cookies else ''
        except CookieError:return ''
    @staticmethod
    def key(token):return hashlib.sha256(token.encode()).hexdigest()
    def session(self,header,authority):
        token=self.cookie_value(header,COOKIE)
        if not re.fullmatch(r'[A-Za-z0-9_-]{43}',token) or not self.valid_authority(authority):return None
        with self.lock:
            key=self.key(token);item=self.sessions.get(key)
            if not item:return None
            try:record=self.record()
            except (OSError,ValueError):record=None
            if (not record or item['expires']<=time.monotonic() or item['generation']!=record['generation']
                or item['authority']!=authority.lower()):
                self.sessions.pop(key,None);return None
            return dict(item)
    def nonce(self,authority,purpose):
        if not self.valid_authority(authority):raise ValueError('Invalid host')
        with self.lock:
            now=time.monotonic();self.nonces={key:item for key,item in self.nonces.items() if item['expires']>now}
            while len(self.nonces)>=1024:self.nonces.pop(next(iter(self.nonces)))
            token=secrets.token_urlsafe(32)
            self.nonces[self.key(token)]={'authority':authority.lower(),'purpose':purpose,'expires':now+NONCE_TTL}
            return token
    def consume_nonce(self,header,token,authority,purpose):
        cookie=self.cookie_value(header,NONCE_COOKIE)
        if not isinstance(token,str) or not re.fullmatch(r'[A-Za-z0-9_-]{43}',token) or not hmac.compare_digest(cookie.encode('utf8'),token.encode('ascii')):return False
        with self.lock:
            item=self.nonces.pop(self.key(token),None)
            return bool(item and item['expires']>time.monotonic() and item['authority']==authority.lower() and item['purpose']==purpose)
    def login(self,username,password,peer,authority):
        if not self.valid_authority(authority) or len(password.encode('utf8'))>1024:return None
        with self.lock:
            now=time.monotonic()
            self.attempts={key:[t for t in values if t>now-300] for key,values in self.attempts.items() if any(t>now-300 for t in values)}
            self.global_attempts=[t for t in self.global_attempts if t>now-300]
            if len(self.attempts.get(peer,[]))>=5 or len(self.global_attempts)>=30:raise LoginThrottled('Опитай отново след 5 минути.')
            self.attempts.setdefault(peer,[]).append(now);self.global_attempts.append(now)
            record=self.record()
        # Derive even for the wrong username, with the same work factor.
        salt=record['salt'] if record else '00'*16
        derived=self.digest(password,salt)
        if not record or not hmac.compare_digest(derived,record['password_hash']) or not hmac.compare_digest(username.encode('utf8'),record['username'].encode('utf8')):return None
        with self.lock:
            current=self.record()
            if not current or current['generation']!=record['generation']:return None
            self.sessions={key:item for key,item in self.sessions.items() if item['expires']>now}
            while len(self.sessions)>=128:self.sessions.pop(next(iter(self.sessions)))
            token=secrets.token_urlsafe(32)
            self.sessions[self.key(token)]={'username':record['username'],'generation':record['generation'],'expires':now+SESSION_TTL,'authority':authority.lower()}
            return token
    def logout(self,header):
        token=self.cookie_value(header,COOKIE)
        with self.lock:self.sessions.pop(self.key(token),None)
    def set_account(self,username,password,local=False,current_password=''):
        username=username.strip()
        if not re.fullmatch(r'[A-Za-z0-9_.@-]{3,64}',username):raise ValueError('Името трябва да съдържа 3–64 латински букви, цифри или _.@-.')
        if len(password)<4 or len(password.encode('utf8'))>1024:raise ValueError('Паролата трябва да съдържа поне 4 знака и до 1024 UTF-8 байта.')
        with self.lock:
            try:old=self.record()
            except ValueError:
                if not local:raise
                old=None
            if not local and (not old or not hmac.compare_digest(self.digest(current_password,old['salt']),old['password_hash'])):
                raise ValueError('Текущата парола е неправилна.')
            salt=secrets.token_hex(16)
            record={'version':1,'username':username,'salt':salt,'password_hash':self.digest(password,salt),'generation':secrets.token_hex(16)}
            self.path.parent.mkdir(parents=True,exist_ok=True)
            fd,name=tempfile.mkstemp(prefix='.admin-account-',dir=self.path.parent)
            try:
                with os.fdopen(fd,'w',encoding='utf8') as stream:
                    json.dump(record,stream,ensure_ascii=False,indent=2);stream.flush();os.fsync(stream.fileno())
                os.replace(name,self.path)
            finally:Path(name).unlink(missing_ok=True)
            self.sessions.clear();self.nonces.clear()

MANAGERS={};MANAGER_LOCK=threading.Lock()
def manager(state):
    key=Path(state).resolve()
    with MANAGER_LOCK:
        if key not in MANAGERS:MANAGERS[key]=AdminAccount(key)
        return MANAGERS[key]

def cookie(name,value,max_age,secure=False):
    item=SimpleCookie();item[name]=value
    item[name]['path']='/__admin__/' if name==NONCE_COOKIE else '/'
    item[name]['httponly']=True;item[name]['samesite']='Strict';item[name]['max-age']=max_age
    if secure:item[name]['secure']=True
    return item.output(header='').strip()

def main():
    from getpass import getpass
    from config import STATE_DIR
    parser=argparse.ArgumentParser(description='Create/reset the local library admin account. Password is requested privately.')
    parser.add_argument('--username',default='admin');args=parser.parse_args()
    password=getpass('New password (at least 4 characters): ')
    if password!=getpass('Repeat password: '):raise ValueError('Passwords do not match')
    manager(STATE_DIR).set_account(args.username,password,local=True)
    print('Admin account saved. Existing sessions have been revoked.')
if __name__=='__main__':
    try:main()
    except (OSError,ValueError) as error:raise SystemExit(str(error))
