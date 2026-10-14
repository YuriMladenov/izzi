#!/usr/bin/env bash
# Install a checkout and its tools without changing archived books.
set -euo pipefail

main() {
    local script_dir project python runtime installer
    script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
    if [[ -f "$script_dir/server.py" ]]; then
        project="${1:-$script_dir}"
    else
        project="${1:-$HOME/IZZI/izzi}"
    fi
    [[ -f /etc/debian_version ]] || { echo 'This installer requires Debian or a Debian-based distribution.' >&2; return 1; }
    if (( EUID == 0 )); then
        apt-get update
        apt-get install -y git python3 python3-venv python3-pip curl unzip ffmpeg firefox-esr nodejs
    else
        sudo apt-get update
        sudo apt-get install -y git python3 python3-venv python3-pip curl unzip ffmpeg firefox-esr nodejs
    fi
    if [[ ! -d "$project/.git" ]]; then
        if [[ -e "$project" && -n "$(ls -A -- "$project")" ]]; then
            echo "Installation directory is not empty: $project. Nothing was removed." >&2
            return 1
        fi
        mkdir -p -- "$(dirname -- "$project")"
        git clone --branch WebUI https://github.com/YuriMladenov/izzi.git "$project"
    fi
    cd -- "$project"
    [[ -f server.py && -f requirements-capture.txt ]] || { echo 'This is not an IZZI checkout.' >&2; return 1; }
    [[ "$(git branch --show-current)" == WebUI ]] || { echo 'Use the WebUI branch before installing.' >&2; return 1; }
    # Do not change dependencies while the library or capture is running.
    python3 - <<'PY'
import socket
for port in (8765,8877):
    with socket.socket() as probe:
        probe.settimeout(.5)
        if probe.connect_ex(('127.0.0.1',port)) == 0:
            raise SystemExit(f'Port {port} is busy. Stop library and capture, then retry.')
PY
    if [[ ! -x .venv/bin/python ]]; then python3 -m venv .venv; fi
    python="$PWD/.venv/bin/python"
    "$python" -m pip install --upgrade pip
    "$python" -m pip install -r requirements-capture.txt 'yt-dlp[default]'
    "$python" -m pip check

    export PATH="$HOME/.deno/bin:$PATH"
    runtime="$("$python" youtube_download.py --diagnose)"
    if ! printf '%s' "$runtime" | "$python" -c 'import json,sys; r=json.load(sys.stdin)["runtimes"];sys.exit(not any(r[n]["supported"] for n in ("deno","node")))'; then
        # Download the complete official installer before executing it.
        installer="$(mktemp)"
        if ! curl --fail --show-error --location --proto '=https' --proto-redir '=https' https://deno.land/install.sh -o "$installer"; then
            rm -f -- "$installer"; return 1
        fi
        if ! DENO_INSTALL="$HOME/.deno" sh "$installer" -y --no-modify-path; then
            rm -f -- "$installer"; return 1
        fi
        rm -f -- "$installer"
    fi
    "$python" youtube_download.py --diagnose | "$python" -c 'import json,sys; d=json.load(sys.stdin);print(json.dumps(d,indent=2));r=d["runtimes"];sys.exit(0 if d["yt_dlp"] and d["ejs"] and r["ffmpeg"]["supported"] and any(r[n]["supported"] for n in ("deno","node")) else "YouTube prerequisites are not ready. See diagnostics above.")'
    "$python" checks/test_media_contract.py
    echo
    echo "Installed in: $PWD"
    echo 'Existing archive/ and state/ are preserved.'
    echo 'Start the library from this directory:'
    echo '  PATH="$HOME/.deno/bin:$PATH" .venv/bin/python -u server.py'
    echo 'Open http://127.0.0.1:8765/ and start capture from Menu -> Capture and checks.'
    echo 'Firefox proxy and certificate trust still need manual configuration.'
}

main "$@"
