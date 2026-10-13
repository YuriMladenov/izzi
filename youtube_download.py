"""Optional YouTube downloads; only validated single-video IDs are accepted."""
import atexit,html,json,os,re,shutil,signal,subprocess,sys,threading
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
from config import ARCHIVE_DIR,STATE_DIR
from import_har import load,save
LOCK=threading.RLock();QUEUE=threading.Semaphore(1);JOBS={};PROCESSES={}

def video_id(value):
    if re.fullmatch(r'[A-Za-z0-9_-]{11}',value or ''):return value
    try:
        p=urlsplit(html.unescape(value).replace('\\/','/'));host=p.hostname or ''
        if host not in ('youtube.com','www.youtube.com','m.youtube.com','youtube-nocookie.com','www.youtube-nocookie.com','youtu.be','www.youtu.be'):return None
        candidate=(p.path.strip('/').split('/')[0] if 'youtu.be' in host else parse_qs(p.query).get('v',[''])[0] if p.path=='/watch' else p.path.strip('/').split('/')[-1] if p.path.startswith(('/embed/','/shorts/','/live/')) else '')
        return candidate if re.fullmatch(r'[A-Za-z0-9_-]{11}',candidate) else None
    except ValueError:return None

def local_file(identifier):
    if not video_id(identifier) or len(identifier)!=11:return None
    for ext in ('.mp4','.webm'):
        path=ARCHIVE_DIR/'youtube'/(identifier+ext)
        if path.is_file() and path.stat().st_size>16:
            with path.open('rb') as f:header=f.read(16)
            if (ext=='.mp4' and b'ftyp' in header) or (ext=='.webm' and header.startswith(b'\x1aE\xdf\xa3')):return path
    return None

def status(identifier,start=False):
    if not re.fullmatch(r'[A-Za-z0-9_-]{11}',identifier or ''):return {'state':'failed','error':'Invalid YouTube ID','available':False}
    if local_file(identifier):return {'state':'ready','available':True}
    with LOCK:
        if start and JOBS.get(identifier,{}).get('state') not in ('queued','running'):
            JOBS[identifier]={'state':'queued','available':False}
            threading.Thread(target=worker,args=(identifier,),daemon=True).start()
        return dict(JOBS.get(identifier,{'state':'missing','available':False}))

def terminate(process):
    if process.poll() is not None:return
    if os.name=='nt':subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=10)
    else:os.killpg(process.pid,signal.SIGTERM)

def worker(identifier):
    with QUEUE:
        with LOCK:JOBS[identifier]={'state':'running','available':False}
        logs=STATE_DIR/'youtube';logs.mkdir(parents=True,exist_ok=True)
        outcome=logs/(identifier+'.json');outcome.unlink(missing_ok=True)
        try:
            with (logs/(identifier+'.log')).open('w',encoding='utf8') as log:
                process=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),identifier],stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name=='nt' else 0,start_new_session=os.name!='nt')
                with LOCK:PROCESSES[identifier]=process
                try:process.wait(timeout=900)
                except subprocess.TimeoutExpired:terminate(process);process.wait(timeout=10);raise ValueError('Изтеглянето надвиши 15 минути.')
            result=load(outcome,{})
            if process.returncode or not local_file(identifier):raise ValueError(result.get('error','Изтеглянето е неуспешно. Виж state/youtube/'+identifier+'.log.'))
            with LOCK:JOBS[identifier]={'state':'ready','available':True}
        except Exception as error:
            with LOCK:JOBS[identifier]={'state':'failed','available':False,'error':str(error)}
        finally:
            with LOCK:PROCESSES.pop(identifier,None)

def close():
    for process in list(PROCESSES.values()):
        try:terminate(process)
        except (OSError,subprocess.TimeoutExpired):pass
atexit.register(close)

def download(identifier):
    output=STATE_DIR/'youtube'/(identifier+'.json')
    try:
        try:from yt_dlp import YoutubeDL
        except ImportError:raise ValueError('Липсва yt-dlp. Изпълни install_youtube.bat.')
        if not shutil.which('deno') and not shutil.which('node'):raise ValueError('Нужен е Deno или актуален Node.js за YouTube. Виж install_youtube.bat.')
        target=ARCHIVE_DIR/'youtube';target.mkdir(parents=True,exist_ok=True)
        ffmpeg=bool(shutil.which('ffmpeg'))
        def limit(data):
            if data.get('downloaded_bytes',0)>250*1024*1024:raise ValueError('Видеото надвишава лимита от 250 MiB.')
        options={'js_runtimes':{'deno':{},'node':{}},'outtmpl':str(target/(identifier+'.%(ext)s')),'noplaylist':True,'cachedir':False,'socket_timeout':30,'retries':2,'max_filesize':250*1024*1024,'progress_hooks':[limit],
            'format':'bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]/best[ext=mp4][height<=720][acodec!=none][vcodec!=none]' if ffmpeg else 'best[ext=mp4][height<=720][acodec!=none][vcodec!=none]', 'merge_output_format':'mp4'}
        with YoutubeDL(options) as client:info=client.extract_info('https://www.youtube.com/watch?v='+identifier,download=True)
        video=local_file(identifier)
        if video and video.stat().st_size>250*1024*1024:
            video.unlink();raise ValueError('Видеото надвишава лимита от 250 MiB.')
        if not video:raise ValueError('Няма годен MP4 файл. Инсталирай FFmpeg за комбиниране на видео и звук.')
        save(output,{'state':'ready','title':info.get('title',''),'id':identifier});return 0
    except Exception as error:
        save(output,{'state':'failed','error':str(error),'id':identifier});return 1
if __name__=='__main__':
    identifier=sys.argv[1] if len(sys.argv)==2 else ''
    if not re.fullmatch(r'[A-Za-z0-9_-]{11}',identifier):raise SystemExit('Invalid video ID')
    raise SystemExit(download(identifier))
