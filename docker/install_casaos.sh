#!/usr/bin/env bash
# Run on the CasaOS host, from a Git checkout or the extracted source package.
set -euo pipefail
izzi_source="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$izzi_source"
if (( EUID != 0 )); then
    echo 'Run this script on the CasaOS host with sudo bash docker/install_casaos.sh' >&2
    exit 1
fi
docker info >/dev/null
docker compose version
docker compose -f docker/casaos.yaml config --quiet
mkdir -p /DATA/AppData/izzi/{archive,state,captures,mitmproxy,geogebra,code}
docker build -f docker/Dockerfile -t izzi-library:local .
docker compose -f docker/casaos.yaml up -d
docker compose -f docker/casaos.yaml ps
echo 'Open http://<CasaOS IP>:8765/ ; initial administrator: admin / izzi'
echo 'Data: /DATA/AppData/izzi ; capture starts from the WebUI menu.'
