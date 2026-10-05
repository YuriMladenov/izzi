"""Offline HTML shell for the library's existing routes."""
import html,re
from pathlib import Path
ASSETS=Path(__file__).with_name('webui')
def page(content,title='Библиотека',active='library',search=False):
    content=re.sub(r'<!doctype[^>]*>|<meta[^>]*>|<link[^>]*>|<title>.*?</title>','',content,flags=re.I|re.S)
    links=[('library','/','Библиотека','▤'),('missing','/__missing__','Липсващи ресурси','↧'),('journal','/__journal__','Локален журнал','◷'),('help','/__help__','Как да използвам','?')]
    nav=''.join('<a href="%s" %s><span aria-hidden="true">%s</span>%s</a>'%(url,'aria-current="page"' if key==active else '',icon,label) for key,url,label,icon in links)
    searchbox='<div class="searchbar"><label for="ui-search">Търсене в списъка</label><input id="ui-search" type="search" placeholder="Въведи име, ID или адрес…" autocomplete="off"><span id="ui-count" role="status"></span></div><p id="ui-no-results" hidden>Няма съвпадения. Опитай с друго име или ID.</p>' if search else ''
    return ('<!doctype html><html lang="bg"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="icon" href="data:,"><title>'+html.escape(title)+' · IZZI Library</title><link rel="stylesheet" href="/__ui__/app.css"><script src="/__ui__/app.js" defer></script></head><body><aside class="sidebar"><a class="brand" href="/"><span class="brand-mark">i</span><span>IZZI<span class="brand-sub">OFFLINE LIBRARY</span></span></a><nav aria-label="Основна навигация">'+nav+'</nav><div class="sidebar-note"><span class="dot"></span> Локална библиотека<small>Твоето съдържание, на едно място.</small></div></aside><main><header class="topbar"><span>Работно пространство / '+html.escape(title)+'</span><a href="/__help__">Помощ ↗</a></header><div class="content">'+searchbox+content+'</div><footer>IZZI Offline Library · Съдържанието се предоставя от твоя локален архив.</footer></main></body></html>')
