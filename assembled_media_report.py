from assembled_media import build_index
from urllib.parse import urlparse
exact,paths=build_index()
print("IZZI v3.2.3 Assembled Media Resolver")
print("Verified complete MP4 URLs:",len(exact))
print("Unique host+path mappings:",len(paths))
for u,item in sorted(exact.items()):
    r=item["record"]
    print("\n[COMPLETE]",r.get("size"),"bytes",r.get("source"))
    print(" ",u)
    print(" ->",r.get("key"))
