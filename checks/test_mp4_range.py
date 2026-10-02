import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sys, urllib.request, urllib.error
url=sys.argv[1] if len(sys.argv)>1 else input("Paste LOCAL MP4 URL (http://127.0.0.1:8765/...mp4?...): ").strip()
if not url:
    raise SystemExit("No URL")
req=urllib.request.Request(url,headers={"Range":"bytes=0-1023"})
try:
    with urllib.request.urlopen(req) as r:
        body=r.read()
        print("Status:",r.status)
        print("Content-Type:",r.headers.get("Content-Type"))
        print("Accept-Ranges:",r.headers.get("Accept-Ranges"))
        print("Content-Range:",r.headers.get("Content-Range"))
        print("Content-Length:",r.headers.get("Content-Length"))
        print("X-IZZI-Replay:",r.headers.get("X-IZZI-Replay"))
        print("Received:",len(body),"bytes")
        ok=(r.status==206 and (r.headers.get("Content-Type") or "").lower().startswith("video/mp4")
            and r.headers.get("Content-Range","").startswith("bytes 0-1023/") and len(body)==1024)
        print("RESULT:","PASS" if ok else "FAIL")
        raise SystemExit(not ok)
except urllib.error.HTTPError as e:
    print("HTTP ERROR:",e.code,e.read().decode("utf-8","replace"))
    raise SystemExit(1)
