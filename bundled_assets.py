"""Shared local fallbacks for replay, capture, and strict resource readiness."""
import re
from pathlib import Path
from urllib.parse import unquote
from replay_resolver import _izzi_host

def bundled_font(host,path):
    if not _izzi_host(host):return None
    base=Path(__file__).with_name('vendor')
    patterns=(
        (r'(?:/DOS/\d+)?/(?:components|profil/dist/common/katex)/fonts/(KaTeX_[A-Za-z0-9-]+\.woff2?)','katex/dist/fonts'),
        (r'(?:/DOS/\d+)?/profil/dist/izzi/fonts/IBMPlexSans/(IBMPlexSans-(?:Regular|Italic|Medium|MediumItalic|Bold|BoldItalic)\.woff2?)','ibm-plex-sans'),
        (r'(?:/DOS/\d+)?/profil/dist/common/icons/material/(MaterialIcons(?:-Regular)?\.woff2?)','material-icons'),
        (r'(?:/DOS/\d+)?/datastore/blocks/\d+/assets/fonts/Open_Sans/(OpenSans-(?:Regular|Italic|Light|LightItalic|Bold|BoldItalic)\.woff2?)','open-sans'),
    )
    for pattern,folder in patterns:
        match=re.fullmatch(pattern,path)
        if not match:continue
        name=match[1]
        if folder=='material-icons':name=name.replace('MaterialIcons.','MaterialIcons-Regular.')
        font=base/folder/name
        return font if font.is_file() else None
    return None


def asset(host,path):
    path=unquote(path)
    font=bundled_font(host,path)
    if font:return font
    if not _izzi_host(host):return None
    match=re.fullmatch(r'(?:/DOS/\d+)?/components/js/sounds/(plonk|keypress-(?:delete|return|spacebar|standard))\.wav',path)
    if not match:return None
    sound=Path(__file__).with_name('vendor')/'mathlive/sounds'/(match[1]+'.wav')
    return sound if sound.is_file() else None
