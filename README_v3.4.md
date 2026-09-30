# IZZI Offline Library v3.4 — Final Offline Replay

Built on v3.3.3 Cache-Bust Recovery. Existing `archive` and `state` are reusable.

## What v3.4 changes
- Keeps v3.3.3 capture/recovery and the assembled MP4/Range replay path.
- Adds explicit Firefox-friendly MIME handling for fonts, JS/CSS, SVG, JSON, audio/video and WASM.
- Adds a final readiness report that separates archive failures from resources that were already HTTP 404 on the original site.
- Adds archive integrity and local HTTP smoke tests.
- Does not fabricate upstream-missing assets.

## Final verification
1. Copy your existing `archive` and `state` into this v3.4 folder.
2. Run `replay_self_test.bat`.
3. Run `final_readiness_report.bat`.
4. Run `start_library.bat`.
5. While the server is running, run `local_replay_smoke_test.bat`.
6. Open several lessons and test video, exercises, glossary and navigation.

Expected for the currently captured book:
- 27/27 traversal
- 0 304-only
- all mapped MP4 complete
- the nine origin `*_extracted.png` 404s appear as warnings, not capture failures.

## Status meanings
`READY`: no known archive-completeness problem.
`READY WITH WARNINGS`: archive is complete by observed-resource criteria, but the original site returned 404 for one or more resources.
`INCOMPLETE`: traversal, 304-only, mapped-media completion, or another known capture condition is incomplete.

External services and content that was never loaded/captured remain outside the offline archive.
Do not publish `archive` or `state`.
