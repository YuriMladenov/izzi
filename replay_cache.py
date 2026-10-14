"""Bounded cache of rewritten static responses, keyed by source file identity."""
import hashlib,threading
from collections import OrderedDict

LOCK=threading.Lock()
ITEMS=OrderedDict()
BUILDING={}
BYTES=0
LIMIT=32*1024*1024

def prepared(path,context,build):
    global BYTES
    stat=path.stat()
    key=(str(path.resolve()),stat.st_ino,stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns,context)
    while True:
        with LOCK:
            value=ITEMS.get(key)
            if value is not None:ITEMS.move_to_end(key);return value
            event=BUILDING.get(key)
            if event is None:
                event=BUILDING[key]=threading.Event();break
        # Only duplicate requests for this file wait for its first rewrite.
        event.wait()
    # Disk reads and rewriting must never serialize unrelated HTTP requests.
    try:
        data=build()
        value=(data,'"'+hashlib.sha256(data).hexdigest()+'"')
        if len(data)<=LIMIT:
            with LOCK:
                old=ITEMS.pop(key,None)
                if old:BYTES-=len(old[0])
                ITEMS[key]=value;BYTES+=len(data)
                while BYTES>LIMIT or len(ITEMS)>256:
                    _,removed=ITEMS.popitem(last=False);BYTES-=len(removed[0])
        return value
    finally:
        with LOCK:
            BUILDING.pop(key,None);event.set()
