"""Portable per-book export/import for moving textbooks between installations.

An export is a single ZIP that carries everything replay needs for the chosen
books: the archive bodies, a filtered index slice and the helper state that
describes lessons, media mappings, catalogue order and capture provenance.
Nothing is downloaded, so export/import work fully offline.

Import merges into the target installation instead of replacing it: records
from other books are never touched, shared blobs stay in place and collisions
are verified by size instead of silently overwritten.
"""
import hashlib
import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import threading
import zipfile
from contextlib import closing
from pathlib import Path
from urllib.parse import urlsplit

import archive_db
import youtube_download
from archive_storage import shard_key
from replay_resolver import book_ids

MAX_UPLOAD = 8 * 1024 * 1024 * 1024
FORMAT = 'izzi-book-export'
VERSION = 1
MANIFEST = 'izzi-export.json'
# Helper JSON state copied for the chosen books, keyed by state file name.
# Each filter keeps only the part that belongs to the exported book IDs.
AUX = ('books.json', 'library_catalog.json', 'media_map.json', 'lesson_links.json')
LOCK = threading.Lock()
_LESSON = re.compile(r'/DOS/(\d+)/(\d+)\.html$')
# regex engines vary between platforms, so the download name is sanitised by
# inspecting characters directly instead of relying on a negated class.
SAFE_CHARS = frozenset('0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz._')


def safe_label(text, limit=60):
    """ASCII-only label for a filename, without depending on regex semantics."""
    out = []
    for char in str(text):
        if char in SAFE_CHARS:
            out.append(char)
        elif out and out[-1] != '-':
            out.append('-')
    return ''.join(out).strip('-._')[:limit].strip('-._')


def package_name(books, labels):
    """Readable, filesystem-safe download name for the chosen books."""
    books = sorted(map(str, books))
    if len(books) == 1:
        label = safe_label(labels.get(books[0], books[0]))
        base = 'izzi-%s-%s' % (books[0], label) if label else 'izzi-%s' % books[0]
    elif len(books) <= 3:
        base = 'izzi-' + '-'.join(books)
    else:
        base = 'izzi-%d-books' % len(books)
    return (base or 'izzi-books') + '.zip'


class TransferError(ValueError):
    """Raised for invalid selections and inconsistent export packages."""


# --------------------------------------------------------------------------
# state helpers
# --------------------------------------------------------------------------

def known_books(state):
    """Book IDs present in the index, paired with their titles."""
    from import_har import load
    books = dict(load(Path(state) / 'books.json', {}))
    return {str(book): str(row.get('title') or book) for book, row in books.items()}


def parse_selection(selection, books):
    """Normalise book IDs or titles from the command line; empty means all."""
    if not selection:
        return sorted(books)
    chosen = []
    for item in selection:
        value = str(item).strip()
        if value in books:
            chosen.append(value)
            continue
        matches = [book for book, title in books.items() if title.casefold() == value.casefold()]
        if not matches:
            matches = [book for book, title in books.items() if value.casefold() in title.casefold()]
        if len(matches) != 1:
            detail = 'No book matches' if not matches else 'Ambiguous book selection matches ' + ', '.join(matches)
            raise TransferError(detail + ': ' + value)
        chosen.append(matches[0])
    return sorted(set(chosen))


def read_index(state):
    """Return ({url: rows}, {book: book_row}) read consistently from the live index."""
    state = Path(state)
    from import_har import load
    mapping = dict(load(state / 'url_map.json', {}))
    books = dict(load(state / 'books.json', {}))
    return mapping, books


def _filter_lesson_links(links, keep_urls):
    return {url: entry for url, entry in links.items() if url in keep_urls}


def _filter_media_map(media, chosen):
    lessons = {}
    for key, entry in (media.get('lessons') or {}).items():
        book = str(entry.get('book') or key.split('/')[0])
        if book in chosen:
            lessons[key] = entry
    return {'lessons': lessons}


def _filter_catalog(catalog, chosen):
    return {book: value for book, value in catalog.items() if str(book) in chosen}


def _filter_books(books, chosen):
    return {book: value for book, value in books.items() if str(book) in chosen}


# --------------------------------------------------------------------------
# media collection
# --------------------------------------------------------------------------

def _load(path, default):
    from import_har import load
    return load(path, default)


def export_plan(books, state, archive):
    """Build the complete file plan for an export of the given book IDs."""
    state, archive = Path(state), Path(archive)
    chosen = set(map(str, books))
    if not chosen:
        raise TransferError('No books selected')
    mapping, catalog = read_index(state)
    detected = known_books(state)
    unknown = chosen - set(detected)
    if unknown:
        raise TransferError('Unknown book IDs: ' + ', '.join(sorted(unknown)))

    index_urls = {}
    for url, rows in mapping.items():
        try:
            if book_ids(urlsplit(url).path) & chosen:
                index_urls[url] = rows
        except ValueError:
            continue
    # Lesson roots and every asset they reference, whatever book owns the URL.
    links = _load(state / 'lesson_links.json', {})
    lesson_roots = {url for url in index_urls if _LESSON.search(urlsplit(url).path)}
    referenced = set()
    for root in lesson_roots:
        referenced.update(links.get(root, {}).get('resources') or ())
    keep_urls = {url for url in referenced if url in mapping and url not in index_urls}

    def keys_of(urls):
        return {row['key'] for url, rows in mapping.items() if url in urls
                for row in rows if row.get('key')}

    payload = keys_of(index_urls)
    shared = keys_of(keep_urls) - payload
    files = []
    for key in payload | shared:
        path = archive / key
        files.append({'key': key, 'bucket': 'index' if key in payload else 'shared',
                      'size': path.stat().st_size if path.is_file() else None,
                      'missing': not path.is_file()})
    # Local YouTube downloads referenced by the selected lessons.
    videos = set()
    for url in index_urls:
        identifier = youtube_download.video_id(url)
        if identifier:
            videos.add(identifier)
    youtube = []
    for identifier in sorted(videos):
        for suffix in ('.mp4', '.json', '.log'):
            for folder in (archive / 'youtube', state / 'youtube'):
                path = folder / (identifier + suffix)
                if path.is_file():
                    youtube.append({'source': str(path.relative_to(folder.parent)),
                                    'name': path.name, 'size': path.stat().st_size})
                    break
    # Pending range assemblies for the selected books.
    ranges = []
    for manifest in sorted((state / 'range_assembly').glob('*.json')):
        if not re.fullmatch(r'[a-f0-9]{64}', manifest.stem):
            continue
        data = _load(manifest, {})
        try:
            if book_ids(urlsplit(str(data.get('url') or '')).path) & chosen:
                ranges.append(manifest.name)
                work = manifest.with_suffix('')
                if work.is_dir():
                    ranges.extend(p.name + '/' + c.name for c in sorted(work.iterdir()) if c.is_file())
        except ValueError:
            continue
    aux = {}
    aux['books.json'] = _filter_books(dict(_load(state / 'books.json', {})), chosen)
    aux['library_catalog.json'] = _filter_catalog(dict(_load(state / 'library_catalog.json', {})), chosen)
    aux['media_map.json'] = _filter_media_map(dict(_load(state / 'media_map.json', {'lessons': {}})), chosen)
    aux['lesson_links.json'] = {url: entry for url, entry in links.items() if url in index_urls or url in keep_urls}
    reports = {}
    reports['missing_resources.jsonl'] = _missing_lines(state, chosen, set(index_urls))
    progress = {book: (state / 'progress' / (book + '.jsonl')) for book in chosen
                if (state / 'progress' / (book + '.jsonl')).is_file()}
    return {'books': sorted(chosen), 'titles': {book: detected[book] for book in sorted(chosen)},
            'index': index_urls, 'shared_urls': sorted(keep_urls), 'files': files,
            'youtube': youtube, 'ranges': sorted(ranges), 'aux': aux, 'reports': reports,
            'progress': progress}


def _missing_lines(state, chosen, urls):
    path = Path(state) / 'missing_resources.jsonl'
    if not path.is_file():
        return b''
    lines = []
    for line in path.read_text(encoding='utf8').splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        url = 'https://' + row.get('host', '') + row.get('path', '')
        try:
            if url in urls or (book_ids(row.get('path', '')) & chosen):
                lines.append(line)
        except ValueError:
            continue
    return (''.join(line + '\n' for line in lines)).encode('utf8')


# --------------------------------------------------------------------------
# export
# --------------------------------------------------------------------------

def _add_file(zf, source, arcname, compressible=False):
    method = zipfile.ZIP_DEFLATED if compressible else zipfile.ZIP_STORED
    info = zipfile.ZipInfo.from_file(source, arcname)
    info.compress_type = method
    with source.open('rb') as stream, zf.open(info, 'w', force_zip64=True) as out:
        shutil.copyfileobj(stream, out, 1024 * 1024)


def _add_bytes(zf, data, arcname):
    info = zipfile.ZipInfo(arcname)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.date_time = (2024, 1, 1, 0, 0, 0)
    info.external_attr = 0o644 << 16
    zf.writestr(info, data)


def export(books, state, archive, destination, compress_media=False, allow_missing=False):
    """Write a portable ZIP with all state and media of the chosen books.

    By default a package is refused when the index references files that are not
    in the archive, because importing it would reproduce the same 404s on the
    target machine. allow_missing=True exports only what exists and reports the
    omitted files.
    """
    state, archive = Path(state), Path(archive)
    destination = Path(destination)
    plan = export_plan(books, state, archive)
    failed = [entry['key'] for entry in plan['files'] if entry['missing']]
    if failed and not allow_missing:
        raise TransferError(
            'Export refused: {} archived file(s) referenced by the index are missing '
            '(first: {}). Repair the archive before migrating, or pass --allow-missing '
            'to export only the files that exist.'.format(len(failed), failed[0]))
    if failed:
        print('Warning: skipping %d missing archive file(s); those lessons will still '
              'report "Not captured" after import.' % len(failed), file=sys.stderr)
    plan['files'] = [entry for entry in plan['files'] if not entry['missing']]
    destination.parent.mkdir(parents=True, exist_ok=True)
    manifest = {'format': FORMAT, 'version': VERSION, 'books': plan['titles'],
                'resources': len(plan['index']), 'shared': len(plan['shared_urls']),
                'files': [{k: v for k, v in entry.items() if k != 'bucket'} for entry in plan['files']],
                'youtube': plan['youtube'], 'ranges': plan['ranges']}
    checksums = {}
    fd, tempname = tempfile.mkstemp(prefix='.' + destination.name + '-', suffix='.tmp',
                                    dir=destination.parent)
    os.close(fd)
    temp = Path(tempname)
    try:
        with zipfile.ZipFile(temp, 'w', allowZip64=True) as zf:
            for entry in plan['files']:
                source = archive / entry['key']
                _add_file(zf, source, 'archive/' + entry['key'], compressible=compress_media)
                checksums['archive/' + entry['key']] = hashlib.sha256(source.read_bytes()).hexdigest()
            for entry in plan['youtube']:
                source = (archive if entry['source'].startswith('youtube/') or
                          entry['source'].startswith('youtube' + os.sep) else state) / entry['source'].split(os.sep, 1)[1]
                _add_file(zf, source, entry['source'])
                checksums[entry['source']] = hashlib.sha256(source.read_bytes()).hexdigest()
            for name in plan['ranges']:
                source = state / 'range_assembly' / name
                arcname = 'state/range_assembly/' + name
                if source.is_dir():
                    for child in sorted(source.iterdir()):
                        if child.is_file():
                            _add_file(zf, child, arcname + '/' + child.name)
                            checksums[arcname + '/' + child.name] = hashlib.sha256(child.read_bytes()).hexdigest()
                elif source.is_file():
                    _add_file(zf, source, arcname)
                    checksums[arcname] = hashlib.sha256(source.read_bytes()).hexdigest()
            for name, data in plan['aux'].items():
                raw = json.dumps(data, ensure_ascii=False, indent=2).encode('utf8')
                _add_bytes(zf, raw, 'state/' + name)
                checksums['state/' + name] = hashlib.sha256(raw).hexdigest()
            for name, raw in plan['reports'].items():
                if raw:
                    _add_bytes(zf, raw, 'state/' + name)
                    checksums['state/' + name] = hashlib.sha256(raw).hexdigest()
            for book, source in plan['progress'].items():
                _add_file(zf, source, 'state/progress/' + source.name)
                checksums['state/progress/' + source.name] = hashlib.sha256(source.read_bytes()).hexdigest()
            index = {url: rows for url, rows in plan['index'].items()}
            raw = json.dumps({'format': FORMAT, 'version': VERSION, 'books': plan['titles'],
                              'url_map': index, 'books_index': plan['aux']['books.json']},
                             ensure_ascii=False, separators=(',', ':')).encode('utf8')
            _add_bytes(zf, raw, 'state/index.json')
            checksums['state/index.json'] = hashlib.sha256(raw).hexdigest()
            manifest['checksums'] = checksums
            _add_bytes(zf, json.dumps(manifest, ensure_ascii=False, indent=2).encode('utf8'), MANIFEST)
        os.replace(temp, destination)
    except BaseException:
        temp.unlink(missing_ok=True)
        raise
    return {'path': str(destination), 'books': plan['titles'], 'files': len(plan['files']),
            'shared': len(plan['shared_urls']), 'bytes': destination.stat().st_size,
            'missing': len(failed)}


# --------------------------------------------------------------------------
# import
# --------------------------------------------------------------------------

def inspect_package(path):
    """Read and validate the manifest of an export without modifying anything."""
    path = Path(path)
    if not path.is_file():
        raise TransferError('Export file not found: ' + str(path))
    try:
        with zipfile.ZipFile(path) as zf:
            names = set(zf.namelist())
            if MANIFEST not in names:
                raise TransferError('Not an IZZI book export (missing ' + MANIFEST + ')')
            manifest = json.loads(zf.read(MANIFEST).decode('utf8'))
            if manifest.get('format') != FORMAT or int(manifest.get('version', 0)) != VERSION:
                raise TransferError('Unsupported export format or version')
            for name in names:
                if name == MANIFEST or name.startswith('state/') or name.startswith('archive/'):
                    parts = Path(name).parts
                    if any(part in ('..', '') or part.startswith('/') for part in parts):
                        raise TransferError('Unsafe path in export: ' + name)
            missing = {'archive/' + entry['key'] for entry in manifest.get('files', [])} - names
            if missing:
                raise TransferError('Export is incomplete (' + str(len(missing)) + ' files missing)')
            if 'state/index.json' not in names:
                raise TransferError('Export is incomplete (missing state/index.json)')
            index = json.loads(zf.read('state/index.json').decode('utf8'))
            return manifest, index
    except zipfile.BadZipFile as error:
        raise TransferError('Damaged export archive: ' + str(error)) from error


def preview(path, state, archive):
    """Report what an import would add, skip or conflict with."""
    state, archive = Path(state), Path(archive)
    manifest, index = inspect_package(path)
    existing_books = known_books(state)
    mapping, _ = read_index(state)
    report = {'books': manifest.get('books', {}), 'adding': [], 'replacing': [],
              'files_new': 0, 'files_present': 0, 'URLs_new': 0, 'URLs_replaced': 0,
              'conflicts': []}
    for book in report['books']:
        (report['replacing'] if book in existing_books else report['adding']).append(book)
    with zipfile.ZipFile(path) as zf:
        sizes = {info.filename: info.file_size for info in zf.infolist()}
    for entry in manifest.get('files', []):
        target = archive / shard_key(entry['key'])
        if not target.is_file():
            report['files_new'] += 1
        elif target.stat().st_size != entry['size']:
            report['conflicts'].append(entry['key'])
        else:
            report['files_present'] += 1
    for url in index.get('url_map', {}):
        if url in mapping:
            report['URLs_replaced'] += 1
        else:
            report['URLs_new'] += 1
    return report


def import_books(path, state, archive, replace=False):
    """Merge an export into the target installation; never deletes other books."""
    state, archive = Path(state), Path(archive)
    manifest, index = inspect_package(path)
    archive.mkdir(parents=True, exist_ok=True)
    state.mkdir(parents=True, exist_ok=True)
    with LOCK:
        existing_books = known_books(state)
        clash = [book for book in manifest.get('books', {}) if book in existing_books]
        if clash and not replace:
            raise TransferError('Books already installed: ' + ', '.join(clash) +
                                '. Use --replace to update them from the export.')
        with zipfile.ZipFile(path) as zf:
            copied = restored = 0
            for entry in manifest.get('files', []):
                target = archive / shard_key(entry['key'])
                if target.is_file():
                    if target.stat().st_size != entry['size']:
                        raise TransferError('Conflicting local file for ' + entry['key'] +
                                            '; move it away before importing')
                    restored += 1
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                fd, tempname = tempfile.mkstemp(prefix='.' + target.name + '-', suffix='.tmp',
                                                dir=target.parent)
                os.close(fd)
                temp = Path(tempname)
                try:
                    with zf.open('archive/' + entry['key']) as source, temp.open('wb') as out:
                        shutil.copyfileobj(source, out, 1024 * 1024)
                    if temp.stat().st_size != entry['size']:
                        raise TransferError('Size mismatch after copying ' + entry['key'])
                    os.replace(temp, target)
                    copied += 1
                except BaseException:
                    temp.unlink(missing_ok=True)
                    raise
            for entry in manifest.get('youtube', []):
                name = entry['source'].replace('\\', '/')
                folder = archive if name.startswith('youtube/') else state
                target = folder / name.split('/', 1)[1]
                if target.is_file():
                    continue
                if name in zf.namelist():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(name) as source, target.open('wb') as out:
                        shutil.copyfileobj(source, out)
            for name in manifest.get('ranges', []):
                source_name = 'state/range_assembly/' + name
                target = state / 'range_assembly' / name
                if name in zf.namelist():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if not target.is_file():
                        with zf.open(source_name) as source, target.open('wb') as out:
                            shutil.copyfileobj(source, out)
                elif any(n.startswith(source_name + '/') for n in zf.namelist()):
                    target.mkdir(parents=True, exist_ok=True)
                    for n in zf.namelist():
                        if n.startswith(source_name + '/') and n != source_name + '/':
                            child = target / n[len(source_name) + 1:]
                            child.parent.mkdir(parents=True, exist_ok=True)
                            with zf.open(n) as source, child.open('wb') as out:
                                shutil.copyfileobj(source, out)
            incoming = index.get('url_map') or {}
            if incoming:
                from import_har import load
                mapping = dict(load(state / 'url_map.json', {}))
                mapping.update(incoming)
                archive_db.write(state / 'url_map.json', mapping)
            chosen = set(manifest.get('books', {}))
            from import_har import load, save
            for name in AUX:
                member = 'state/' + name
                if member not in zf.namelist():
                    continue
                data = json.loads(zf.read(member).decode('utf8'))
                current = load(state / name, {})
                if name == 'media_map.json':
                    merged = {'lessons': dict(current.get('lessons') or {})}
                    merged['lessons'].update(data.get('lessons') or {})
                    save(state / name, merged)
                else:
                    merged = dict(current)
                    merged.update(data)
                    save(state / name, merged)
            member = 'state/missing_resources.jsonl'
            if member in zf.namelist():
                target = state / 'missing_resources.jsonl'
                existing = target.read_text(encoding='utf8').splitlines() if target.is_file() else []
                extra = [line for line in zf.read(member).decode('utf8').splitlines() if line]
                if extra:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(''.join(line + '\n' for line in existing + extra), encoding='utf8')
            for book in chosen:
                member = 'state/progress/' + book + '.jsonl'
                if member in zf.namelist():
                    target = state / 'progress' / (book + '.jsonl')
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(target.read_bytes() + zf.read(member) if target.is_file()
                                       else zf.read(member))
        # Rebuild the SQLite index so replay sees the merged URLs and books.
        try:
            archive_db.initialize(state)
        except (ValueError, sqlite3.Error):
            pass
        return {'books': manifest.get('books', {}), 'copied': copied, 'restored': restored,
                'URLs': len(incoming)}
