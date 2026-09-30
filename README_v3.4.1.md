# v3.4.1 Replay Resolver Hotfix

This hotfix addresses the v3.4 situation where `replay_self_test` passes but local HTTP
requests return 404.

Cause: IZZI resources can be captured under both `/datastore/...` / `/profil/...` and
`/DOS/<book>/datastore/...` / `/DOS/<book>/profil/...`. The old resolver compared paths
literally.

v3.4.1 adds a conservative logical-path alias resolver:
- exact URL remains first choice;
- exact host/path ignoring query remains second;
- only static `/datastore`, `/profil`, and `/_nuxt` resources normalize the DOS prefix;
- lesson HTML keeps its book/lesson identity, with a unique lesson-ID fallback.

The archive blobs are unchanged and no recapture is required.

The final readiness report now reads `capture_session.json` using its real `visits`
array and unions lesson IDs from books.json, URL-map lesson bodies, and capture visits.
This prevents the false `0 / N` traversal result seen in v3.4.

Use:
1. copy existing `archive` and `state`;
2. run `replay_self_test.bat`;
3. run `final_readiness_report.bat`;
4. start `start_library.bat`;
5. run `local_replay_smoke_test.bat`.
