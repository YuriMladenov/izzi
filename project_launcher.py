"""Keep the server's restart operation usable on Windows and in containers."""
import os,signal,subprocess,sys
from pathlib import Path

def main():
    root=Path(__file__).resolve().parent
    env={**os.environ,'IZZI_MANAGED_LAUNCH':'1','PYTHONUNBUFFERED':'1','PYTHONUTF8':'1'}
    # Old scheduled tasks may still pass --capture; startup is now library-only.
    env.pop('IZZI_START_CAPTURE',None)
    stopping=False;child=None
    def stop(signum,frame):
        nonlocal stopping
        stopping=True
        if child and child.poll() is None:
            try:child.send_signal(signal.CTRL_BREAK_EVENT if os.name=='nt' else signal.SIGINT)
            except OSError:pass
    signal.signal(signal.SIGINT,stop);signal.signal(signal.SIGTERM,stop)
    if os.name=='nt':signal.signal(signal.SIGBREAK,stop)
    while not stopping:
        kwargs={'creationflags':subprocess.CREATE_NEW_PROCESS_GROUP} if os.name=='nt' else {'start_new_session':True}
        child=subprocess.Popen([sys.executable,'-u',str(root/'server.py')],cwd=root,env=env,**kwargs)
        code=child.wait()
        if stopping:return 0
        if code!=75:return code
    return 0

if __name__=='__main__':sys.exit(main())
