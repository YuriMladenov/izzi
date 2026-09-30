# IZZI Offline Library v3.2.1 — Media Replay Fix

Focused upgrade over v3.2. It does not change the working decoded JS/CSS capture.

## Changes
- Complete assembled MP4 records keep highest replay priority.
- Incomplete captured HTTP 206 chunks are never served as complete videos.
- `.mp4` is forced to `Content-Type: video/mp4` when needed.
- Local server supports browser `Range` requests and replies with:
  - `206 Partial Content`
  - `Accept-Ranges: bytes`
  - correct `Content-Range`
  - correct `Content-Length`
- Absolute and protocol-relative `bg.izzi.digital` URLs in decoded HTML/JS/CSS/JSON are rewritten to local replay.
- Media requests are logged as `[MEDIA REPLAY]`.
- Response header `X-IZZI-Replay` makes range diagnostics easy.

## Upgrade
This is a full package. To retain your archive, copy your existing `archive` and `state`
folders from v3.2 into this folder before starting it.

## Check
1. Run `media_replay_check.bat`.
2. Start `start_library.bat`.
3. Open the lesson and play its video.
4. Server should show `[MEDIA REPLAY] ... range=bytes=...`.
5. Firefox Network should show the MP4 request as `206` and `Content-Type: video/mp4`.

For an exact server test, copy the LOCAL MP4 request URL from Firefox Network and run
`test_mp4_range.bat`, then paste that URL. Expected result: `PASS`.

A `style.css.map` 404 is only a developer source-map issue and does not affect lesson playback.
A media attempt whose URL is literally the lesson URL plus `#` indicates an empty placeholder
source in the lesson; it is not itself the captured MP4 request. The actual MP4 request is what
must be checked in Network.
