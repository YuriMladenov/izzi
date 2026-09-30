# IZZI v3.4.2 Canonical Replay Hotfix

No recapture is required.

Fixes two replay regressions:
1. Lesson/static lookup now indexes the actual URL map by canonical IZZI path and
   parsed hostname. It no longer fails merely because a captured URL has a host/port
   variation or because static resources appear with/without `/DOS/<book>/`.
2. The assembled MP4 resolver is actually called before normal URL-map replay.
   v3.4 imported it but did not use it.

Normal replay also applies explicit MIME overrides for fonts/media.

Verification:
- copy the existing `archive` and `state`;
- run `replay_map_diagnostic.bat`;
- run `replay_self_test.bat`;
- start the server;
- run `local_replay_smoke_test.bat`.

If a lesson still returns 404, send the output of `replay_map_diagnostic.bat` plus
the server console lines around `[MISS]`. Do not recapture first.
