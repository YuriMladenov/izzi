import json
from pathlib import Path
from urllib.parse import urlparse
from config import *
def load(p,d):
    try:return json.loads(Path(p).read_text(encoding="utf-8"))
    except:return d
m=load(URL_MAP_FILE,{});b=load(BOOKS_FILE,{});im=load(IMPORTS_FILE,[])
fonts=[u for u in m if Path(urlparse(u).path).suffix.lower() in {".woff",".woff2",".ttf",".otf",".eot"}]
print("Books:",len(b))
for bid,x in b.items():print(" ",bid,"-",x.get("title"),"- lessons:",len(x.get("lessons",{})))
print("Unique URLs:",len(m));print("Fonts captured:",len(fonts));print("HAR imports:",len(im))
