"""Command line front end for per-book export and import.

    python book_transfer.py list
    python book_transfer.py export --books "История и цивилизации за 5. клас" --out izzi-68724.zip
    python book_transfer.py export --all --out izzi-all.zip
    python book_transfer.py inspect izzi-68724.zip
    python book_transfer.py import izzi-68724.zip
    python book_transfer.py import izzi-68724.zip --replace --dry-run
"""
import argparse
import sys
from pathlib import Path

import book_transfer
from config import ARCHIVE_DIR, STATE_DIR


def human(size):
    value = float(size or 0)
    for unit in ('B', 'KiB', 'MiB', 'GiB', 'TiB'):
        if value < 1024 or unit == 'TiB':
            return ('%.1f %s' % (value, unit)) if unit != 'B' else ('%d B' % value)
        value /= 1024


def command_list(args):
    books = book_transfer.known_books(STATE_DIR)
    if not books:
        print('No books in the library yet.')
        return 0
    width = max(len(book) for book in books)
    for book, title in books.items():
        print('%s  %s' % (book.ljust(width), title))
    print('\n%d book(s).' % len(books))
    return 0


def pick(selection, all_books):
    books = book_transfer.known_books(STATE_DIR)
    if all_books:
        return book_transfer.parse_selection(None, books)
    if not selection:
        raise book_transfer.TransferError('Choose books with --books or use --all')
    return book_transfer.parse_selection(selection, books)


def command_export(args):
    books = pick(args.books, args.all)
    destination = Path(args.out or 'izzi-books.zip')
    if destination.is_dir():
        destination = destination / ('izzi-books-%d.zip' % len(books))
    print('Exporting %d book(s): %s' % (len(books), ', '.join(books)))
    result = book_transfer.export(books, STATE_DIR, ARCHIVE_DIR, destination,
                                  compress_media=args.compress,
                                  allow_missing=args.allow_missing)
    print('Books : %s' % ', '.join('%s (%s)' % (b, t) for b, t in result['books'].items()))
    print('Files : %d archive file(s), %d shared resource(s)' % (result['files'], result['shared']))
    if result.get('missing'):
        print('Warn  : %d missing file(s) were skipped' % result['missing'])
    print('Output: %s (%s)' % (result['path'], human(result['bytes'])))
    return 0


def command_inspect(args):
    report = book_transfer.preview(args.package, STATE_DIR, ARCHIVE_DIR)
    print('Package contains %d book(s):' % len(report['books']))
    for book, title in report['books'].items():
        print('  %s  %s' % (book, title))
    if report['adding']:
        print('New books      : %s' % ', '.join(report['adding']))
    if report['replacing']:
        print('Already present: %s (needs --replace)' % ', '.join(report['replacing']))
    print('Archive files  : %d new, %d already present' % (report['files_new'], report['files_present']))
    print('Indexed URLs   : %d new, %d overwritten' % (report['URLs_new'], report['URLs_replaced']))
    if report['conflicts']:
        print('Conflicts      : %d file(s) differ from the local copy' % len(report['conflicts']))
        for key in report['conflicts'][:10]:
            print('  %s' % key)
        return 1
    return 0


def command_import(args):
    status = command_inspect(argparse.Namespace(package=args.package))
    if status and not args.force:
        print('\nImport refused; move the conflicting files away or use --force.')
        return status
    if args.dry_run:
        print('\nDry run: nothing was written.')
        return 0
    result = book_transfer.import_books(args.package, STATE_DIR, ARCHIVE_DIR,
                                        replace=args.replace)
    print('\nImported %d book(s): %s' % (len(result['books']), ', '.join(result['books'])))
    print('Archive files  : %d copied, %d already present' % (result['copied'], result['restored']))
    print('Indexed URLs   : %d merged' % result['URLs'])
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description='Move selected textbooks between IZZI installations')
    sub = parser.add_subparsers(dest='command', required=True)

    sub.add_parser('list', help='show installed books').set_defaults(func=command_list)

    export = sub.add_parser('export', help='write a portable ZIP with selected books')
    export.add_argument('--books', nargs='+', metavar='ID|TITLE',
                        help='book IDs or (partial) titles; default: all with --all')
    export.add_argument('--all', action='store_true', help='export every installed book')
    export.add_argument('--out', metavar='FILE', help='destination ZIP file')
    export.add_argument('--allow-missing', action='store_true',
                        help='export the files that exist even if the index references missing ones')
    export.add_argument('--compress', action='store_true',
                        help='compress media too (smaller file, much slower)')
    export.set_defaults(func=command_export)

    inspect = sub.add_parser('inspect', help='validate a package and show what it would add')
    inspect.add_argument('package')
    inspect.set_defaults(func=command_inspect)

    imp = sub.add_parser('import', help='merge a package into this installation')
    imp.add_argument('package')
    imp.add_argument('--replace', action='store_true', help='update books that already exist')
    imp.add_argument('--force', action='store_true', help='continue despite file conflicts')
    imp.add_argument('--dry-run', action='store_true', help='report only, write nothing')
    imp.set_defaults(func=command_import)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (book_transfer.TransferError, OSError) as error:
        print('Error: %s' % error, file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
