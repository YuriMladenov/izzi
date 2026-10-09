"""Fixed local tasks; no arbitrary commands or shell execution."""
import atexit,os,re,secrets,shutil,signal,socket,subprocess,sys,sysconfig,threading
from collections import deque
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def capture_port_busy():
    from config import CAPTURE_PROXY_PORT
    with socket.socket() as probe:
        try:probe.bind(('127.0.0.1',CAPTURE_PROXY_PORT))
        except OSError:return True
    return False

def find_mitmdump():
    filename='mitmdump.exe' if os.name=='nt' else 'mitmdump'
    candidates=[Path(sys.executable).parent/filename,
                Path(sys.executable).parent/'Scripts'/filename,
                Path(sysconfig.get_path('scripts'))/filename]
    try:
        scheme='nt_user' if os.name=='nt' else 'posix_user'
        candidates.append(Path(sysconfig.get_path('scripts',scheme=scheme))/filename)
    except (KeyError,TypeError):pass
    for candidate in candidates:
        if candidate.is_file():return str(candidate)
    executable=shutil.which('mitmdump')
    if executable:return executable
    # Windows launcher lists other Python installations even when Scripts is absent from PATH.
    launcher=shutil.which('py') if os.name=='nt' else None
    if launcher:
        try:
            listing=subprocess.run([launcher,'-0p'],capture_output=True,text=True,timeout=5)
            for line in listing.stdout.splitlines()[:20]:
                match=re.search(r'([A-Za-z]:\\.*python(?:w)?\.exe)\s*$',line,re.I)
                if match:
                    candidate=Path(match[1]).parent/'Scripts'/filename
                    if candidate.is_file():return str(candidate)
        except (OSError,subprocess.TimeoutExpired):pass
    raise ValueError('mitmdump не е намерен в Python Scripts или PATH. Изпълни install_capture.bat и рестартирай библиотеката.')

class Tasks:
    def __init__(self):
        self.token=secrets.token_urlsafe(32);self.lock=threading.RLock();self.jobs={}
    def command(self,name):
        if name=='checks':return [sys.executable,'-u',str(ROOT/'checks/run_all.py')]
        if name!='capture':raise ValueError('Unknown task')
        from config import CAPTURE_PROXY_PORT
        if capture_port_busy():
            raise ValueError(f'Порт {CAPTURE_PROXY_PORT} вече е зает. Ако capture_mode.bat работи, използвай него; спри го в неговия прозорец, преди да стартираш capture от WebUI.')
        executable=find_mitmdump()
        return [executable,'--listen-host','127.0.0.1','-p',str(CAPTURE_PROXY_PORT),'-s',str(ROOT/'capture_addon.py')]
    def start(self,name,command=None):
        if name not in ('capture','checks'):raise ValueError('Unknown task')
        with self.lock:
            previous=self.jobs.get(name)
            if previous and previous['process'].poll() is None:raise ValueError('Задачата вече работи.')
            kwargs={'creationflags':subprocess.CREATE_NEW_PROCESS_GROUP} if os.name=='nt' else {'start_new_session':True}
            process=subprocess.Popen(command or self.command(name),cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,text=True,encoding='utf-8',errors='replace',env={**os.environ,'PYTHONUNBUFFERED':'1','PYTHONIOENCODING':'utf-8'},**kwargs)
            job={'process':process,'lines':deque(maxlen=500),'stopped':False};self.jobs[name]=job
            threading.Thread(target=self.read,args=(job,),daemon=True).start()
    def read(self,job):
        try:
            with job['process'].stdout as stream:
                for line in stream:
                    with self.lock:job['lines'].append(line.rstrip()[:4000])
        finally:job['process'].wait()
    def stop(self,name):
        if name not in ('capture','checks'):raise ValueError('Unknown task')
        with self.lock:
            job=self.jobs.get(name)
            if not job or job['process'].poll() is not None:return
            process=job['process'];job['stopped']=True
        try:
            if os.name=='nt':process.send_signal(signal.CTRL_BREAK_EVENT)
            else:os.killpg(process.pid,signal.SIGINT)
            process.wait(timeout=5)
        except (ProcessLookupError,OSError,subprocess.TimeoutExpired):
            if process.poll() is None:
                if os.name=='nt':subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=10)
                else:os.killpg(process.pid,signal.SIGKILL)
                process.wait(timeout=5)
    def snapshot(self):
        with self.lock:
            result={}
            for name in ('capture','checks'):
                job=self.jobs.get(name)
                if not job or (name=='capture' and job['process'].poll() is not None):
                    if name=='capture' and capture_port_busy():
                        result[name]={'state':'external','exit_code':None,'log':'Capture портът е зает от процес извън WebUI. Ако capture_mode.bat работи, записването може да продължи. Спри го от неговия прозорец; WebUI не управлява този процес.'}
                        continue
                    if not job:result[name]={'state':'idle','exit_code':None,'log':''};continue
                code=job['process'].poll()
                state='running' if code is None else ('stopped' if job['stopped'] else ('success' if code==0 else 'failed'))
                result[name]={'state':state,'exit_code':code,'log':'\n'.join(job['lines'])}
            return result
    def close(self):
        for name in ('capture','checks'):self.stop(name)
tasks=Tasks()
atexit.register(tasks.close)
