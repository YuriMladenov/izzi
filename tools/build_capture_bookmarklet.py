"""Build the self-contained Firefox bookmarklet from its readable helpers."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
path=root/'auto_book_capture_bookmarklet.txt'
source=path.read_text(encoding='utf8')
legacy="const loadLesson=u=>new Promise(resolve=>{let done=false,timer;const finish=()=>{if(done)return;done=true;clearTimeout(timer);setTimeout(resolve,10000);};timer=setTimeout(finish,22000);f.onload=finish;f.src=u.href;});"
source=source.replace(legacy,"const loadLesson=u=>captureLoadLesson(f,u);")
if "f.id='izzi-offline-capture-frame'" not in source:
    source=source.replace("const f=document.createElement('iframe');Object.assign", "const f=document.createElement('iframe');f.id='izzi-offline-capture-frame';Object.assign")
    source=source.replace("globalThis.__IZZI_CAPTURE_ACTIVE__=false;})()", "document.getElementById('izzi-offline-capture-frame')?.remove();globalThis.__IZZI_CAPTURE_ACTIVE__=false;})()")
    source=source.replace("document.getElementById('izzi-offline-lesson-picker')?.remove();console.error", "document.getElementById('izzi-offline-lesson-picker')?.remove();document.getElementById('izzi-offline-capture-frame')?.remove();console.error")
for name,file in [('NAV','capture_navigation.js'),('LINKS','capture_links.js'),('RESOURCES','capture_resources.js'),('STRICT','capture_strict.js')]:
    start,end=f'/*IZZI_{name}_START*/',f'/*IZZI_{name}_END*/'
    prefix,remainder=source.split(start,1);_,suffix=remainder.split(end,1)
    helper=''.join((root/file).read_text(encoding='utf8').splitlines())
    source=prefix+start+helper+end+suffix
path.write_text(''.join(source.splitlines())+'\n',encoding='utf8',newline='\n')
