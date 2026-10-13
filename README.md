# IZZI Offline Library

Локална библиотека за архивирани IZZI уроци: Firefox capture proxy, HAR import, offline replay, MP4 byte-range assembly, отчети и диагностика. Това е общото ръководство за v3.4.2 и последващите поправки; историята на по-старите версии е в края.

## WebUI

Началният екран е изчистен каталог с търсене и малки карти, групирани в начален и прогимназиален етап според класа. Учебници без установен клас се показват отделно, без да се скриват. Всички локални страници използват общата горна лента с оригиналното IZZI лого (`webui/izzi-logo.svg`, взето от `/assets/branding/izzi-logo.svg` в записа на сайта), еднакви цветове и оформление. Логото се обслужва локално и не изисква интернет; архивираните уроци запазват своя собствен изглед. Бутонът **Меню** отваря петте раздела: Библиотека, Липсващи ресурси, Локален журнал, Capture и проверки и Как да използвам. Менюто работи и без JavaScript. Кориците се вземат от оригиналния каталог (`/api/online-bookshelf-publications`) само когато съответното изображение е налично в локалния архив. При липсваща индивидуална корица се използва наличната оригинална картинка на същата група учебници. Без записан каталог или налично изображение се показва малка неутрална икона. За записване на каталога отворете оригиналната начална страница с активен capture proxy и Disable Cache, презаредете и превъртете до кориците. След това обновете локалната библиотека. Няма автоматично онлайн изтегляне и не се зарежда оригиналното JavaScript приложение. Подробните броячи остават в страницата на учебника и проверките. `book_covers.py` намира наличната корица и класа по ID.

От **Capture и проверки** можете да стартирате/спирате capture proxy и общите проверки, да виждате статуса, exit code и последните 500 лог реда. Управлението и логовете са разрешени само от самия компютър през `127.0.0.1`/`localhost`; LAN страницата показва указание вместо бутоните. Заявките се ограничават до две фиксирани задачи и start/stop, със защита на локалния Host, socket peer, Origin и control token. Не се приемат произволни команди.

Сървърът стартира процесите директно, без BAT паузи, не допуска повторно стартиране на активна задача и спира само собствените процеси. Зает capture порт се отчита като грешка — външен proxy не се прекратява. Capture търси mitmdump до Python, в системната и потребителската Scripts папка, в PATH и в останалите Windows Python инсталации, изброени от `py -0p`; при липса пуснете install_capture.bat. Настройте Firefox proxy `127.0.0.1:8877`, сертификата, login и Disable Cache ръчно. След спиране възстановете нормалните proxy настройки. При нормално спиране на server се спират и управляваните задачи; преди затваряне на Windows терминала е препоръчително да използвате „Спри“. Финалните readiness отчети пускайте след приключване на capture.

След `start_library.bat` отворете `http://127.0.0.1:8765/` или LAN адреса на компютъра. WebUI работи с локални CSS/JavaScript файлове, без CDN, интернет fonts или допълнителен frontend server. Оригиналните архивирани уроци се отварят от съществуващите replay адреси.

- **Библиотека:** малки карти с оригинални корици, имена и book IDs; търсене по име и ID.
- **Учебник:** подреден списък с търсене и редактор за имена, ред и скриване.
- **Липсващи ресурси:** търсене по адрес, индивидуално/общо изтегляне, спиране и статус. Capture proxy остава нужен за архивиране.
- **Локален журнал:** броячи по book и endpoint, без показване на private request bodies.
- **Помощ:** capture, проверки, подреждане, обновяване и LAN инструкции.

Изгледът е responsive за компютър и телефон. Без JavaScript основната навигация и server-rendered списъците остават достъпни; търсенето и общото изтегляне изискват JavaScript. `webui.py` изгражда общия HTML shell; `webui/app.css` и `webui/app.js` обслужват изгледа и търсенето. WebUI използва фиксирани фонови процеси за capture и проверки; Firefox login/proxy workflow остава отделен.

## Как работи проектът

Проектът има два основни режима. **Capture** записва отговорите, които Firefox получава от IZZI при нормална работа с оригиналния сайт. **Локална библиотека** използва тези файлове и ги предоставя през локален HTTP сървър, за да се отварят уроци без интернет. Capture трябва да се направи предварително; обновяването на програмата от GitHub не изтегля учебници.

Работният цикъл е: инсталиране → capture на избраните срокове/раздели → ръчно активиране на интерактивните ресурси → проверки → локално използване. Може да се допълва съществуващ архив. Списъкът с уроци, историята на обхода и наличните файлове са различни неща: известен урок или `lesson-done` запис не гарантира запазен HTML и всички негови зависимости.

Локалната библиотека показва учебниците по ID и позволява преименуване, подреждане и скриване на уроците. Два записа с еднакво заглавие може да са различни публикации, например интерактивен и PDF вариант. Архивираните упражнения се изпълняват доколкото имат нужните локални ресурси. Записва се локален журнал на write requests; възстановяване на оригиналния server-side progress не е реализирано.

## Оперативни файлове в основната папка

Всички BAT файлове сменят работната директория към собствената си папка. Пускайте ги от инсталацията, в която са вашите `archive` и `state`. За Python командите е нужна работеща `py` команда; за Git обновяването — `git`.

| Файл | Кога се използва | Какво променя |
| --- | --- | --- |
| `install_capture.bat` | Подготовка за capture | Инсталира Python зависимости |
| `capture_mode.bat` | Записване от оригиналния сайт | Допълва archive/state |
| `start_library.bat` | Библиотека и capture | Стартира proxy при свободен порт и сървър; записва misses и локални настройки/журнал при работа |
| `import_har.bat` | Импорт на запазен HAR | Допълва archive/state/captures |
| `update_project.bat` | Обновяване от GitHub | Обновява програмните файлове чрез Git |
| `repair_library.bat` | Възстановяване на каталожни данни | Обновява каталога в SQLite (или стария books.json) от наличните HTML записи и стария каталог |
| `build_recovery_manifest.bat` | Подготовка на 304-only recovery | Презаписва recovery_manifest.json |
| `prepare_recovery.bat` | Същата подготовка с напомняне | Същият manifest; не стартира browser recovery |
| `reset_capture_diagnostics.bat` | Съзнателно започване на нова диагностична история | Изтрива три diagnostic state файла |
| `clear_missing.bat` | Изчистване на историческия missing log | Изтрива missing_resources.jsonl |
| `run_all_checks.bat` | Общ преглед на тестовете и архива | Изпълнява checks; HTTP probes могат да добавят missing-log записи |

### `install_capture.bat` — зависимости за записване

Изпълнява `py -m pip install -r requirements-capture.txt`. Декларацията допуска mitmproxy версии `>=11,<13`; облачната среда е проверена с 12.2.3. BAT не създава отделна virtual environment: пакетите се инсталират в Python средата, избрана от `py`. Нужен е интернет за изтеглянето им. Командата не настройва Firefox proxy, не инсталира автоматично browser доверие към сертификата и не записва учебници. При успешно инсталиране `mitmdump` трябва да е достъпен в PATH; иначе `capture_mode.bat` ще спре с обяснение.

### `capture_mode.bat` — capture proxy

Изпълнява `mitmdump --listen-host 0.0.0.0 -p 8877 -s capture_addon.py` и остава отворен, докато proxy работи. Firefox трябва да използва HTTP/HTTPS proxy `127.0.0.1:8877`, да доверява mitmproxy сертификата и да е логнат нормално в IZZI. Включете Disable Cache, отваряйте оригиналните уроци и пускайте необходимите медии.

Addon пази bodies в `archive`, URL записите и каталожните данни в `state/library.sqlite3`, както и отделни media mappings и observations. При първо стартиране прехвърля старите `url_map.json` и `books.json` в SQLite. При MP4 Range заявки натрупва части и регистрира завършена медия само след проверено пълно покритие. Контролните събития от bookmarklet се обработват локално. Командата сама не обхожда учебника, не настройва proxy в браузъра и не автоматизира login. Спрете с Ctrl+C, след което възстановете нормалния Firefox proxy. Запазените данни остават на диска.

### `start_library.bat` — локална библиотека и capture

Проверява за Python, после проверява capture порт 8877. Ако е свободен, стартира `capture_mode.bat` в отделен прозорец; ако е зает, не стартира втори proxy. След това отваря браузъра и стартира `py server.py`. При липсващ mitmdump capture прозорецът показва грешката, но библиотеката може да работи с вече записания архив. За capture първо изпълнете `install_capture.bat` и настройте browser proxy/сертификата.

Оставете двата прозореца отворени. Capture, стартиран чрез BAT, е външен процес за WebUI: спира се с Ctrl+C в собствения му прозорец. Затварянето на библиотеката не спира този capture. За LAN са нужни Firewall разрешения за 8765 и 8877. За стартиране само на библиотеката използвайте `py server.py`. При задача преди Windows login стартирайте директно `server.py` чрез Task Scheduler; тя не използва този интерактивен BAT.

### `import_har.bat` — импорт от HAR

Плъзнете един или повече HAR файлове върху BAT или го изпълнете с пътища:

```powershell
.\import_har.bat "D:\Captures\lesson.har"
```

Извиква `import_har.py`. Чете HAR entries, записва наличните response bodies като blobs, добавя URL records и извлича book/lesson metadata от HTML. Импортът е добавъчен; налични записи не се изчистват. HAR без запазени response bodies не може да възстанови съдържанието само от URL-и. Импортът не изпълнява пълния MP4 range assembly workflow на capture proxy.

В `captures/` се записва обработено HAR копие с премахнати избрани чувствителни headers, cookies и request postData. Това не е гаранция за пълно обезличаване: URL query parameters и response bodies могат да съдържат лични данни. Оригиналният HAR се запазва непроменен. Пазете резервно копие и избягвайте едновременен import и capture, тъй като и двата обновяват индекси.

### `update_project.bat` — GitHub обновяване

Изисква Git checkout, branch `main` или `WebUI` и липса на локални промени или неигнорирани untracked файлове. Показва напомняне да спрете capture/server и след пауза изпълнява `git pull --ff-only origin <текущия клон>`. При конфликт, divergent история или локални промени спира; не използва reset/clean. Накрая показва последния commit.

Архивът и state са игнорирани от Git и не се изтеглят от GitHub. Запазвайте ги с отделно резервно копие. При инсталация само от ZIP този BAT няма да работи без Git checkout. След обновяване стартирайте отново сървъра, а при промяна на bookmarklet — обновете и запазения Firefox bookmark.

### `repair_library.bat` — възстановяване на каталога

Извиква `repair_library.py`: преглежда директните lesson URL-и за основния source host в URL map, чете наличните HTML blobs и извлича имена на учебници и уроци. Обновява каталога в SQLite (или `state/books.json` при стар формат), като запазва старите book/lesson записи, които не могат да се възстановят. Показва броя възстановени lessons.

Използвайте го при липсващи или остарели каталожни данни, след резервно копие и със спрян capture. Не възстановява `url_map.json`, липсващи blobs, видеа или зависимости; не премахва автоматично дублиращи се по заглавие книги и не доказва readiness. Локалните имена/ред/скриване са в отделния `library_catalog.json`.

### `build_recovery_manifest.bat` — списък за recovery

Извиква `build_recovery_manifest.py`. От `capture_observed.json` избира вече наблюдавани IZZI URL-и със статус 304 и без наблюдаван 200/206. Изключва MP4/audio формати и записва сортиран, уникален списък в `state/recovery_manifest.json`, заменяйки предишния manifest.

Не изтегля ресурси. След него трябва да изпълните recovery bookmarklet във Firefox при активен capture и нормален login. Филтърът е по наблюдаваните statuses; readiness проверката отделно определя дали вече има usable body в архива. Празен manifest означава липса на кандидати по този филтър, а не непременно пълен архив.

### `prepare_recovery.bat` — удобен вариант на подготовката

Изпълнява същия `build_recovery_manifest.py`, после показва напомняне да натиснете Firefox bookmark от `cache_bust_recovery_bookmarklet.txt`. Разликата спрямо `build_recovery_manifest.bat` е само напомнянето. Нито един от двата BAT файла не стартира автоматично browser recovery.

### `reset_capture_diagnostics.bat` — нова diagnostic история

Извиква `reset_capture_diagnostics.py` и изтрива, ако съществуват, точно:

- `state/capture_observed.json` — наблюдавани заявки/statuses;
- `state/capture_session.json` — traversal visits/start/done;
- `state/active_lesson.json` — активен lesson context.

Използвайте със спрян capture, когато съзнателно искате нов диагностичен обход. Archive, URL map, books, media map, локалният каталог и progress journal се запазват. Изтриването на session премахва и историята, от която се извежда автоматичният ред на уроците; ръчно записаният ред в `library_catalog.json` остава. Отчетите няма да могат да използват старите traversal markers. Това не поправя липсващ HTML или неуспешен capture.

### `clear_missing.bat` — изчистване на missing history

Извиква `clear_missing.py` и изтрива само `state/missing_resources.jsonl`. Ако няма файл, показва съобщение. Използвайте при нужда от чист missing log, за предпочитане със спрян server. Следващите неуспешни локални заявки отново ще се записват.

Изчистването не добавя липсващи ресурси и не прави архива READY. Страницата `/__missing__` вече филтрира възстановените ресурси, така че за тях не е необходимо да изтривате историята.

### `run_all_checks.bat` — общ стартер за проверки

Извиква `checks/run_all.py` със същия Python, продължава след неуспешни проверки и накрая показва SUMMARY. Изпълнява изолирани tests, informational reports, readiness и локални HTTP проверки. При свободен порт стартира временен replay server и го спира при приключване; ако има разпознаваем работещ server, използва го без да го спира. За MP4 Range test избира complete assembled URL; ако няма такъв, отбелязва SKIPPED.

```powershell
.\run_all_checks.bat
.\run_all_checks.bat --synthetic-only
```

Вторият вариант изпълнява само четирите synthetic/contract suites и не проверява личния архив. Общият runner не стартира capture, import, repair, reset, recovery или Git update. HTTP probes минават през обичайния server и могат да допълнят missing log при пропуски. Индивидуалните инструменти остават в `checks/`.

След края BAT запазва exit code: 0 при липса на FAILED проверки, 1 при неуспех. Пауза има само накрая. При информационни reports `OK` означава, че script е изпълнен; четете и неговите броячи. SKIPPED не означава успешно проверена медия. HTML/runtime suite изисква Node.js за четири теста; без него те са пропуснати.

## Firefox bookmarklet файлове

Тези `.txt` файлове съдържат JavaScript за URL полето на bookmark, а не команди за двойно щракване. Създайте bookmark, поставете целия текст като адрес и го изпълнете от оригиналния IZZI сайт при активен capture.

### `auto_book_capture_bookmarklet.txt`

Препоръчаният автоматичен обход. Прочита навигацията на текущия учебник, показва избор на раздели и събира уроците от секциите на избраните раздели в оригиналния ред. Следва избор с имената и оригиналните номера на уроците, например „3.1.“; отметката „Пропусни“ изключва урок. Общите менюта за PDF, видеотека и материали за учителя не се включват. Страниците за навигация се прочитат като HTML, без изпълнение на техните скриптове и зареждане на изображенията им. При по-старо съдържание без разпознаваема структура се използват връзките в основното съдържание на отворената страница.

След потвърждение посещава избраните уроци в iframe, изпраща start/active/done събития към локалния proxy и проверява ресурси. Оригиналният номер, заглавието и името на раздела се записват с `lesson-start`. В локалната библиотека името на раздела се показва като заглавие, а под него се изброяват уроците с оригиналната им номерация. Уроците се групират по раздел в реда на първата му поява; ръчната подредба определя реда вътре в раздела. Записите без информация за раздел са в отделна група. При стари записи без тази информация трябва нов обход с актуалния bookmarklet, за да се добави разделът. Ръчното пренареждане и преименуване не променят оригиналния номер. Медията и интерактивните задачи може да изискват ръчно активиране. След съобщението за край проверете наличния HTML; done marker сам по себе си не доказва успешен capture.

### `capture_navigation.js` и `tools/build_capture_bookmarklet.py`

Четимият JavaScript източник за избора на раздели и извличането на секции, уроци, заглавия и номера. Не е отделен bookmark и не се зарежда от мрежата. След редакция изпълнете `py tools\build_capture_bookmarklet.py`, за да обновите вграденото копие в `auto_book_capture_bookmarklet.txt`. Проверките проверяват съвпадението на двете копия.

### `cache_bust_recovery_bookmarklet.txt`

Чете manifest от локално прихванатия `/__offline_capture__/recovery_manifest`, после заявява URL-ите последователно с cache-bust marker и browser credentials. Proxy премахва marker при индексиране и записва резултатите от опитите. Използва се след `build_recovery_manifest.bat` или `prepare_recovery.bat`. Не открива нови lessons, не сглобява MP4 и не възстановява съдържание, което оригиналният сайт не предоставя.

### `capture_bookmarklet.txt`

По-стар прост обход: посещава lesson links в iframe приблизително през 7 секунди. Няма избор за пропускане и не изпраща traversal start/done или active-lesson heartbeat. Запазен е за съвместимост; за текущия workflow използвайте `auto_book_capture_bookmarklet.txt`.

## Папки, настройки и вътрешни компоненти

| Път | Съдържание и роля |
| --- | --- |
| `archive/` | Response blobs, части за range assembly и assembled media; основното съдържание за replay |
| `state/library.sqlite3` | Активните URL → response records → blob ключове и оригинални book/lesson имена, ID-и и paths; SQLite база с индекси за търсене |
| `state/url_map.json`, `state/books.json` | Стар формат; след миграцията са резервни копия от този момент и не се обновяват |
| `state/library_catalog.json` | Локални имена, ред и hidden flags |
| `state/media_map.json` | Lesson/block → media връзки |
| `state/capture_session.json`, `state/capture_observed.json` | История на обхода и наблюдавани заявки |
| `state/progress/` | Локален request journal по book ID |
| `state/missing_resources.jsonl` | Исторически локални misses |
| `captures/` | Обработени HAR копия от import |
| `checks/` | Всички test/report/diagnostic scripts и индивидуални BAT wrappers |
| `tools/` | Linux setup helper, dependency lock и setup report |

`config.py` определя папките спрямо местоположението си, source host, replay host/port и capture port. BAT launchers и bookmarklets съдържат и фиксирани адреси/портове; промяна само в config не обновява автоматично всички launchers. `VERSION.txt` е исторически base-version етикет; актуалните възможности и поправки са описани тук.

Вътрешните `.py` модули обикновено не се стартират ръчно: `capture_addon.py` е mitmproxy addon; `server.py` е replay сървърът; `replay_resolver.py` намира годни canonical bodies; `range_assembler.py` и `assembled_media.py` управляват complete media; `media_mapping.py` свързва медии с lessons; `library_catalog.py` пази локалния изглед; `progress_journal.py` записва локални requests; `readiness.py` оценява наличния архив. Едноименните Python файлове зад оперативните BAT команди изпълняват описаните операции.

`requirements-capture.txt` е pip dependency декларацията за Windows capture. `tools/capture-requirements.lock` пази resolved версии за облачния setup. `tools/setup.sh` създава Linux `.venv`, инсталира lock dependencies, проверява pip packages и изпълнява media contract test. `tools/SETUP_REPORT.md` описва проверената среда и ограниченията; не е инструкция за възстановяване на личен архив.

## Инсталиране и обновяване (Windows)

Необходими са Python с командата `py`, Firefox и Git за обновяване от GitHub.

```powershell
git clone https://github.com/YuriMladenov/izzi.git
cd izzi
```

За capture изпълнете `install_capture.bat` (използва `requirements-capture.txt`). Локалният replay не изисква работещ capture proxy. `requirements.txt` съдържа пояснения, а не pip списък.

При обновяване спрете capture и replay процесите, запазете резервно копие на `archive` и `state`, след което изпълнете `update_project.bat` или `git pull --ff-only origin WebUI` за клона WebUI. BAT файлът изисква branch `main` или `WebUI` и чист working tree; при локални промени спира, без reset/clean. При обновяване от ZIP запазете съществуващите `archive` и `state` до `server.py`. Не смесвайте данните от различни инсталационни папки.

## Достъп от локалната мрежа

Replay server слуша на `0.0.0.0:8765`, тоест на всички IPv4 мрежови интерфейси. На основния компютър използвайте `http://127.0.0.1:8765/`. От друго устройство в същата мрежа използвайте `http://<IPv4 на компютъра>:8765/`, например `http://192.168.1.20:8765/`. Адресът се вижда с `ipconfig`; `0.0.0.0` не е адрес за браузъра.

Стартирайте `start_library.bat` на компютъра с архива и оставете сървъра работещ. Разрешете входящ TCP порт 8765 в Windows Firewall само за Private профила и локалната подмрежа. Firewall настройките не се променят автоматично от проекта. Използвайте доверена локална мрежа: няма login, а достъпните устройства могат да четат съдържанието; управлението на каталога е достъпно само през localhost. Не правете router port forwarding към интернет.

За достъп само от същия компютър задайте `HOST="127.0.0.1"` в `config.py` и рестартирайте сървъра. `CLIENT_HOST="127.0.0.1"` остава адресът за локалните проверки, независимо от адреса за слушане. Capture proxy и Firefox capture настройките не се променят.

## Capture на урок

1. Стартирайте `capture_mode.bat`.
2. В Firefox задайте HTTP/HTTPS proxy `127.0.0.1:8877` и доверете mitmproxy сертификата.
3. Влезте нормално в IZZI и отворете урок, до който имате достъп.
4. В F12 → Network включете **Disable Cache**, презаредете с Ctrl+Shift+R.
5. Пуснете видеата и активирайте упражненията/изтеглянията, които искате офлайн.
6. Спрете capture с Ctrl+C и възстановете нормалните proxy настройки на Firefox.
7. Стартирайте `start_library.bat` и отворете `http://127.0.0.1:8765/`.

Proxy архивира `*.izzi.digital`, избраните връзки от уроците и техните GET зависимости, както и `cdnjs.cloudflare.com` за библиотеките на вградените приложения, въпреки че друг browser traffic може да преминава през него. Login остава ръчен. DRM и външни услуги с жив backend не се превръщат автоматично в офлайн медия. YouTube има отделно изтегляне чрез yt-dlp, описано по-долу. Познатите YouTube API loaders получават локален празен script; стандартните embeds отварят локален HTML5 плеър, ако видеото е записано, иначе съобщение за недостъпност.

Capture пази декодирани HTML/JS/CSS bodies, вместо gzip/Brotli transport bytes. При архив от преди v3.2 с `illegal character U+FFFD` използвайте нормален fresh capture на засегнатия урок; `checks\inspect_blobs.bat` проверява за компресирани/повредени blobs. HAR import е достъпен чрез `import_har.bat`.

## Автоматичен обход на учебник

При активен capture отворете съдържанието на учебника във Firefox. Създайте bookmark с целия текст на `auto_book_capture_bookmarklet.txt` като URL, стартирайте го и потвърдете обхода. Дръжте таба отворен до съобщението за завършване. Изберете разделите, после пропуснете ненужните уроци. Bookmarklet посещава избраните same-book lesson links в iframe и изчаква около 10 секунди след load.

Автоматичният обход не активира всички lazy ресурси. След него пуснете ръчно видеата, упражненията и downloads. Контролните `/__offline_capture__/event` заявки се прихващат локално; start/done запис без HTML body не доказва наличен урок.

Capture премахва conditional cache headers и добавя no-cache directives за обичайни IZZI GET/HEAD заявки. Реалният Referer има приоритет при lesson/media mapping; краткотрайният `lesson-active` контекст служи като fallback. Няма глобално прехвърляне на медия между уроци.

### Проверка на изображенията при обход

Кандидатите се извличат от image елементи и image markup във вложени конфигурации, а не от произволни URL фрагменти в scripts или metadata. SVG sprite references не се зареждат като самостоятелни картинки. Реалните image заявки използват уникалния recovery marker, за да избегнат browser memory cache; proxy го премахва при записване и проверява оригиналния адрес.

Iframe е 1280 × 900 px за desktop layout; визуално е намален с CSS scale, без да се намалява вътрешният viewport. Урокът се превърта постепенно по основния scroll container, с паузи за lazy loading, след което позицията се възстановява и се проверяват изображенията. Превъртането следи увеличаването на страницата, има лимит 120 стъпки и отчита `scroll-incomplete`, ако не достигне края. Отделни вложени панели с независимо превъртане остават за ръчно активиране.

След зареждане на всеки урок bookmarklet събира изображенията от HTML, image/custom elements, srcset и вложения HTML в конфигурациите на упражненията. Заявява IZZI изображенията през браузъра (до четири едновременно), изчаква load/error и проверява чрез capture proxy дали има годен архивиран body. Използва реално посочените URL-и; не предполага други адреси. След повторни сканирания за динамични изображения преминава нататък. При грешка прави втори опит.

`image-failed` записите в `checks\capture_session_report.bat` показват адрес и причина; `images-checked` съдържа броя проверени и неуспешни изображения. Урок с грешка получава `lesson-incomplete`, а не `lesson-done`. Readiness използва последния done/incomplete резултат за всеки урок. Отчитат се и iframe/login проблеми и незаписан HTML. Външни изображения се отбелязват като непълни, тъй като proxy архивира само IZZI.

Нужни са обновеният capture addon и обновеният Firefox bookmark; спрете и стартирайте отново capture след обновяване. Започнете с проблемния урок 1408780 и проверете image-failed и readiness след обхода. Целта е потвърдено зареждане и записване на всички открити изображения, а не безусловен успех: origin 404, timeout и блокирани ресурси се показват като пропуски. Изображения, появяващи се само след непосетени интеракции, не могат да се открият предварително. Видеата продължават да изискват отделна проверка.

### Прикачени файлове при обход

След изображенията bookmarklet записва прикачените файлове от lesson links и вложените HTML links в конфигурациите. Поддържа IZZI `/files/` адреси и познати download формати, включително `.exe`, Scratch `.sb3`/`.sb2`, архиви и документи. Използва browser fetch с нормалната сесия и recovery marker, изчаква и проверява архива, с два опита и лимит 120 секунди за опит. Не изпълнява файловете и не ги стартира като приложения.

`files-checked` и `file-failed` се показват в capture session report. Непотвърден файл прави lesson traversal непълен. Capture има съществуващ лимит 250 MiB на body; по-големи файлове няма да бъдат потвърдени. Линкове, които се появяват само след непосетена интеракция, остават за ръчна проверка. Запазените файлове се свалят от локалната библиотека с download header; `.exe` и `.sb3` се броят като документи. Обновете capture/replay файловете и Firefox bookmark преди нов обход.

## Подреждане, преименуване и скриване

На страницата на учебника изберете **Подреди / преименувай / скрий**. Задайте номера в колоната „Ред“ (по-малкият е по-рано), редактирайте името и отметнете „Скрит“ за ненужните страници. Натиснете „Запази“. Скритите уроци остават достъпни в редактора, където можете да ги покажете отново.

Настройките се пазят в `state/library_catalog.json` и оцеляват след рестарт и обновяване. Оригиналните books metadata и архивираните файлове се запазват. Скриването засяга списъка в локалната библиотека; директните URL-и, навигацията вътре в оригиналните уроци и readiness отчетите не се променят.

Без ръчно зададен ред се използва последователността на първите `lesson-start` посещения в capture session, следвана от останалите metadata страници. Bookmarklet обхожда връзките в DOM реда на съдържанието, който може да се различава от визуалния ред при специален layout. Пускайте първи срок преди втори, или разделите последователно. За стари архиви без надеждна история задайте реда ръчно; последователността не може да се възстанови само от numeric lesson IDs.

Преди обход bookmarklet показва избор на раздели, когато учебникът има такава структура, а после прозорец с имената и оригиналните номера на уроците от избраните секции. Отметнете **„Пропусни“** за тези, които не искате да се обхождат; неотметнатите се включват. Бутоните „Пропусни всички“ и „Обходи всички“ сменят избора, а броячът показва колко остават. Натиснете „Стартирай обхода“ или „Отказ“. Ако връзката няма име, се показва „Урок <ID>“. Обновете URL-а на Firefox bookmark от новия `auto_book_capture_bookmarklet.txt`. Пропуснатите страници не се посещават от този обход; оригиналният сайт все пак може да зарежда свързани ресурси. Вече архивирани страници се скриват чрез редактора, а не се изтриват. Началната страница, от която стартирате обхода, вече е заредена и може да е архивирана.

## Възстановяване на 304-only ресурси

Първо проверете диагностиката: 304 не е проблем, ако има друг годен body за същия ресурс. При действителен 304-only gap:

1. Запазете `archive` и `state`; изпълнете `build_recovery_manifest.bat` след нормален capture.
2. Създайте Firefox bookmark от целия `cache_bust_recovery_bookmarklet.txt`.
3. Докато сте логнати в IZZI и capture е активен, изпълнете bookmark и изчакайте завършване.
4. Проверете `checks\recovery_report.bat`, `checks\fresh_capture_report.bat` и `checks\final_readiness_report.bat`.

Recovery използва само вече наблюдавани URL-и, изключва MP4/audio и добавя `__izzi_offline_recover`; proxy премахва маркера при индексиране. Не открива непосетено съдържание. `reset_capture_diagnostics.bat` премахва observation/session diagnostics; използвайте го само когато съзнателно започвате нов диагностичен обход, а не като поправка за липсващ HTML.

## Проверки и диагностика

**Изтегли всички** заявява ресурсите от списъка и предупрежденията последователно през браузъра, с recovery marker, и проверява записа им в текущия архив. Има брояч, краен резултат и бутон **Спри**. Нужно е интернет и активен browser capture proxy към компютъра с библиотеката. Непотвърден запис или origin 404 се отчита като неуспех; успешната мрежова заявка сама по себе си не се обявява за архивиране. След края презаредете страницата.

На страницата „Текущи липсващи ресурси“ бутонът **Изтегли** до всеки IZZI запис отваря оригиналния HTTPS адрес в нов таб с recovery marker за нова заявка. Нужно е Firefox да е настроен към активния capture proxy и да има интернет; нормалният browser login се запазва. След зареждане върнете се към списъка и го презаредете — годните възстановени ресурси изчезват. Бутонът не е директен server-side downloader и без capture отварянето не записва в архива. За LAN ползвайте browser proxy към компютъра с архива, не proxy на друг компютър. В логовете не се показват query параметри; ако ресурсът изисква специални параметри, отворете оригиналния урок през capture. Origin 404 не се възстановява само с натискане на бутона.

Всички test/report/diagnostic scripts и отделните BAT wrappers са в `checks/`. В основната папка пуснете **`run_all_checks.bat`**: изпълнява проверките последователно, продължава след грешки и показва общ резултат. Не спира на всяка отделна проверка. За HTTP проверките стартира временен replay server, ако портът е свободен, и го спира след края; вече работещият server се запазва. MP4 URL се избира автоматично от complete assembly index; при липса на такъв тестът е SKIPPED. `run_all_checks.bat --synthetic-only` изпълнява само изолираните тестове.

Readiness може да завърши с грешка за непълен личен архив, въпреки успешните synthetic тестове. `OK` при информационен отчет означава успешно изпълнение, а не пълен архив. Прегледайте броячите. Инструментите за capture, import, repair и update остават отделни оперативни команди; общият runner не ги изпълнява.

| Команда | Предназначение |
| --- | --- |
| `checks\validate_replay.bat` | 22 synthetic HTTP проверки; не валидира личния архив |
| `checks\test_library_workflow.bat` | 26 regression теста с временни данни |
| `checks\test_media_contract.bat` | Media mapping/server API contract |
| `checks\final_readiness_report.bat`, `checks\book_readiness_report.bat` | Пълнота на текущия archive/state |
| `checks\missing_assets_report.bat` | Известни пропуски и origin 404 warnings |
| `checks\lesson_diagnostic.bat` | HTML записи/blobs за 1408782 и 1408803; приема друг URL като аргумент |
| `checks\asset_diagnostic.bat`, `checks\font_diagnostic.bat` | Годни image/font bodies |
| `checks\replay_map_diagnostic.bat`, `checks\replay_self_test.bat` | URL map и archive integrity |
| `checks\local_replay_smoke_test.bat` | HTTP проверка при работещ replay server |
| `checks\media_map_report.bat`, `checks\assembled_media_report.bat` | Lesson/media mapping и завършени MP4 |
| `checks\media_replay_check.bat`, `checks\test_all_assembled.bat` | Media replay диагностика |
| `checks\test_mp4_range.bat` | Range тест с локален MP4 URL от Firefox Network |
| `checks\capture_session_report.bat`, `checks\fresh_capture_report.bat` | Обход и fresh capture статистика |
| `checks\progress_report.bat` | Summary на локалния журнал |

Пример за конкретен ресурс:

```powershell
py checks\asset_diagnostic.py "/__host__/api.izzi.digital/път/до/картинка.png"
py checks\lesson_diagnostic.py "/DOS/1408736/1408782.html"
```

`UNRESOLVED` означава, че няма намерен годен body. Проверете status, body availability, blob presence и размер, преди да правите нов capture. При lesson 404 изпратете lesson diagnostics и `[MISS]` редовете. `503 Archive state unavailable` означава нечетим state, а не липсващ capture. JSON се записва с atomic replace; това не възстановява вече изгубени записи.

Страницата `/__missing__` проверява историческите пропуски срещу текущия архив, изключва възстановените ресурси и отделя origin 404 и optional favicon/source-map warnings. Историческият журнал се запазва. Библиотеката показва познати страници и наличен HTML поотделно. Еднакви заглавия с различни book IDs не се сливат.

След обновяване проверете в реалния Firefox картинки, шрифтове, видео, seek и преминаване към друг урок с изключен интернет. CSS source-map 404 и legacy/vendor CSS warnings обикновено не блокират урока.

## Replay и MP4

Resolver предпочита годни complete assembled media и архивирани GET bodies; exact URL има приоритет, а canonical fallback допуска IZZI host/port aliases и статични `/datastore`, `/profil`, `/_nuxt` пътища със/без DOS prefix. Lesson HTML запазва book/lesson identity. Няма upstream fetch или фабрикуване на липсващи картинки/шрифтове.

MP4 се обслужва с `video/mp4`, правилни Range/206, Content-Range, Content-Length, Accept-Ranges и `X-IZZI-Replay`. Assembly изисква 100% проверено покритие. Пълен единичен 206 е допустим при Content-Range от byte 0 до последния byte и съвпадащ blob размер; частичен chunk не е пълен ресурс. Пълен HTTP 200 MP4 може да се използва без assembly marker.

Media shim премахва невалидни `#`/lesson HTML sources и наблюдава динамични промени. Запазва валидните sources, използва lesson/block context и не задава MP4 на скрит audio player. MP4 source MIME се нормализира. Стар URL map без Referer не може надеждно да възстанови lesson/media връзките самостоятелно.

Полезни server/browser markers са `[REPLAY]`, `[MEDIA REPLAY]`, `[ASSEMBLED MEDIA]` и `[IZZI OFFLINE MEDIA MAP]`. Font selection проверява разпознаваем header; image selection отхвърля празни/HTML error bodies. Реален origin 404 се запазва, когато няма годен вариант.

## Readiness

Уроците са union от books metadata, URL map, наблюдавани lesson URL-и, session visits и lesson media map. Book/lesson IDs се нормализират като strings. Само изричен `lesson-done` доказва завършен traversal; зареден HTML не се счита за завършен обход. Познатите уроци без done marker блокират READY.

Проверява се реалното наличие на избрания blob, записаният размер, HTTP status и пълнота на 206 body. Font header-и и image HTML error bodies се проверяват със същите правила като сървъра. Частичен MP4 chunk не означава пълен ресурс. Напълно архивиран HTTP 200 MP4 е наличен и без отделен assembly marker.

`304-only` е gap само когато няма usable canonical body. Стар 404, за който вече има usable body, не е warning. Origin-only 404 са отделни предупреждения и не превръщат otherwise complete архив в INCOMPLETE. Непозната/нечетима schema и празен archive не получават READY.

Историческите 27/27, 0 gaps и 9 origin 404 за книга 1408736 не са hardcoded. При такива действителни данни резултатът е `READY WITH WARNINGS`. Реалният state остава за локална проверка. Отчетът покрива известни/наблюдавани ресурси, не недокоснати интерактивности.

## Локален request journal

По избора на потребителя се реализират журнал и диагностика, **не** непотвърдени правила за completion/score/restore. Write API response остава `offline:true, saved:true` само след успешен запис на диска. Това не означава, че оригиналният server-side progress е възпроизведен.

Всеки POST/PUT/PATCH/DELETE body се пази без отрязване, включително lossless base64 representation за binary/невалиден UTF-8. Записите са в `state/progress/<book>.jsonl`; book се определя по lesson Referer/път, а при липса на контекст — `general`. Едновременните writes се сериализират и flush/fsync приключва преди success response. Requests над 10 MiB, невалиден Content-Length, неподдържан Transfer-Encoding и disk errors връщат изрична грешка вместо success.

Новият diagnostics endpoint `/__offline__/progress` съдържа само summary. Записите оцеляват след server restart. Старите journal records се пазят непроменени и се отбелязват като legacy — пълнотата на старите отрязани bodies не може да се възстанови. Повредени JSONL редове се броят като invalid без изтриване/repair на state.

## Изолация

Общият `replay_resolver.py` се използва от HTTP replay, readiness и diagnostics. Canonical fallback проверява book IDs в `/DOS/<book>/` и `/publication/<book>/`. Унаследен book context от локалния Referer се използва за shared routes; двусмислен unscoped path с различни bodies за различни книги връща miss вместо произволен избор. Валидни общи ресурси остават reusable. Capture и injection отказват изрично чужд publication/book media URL.

Тестовете покриват две synthetic книги. Реална втора книга и UI прогрес след рестарт остават за локално упражняване; не се извлича ново съдържание и не се променя Firefox login/capture моделът.

## Среда за разработка и резултати

На Linux с Python 3.12 изпълнете `bash tools/setup.sh`; capture dependency е mitmproxy 12.2.3, resolved versions са в `tools/capture-requirements.lock`.

```bash
.venv/bin/python checks/validate_replay.py
.venv/bin/python checks/test_library_workflow.py
.venv/bin/python checks/test_replay_html.py
```

Последната проверка: 22 HTTP + 26 workflow + 13 HTML/runtime теста са успешни; четири runtime теста използват Node.js. Тестовете работят с временни synthetic данни, не с личния archive/state. Chromium проверката изтече по timeout преди достигане на test server; browser rendering не е потвърдено за всички последващи поправки. Потребителят потвърди Windows offline video/seek/navigation и възстановена PNG; конкретните липсващи lesson bodies остават за локална диагностика.

## История на версиите

| Версия | Основна промяна |
| --- | --- |
| v3.2 | Декодирани JS/CSS/HTML bodies; MP4 range assembly |
| v3.2.1 | Range/206 replay, MP4 MIME и локално URL rewriting |
| v3.2.2 | Persistent lesson/media mapping и media shim |
| v3.2.3 | Complete assembled resolver и MP4 source MIME normalization |
| v3.3 | Auto Book Capture и session reports |
| v3.3.1 | Strict lesson mapping, capture observations и readiness |
| v3.3.2 | Forced fresh capture и active-lesson heartbeat |
| v3.3.2.1 | Hotfix за strings/dictionaries media API mismatch; не изисква recapture |
| v3.3.3 | Targeted 304-only cache-bust recovery |
| v3.4 | MIME handling, integrity/smoke tests и origin 404 warnings |
| v3.4.1 | Logical path aliases и readiness от реалния session visits array |
| v3.4.2 | Canonical host/path lookup и извикване на assembled MP4 resolver |
| Последващи поправки | Resolver tuple fix, media/assets selection, book isolation, локален журнал, проверен full 206, atomic JSON writes и текущ списък с пропуски |

Старите 27/27 traversal и девет origin 404 са исторически резултати за конкретен архив, а не очаквани стойности за всеки учебник. Само replay поправка не изисква recapture, ако годните bodies вече са налични.

## Данни и поверителност

Пазете резервно копие на `archive` и `state`. Не ги публикувайте заедно с HAR или raw journal bodies: могат да съдържат account/application metadata. За диагностика споделяйте броячи, `FAILURE`/`MISS` редове и schema errors, без cookies, tokens или credential query parameters.


### Ресурси от по-стари публикации и записване от друг Firefox профил

ID на учебника в `/DOS/<ID>/` може да се различава от ID в `/publication/<ID>/` на използваните изображения и видеа. Например урок от учебник `412693` може да ползва ресурси от публикации `3931` и `4043`. Replay, media mapping и проверките различават тези два вида идентификатори; отделните учебници и техните уроци запазват своята идентичност.

Обновеният `auto_book_capture_bookmarklet.txt` открива директни MP4/аудио ресурси в елементите и HTML конфигурациите на урока, изтегля ги последователно без Range заявка и проверява наличието на пълен архивен файл. Наличните пълни файлове се пропускат. Непотвърден файл създава `media-failed` и урокът се маркира като непълен. За всяко изтегляне има лимит 4 минути и до два опита; proxy лимитът за body остава 250 MiB. Външни видеа, HLS/DASH стриймове, DRM и съдържание, появяващо се след непосетени действия, не се архивират чрез тази функция. Не се заобикалят вход или права за достъп. „Изтегли всички“ също изчаква до 4 минути за медийни файлове; отваряне на видео в таб може да запише само частични диапазони.

При смяна на Firefox профила настройте proxy `127.0.0.1:8877`, доверете mitmproxy сертификата и включете Disable Cache и в новия профил. Влезте нормално в IZZI и първо проверете, че оригиналните видеа се възпроизвеждат. Bookmarklet preflight трябва да разпознае активния capture proxy; самото включване на proxy процеса в WebUI не настройва Firefox. Служебните `/__offline_capture__/` адреси не са ресурси на учебника и не се показват в списъка за възстановяване.

### Кориците и достъпът през LAN

Картите използват оригиналния градиент (`dos_class` / `palette…`) и двете изображения (`thumbs.image1` и `thumbs.image2`) от записания каталог. Изображенията се показват само ако са налични в архива; няма онлайн заявки. Ако липсва второто изображение или каталожният запис, е нужен capture/import на каталога и съответните изображения.

През LAN са достъпни библиотеката, списъците с уроци и архивираното им съдържание. Менюто и връзката към редактора са скрити. Директните адреси за редактиране, запис на подредба, липсващи ресурси, журнал, помощ и операции са блокирани. Управлението остава достъпно на сървъра през `http://127.0.0.1:8765/` или `localhost`; проверяват се и адресът на клиента, и Host. Локалният журнал на заявки от упражненията продължава да работи.

### Capture от друг компютър през LAN

Стартирайте `capture_mode.bat` на компютъра с архива. Proxy слуша на всички IPv4 интерфейси на порт 8877. На другия компютър задайте във Firefox HTTP/HTTPS proxy `<IPv4 на компютъра с архива>:8877`. Отворете `http://mitm.it` през този proxy и импортирайте неговия PEM сертификат във Firefox → Сертификати → Удостоверители, с доверие за идентифициране на уебсайтове. Включете Disable Cache и влезте в IZZI с желания профил. Записите се пазят на компютъра с proxy. За локалната библиотека добавете LAN адреса му в „Без прокси за“.

Разрешете входящ TCP 8877 в Windows Firewall само за Private профила и LocalSubnet; използвайте доверена мрежа. BAT не променя автоматично Firewall. След приключване възстановете browser proxy настройките. Capture, стартиран от WebUI, използва отделната команда в `operations.py` и остава на `127.0.0.1`; за LAN използвайте BAT.

Ако `capture_mode.bat` вече работи, WebUI показва „Портът е зает извън WebUI“ и не предлага повторно стартиране или спиране на външния процес. Зает порт не доказва, че процесът е capture proxy. За управление през WebUI първо спрете ръчния capture с Ctrl+C в неговия прозорец. След инсталиране на capture пакетите рестартирайте библиотеката.

### Свързани приложения и външни препратки

`capture_links.js` е вграден в `auto_book_capture_bookmarklet.txt` чрез `tools/build_capture_bookmarklet.py`. Обходът открива връзки и iframe адреси в съдържанието и вложените конфигурации. Отваря HTML приложенията в отделен iframe с размер 1280 × 900, изчаква зареждането и превърта страницата; файловете се заявяват без изпълнение. Пояснителните страници и изображения в IZZI се включват като свързани ресурси; стандартните адреси към други уроци не се включват. Backslash адресите на издателя се нормализират.

`external_links.py` пази избраните адреси и зависимостите им в `state/lesson_links.json`. Proxy записва GET ресурсите от тези адреси и техните зависимости, разпознати чрез Referer, HTML или CSS. Проверява се наличието на годен body; липси създават `link-failed` и `lesson-incomplete`. Обходът опитва да заяви липсващите зависимости. Външните POST заявки не се записват. Analytics, локални адреси и нестандартни протоколи не се включват.

Архивираните външни страници се отварят през `/__host__/<host>/…`; абсолютните адреси към записаните домейни и кореновите ресурсни адреси се пренасочват локално. Не се обхождат безкрайно всички страници на външен сайт. Login, DRM, стрийминг, действия на потребителя, зависимости с неразпознаваем динамичен адрес и сайтове, които изискват жив backend, могат да останат недостъпни офлайн. Проверка на записаните файлове не доказва, че всички функции на външно приложение работят.

След обновяването заменете Firefox bookmark с новия текст и обходете засегнатите уроци отново при активен capture. HAR файловете се импортират чрез `import_har.bat`; каченият HAR не се добавя в GitHub.

### Подреждане на вече записани учебници

От компютъра със сървъра отворете учебника → „Подреди / преименувай / скрий“. Полетата „Име“, „Раздел“, „Оригинален номер“ и „Ред“ позволяват ръчно описание без нов capture. Еднаквите имена на раздел групират уроците под общо заглавие. Натиснете „Запази“.

„Предложи имена и раздели от архива“ използва `catalog_restore.py` за прочит на годните архивирани HTML страници, breadcrumbs и списъците с уроци. Показва предложение за имена, номера, раздели и ред, без запис и без интернет. Проверете предложението и натиснете „Запази“. При липсваща навигация разделите не могат да се възстановят надеждно: попълнете ги ръчно или направете нов capture. Настройките се пазят в `state/library_catalog.json`; архивът не се променя. Редакторът и автоматичното предложение са блокирани при LAN достъп.

### Допълване само на липсващите ресурси на учебник

В актуалния bookmarklet изберете всички раздели и уроци. В прозореца за избор режимът „Само липсващите ресурси“ е включен по подразбиране; бутонът го сменя на „Пълен повторен запис“. При първия режим proxy връща годните декодирани статични файлове от архива, вместо да ги изтегля отново. Липсващите, неуспешните и непълните записи се заявяват от оригинала. Обходът зарежда уроците, за да открие зависимостите им, и проверява изображения, медия, файлове и свързани приложения. Записите за вход и API заявките не се подменят с архивни данни.

Навигацията за избора на раздели се прочита от оригинала преди включването на режима. Статичните ресурси на отворената страница и тази навигация могат да се заявят отново. Режимът не открива промени в вече записан HTML; за обновяване на съдържанието използвайте пълен повторен запис. Непосетени действия, външни backend услуги и неизвестни ресурси остават за ръчна проверка. Режимът се изключва при завършване; при прекъснат обход изтича 10 минути след последния heartbeat или се нулира при нов обход/рестарт на proxy.

Обходът включва публикуваните (`status=2`) раздели и уроци, дори когато навигационното поле `isVisible` е 0. Disabled записите остават изключени. Повреден HTML с нулеви байтове не се използва от архива; частичен 206 отговор за навигацията се отчита като грешка, вместо да се приема за пълен списък.

Началната страница групира учебниците по класове във възходящ ред. Класът се определя първо от заглавието (цифри, думи или римски числа), после от името в каталога и текстовия етикет на класа. Числовото поле в каталога се използва само като резервен вариант, за да не замества ясно посочения клас. Учебниците без установен клас се показват в „Без определен клас“. Празните класове не се показват.

### Изтриване на учебник

На компютъра със сървъра отворете учебника → „Изтрий учебника“. Екранът показва името и броя на отделните архивни файлове за премахване; „Отказ“ връща към учебника. Спрете capture, после потвърдете „Изтрий учебника и съдържанието“. Изтриват се каталожният запис, локалните настройки и журнал на учебника, capture посещенията и принадлежащите му архивни записи и изключителни blobs. Споделените файлове и ресурсите с неясна принадлежност остават. Премахват се и съответните MP4 range части. Оригиналните HAR файлове се запазват. Изтриването е необратимо; пазете резервно копие на archive/state. LAN достъпът не позволява преглед или изпълнение на изтриването. `delete_book.py` изготвя предварителния списък и извършва премахването.

### Вътрешни препратки и YouTube

Обходът следва вътрешните връзки към пояснителни текстове, изображения и допълнителни ресурси в IZZI, както и вложените приложения. Стандартните `/DOS/<book>/<lesson>.html` препратки към други уроци са изключени. Навигационните header/nav/aside не се включват; повторените адреси и цикличните връзки не се обхождат повторно. За други уроци използвайте обичайния избор на уроци.

За YouTube изпълнете `install_youtube.bat` в Python средата, която използва capture. Инсталирайте Deno (или актуален Node.js) за извличането на YouTube и FFmpeg за комбиниране на звук и картина. Команди за Windows: `winget install --id DenoLand.Deno -e` и `winget install --id Gyan.FFmpeg -e`. Отворете нов терминал и рестартирайте capture, за да се използва обновеният PATH. `youtube_download.py` изтегля по едно публично видео, без playlist или browser cookies, и записва файла в `archive/youtube/<ID>.mp4`. Видеото се преизползва по ID. При наличен FFmpeg се избира MP4 до 720p с отделен звук; без него се опитва готов MP4 със звук. Неуспехите, включително липсващ формат или ограничения за достъп, се отчитат като непълен урок. Има срок 15 минути и лимит 250 MiB за готовия файл. YouTube понякога променя протокола; обновявайте yt-dlp чрез install_youtube.bat.

Проверявайте state/youtube/<ID>.log при грешка. Записаните стандартни YouTube връзки и iframe embeds отварят локален HTML5 плеър с поддръжка на seek и LAN. Компонентът `youtube-player` на IZZI се заменя с локален iframe плеър, като се запазват заглавието и описанието. Обходът извлича ID както от този компонент, така и от неговата JSON конфигурация. Други custom плеъри, които изискват YouTube API, може да се нуждаят от отделна адаптация. DRM, изискване за вход и други ограничения не се заобикалят. След обновяване сменете bookmarklet-а и направете нов обход.

### Бързодействие при локално зареждане

`archive_state.py` преизползва прочетените replay данни. При SQLite следи ревизията на базата и идентификатора на файла; при стар JSON следи размера, времето и идентификатора на файла. Нечетимият индекс се отчита като грешка, а не се прикрива със стар кеш. URL картата има индекс по канонични пътища; проверките за принадлежност към учебник и годност на body остават. Индексът за сглобени видеа и списъкът с външни домейни се преизползват. Писането при capture и редакция продължава да използва отделни свежи данни. Видеата и Range отговорите се изпращат на блокове до 1 MiB, без зареждане на целия файл в паметта. След обновяването рестартирайте библиотеката.

### Браузърен кеш на локалните ресурси

CSS, JavaScript, изображения, шрифтове, прикачени файлове и медия могат да се пазят в частния кеш на браузъра. Сървърът изпраща ETag и изисква проверка при повторно използване: непромененият ресурс получава 304 без повторно прехвърляне на body. Променените файлове се изпращат отново; премахнатите ресурси не се обслужват от стария кеш. Range/If-Range запазват seek поведението на видеата. Страниците за управление, HTML уроците и динамичните API отговори остават с no-store.

При разглеждане на локалната библиотека изключете Firefox DevTools „Disable Cache“, за да работи браузърният кеш. За capture от оригиналния сайт отново го включете. След обновяването рестартирайте библиотеката.

### Почистване на архива

Меню → „Почистване на архива“ (`/__cleanup__`) е достъпно само на компютъра със сървъра. `archive_cleanup.py` изготвя предварителен отчет за неизползваните хеширани blobs/assembled файлове и частите на проверено завършени видеа. Споделените и индексирани файлове се пазят. Готовите YouTube видеа и неразпознатите файлове се запазват консервативно. Индексите (SQLite или старият JSON формат) трябва да са четими и посочените bodies да съществуват; при проблем преместването е блокирано.

Показват се броят, размерът, категориите и първите 200 файла; „Изтегли пълния отчет“ дава JSON с целия списък. Недовършените видео части са изключени по подразбиране. За тях има изрична отметка и предупреждение за загуба на натрупаното изтегляне.

Спрете capture и импорта на HAR, генерирайте отчета и потвърдете преместването. При промяна на индексите или файловете след отчета е нужен нов отчет. Файловете се преместват в `state/cleanup_trash/<batch>` с manifest за възстановяване, без промяна на URL индекса. „Възстанови“ връща файловете само ако оригиналните им места са свободни; не презаписва ново съдържание. Това не освобождава място на диска.

„Изтрий окончателно…“ показва отделен отчет и изисква ново потвърждение. Тогава папката за възстановяване се изтрива необратимо и мястото се освобождава. Пазете отделно резервно копие на archive/state. Прегледът и всички действия за почистване са блокирани през LAN.

Новооткрити неизползвани файлове се запазват поне 5 минути след последното им създаване/изменение, за да не се премахнат тела, които още чакат записване в индекса. Те се виждат като запазени в пълния отчет.


### SQLite индекси и архивни подпапки

При първото стартиране на обновените `server.py`, capture proxy или HAR import индексите `state/url_map.json` и `state/books.json` се прехвърлят автоматично в `state/library.sqlite3`. Не се изтегля наново съдържание. Старите JSON файлове се запазват като резервно копие от момента на миграцията; след това **не са актуални индекси** и не трябва да се използват за диагностика или ръчно редактиране. Използвайте проверките от `checks/`. Нечетим или невалиден стар индекс блокира миграцията; непълна/повредена база не се прикрива с празна библиотека.

`archive_db.py` управлява транзакциите и индексира точния URL, каноничния ресурсен път и урока. Capture обновява само засегнатия URL или учебник; едновременни записвания към един URL се обединяват в транзакция. Сървърът намира кандидатите с SQL, без да прочита целия URL индекс за всяка заявка. HAR import, поправката и изтриването на учебник, почистването и диагностиката използват активния формат. Журналите, настройките на изгледа, capture диагностиката и manifest файловете остават отделни JSON/JSONL файлове.

`archive_storage.py` определя новото разпределение: `archive/blobs/ab/cd/<64-символен-хеш>.png` и `archive/assembled/ab/cd/<хеш-на-URL>.mp4`. Новите capture/HAR bodies и сглобени видеа се записват така автоматично. Старите плоски пътища продължават да работят. Адресите на уроците и ресурсите в браузъра не се променят. YouTube файловете запазват собствената си папка.

За разпределяне и на вече записаните файлове спрете библиотеката, capture, HAR import и останалите операции по архива. Направете резервно копие на `archive` и `state`. `migrate_archive.bat` (или `py migrate_archive.py`) подготвя SQLite индекса и показва предварителен отчет; не копира ресурсните файлове. Пълният отчет е `state/storage_migration_report.json`, с брой, допълнително нужно дисково място и липсващи индексирани bodies. За прилагане изпълнете:

```powershell
py migrate_archive.py --apply
```

`migrate_archive.py` проверява свободното място и конфликтите, запазва последователно SQLite резервно копие и копия на помощните JSON данни в `state/storage_backups/<дата-час>/`, копира и сравнява SHA-256 на файловете, след което обновява пътищата в активните индекси и помощните JSON данни. Оригиналните ресурсни файлове остават на място, затова прекъсната миграция може да се повтори и старите препратки остават четими. При липсващи bodies или различно съдържание на целевото място прилагането се блокира. Отчетът и копирането не изискват интернет.

След това стартирайте библиотеката и проверете уроци, изображения, прикачени файлове и видео с seek. Едва след проверката използвайте **Меню → Почистване на архива**, за да преместите старите неизползвани копия и по желание да ги изтриете окончателно. Миграцията временно изисква място за допълнителни копия.

При преместване на друг компютър прехвърляйте целите `archive` и `state` при спрени процеси. SQLite може да има `library.sqlite3-wal` и `library.sqlite3-shm`; не копирайте само основния файл от работеща библиотека. `archive_db.backup` се използва от миграцията за последователно резервно копие. За връщане от него спрете всички процеси, запазете текущото `state`, върнете архивната `library.sqlite3` и съответните помощни JSON копия, като премахнете остатъчните WAL/SHM файлове на старата база. Оригиналните resource bodies са запазени до изричното почистване.


### Автоматично довършване на IZZI MP4 видеа

**Меню → Недовършени видеа** (`/__videos__`) проверява действително наличните файлове и range части, показва процента, размера и бутон „Довърши“ за всяко видео. „Довърши всички“ обработва последователно всички открити недовършени IZZI MP4 адреси. Има и „Спри изтеглянето“; текущата заявка може да приключи, а натрупаните части се запазват за следващ опит. Страницата, статусът и командите са достъпни само на компютъра със сървъра; LAN библиотеката остава без административни функции.

Нужни са интернет и стартиран обновен capture proxy. `video_resume.py` изтегля липсващите диапазони на части до 4 MiB през proxy, с TLS проверка чрез сертификата в `%USERPROFILE%\.mitmproxy\mitmproxy-ca-cert.pem`. Наличните архивни 206 bodies могат да се използват за възстановяване на липсващи `.part` файлове. `range_assembler.py` сглобява и регистрира пълното видео в SQLite едва след пълно покритие. Ако сайтът не поддържа Range и връща 200, може да бъде изтеглен целият файл. Запазва се съществуващият лимит от 250 MiB за видео. YouTube видеата се изтеглят чрез отделния YouTube механизъм. Поточни HLS/DASH видеа не се включват в този MP4 отчет.

За защитено видео първо го отвори в оригиналния урок във Firefox с правилния профил, активен capture proxy и Disable Cache. Proxy запомня Cookie/Authorization/Referer/Origin/User-Agent **само в паметта и само за точния URL**, максимум за 256 видеа. Те не се записват в state/archive. След рестарт на capture при нужда отвори видеото отново. Отказ 401/403, липсващ сертификат, невалиден диапазон или липса на напредък се показват в лога; задачата не обявява видеото за завършено. Пренасочванията се ограничават до HTTPS IZZI MP4 адреси.

ETag/Last-Modified се използва за If-Range; при променен размер или известен идентификатор на версията старото покритие не се смесва с новите части. Изчаквай приключването, преди да спираш proxy или да мигрираш/почистваш архива. `checks/media_replay_check.py` насочва към новата страница, а `checks/test_video_resume.py` проверява довършването, session scope, спирането, променена версия и локалния контрол.
