"""Local GeoGebra web3d runtime installed from an official offline ZIP."""
import re
from pathlib import Path
from urllib.parse import unquote
from config import ROOT
from replay_resolver import _izzi_host

DIRECTORY=ROOT/'vendor/geogebra/HTML5/5.0'
PREFIX='/profil/dist/common/GeoGebra/HTML5/5.0/'

def installed():
    entry=DIRECTORY/'web3d/web3d.nocache.js'
    return entry.is_file() and entry.stat().st_size>0

def asset(host,path):
    if not _izzi_host(host):return None
    path=unquote(path)
    match=re.fullmatch(r'(?:/DOS/\d+)?'+re.escape(PREFIX)+r'(.+)',path)
    if not match or not installed():return None
    relative=match[1]
    if '\\' in relative or any(part in ('','..','.') for part in relative.split('/')):return None
    root=DIRECTORY.resolve();file=(root/relative).resolve()
    if not file.is_relative_to(root) or not file.is_file():return None
    return file
