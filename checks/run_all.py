"""Run checks independently, preserve failures and clean up our replay server."""
import argparse
import subprocess
import sys
import threading
import urllib.request
from pathlib import Path
from http.server import ThreadingHTTPServer
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
SYNTHETIC=['test_media_contract','validate_replay','test_library_workflow','test_replay_html','test_original_catalog']
REPORTS=['inspect_library','inspect_blobs','replay_map_diagnostic','replay_self_test','capture_report','capture_session_report','fresh_capture_report','recovery_report','media_map_report','media_replay_check','assembled_media_report','asset_diagnostic','font_diagnostic','lesson_diagnostic','book_readiness_report','final_readiness_report','missing_assets_report','progress_report']

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--synthetic-only',action='store_true',help='Only isolated tests; no private archive checks')
    args=parser.parse_args()
    results=[];owned=None;thread=None
    def run(name,extra=()):
        print('\n=== '+name+' ===',flush=True)
        try:
            result=subprocess.run([sys.executable,str(Path(__file__).with_name(name+'.py')),*extra],cwd=ROOT,stdin=subprocess.DEVNULL,timeout=600)
            status='OK' if result.returncode==0 else 'FAILED'
        except (OSError,subprocess.TimeoutExpired) as error:
            print(type(error).__name__,flush=True);status='FAILED'
        results.append((name,status))
    try:
        for name in SYNTHETIC:run(name)
        if not args.synthetic_only:
            for name in REPORTS:run(name)
            import config
            import server
            base=f'http://{config.CLIENT_HOST}:{config.PORT}'
            try:
                owned=ThreadingHTTPServer((config.HOST,config.PORT),server.H)
                thread=threading.Thread(target=owned.serve_forever,daemon=True);thread.start()
                available=True
                print('\nTemporary replay server started for HTTP checks.',flush=True)
            except OSError:
                try:
                    with urllib.request.urlopen(base+'/',timeout=5) as response:
                        available=b'IZZI Offline Library' in response.read(65536)
                except Exception:available=False
            if available:
                run('local_replay_smoke_test');run('test_all_assembled')
                from assembled_media import build_index
                from urllib.parse import urlparse
                exact,_=build_index()
                if exact:
                    url=urlparse(next(iter(exact)))
                    local=base+url.path+('?' + url.query if url.query else '')
                    run('test_mp4_range',[local])
                else:results.append(('test_mp4_range','SKIPPED: no complete MP4'))
            else:
                for name in ['local_replay_smoke_test','test_all_assembled','test_mp4_range']:
                    results.append((name,'FAILED: replay port unavailable'))
    finally:
        if owned:
            owned.shutdown();owned.server_close();thread.join()
    print('\n=== SUMMARY ===',flush=True)
    for name,status in results:print(status,name)
    failed=sum(status.startswith('FAILED') for _,status in results)
    skipped=sum(status.startswith('SKIPPED') for _,status in results)
    print(f'{len(results)-failed-skipped} completed successfully; {failed} failed; {skipped} skipped.')
    print('OK reports mean the script completed; read their counters and warnings.')
    return int(bool(failed))
if __name__=='__main__':raise SystemExit(main())
