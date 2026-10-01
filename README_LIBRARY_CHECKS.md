# Readiness, липсващи ресурси и локален журнал

## Windows

След обновяване спрете стария capture/replay процес и стартирайте новия от същата папка с вашите archive/state. Пазете резервно копие.

1. `test_library_workflow.bat` — 12 regression теста с временни данни; не използва личния архив и не изисква активен сървър.
2. `final_readiness_report.bat` — readiness на реалния archive/state. `book_readiness_report.bat` използва същите правила.
3. `missing_assets_report.bat` — липсващи известни ресурси и отделни `UPSTREAM 404 WARNING` записи.
4. `progress_report.bat` — статистика за локалния request journal; не показва request bodies, cookies или tokens.

Изпратете броячи, `FAILURE` редове и имената на state schema грешки за локална диагностика. Не публикувайте archive/state/HAR, raw journal bodies или credential query parameters.

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
