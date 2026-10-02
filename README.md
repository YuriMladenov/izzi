# IZZI Offline Library

Локална библиотека за архивирани IZZI уроци: Firefox capture proxy, HAR import, offline replay, MP4 byte-range assembly, отчети и диагностика. Това е общото ръководство за v3.4.2 и последващите поправки; историята на по-старите версии е в края.

## Инсталиране и обновяване (Windows)

Необходими са Python с командата `py`, Firefox и Git за обновяване от GitHub.

```powershell
git clone https://github.com/YuriMladenov/izzi.git
cd izzi
```

За capture изпълнете `install_capture.bat` (използва `requirements-capture.txt`). Локалният replay не изисква работещ capture proxy. `requirements.txt` съдържа пояснения, а не pip списък.

При обновяване спрете capture и replay процесите, запазете резервно копие на `archive` и `state`, след което изпълнете `update_project.bat` или `git pull --ff-only origin main`. BAT файлът изисква branch `main` и чист working tree; при локални промени спира, без reset/clean. При обновяване от ZIP запазете съществуващите `archive` и `state` до `server.py`. Не смесвайте данните от различни инсталационни папки.

## Capture на урок

1. Стартирайте `capture_mode.bat`.
2. В Firefox задайте HTTP/HTTPS proxy `127.0.0.1:8877` и доверете mitmproxy сертификата.
3. Влезте нормално в IZZI и отворете урок, до който имате достъп.
4. В F12 → Network включете **Disable Cache**, презаредете с Ctrl+Shift+R.
5. Пуснете видеата и активирайте упражненията/изтеглянията, които искате офлайн.
6. Спрете capture с Ctrl+C и възстановете нормалните proxy настройки на Firefox.
7. Стартирайте `start_library.bat` и отворете `http://127.0.0.1:8765/`.

Proxy архивира само `*.izzi.digital`, въпреки че друг browser traffic може да преминава през него. Login остава ръчен. YouTube, DRM и други външни услуги не се превръщат автоматично в офлайн медия. Познатите YouTube loaders получават локален празен script, а embeds — съобщение за недостъпна външна медия.

Capture пази декодирани HTML/JS/CSS bodies, вместо gzip/Brotli transport bytes. При архив от преди v3.2 с `illegal character U+FFFD` използвайте нормален fresh capture на засегнатия урок; `inspect_blobs.bat` проверява за компресирани/повредени blobs. HAR import е достъпен чрез `import_har.bat`.

## Автоматичен обход на учебник

При активен capture отворете съдържанието на учебника във Firefox. Създайте bookmark с целия текст на `auto_book_capture_bookmarklet.txt` като URL, стартирайте го и потвърдете обхода. Дръжте таба отворен до съобщението за завършване. Bookmarklet посещава same-book lesson links в iframe и изчаква около 9 секунди след load.

Автоматичният обход не активира всички lazy ресурси. След него пуснете ръчно видеата, упражненията и downloads. Контролните `/__offline_capture__/event` заявки се прихващат локално; start/done запис без HTML body не доказва наличен урок.

Capture премахва conditional cache headers и добавя no-cache directives за обичайни IZZI GET/HEAD заявки. Реалният Referer има приоритет при lesson/media mapping; краткотрайният `lesson-active` контекст служи като fallback. Няма глобално прехвърляне на медия между уроци.

## Възстановяване на 304-only ресурси

Първо проверете диагностиката: 304 не е проблем, ако има друг годен body за същия ресурс. При действителен 304-only gap:

1. Запазете `archive` и `state`; изпълнете `build_recovery_manifest.bat` след нормален capture.
2. Създайте Firefox bookmark от целия `cache_bust_recovery_bookmarklet.txt`.
3. Докато сте логнати в IZZI и capture е активен, изпълнете bookmark и изчакайте завършване.
4. Проверете `recovery_report.bat`, `fresh_capture_report.bat` и `final_readiness_report.bat`.

Recovery използва само вече наблюдавани URL-и, изключва MP4/audio и добавя `__izzi_offline_recover`; proxy премахва маркера при индексиране. Не открива непосетено съдържание. `reset_capture_diagnostics.bat` премахва observation/session diagnostics; използвайте го само когато съзнателно започвате нов диагностичен обход, а не като поправка за липсващ HTML.

## Проверки и диагностика

| Команда | Предназначение |
| --- | --- |
| `validate_replay.bat` | 22 synthetic HTTP проверки; не валидира личния архив |
| `test_library_workflow.bat` | 18 regression теста с временни данни |
| `test_media_contract.bat` | Media mapping/server API contract |
| `final_readiness_report.bat`, `book_readiness_report.bat` | Пълнота на текущия archive/state |
| `missing_assets_report.bat` | Известни пропуски и origin 404 warnings |
| `lesson_diagnostic.bat` | HTML записи/blobs за 1408782 и 1408803; приема друг URL като аргумент |
| `asset_diagnostic.bat`, `font_diagnostic.bat` | Годни image/font bodies |
| `replay_map_diagnostic.bat`, `replay_self_test.bat` | URL map и archive integrity |
| `local_replay_smoke_test.bat` | HTTP проверка при работещ replay server |
| `media_map_report.bat`, `assembled_media_report.bat` | Lesson/media mapping и завършени MP4 |
| `media_replay_check.bat`, `test_all_assembled.bat` | Media replay диагностика |
| `test_mp4_range.bat` | Range тест с локален MP4 URL от Firefox Network |
| `capture_session_report.bat`, `fresh_capture_report.bat` | Обход и fresh capture статистика |
| `progress_report.bat` | Summary на локалния журнал |

Пример за конкретен ресурс:

```powershell
py tools\asset_diagnostic.py "/__host__/api.izzi.digital/път/до/картинка.png"
py tools\lesson_diagnostic.py "/DOS/1408736/1408782.html"
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
.venv/bin/python tools/validate_replay.py
.venv/bin/python tools/test_library_workflow.py
.venv/bin/python tools/test_replay_html.py
```

Последната проверка: 22 HTTP + 18 workflow + 10 HTML/runtime теста са успешни; един runtime тест използва Node.js. Тестовете работят с временни synthetic данни, не с личния archive/state. Chromium проверката изтече по timeout преди достигане на test server; browser rendering не е потвърдено за всички последващи поправки. Потребителят потвърди Windows offline video/seek/navigation и възстановена PNG; конкретните липсващи lesson bodies остават за локална диагностика.

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
