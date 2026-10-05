# IZZI v3.4.2 cloud setup

Source: uploaded `IZZI_Offline_Library_v3.4.2_Canonical_Replay_Hotfix_FULL.zip`, imported at the repository root.
Validated with Python 3.12. Run `bash tools/setup.sh` from this checkout to create `.venv` on Linux. Capture dependency: mitmproxy 12.2.3; resolved versions retained in `capture-requirements.lock`.

Replay uses the Python standard library. `requirements.txt` contains prose rather than pip requirements; do not pass it to pip. The MP4 resolver result handling in `server.py` has been corrected after importing the ZIP; development helpers and ignore rules were added. No real capture data was supplied or committed.

Verified: dependency consistency; existing strict media-map contract; startup and root HTTP response; capture addon startup and forwarding to local replay; isolated range assembly including overlaps and incomplete coverage rejection.

Synthetic HTTP integration: 22 passed, 0 failed. Run `.venv/bin/python checks/validate_replay.py`. It starts and stops a server on a temporary port, uses temporary synthetic state, never touches real archive/state, and exits nonzero on failures. Checks cover root, lesson HTML with captured :443 host, canonical CSS alias, JS, WOFF2 MIME, assembled MP4 Range (including canonical DOS alias and query variation), normal captured MP4 fallback, HEAD, full-body GET, seek and suffix ranges, invalid range rejection, incomplete media rejection, and missing media. Additional checks cover font record selection, image API/BG alias selection, preserved upstream 404, invalid font rejection, publication isolation, and local external API response. The bytes exercise HTTP transport, not actual video decoding.

Fixed repository defect: `assembled_media.resolve()` returns `(item, match_kind)` or `(None, None)`. `server.H.archive()` now unpacks the result, tests the item for a match, and constructs the file path from `ARCHIVE_DIR / item["record"]["key"]`. Previously it passed the tuple to `Path()` and crashed, including on misses. Canonical fallback now runs when the resolver returns no item. Complete assembled media takes precedence over incomplete captured chunks; absent assembled media falls back to normal URL-map lookup.

Existing smoke test checks only root with absent state. Its 1-pass result does not validate a captured library. Archive self-test was not counted as validation because no archived records exist. Real-record replay, readiness counts, Windows launchers, authenticated Firefox capture, and browser media behavior remain unverified.

No online capture, login, certificate trust installation in Firefox, or archive publication was performed. Capture proxy process was stopped after validation. Replay can be started with `.venv/bin/python -u server.py` from the repository root.

The synthetic integration test is a passing regression gate for the MP4 contract fix. Real archive replay and browser video playback still need validation with authorized private capture data. `requirements.txt` is unchanged upstream prose; only `requirements-capture.txt` or the tools lockfile should be installed with pip.

Subsequent replay changes and Windows checks are documented in `README.md`. HTML and media shim runtime tests: `.venv/bin/python checks/test_replay_html.py` (10 passed with Node.js available). Chromium browser rendering checks timed out before reaching the local fixture server; do not claim browser validation for the subsequent changes. User confirmed the earlier MP4 fix on Windows offline, including seek and navigation. Real font/image archive resolution remains unverified until local diagnostics are supplied.

Later user diagnostics confirmed usable Regular/Bold WOFF2 bodies and successful capture/resolution/display of a previously missing PNG. Readiness/journal/multi-book changes are documented in `README.md`; run `.venv/bin/python checks/test_library_workflow.py` (26 tests). Added verified full-range 206 replay, atomic JSON state writes, explicit state errors, current missing-resource filtering and lesson record diagnostics. Progress scope was explicitly limited to local journal and diagnostics; upstream progress restoration is not implemented. Readiness counts and real second-book behavior must still be checked against the user's private data.
