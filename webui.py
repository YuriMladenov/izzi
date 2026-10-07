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
        return ('<!doctype html><html lang="bg"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="icon" href="data:,"><title>'+html.escape(title)+' · IZZI Library</title><link rel="stylesheet" href="/__ui__/app.css"><script src="/__ui__/app.js" defer></script></head><body class="catalog-home"><header class="catalog-header"><a class="catalog-logo" href="/" aria-label="IZZI — Библиотека">izzi<span>локална библиотека</span></a><span class="catalog-offline"><span class="dot"></span>Достъпно офлайн</span>'+menu+'</header><main id="main-content"><section class="catalog-intro"><div><span class="catalog-eyebrow">УЧИ. ОТКРИВАЙ. СЪЗДАВАЙ.</span><h1>Твоите дигитални учебници</h1><p>Избери учебник и отвори света на знанието.</p></div><span class="catalog-art" aria-hidden="true">а б в<span>1 2 3</span></span></section><div class="content"><div class="catalog-heading"><h2>Моята библиотека</h2><span>Учебници от локалния архив</span></div>'+searchbox+content+'</div><footer>IZZI Offline Library · Съдържанието се предоставя от твоя локален архив.</footer></main></body></html>')
    return ('<!doctype html><html lang="bg"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="icon" href="data:,"><title>'+html.escape(title)+' · IZZI Library</title><link rel="stylesheet" href="/__ui__/app.css"><script src="/__ui__/app.js" defer></script></head><body><aside class="sidebar"><a class="brand" href="/"><span class="brand-mark">i</span><span>IZZI<span class="brand-sub">OFFLINE LIBRARY</span></span></a><nav aria-label="Основна навигация">'+nav+'</nav><div class="sidebar-note"><span class="dot"></span> Локална библиотека<small>Твоето съдържание, на едно място.</small></div></aside><main><header class="topbar"><span>Работно пространство / '+html.escape(title)+'</span><a href="/__help__">Помощ ↗</a></header><div class="content">'+searchbox+content+'</div><footer>IZZI Offline Library · Съдържанието се предоставя от твоя локален архив.</footer></main></body></html>')


def book_card(book_id,title,info,available):
    """A local title cover; does not require original cover images or internet."""
    bid=html.escape(str(book_id),quote=True)
    title=html.escape(str(title))
    return ('<li data-search-item class="catalog-book"><a class="book-open" href="/__book__/'+bid+'">'
            '<div class="title-cover" aria-hidden="true"><span class="cover-brand">izzi</span>'
            '<span class="cover-title">'+title+'</span><span class="cover-orbit"></span>'
            '<span class="cover-caption">ДИГИТАЛЕН УЧЕБНИК</span></div><h3>'+title+'</h3>'
            '<span class="book-cta">Отвори учебника <span aria-hidden="true">→</span></span></a>'
            '<div class="book-details"><span class="book-state">'+('Наличен HTML' if available else 'Няма записани страници')+'</span>'
            '<small>ID '+bid+'</small><details><summary>Съдържание на архива</summary><p>'+html.escape(info)+'</p></details></div></li>')
