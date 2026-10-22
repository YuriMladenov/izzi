"""Fixed GitHub fast-forward updates and native Windows startup setup."""
import ast,base64,ctypes,hashlib,json,os,subprocess,sys,threading
from collections import deque
from pathlib import Path,PurePosixPath
ROOT=Path(__file__).resolve().parent
REMOTE='https://github.com/YuriMladenov/izzi.git'
PROTECTED={'archive','state','capture','captures','.git','.venv'}

def git(root,*args,check=True,timeout=120):
    env={**os.environ,'GIT_TERMINAL_PROMPT':'0','GCM_INTERACTIVE':'never'}
    try:
        result=subprocess.run(['git','-C',str(root),*args],capture_output=True,text=True,
            encoding='utf8',errors='replace',timeout=timeout,env=env,
            **({'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {}))
    except FileNotFoundError:raise ValueError('Git не е инсталиран или не е в PATH.') from None
    if check and result.returncode:raise ValueError(result.stderr.strip() or result.stdout.strip() or 'Git command failed')
    return result

def require_idle():
    import operations,video_resume
    if operations.capture_port_busy():raise ValueError('Спри capture преди обновяване.')
    if any(job['state']=='running' for job in operations.tasks.snapshot().values()):raise ValueError('Изчакай проверките и фоновите задачи да приключат.')
    if video_resume.jobs.snapshot()['state']=='running':raise ValueError('Спри изтеглянето на видеа преди обновяване.')

def update(root=ROOT,log=lambda message:None,idle=require_idle):
    root=Path(root).resolve();idle()
    if Path(git(root,'rev-parse','--show-toplevel').stdout.strip()).resolve()!=root:raise ValueError('Папката на проекта не е корен на Git checkout.')
    origin=git(root,'remote','get-url','origin').stdout.strip()
    if origin.rstrip('/') not in (REMOTE,REMOTE.removesuffix('.git')):raise ValueError('Обновяването е разрешено само от YuriMladenov/izzi в GitHub.')
    branch=git(root,'branch','--show-current').stdout.strip()
    if branch not in ('main','WebUI'):raise ValueError('Обновяването изисква клон main или WebUI.')
    if git(root,'status','--porcelain','--untracked-files=normal').stdout.strip():raise ValueError('Има локални промени. Запази ги преди обновяване; няма да бъдат презаписани.')
    old=git(root,'rev-parse','HEAD').stdout.strip();log('Проверка на GitHub: '+branch)
    git(root,'fetch','--no-tags','origin',branch)
    target=git(root,'rev-parse','FETCH_HEAD').stdout.strip()
    if old==target:log('Проектът вече е актуален.');return {'before':old,'after':target,'changed':False}
    if git(root,'merge-base','--is-ancestor',old,target,check=False).returncode:raise ValueError('Клоновете са се разделили. Нужна е ръчна проверка; няма направени промени по кода.')
    changed=[name for name in git(root,'diff','--name-only','--no-renames','-z',old,target).stdout.split('\0') if name]
    for name in changed:
        parts=PurePosixPath(name.replace('\\','/').casefold()).parts
        if not parts or parts[0] in PROTECTED or parts[:2] in (('vendor','geogebra'),('vendor','geogebra-backups')):raise ValueError('Обновяването засяга защитена папка: '+name)
        if name.startswith('requirements') or name=='docker/Dockerfile':raise ValueError('Има промяна на зависимости или Docker образа. Обнови инсталацията ръчно; кодът не е променен.')
    # Parse new Python sources before any running code is changed.
    files=set(git(root,'ls-tree','-r','--name-only','-z',target).stdout.split('\0'))
    for name in changed:
        if name.endswith('.py') and name in files:
            ast.parse(git(root,'show',target+':'+name).stdout,filename=name)
    idle()
    if git(root,'rev-parse','HEAD').stdout.strip()!=old or git(root,'status','--porcelain').stdout.strip():raise ValueError('Локалният проект е променен по време на проверката. Повтори обновяването.')
    log('Прилагане на '+old[:8]+' → '+target[:8])
    git(root,'merge','--ff-only',target)
    log('Кодът е обновен. Рестартирай библиотеката, за да се зареди новата версия.')
    return {'before':old,'after':target,'changed':True}

class UpdateJob:
    def __init__(self):
        self.lock=threading.RLock();self.state='idle';self.lines=deque(maxlen=100);self.result=None
    def snapshot(self):
        with self.lock:return {'state':self.state,'log':'\n'.join(self.lines),'result':self.result}
    def log(self,message):
        with self.lock:self.lines.append(str(message)[:2000])
    def start(self):
        with self.lock:
            if self.state=='running':raise ValueError('Обновяването вече работи.')
            self.state='running';self.lines.clear();self.result=None
        threading.Thread(target=self.run,daemon=True).start()
    def run(self):
        try:
            result=update(log=self.log)
            with self.lock:self.result=result;self.state='success'
        except Exception as error:
            self.log(str(error))
            with self.lock:self.state='failed'

updates=UpdateJob()

def windows_account():
    if os.name!='nt':return ''
    size=ctypes.c_ulong(0);ctypes.windll.secur32.GetUserNameExW(2,None,ctypes.byref(size))
    value=ctypes.create_unicode_buffer(size.value)
    if not ctypes.windll.secur32.GetUserNameExW(2,value,ctypes.byref(size)):raise OSError('Не може да се прочете Windows потребителят.')
    return value.value

def task_name(root=ROOT):return 'IZZI Library '+hashlib.sha256(str(Path(root).resolve()).casefold().encode()).hexdigest()[:10]

def psquote(value):return "'"+str(value).replace("'","''")+"'"

def launch_startup_setup(root=ROOT):
    if os.name!='nt':raise ValueError('Windows Task Scheduler е достъпен само на Windows сървър.')
    root=Path(root).resolve();account=windows_account()
    if account.upper().startswith(('NT AUTHORITY\\','NT SERVICE\\')):raise ValueError('Стартирай библиотеката под своя Windows потребител, за да създадеш задачата.')
    script=root/'tools/register_startup.ps1'
    command='& '+psquote(script)+' -ProjectRoot '+psquote(root)+' -PythonExe '+psquote(sys.executable)+' -Account '+psquote(account)+' -TaskName '+psquote(task_name(root))
    encoded=base64.b64encode(command.encode('utf-16le')).decode()
    elevated="Start-Process -FilePath 'powershell.exe' -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-EncodedCommand',"+psquote(encoded)+") -Verb RunAs -WindowStyle Hidden"
    result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-EncodedCommand',base64.b64encode(elevated.encode('utf-16le')).decode()],capture_output=True,text=True,timeout=90,creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:raise ValueError('Системният прозорец за настройване не беше стартиран или UAC беше отказан.')
    return {'message':'Потвърди UAC и въведи Windows паролата в системния прозорец. След това обнови статуса.','account':account,'task':task_name(root)}

def startup_status(state):
    path=Path(state)/'startup_task_result.json'
    try:return json.loads(path.read_text(encoding='utf8-sig'))
    except (OSError,ValueError):return None
