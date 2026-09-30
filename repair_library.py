import json,re
from pathlib import Path
from urllib.parse import urlparse
from config import *
from import_har import load,save,metadata

RX=re.compile(r"^/DOS/(\d+)/(\d+)\.html$")

def main():
    mapping=load(URL_MAP_FILE,{})
    old_books=load(BOOKS_FILE,{})
    books={}
    repaired=0
    for url,records in mapping.items():
        p=urlparse(url)
        if p.netloc!=SOURCE_HOST:continue
        m=RX.match(p.path)
        if not m:continue
        usable=[r for r in records if r.get("body_available") and r.get("key")]
        if not usable:continue
        r=usable[-1]
        f=ARCHIVE_DIR/r["key"]
        if not f.exists():continue
        bid,lid=m.groups()
        book_title,lesson_title=metadata(f.read_bytes(),bid,lid)
        b=books.setdefault(bid,{"id":bid,"title":book_title,"lessons":{}})
        if b["title"].startswith("Учебник ") and not book_title.startswith("Учебник "):
            b["title"]=book_title
        b["lessons"][lid]={"id":lid,"path":p.path,"title":lesson_title}
        repaired+=1

    # Keep books/lessons that cannot currently be reconstructed.
    for bid,ob in old_books.items():
        b=books.setdefault(bid,ob)
        for lid,lesson in ob.get("lessons",{}).items():
            b.setdefault("lessons",{}).setdefault(lid,lesson)

    save(BOOKS_FILE,books)
    print("Books repaired:",len(books))
    print("Lessons rebuilt:",repaired)
    for bid,b in sorted(books.items()):
        print(f'  {bid}: {b.get("title")} ({len(b.get("lessons",{}))} lessons)')

if __name__=="__main__":
    main()
