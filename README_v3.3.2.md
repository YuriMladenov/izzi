# IZZI Offline Library v3.3.2 — Forced Fresh Capture

Full upgrade over v3.3.1. Keeps the working replay, decoded resources, MP4 range
assembler, media source mapping, and assembled-media resolver.

## Why this version exists
v3.3.1 proved that Auto Book Capture traversed all lessons, but many assets were seen
only as HTTP 304. A 304 has no response body to archive. v3.3.2 makes Capture Mode
request fresh representations by removing `If-None-Match` and `If-Modified-Since`
from ordinary IZZI GET/HEAD requests and adding no-cache request directives.

It does NOT remove cookies, authorization, or access-control data and does not automate login.

## Strict media context
The bookmarklet now sends a local `lesson-active` heartbeat while each lesson iframe is
open. The proxy intercepts this synthetic control URL locally; it is not forwarded to IZZI.
MP4 mapping uses the real lesson Referer first and the short-lived active lesson context
only as a fallback. This avoids the old global/index media fallback.

## Recommended upgrade run
1. Copy existing `archive` and `state` from v3.3.1 into this package.
2. Run `reset_capture_diagnostics.bat`.
   This removes only observation/session diagnostics, NOT archive/media files.
3. Run `capture_mode.bat`.
4. Firefox through the capture proxy; log in normally.
5. Open the book contents page.
6. F12 > Network > Disable Cache (still recommended).
7. Run the bookmarklet from `auto_book_capture_bookmarklet.txt`.
8. Wait for all lessons to finish.
9. Manually activate videos/exercises/downloads that require real user interaction.
10. Stop Capture Mode and restore Firefox's normal proxy setting.

Then run:
- `fresh_capture_report.bat`
- `book_readiness_report.bat`
- `missing_assets_report.bat`
- `assembled_media_report.bat`

A successful fresh pass should dramatically reduce 304-only resources and missing bodies.
Some resources may legitimately remain unavailable or be loaded only after manual interaction.

## Privacy
Do not publish archive/state folders. Captured application responses can contain account
or application metadata.
