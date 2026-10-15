"""Compare public IZZI resource addresses with bounded GETs; no login/session storage."""
import argparse,concurrent.futures,hashlib,json,re,sys,urllib.error,urllib.request
from pathlib import Path
from urllib.parse import urlsplit,urlunsplit

FILES=('index.html','GeoGebra/deployggb.js','jquery-3.2.1.min.js','variables.js','assets/scripts.js','assets/style.css','images/loading-icon.gif')
LIMIT=4*1024*1024

def addresses(book,block):
    if not re.fullmatch(r'\d+',book) or not re.fullmatch(r'\d+',block):raise ValueError('Numeric book and block IDs required')
    for host,prefix in [('bg.izzi.digital',f'/DOS/{book}'),('bg.izzi.digital',''),('api.izzi.digital','')]:
        for file in FILES:yield f'https://{host}{prefix}/datastore/blocks/{block}/{file}'

def classify(url,status,content_type,body):
    if status in (401,403):return 'ACCESS_DENIED'
    if not 200<=status<300:return 'HTTP_ERROR'
    head=body.lstrip()[:1024].lower()
    if not body:return 'EMPTY'
    if b'<error' in head or b'<code>nosuchkey' in head:return 'ORIGIN_ERROR_XML'
    html='text/html' in content_type.lower() or b'<!doctype html' in head or b'<html' in head
    if urlsplit(url).path.endswith('.html'):return 'HTML_CANDIDATE' if html else 'UNEXPECTED_BODY'
    if html:return 'HTML_INSTEAD_OF_ASSET'
    if urlsplit(url).path.endswith('.gif'):return 'GIF_CANDIDATE' if body.startswith((b'GIF87a',b'GIF89a')) else 'UNEXPECTED_BODY'
    if urlsplit(url).path.endswith('.js') and body.lstrip().startswith(b'<'):return 'UNEXPECTED_BODY'
    return 'TEXT_CANDIDATE'

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None

def probe(url,timeout=15):
    result={'url':url,'status':None,'kind':'TRANSPORT_ERROR','bytes':0}
    request=urllib.request.Request(url,headers={'User-Agent':'IZZI-Resource-Diagnostic/1.0','Cache-Control':'no-cache','Accept-Encoding':'identity'})
    opener=urllib.request.build_opener(NoRedirect())
    try:
        try:response=opener.open(request,timeout=timeout)
        except urllib.error.HTTPError as error:response=error
        with response:
            body=response.read(LIMIT+1);status=response.code;ct=response.headers.get('Content-Type','')
            result.update(status=status,content_type=ct,bytes=len(body),sha256=hashlib.sha256(body).hexdigest())
            if 300<=status<400:
                location=urlsplit(response.headers.get('Location',''))
                result.update(kind='REDIRECT',location=urlunsplit((location.scheme,location.netloc,location.path,'','')))
            elif len(body)>LIMIT:result['kind']='TOO_LARGE'
            elif response.headers.get('Content-Encoding','identity').lower() not in ('','identity'):result['kind']='UNEXPECTED_ENCODING'
            else:result['kind']=classify(url,status,ct,body)
    except (OSError,ValueError,urllib.error.URLError) as error:
        # Do not print response bodies, cookies, headers, or redirect query tokens.
        result['error']=type(error).__name__
        if 'Tunnel connection failed: 403' in str(error):result['kind']='PROXY_CONNECT_DENIED'
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--book',default='888413');parser.add_argument('--block',default='657825')
    parser.add_argument('--output',type=Path,help='Optional JSON report path')
    args=parser.parse_args();urls=list(addresses(args.book,args.block))
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:rows=list(pool.map(probe,urls))
    for row in rows:print(str(row['status'] or '-').ljust(4),row['kind'].ljust(25),str(row['bytes']).rjust(8),row['url'])
    if args.output:args.output.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
    print('\nCANDIDATE means content resembles the expected type; application execution and dependencies still require verification.')
    print('No browser login is reused. ACCESS_DENIED/REDIRECT are not proof that a file is missing.')
    complete=any(all(row['kind'].endswith('_CANDIDATE') for row in rows[start:start+len(FILES)]) for start in range(0,len(rows),len(FILES)))
    print('Complete candidate set:',complete)
    return 0 if complete else 1

if __name__=='__main__':raise SystemExit(main())
