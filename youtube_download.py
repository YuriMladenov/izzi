"""Optional YouTube downloads; only validated single-video IDs are accepted."""
import atexit,html,json,os,re,shutil,signal,subprocess,sys,threading,tempfile
from importlib import metadata,util
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
        result=JOBS.get(identifier)
        if result is None:
            saved=load(STATE_DIR/'youtube'/(identifier+'.json'),{})
            result={'state':'failed','error':saved['error'],'available':False} if saved.get('state')=='failed' else {'state':'missing','available':False}
        return dict(result)

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
                    env={**os.environ,'PYTHONUTF8':'1','PYTHONIOENCODING':'utf-8'},
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

def diagnose():
    result={'python':sys.executable,'runtimes':{}}
    try:result['yt_dlp']=metadata.version('yt-dlp')
    except metadata.PackageNotFoundError:result['yt_dlp']=None
    result['ejs']=util.find_spec('yt_dlp_ejs') is not None
    for name,args,minimum in (('deno',['--version'],(2,3,0)),('node',['--version'],(22,0,0)),('ffmpeg',['-version'],(0,))):
        path=shutil.which(name);entry={'path':path,'supported':False}
        if path:
            try:
                process=subprocess.run([path,*args],capture_output=True,timeout=10)
                line=process.stdout.decode('utf-8',errors='replace').splitlines()[0]
                match=re.search(r'(\d+)\.(\d+)(?:\.(\d+))?',line)
                version=tuple(int(x or 0) for x in match.groups()) if match else ()
                entry.update(version=line,supported=process.returncode==0 and (name=='ffmpeg' or version>=minimum))
            except (OSError,subprocess.TimeoutExpired,IndexError):pass
        result['runtimes'][name]=entry
    return result

def download(identifier):
    output=STATE_DIR/'youtube'/(identifier+'.json')
    try:
        try:from yt_dlp import YoutubeDL
        except ImportError:raise ValueError('Липсва yt-dlp. Изпълни install_youtube.bat.')
        setup=diagnose()
        if not setup['ejs']:raise ValueError('Липсва yt-dlp-ejs. Изпълни install_youtube.bat в Python средата на capture.')
        runtimes={name:{'path':entry['path']} for name,entry in setup['runtimes'].items() if name in ('deno','node') and entry['supported']}
        if not runtimes:raise ValueError('Нужен е Deno 2.3+ или Node.js 22+. Виж install_youtube.bat и рестартирай capture след инсталацията.')
        target=ARCHIVE_DIR/'youtube';target.mkdir(parents=True,exist_ok=True)
        ffmpeg=setup['runtimes']['ffmpeg']['supported']
        def limit(data):
            if data.get('downloaded_bytes',0)>250*1024*1024:raise ValueError('Видеото надвишава лимита от 250 MiB.')
        options={'js_runtimes':runtimes,'noplaylist':True,'cachedir':False,'socket_timeout':30,'retries':2,'max_filesize':250*1024*1024,'progress_hooks':[limit],
            'format':'bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]/best[ext=mp4][height<=720][acodec!=none][vcodec!=none]' if ffmpeg else 'best[ext=mp4][height<=720][acodec!=none][vcodec!=none]', 'merge_output_format':'mp4'}
        if ffmpeg:options['ffmpeg_location']=setup['runtimes']['ffmpeg']['path']
        # Publish only the finished merge. A crash must never expose its partial
        # MP4 under the final name, or delete an older valid archived video.
        with tempfile.TemporaryDirectory(prefix='.'+identifier+'-',dir=target) as staging:
            options['outtmpl']=str(Path(staging)/(identifier+'.%(ext)s'))
            with YoutubeDL(options) as client:info=client.extract_info('https://www.youtube.com/watch?v='+identifier,download=True)
            video=Path(staging)/(identifier+'.mp4')
            if not video.is_file() or video.stat().st_size<=16:raise ValueError('Няма годен MP4 файл. Инсталирай FFmpeg за комбиниране на видео и звук.')
            with video.open('rb') as stream:valid=b'ftyp' in stream.read(16)
            if not valid:raise ValueError('Изтегленият файл не е MP4.')
            if video.stat().st_size>250*1024*1024:raise ValueError('Видеото надвишава лимита от 250 MiB.')
            os.replace(video,target/(identifier+'.mp4'))
        save(output,{'state':'ready','title':info.get('title',''),'id':identifier});return 0
    except Exception as error:
        save(output,{'state':'failed','error':str(error),'id':identifier});return 1
if __name__=='__main__':
    if sys.argv[1:]==['--diagnose']:
        print(json.dumps(diagnose(),indent=2));raise SystemExit(0)
    identifier=sys.argv[1] if len(sys.argv)==2 else ''
    if not re.fullmatch(r'[A-Za-z0-9_-]{11}',identifier):raise SystemExit('Invalid video ID')
    raise SystemExit(download(identifier))
