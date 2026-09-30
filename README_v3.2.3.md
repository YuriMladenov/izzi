# IZZI Offline Library v3.2.3 — Assembled Media Resolver

This release fixes the state seen after v3.2.2:
- media source mapping succeeds;
- one MP4 can return 409 because a partial 206 record is selected;
- another can return 404 because the exact query/version URL does not match;
- some `<source>` elements declare MP4 URLs as video/ogg, video/avi, video/mpeg or application/octet-stream.

## Resolver order
For every local `.mp4` request the server now checks complete assembled media BEFORE the normal
URL map:
1. exact original URL including query;
2. same host + path, ignoring query/version;
3. local path mapped back to bg.izzi.digital.

Only records explicitly marked `complete` with a real archive file are eligible. `assembled_ranges`
gets preference. If found, the server prints `[ASSEMBLED MEDIA]` and serves that file directly with
`Content-Type: video/mp4`. The existing Range handler returns proper HTTP 206.

## HTML normalization
Captured lesson HTML is normalized so a `<source>` whose URL ends in `.mp4` is declared
`type="video/mp4"`. This prevents Firefox from rejecting a valid MP4 because the page labels it
video/ogg, video/avi, video/mpeg or application/octet-stream.

## Upgrade / test
Copy your existing `archive` and `state` folders into this full package.

Run:
- `assembled_media_report.bat` — should list the two verified complete MP4s.
- `start_library.bat`
- in another window: `test_all_assembled.bat`

Expected HTTP test:
`PASS 206 bytes 0-1023/<total> http://127.0.0.1:8765/...mp4?...`

Then open the lesson. Expected server log:
`[ASSEMBLED MEDIA] exact|path|local-path archive/assembled/...mp4 /DOS/...mp4`
followed by HTTP 206 requests when Firefox seeks/plays.

The source-map CSS 404 and compatibility CSS warnings are unrelated to media playback.
