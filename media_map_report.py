from media_mapping import load
x=load(); lessons=x.get("lessons",{})
print("IZZI v3.2.2 Media Source Mapping")
print("Lessons with media:",len(lessons))
for k,e in sorted(lessons.items()):
    print(f"\n[{k}] {len(e.get('media',[]))} media")
    for i,r in enumerate(e.get("media",[]),1):
        print(f" {i}. blocks={','.join(r.get('blocks',[])) or '-'}")
        print("   ",r.get("url"))
