#!/usr/bin/env bash
# Fast-forward WebUI; never reset, clean, or remove the archive.
set -euo pipefail

# Parse the complete function before Git updates this script on disk.
main() {
    local project python script_dir
    script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
    if [[ -f "$script_dir/server.py" ]]; then project="${1:-$script_dir}";
    else project="${1:-$HOME/IZZI/izzi}"; fi
    cd -- "$project"
    git rev-parse --is-inside-work-tree >/dev/null
    [[ "$(git branch --show-current)" == WebUI ]] || { echo 'Updates require the WebUI branch.' >&2; return 1; }
    if [[ -n "$(git status --porcelain)" ]]; then
        echo 'Local changes or untracked files exist. Update stopped; keep your changes.' >&2
        git status --short
        return 1
    fi
    python="$PWD/.venv/bin/python"
    [[ -x "$python" ]] || { echo 'Run install_debian.sh for this project first.' >&2; return 1; }
    "$python" - <<'PY'
import socket
for port in (8765,8877):
    with socket.socket() as probe:
        probe.settimeout(.5)
        if probe.connect_ex(('127.0.0.1',port)) == 0:
            raise SystemExit(f'Port {port} is busy. Stop library and capture, then retry.')
PY
    git pull --ff-only origin WebUI
    "$python" -m pip install -r requirements-capture.txt --upgrade 'yt-dlp[default]'
    "$python" -m pip check
    export PATH="$HOME/.deno/bin:$PATH"
    "$python" youtube_download.py --diagnose | "$python" -c 'import json,sys; d=json.load(sys.stdin);print(json.dumps(d,indent=2));r=d["runtimes"];sys.exit(0 if d["yt_dlp"] and d["ejs"] and r["ffmpeg"]["supported"] and any(r[n]["supported"] for n in ("deno","node")) else "YouTube prerequisites are not ready. Rerun install_debian.sh.")'
    "$python" checks/test_media_contract.py
    echo
    git log -1 --oneline
    echo 'Update complete. Existing archive/ and state/ are preserved.'
    echo 'Restart the library: PATH="$HOME/.deno/bin:$PATH" .venv/bin/python -u server.py'
    echo 'Replace the Firefox bookmarklet if its contents changed.'
}

main "$@"
