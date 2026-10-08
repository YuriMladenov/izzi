"""Offline HTML shell for the library's existing routes."""
import html,re
from pathlib import Path
ASSETS=Path(__file__).with_name('webui')
def page(content,title='Библиотека',active='library',search=False,catalog=False):
    content=re.sub(r'<!doctype[^>]*>|<meta[^>]*>|<link[^>]*>|<title>.*?</title>','',content,flags=re.I|re.S)
    links=[('library','/','Библиотека','▤'),('missing','/__missing__','Липсващи ресурси','↧'),('journal','/__journal__','Локален журнал','◷'),('operations','/__operations__','Capture и проверки','▷'),('help','/__help__','Как да използвам','?')]
    nav=''.join('<a href="%s" %s><span aria-hidden="true">%s</span>%s</a>'%(url,'aria-current="page"' if key==active else '',icon,label) for key,url,label,icon in links)
    searchbox='<div class="searchbar"><label for="ui-search">Търсене в списъка</label><input id="ui-search" type="search" placeholder="Въведи име, ID или адрес…" autocomplete="off"><span id="ui-count" role="status"></span></div><p id="ui-no-results" hidden>Няма съвпадения. Опитай с друго име или ID.</p>' if search else ''
    if catalog:
        menu='<details class="library-menu"><summary>☰ <span>Меню</span></summary><nav aria-label="Основна навигация">'+nav+'</nav></details>'
        if search:
            searchbox=searchbox.replace('Търсене в списъка','Търсене на учебник').replace('Въведи име, ID или адрес…','Име на учебник или ID…')
        return ('<!doctype html><html lang="bg"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="icon" href="data:,"><title>'+html.escape(title)+' · IZZI Library</title><link rel="stylesheet" href="/__ui__/app.css"><script src="/__ui__/app.js" defer></script></head><body class="catalog-home"><header class="catalog-header"><a class="catalog-logo" href="/" aria-label="IZZI — Библиотека">izzi</a>'+menu+'</header><main id="main-content"><div class="content"><h1>Библиотека</h1>'+searchbox+content+'</div></main></body></html>')
    return ('<!doctype html><html lang="bg"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="icon" href="data:,"><title>'+html.escape(title)+' · IZZI Library</title><link rel="stylesheet" href="/__ui__/app.css"><script src="/__ui__/app.js" defer></script></head><body><aside class="sidebar"><a class="brand" href="/"><span class="brand-mark">i</span><span>IZZI<span class="brand-sub">OFFLINE LIBRARY</span></span></a><nav aria-label="Основна навигация">'+nav+'</nav><div class="sidebar-note"><span class="dot"></span> Локална библиотека<small>Твоето съдържание, на едно място.</small></div></aside><main><header class="topbar"><span>Работно пространство / '+html.escape(title)+'</span><a href="/__help__">Помощ ↗</a></header><div class="content">'+searchbox+content+'</div><footer>IZZI Offline Library · Съдържанието се предоставя от твоя локален архив.</footer></main></body></html>')


def book_card(book_id,title,cover=''):
    bid=html.escape(str(book_id),quote=True)
    title=html.escape(str(title))
    icon='<span class="cover-placeholder" aria-hidden="true"><svg viewBox="0 0 48 60" width="40" height="50"><rect x="5" y="4" width="36" height="50" rx="3" fill="none" stroke="currentColor" stroke-width="2"/><path d="M12 4v50M19 19h15M19 26h12" fill="none" stroke="currentColor" stroke-width="2"/></svg></span>'
    image='<img class="original-cover" src="'+html.escape(cover,quote=True)+'" alt="" loading="lazy" width="108" height="140">' if cover else ''
    return ('<li data-search-item class="catalog-book"><a class="book-open" href="/__book__/'+bid+'">'
            '<div class="book-thumbnail'+('' if cover else ' no-cover')+'">'+image+icon+'</div>'
            '<h3>'+title+'</h3><small>ID '+bid+'</small></a></li>')
