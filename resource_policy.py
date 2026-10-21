"""Conservative shared policy: unknown dependencies remain required."""
import re
from urllib.parse import urlsplit


def optional_reason(url):
    parsed = urlsplit(url)
    path = parsed.path.lower()
    if parsed.hostname in ('bg.izzi.digital','api.izzi.digital') and re.fullmatch(r'/(?:DOS/\d+/)?datastore/?',parsed.path):
        return 'Празен адрес за ресурс: посочена е само папката datastore'
    if path.endswith('.map'):
        return 'Диагностична карта за разработчици'
    if path == '/favicon.ico':
        return 'Икона на браузърния таб'
    return ''
