# IZZI Offline Library v3.3.2.1 Hotfix

Fixes the v3.3.2 replay crash caused by an API mismatch: `lesson_media()` returned
URL strings while `server.py` expected media dictionaries and called `.get("url")`.

The hotfix restores media record dictionaries and makes `server.py` defensive against
malformed/legacy media entries.

Forced Fresh Capture, active-lesson context, strict lesson mapping, decoded capture,
MP4 range assembly/resolver, and archive/state formats are unchanged.

No recapture is required for this NET_RESET fix.

Upgrade: copy your current `archive` and `state` into this package, or replace
`media_mapping.py` and `server.py` in v3.3.2.

Run `test_media_contract.bat`, then `start_library.bat`.
Expected test result:
PASS: media_mapping/server contract is compatible.
