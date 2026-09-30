"""Validate unmodified server against isolated synthetic data, never real archives."""
import hashlib
import json
import sys
import tempfile
import threading
import urllib.request
from pathlib import Path
from http.server import ThreadingHTTPServer

SOURCE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE))
import server
import assembled_media
import media_mapping

failures = []
with tempfile.TemporaryDirectory(prefix='izzi-validation-') as td:
    root = Path(td)
    archive = root / 'archive'
    state = root / 'state'
    archive.mkdir()
    state.mkdir()
    for mod in (server, assembled_media):
        mod.ARCHIVE_DIR = archive
        mod.URL_MAP_FILE = state / 'url_map.json'
    server.STATE_DIR = state
    server.BOOKS_FILE = state / 'books.json'
    server.PROGRESS_DIR = state / 'progress'
    media_mapping.P = state / 'media_map.json'
    mapping = {}
    def add(url, body, content_type, **extra):
        key = hashlib.sha256(body).hexdigest()
        (archive / key).write_bytes(body)
        mapping[url] = [dict(key=key, content_type=content_type, status=200,
                             body_available=True, method='GET', decoded=True,
                             size=len(body), **extra)]
    add('https://bg.izzi.digital:443/DOS/1408736/1408788.html',
        b'<html><body>fixture lesson</body></html>', 'text/html')
    add('https://bg.izzi.digital/datastore/test.css', b'body{color:red}', 'text/css')
    add('https://bg.izzi.digital/datastore/test.js', b'window.fixture=true;', 'application/javascript')
    add('https://bg.izzi.digital/datastore/test.woff2', b'wOF2' + bytes(128), 'application/octet-stream')
    video = bytes(range(256)) * 8
    add('https://bg.izzi.digital/datastore/test.mp4', video, 'video/mp4',
        source='assembled_ranges', complete=True)
    (state / 'url_map.json').write_text(json.dumps(mapping))
    (state / 'books.json').write_text(json.dumps({'1408736': {'title': 'Fixture book',
        'lessons': {'1408788': {'id':'1408788', 'title':'Fixture lesson',
                              'path':'/DOS/1408736/1408788.html'}}}}))
    httpd = ThreadingHTTPServer(('127.0.0.1', 0), server.H)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    checks = [('/', 'text/html', None),
              ('/DOS/1408736/1408788.html', 'text/html', None),
              ('/DOS/1408736/datastore/test.css', 'text/css', b'body{color:red}'),
              ('/datastore/test.js', 'application/javascript', b'window.fixture=true;'),
              ('/datastore/test.woff2', 'font/woff2', b'wOF2' + bytes(128)),
              ('/datastore/test.mp4', 'video/mp4', video[:1024])]
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        for path, mime, expected in checks:
            try:
                req = urllib.request.Request(f'http://127.0.0.1:{httpd.server_port}{path}',
                    headers={'Range':'bytes=0-1023'} if mime=='video/mp4' else {})
                with opener.open(req, timeout=5) as r:
                    body = r.read()
                    assert r.status == (206 if mime=='video/mp4' else 200)
                    assert r.headers['Content-Type'].startswith(mime)
                    if expected is not None: assert body == expected
                    if path.endswith('.html'): assert b'fixture lesson' in body
                    if mime=='video/mp4':
                        assert r.headers['Content-Range']=='bytes 0-1023/2048'
                        assert r.headers['Content-Length']=='1024'
                print('PASS', path)
            except Exception as e:
                failures.append(path)
                print('FAIL', path, repr(e))
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join()
print(f'Synthetic replay checks: {len(checks)-len(failures)} passed, {len(failures)} failed')
raise SystemExit(bool(failures))
