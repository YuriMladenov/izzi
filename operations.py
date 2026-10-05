"""Fixed local tasks; no arbitrary commands or shell execution."""
import atexit,os,secrets,shutil,signal,socket,subprocess,sys,threading
from collections import deque
from pathlib import Path
ROOT=Path(__file__).resolve().parent
class Tasks:
    def __init__(self):
        self.token=secrets.token_urlsafe(32);self.lock=threading.RLock();self.jobs={}
    def command(self,name):
        if name=='checks':return [sys.executable,'-u',str(ROOT/'checks/run_all.py')]
        if name!='capture':raise ValueError('Unknown task')
        executable=Path(sys.executable).parent/('mitmdump.exe' if os.name=='nt' else 'mitmdump')
        executable=str(executable) if executable.exists() else shutil.which('mitmdump')
        if not executable:raise ValueError('mitmdump липсва. Изпълни install_capture.bat.')
        from config import CAPTURE_PROXY_PORT
        with socket.socket() as probe:
            try:probe.bind(('127.0.0.1',CAPTURE_PROXY_PORT))
            except OSError:raise ValueError('Capture портът е зает. Провери за вече стартиран proxy.')
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
                if not job:result[name]={'state':'idle','exit_code':None,'log':''};continue
                code=job['process'].poll()
                state='running' if code is None else ('stopped' if job['stopped'] else ('success' if code==0 else 'failed'))
                result[name]={'state':state,'exit_code':code,'log':'\n'.join(job['lines'])}
            return result
    def close(self):
        for name in ('capture','checks'):self.stop(name)
tasks=Tasks()
atexit.register(tasks.close)
