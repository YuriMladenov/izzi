# IZZI Offline Library v3.3 — Auto Book Capture

Built on v3.2.3 (working decoded assets, media mapping, MP4 range assembly, assembled-media resolver).

## Scope
Auto Book Capture does NOT automate login and does not bypass access controls. Use Firefox normally,
already authenticated to content you can access. The capture proxy only archives IZZI resources the
browser actually requests.

## Setup / upgrade
Copy your existing `archive` and `state` folders from v3.2.3 into this package.
Use the same mitmproxy certificate/proxy setup as before.

1. Run `capture_mode.bat`.
2. Firefox: use the proxy, sign in normally, and open the book's contents/index page.
3. F12 -> Network -> Disable Cache.
4. Create/run a bookmark whose URL is the entire contents of `auto_book_capture_bookmarklet.txt`.
5. Confirm the traversal. A small iframe visits each same-book `/DOS/<book>/<lesson>.html` link found
   on the current contents page and waits about 9 seconds after load.
6. Keep the contents tab open until the completion alert.

## Important limitation
Some videos, exercises, downloads or lazy assets are requested only after a real user interaction.
The automatic traversal cannot know which interactions are pedagogically meaningful and deliberately
does not synthesize clicks. After traversal, manually open/play the interactive items you want offline.
MP4s requested through normal playback continue to be assembled by the v3.2.x range assembler.

## Reports
After capture:
- `capture_session_report.bat` — traversal history.
- `book_readiness_report.bat` — lessons, media mappings, complete assembled MP4 coverage.
- `assembled_media_report.bat` — complete MP4 resolver index.
- `media_map_report.bat` — lesson-to-media mappings.

Then stop capture, restore Firefox's normal proxy setting, run `start_library.bat`, and test offline.

## Safety/privacy
The synthetic `/__offline_capture__/event` requests are intercepted locally by mitmproxy and are not
forwarded to IZZI. Do not publish the archive/state directories: captured application responses can
contain account/application metadata.
