# IZZI v3.4.2 cloud setup

Source: uploaded `IZZI_Offline_Library_v3.4.2_Canonical_Replay_Hotfix_FULL.zip`, imported at the repository root.
Validated with Python 3.12. Run `bash tools/setup.sh` from this checkout to create `.venv` on Linux. Capture dependency: mitmproxy 12.2.3; resolved versions retained in `capture-requirements.lock`.

Replay uses the Python standard library. `requirements.txt` contains prose rather than pip requirements; do not pass it to pip. Application Python source is unchanged from ZIP; development helpers and ignore rules were added. No real capture data was supplied or committed.

Verified: dependency consistency; existing strict media-map contract; startup and root HTTP response; capture addon startup and forwarding to local replay; isolated range assembly including overlaps and incomplete coverage rejection.

Synthetic HTTP integration: 5 passed (root, lesson HTML with captured :443 host, canonical CSS alias, JS, WOFF2 MIME), 1 failed (complete MP4 Range). Run `.venv/bin/python tools/validate_replay.py`. It starts and stops a server on a temporary port, uses temporary synthetic state, never touches real archive/state, and exits nonzero on failures. The bytes exercise HTTP transport, not actual video decoding.

Confirmed repository defect: `assembled_media.resolve()` returns `(item, match_kind)` or `(None, None)`. `server.H.archive()` treats this as a file path and crashes with TypeError at server.py:272. The synthetic assembled MP4 request closes without an HTTP response. Resolver result handling needs a separate code fix. The `(None, None)` result is also truthy; this branch cannot safely treat it as a missing result.

Existing smoke test checks only root with absent state. Its 1-pass result does not validate a captured library. Archive self-test was not counted as validation because no archived records exist. Real-record replay, readiness counts, Windows launchers, authenticated Firefox capture, and browser media behavior remain unverified.

No online capture, login, certificate trust installation in Firefox, or archive publication was performed. Capture proxy process was stopped after validation. Replay can be started with `.venv/bin/python -u server.py` from the repository root.

The synthetic integration test deliberately exits nonzero for the confirmed MP4 defect. It is a diagnostic baseline, not a passing regression gate. `requirements.txt` is unchanged upstream prose; only `requirements-capture.txt` or the tools lockfile should be installed with pip.
