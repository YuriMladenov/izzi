"""Conservative shared policy: unknown dependencies remain required."""
import re
from urllib.parse import urlsplit


def optional_reason(url):
    parsed = urlsplit(url)
    path = parsed.path.lower()
    if parsed.hostname in ('bg.izzi.digital','api.izzi.digital') and path in ('/api/v2/xapi/pages-xpscore','/api/v2/xapi/last-records','/api/v2/x/reports/best_xpscore','/api/sync'):
        return 'История на напредъка, а не ресурс на задачата'
    if parsed.hostname=='xapi.izzi.digital' and path=='/statements':
        return 'Телеметрия за учебния напредък'
    if parsed.hostname in ('bg.izzi.digital','api.izzi.digital') and re.fullmatch(r'(?:/DOS/\d+)?/profil/dist/izzi/images/svg/no-classrooms\.svg',parsed.path):
        return 'Служебна икона на менюто за класове'
    if parsed.hostname in ('bg.izzi.digital','api.izzi.digital') and re.fullmatch(r'/(?:DOS/\d+/)?datastore/?',parsed.path):
        return 'Празен адрес за ресурс: посочена е само папката datastore'
    if path.endswith('.map'):
        return 'Диагностична карта за разработчици'
    if path == '/favicon.ico':
        return 'Икона на браузърния таб'
    return ''
