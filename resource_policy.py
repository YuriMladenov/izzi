"""Conservative shared policy: unknown dependencies remain required."""
from urllib.parse import urlsplit


def optional_reason(url):
    path = urlsplit(url).path.lower()
    if path.endswith('.map'):
        return 'Диагностична карта за разработчици'
    if path == '/favicon.ico':
        return 'Икона на браузърния таб'
    return ''
