import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import *
from import_har import load
from urllib.parse import urlparse
from pathlib import Path
m=load(URL_MAP_FILE,{})
books=load(BOOKS_FILE,{})
c={"images":0,"media":0,"documents":0,"fonts":0,"ranges":0,"decoded_v32":0,"complete_mp4":0}
for u,rs in m.items():
    e=Path(urlparse(u).path).suffix.lower()
    if e in {".jpg",".jpeg",".png",".gif",".svg",".webp"}:c["images"]+=1
    elif e in {".mp4",".webm",".mp3",".ogg",".wav",".m4a"}:c["media"]+=1
    elif e in {".pdf",".doc",".docx",".ppt",".pptx",".xls",".xlsx",".zip"}:c["documents"]+=1
    elif e in {".woff",".woff2",".ttf",".otf",".eot"}:c["fonts"]+=1
    c["ranges"]+=sum(1 for r in rs if r.get("status")==206)
    c["decoded_v32"]+=sum(1 for r in rs if r.get("source")=="capture_proxy_v3.2" and r.get("decoded"))
    c["complete_mp4"]+=sum(1 for r in rs if r.get("complete"))
print("IZZI v3.2 Capture Report")
print("Books:",len(books));print("Lessons:",sum(len(x.get("lessons",{})) for x in books.values()))
for k,v in c.items():print(k.replace("_"," ").title()+":",v)
