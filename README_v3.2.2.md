# IZZI Offline Library v3.2.2 — Media Source Mapping

Focused on the remaining case where the IZZI video component is alive but its media source
collapses to the lesson URL plus `#`.

## What it adds
Capture records a persistent `state/media_map.json`:
lesson -> captured MP4 URL -> any block-like identifiers visible in request/referrer context.

Replay injects a small offline-only media shim into captured lesson HTML. It watches video/audio
elements. It does nothing when a valid source already exists. If a player has an empty source,
`#`, or the lesson HTML as its media source, it supplies a captured media URL belonging to that
lesson. The existing v3.2.1 server then serves the verified assembled MP4 with HTTP Range/206.

## Important
An old URL map does not contain the original request Referer, so v3.2.2 cannot reliably reconstruct
lesson-to-video relationships from old archive metadata alone. Do one normal recapture of the
lesson while authenticated:
1. Start `capture_mode.bat`.
2. Firefox F12 -> Network -> Disable Cache.
3. Reload the lesson.
4. Play each IZZI-hosted video once so its MP4 request occurs.
5. Stop capture.
6. Run `media_map_report.bat`.
7. Start `start_library.bat` and test offline.

For a lesson with two videos, the report should list two media URLs under that lesson.
During local replay Firefox Console will print `[IZZI OFFLINE MEDIA MAP]` only when a broken/empty
player source needed fallback mapping.

The fallback is deliberately conservative: it never replaces an already-valid media source.
External YouTube/DRM media are not converted into offline files.
