"""Build the self-contained Firefox bookmarklet from its readable helpers."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
path=root/'auto_book_capture_bookmarklet.txt'
source=path.read_text(encoding='utf8')
for name,file in [('NAV','capture_navigation.js'),('LINKS','capture_links.js'),('RESOURCES','capture_resources.js'),('STRICT','capture_strict.js')]:
    start,end=f'/*IZZI_{name}_START*/',f'/*IZZI_{name}_END*/'
    prefix,remainder=source.split(start,1);_,suffix=remainder.split(end,1)
    helper=''.join((root/file).read_text(encoding='utf8').splitlines())
    source=prefix+start+helper+end+suffix
path.write_text(''.join(source.splitlines())+'\n',encoding='utf8')
