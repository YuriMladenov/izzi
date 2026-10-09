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
| `repair_library.bat` | Възстановяване на каталожни данни | Презаписва books.json от наличните HTML записи и стария каталог |
| `build_recovery_manifest.bat` | Подготовка на 304-only recovery | Презаписва recovery_manifest.json |
| `prepare_recovery.bat` | Същата подготовка с напомняне | Същият manifest; не стартира browser recovery |
| `reset_capture_diagnostics.bat` | Съзнателно започване на нова диагностична история | Изтрива три diagnostic state файла |
| `clear_missing.bat` | Изчистване на историческия missing log | Изтрива missing_resources.jsonl |
| `run_all_checks.bat` | Общ преглед на тестовете и архива | Изпълнява checks; HTTP probes могат да добавят missing-log записи |

### `install_capture.bat` — зависимости за записване

Изпълнява `py -m pip install -r requirements-capture.txt`. Декларацията допуска mitmproxy версии `>=11,<13`; облачната среда е проверена с 12.2.3. BAT не създава отделна virtual environment: пакетите се инсталират в Python средата, избрана от `py`. Нужен е интернет за изтеглянето им. Командата не настройва Firefox proxy, не инсталира автоматично browser доверие към сертификата и не записва учебници. При успешно инсталиране `mitmdump` трябва да е достъпен в PATH; иначе `capture_mode.bat` ще спре с обяснение.

### `capture_mode.bat` — capture proxy

Изпълнява `mitmdump --listen-host 0.0.0.0 -p 8877 -s capture_addon.py` и остава отворен, докато proxy работи. Firefox трябва да използва HTTP/HTTPS proxy `127.0.0.1:8877`, да доверява mitmproxy сертификата и да е логнат нормално в IZZI. Включете Disable Cache, отваряйте оригиналните уроци и пускайте необходимите медии.

Addon пази bodies в `archive`, URL записи в `state/url_map.json`, каталожни данни в `state/books.json`, media mappings и observations. При MP4 Range заявки натрупва части и регистрира завършена медия само след проверено пълно покритие. Контролните събития от bookmarklet се обработват локално. Командата сама не обхожда учебника, не настройва proxy в браузъра и не автоматизира login. Спрете с Ctrl+C, след което възстановете нормалния Firefox proxy. Запазените данни остават на диска.

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

Извиква `repair_library.py`: преглежда директните lesson URL-и за основния source host в URL map, чете наличните HTML blobs и извлича имена на учебници и уроци. Презаписва `state/books.json`, като запазва старите book/lesson записи, които не могат да се възстановят. Показва броя възстановени lessons.

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
| `state/url_map.json` | URL → response records → blob ключове; имена на файлове сами по себе си не заменят този индекс |
| `state/books.json` | Оригинални book/lesson имена, ID-и и paths |
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

Proxy архивира само `*.izzi.digital`, въпреки че друг browser traffic може да преминава през него. Login остава ръчен. YouTube, DRM и други външни услуги не се превръщат автоматично в офлайн медия. Познатите YouTube loaders получават локален празен script, а embeds — съобщение за недостъпна външна медия.

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
