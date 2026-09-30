# IZZI Offline Library v3.2 — Replay Fixed

This is a complete package: HAR import, local library/replay server, Firefox capture proxy,
MP4 byte-range assembly, reports and diagnostics.

## Critical v3.2 fix
Older Capture Mode stored `flow.response.raw_content`. For gzip/Brotli encoded JS/CSS/HTML,
that can preserve compressed transport bytes. The local server then sent those bytes without
the original Content-Encoding, causing Firefox errors such as `illegal character U+FFFD`.

v3.2 stores mitmproxy's decoded `flow.response.content` for normal resources.
MP4 HTTP 206 ranges remain exact byte ranges and are assembled only after 100% verified coverage.

## First use / upgrade from an older library
1. Keep a backup of your old library.
2. You may copy your existing `archive` and `state` folders into this v3.2 folder.
3. Run `install_capture.bat` if mitmproxy is not installed.
4. Start `capture_mode.bat`.
5. Firefox proxy: HTTP/HTTPS `127.0.0.1`, port `8877`; trust the mitmproxy certificate as before.
6. Open the IZZI lesson normally while authenticated.
7. Open F12 > Network and enable **Disable Cache**.
8. Press Ctrl+Shift+R. This is required to replace old compressed JS/CSS captures with decoded v3.2 captures.
9. Exercise the lesson/media you want available offline.
10. Stop capture with Ctrl+C and restore Firefox's normal proxy setting.
11. Run `inspect_blobs.bat`. Ideally `Looks compressed/corrupt: 0` for the newly recaptured lesson.
12. Run `start_library.bat` and open http://127.0.0.1:8765/

## Replay selection
The v3.2 server prefers:
- verified assembled complete media;
- GET 200 bodies;
- decoded v3.2 captures;
and avoids treating an incomplete 206 chunk as a complete video.

The server prints `[REPLAY]` with the selected blob, source and decoded status.

## Notes
External services such as YouTube are not automatically made offline.
The proxy only archives `*.izzi.digital` responses, although other browser traffic still passes
through the configured proxy. Restore the browser proxy after capture.
