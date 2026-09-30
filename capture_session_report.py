from capture_session import load
x=load()
print("IZZI v3.3 Capture Session")
for v in x.get("visits",[]):
    print(v.get("time"),v.get("kind"),v.get("book") or "-",v.get("lesson") or "-",v.get("url") or "")
