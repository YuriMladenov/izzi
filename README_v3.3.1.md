# IZZI Offline Library v3.3.1 — Capture Completeness Fix

This is a full upgrade over v3.3 and retains the working v3.2.3 MP4 assembly/resolver.

## Fixes
1. Strict lesson-specific media mapping.
   MP4 mapping is accepted only when the captured request has a Referer identifying
   `/DOS/<book>/<lesson>.html`. There is no global/index fallback, preventing media from
   one lesson being injected into another.

2. Capture completeness observation.
   The capture proxy records IZZI requests/statuses/referers in
   `state/capture_observed.json`, including failed/static requests.

3. Readiness categories.
   `book_readiness_report.bat` prints READY or INCOMPLETE using:
   traversal completion, strict media mapping, complete assembled MP4s, and observed
   missing important assets.

4. Missing asset report.
   `missing_assets_report.bat` lists missing fonts and important JS/CSS/JSON/images,
   including `search-index.js` when observed but unavailable.

## Upgrade
Copy your existing `archive` and `state` folders into this package. Existing old media
map entries are not treated as strict unless they were captured by this version, so do
one normal recapture of the affected lessons/book with v3.3.1.

Run:
- `capture_mode.bat`
- Firefox through the configured capture proxy, logged in normally
- F12 > Network > Disable Cache
- run the v3.3 Auto Book Capture bookmarklet from the book contents page
- manually activate media/exercises that only load after user interaction
- stop capture and restore normal Firefox proxy

Then:
- `book_readiness_report.bat`
- `missing_assets_report.bat`
- `assembled_media_report.bat`

Finally run `start_library.bat` and test the lessons offline.

## Notes
Source-map 404s and browser-specific CSS warnings are not treated as readiness failures.
The capture process does not automate login or bypass access controls.
