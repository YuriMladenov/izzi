"""Embed navigation helpers into the self-contained Firefox bookmarklet."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
path = root / 'auto_book_capture_bookmarklet.txt'
source = path.read_text(encoding='utf-8')
start, end = '/*IZZI_NAV_START*/', '/*IZZI_NAV_END*/'
helper = ''.join((root / 'capture_navigation.js').read_text(encoding='utf-8').splitlines())
prefix, remainder = source.split(start, 1)
_, suffix = remainder.split(end, 1)
path.write_text(prefix + start + helper + end + suffix, encoding='utf-8')
