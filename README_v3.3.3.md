# IZZI Offline Library v3.3.3 — Cache-Bust Recovery

Built on v3.3.2.1 Hotfix.

This adds a targeted second pass for resources already observed as `304-only`.
It does not discover new URLs. MP4/audio are excluded because media uses the existing
Range/assembler path.

## Recovery sequence
1. Keep your existing `archive` and `state`.
2. Run normal Auto Book Capture while `capture_mode.bat` is active.
3. Run `build_recovery_manifest.bat`.
4. Create a Firefox bookmark from the complete contents of
   `cache_bust_recovery_bookmarklet.txt`.
5. While logged into IZZI and Capture Mode is still active, click that bookmark.
6. Wait for the completion alert.
7. Run:
   - `recovery_report.bat`
   - `fresh_capture_report.bat`
   - `book_readiness_report.bat`
   - `missing_assets_report.bat`

The recovery bookmarklet asks Firefox to reload only URLs in the generated 304-only
manifest and adds a unique `__izzi_offline_recover` query marker. The proxy removes
that marker before writing URL-map records, so recovered bodies are indexed under the
original URL used by offline replay.

Authentication/access-control data are not removed or bypassed. Recovery is limited
to URLs already requested by the authenticated browser and observed by Capture Mode.

Do not publish `archive` or `state`.
