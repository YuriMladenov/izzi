"""Install a compatible GeoGebra offline web3d ZIP without touching book data."""
import argparse,hashlib,json,os,socket,stat,tempfile,time,urllib.request,zipfile
from pathlib import Path,PurePosixPath
import geogebra_runtime

URL='https://download.geogebra.org/package/geogebra-math-apps-bundle'
MAX_DOWNLOAD=512*1024*1024
MAX_UNPACKED=2*1024*1024*1024

def install(archive,directory=None):
    directory=Path(directory) if directory else geogebra_runtime.DIRECTORY.parent.parent
    directory.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(archive) as package:
        entries=package.infolist()
        if len(entries)>20000 or sum(x.file_size for x in entries)>MAX_UNPACKED:raise ValueError('GeoGebra ZIP exceeds installation limits.')
        roots={x.filename[:-len('web3d/web3d.nocache.js')] for x in entries if x.filename.endswith('web3d/web3d.nocache.js')}
        if len(roots)!=1:raise ValueError('ZIP must contain one compatible web3d/web3d.nocache.js runtime. Newer web-only bundles cannot replace web3d automatically.')
        prefix=roots.pop()
        with tempfile.TemporaryDirectory(prefix='.geogebra-',dir=directory.parent) as temporary:
            stage=Path(temporary)/'geogebra';runtime=stage/'HTML5/5.0';runtime.mkdir(parents=True)
            manifest={}
            for entry in entries:
                path=PurePosixPath(entry.filename)
                if path.is_absolute() or '..' in path.parts or '\\' in entry.filename or ':' in entry.filename or stat.S_ISLNK(entry.external_attr>>16):raise ValueError('Unsafe ZIP member: '+entry.filename)
                if entry.is_dir() or not entry.filename.startswith(prefix):continue
                relative=PurePosixPath(entry.filename[len(prefix):])
                if relative.is_absolute() or not relative.parts:raise ValueError('Unsafe runtime path')
                target=runtime.joinpath(*relative.parts)
                if target.exists():raise ValueError('Duplicate runtime path: '+str(relative))
                target.parent.mkdir(parents=True,exist_ok=True)
                digest=hashlib.sha256()
                with package.open(entry) as source,target.open('wb') as output:
                    while chunk:=source.read(1024*1024):output.write(chunk);digest.update(chunk)
                manifest[str(relative)]={'bytes':target.stat().st_size,'sha256':digest.hexdigest()}
            # Preserve package notices even if they are above the runtime folder.
            for index,entry in enumerate(entries):
                if entry.is_dir() or not any(word in PurePosixPath(entry.filename).name.lower() for word in ('license','licence','copyright')):continue
                if entry.file_size>4*1024*1024:continue
                notice=stage/'package-notices'/(str(index)+'-'+PurePosixPath(entry.filename).name)
                notice.parent.mkdir(exist_ok=True);notice.write_bytes(package.read(entry))
            if not manifest.get('web3d/web3d.nocache.js',{}).get('bytes'):raise ValueError('Empty GeoGebra loader')
            (stage/'installation.json').write_text(json.dumps({'source':URL,'license':'https://www.geogebra.org/license','files':manifest},indent=2),encoding='utf8')
            backup=None
            if directory.exists():
                backups=directory.parent/'geogebra-backups';backups.mkdir(exist_ok=True)
                backup=backups/(time.strftime('%Y%m%d-%H%M%S')+'-'+os.urandom(4).hex());directory.rename(backup)
            try:stage.rename(directory)
            except OSError:
                if backup:backup.rename(directory)
                raise
    return len(manifest)

def download(target):
    # urllib keeps certificate verification enabled. No cookies or credentials.
    class HTTPSOnly(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,request,fp,code,msg,headers,newurl):
            if not newurl.startswith('https://'):raise ValueError('HTTPS redirects required')
            return super().redirect_request(request,fp,code,msg,headers,newurl)
    opener=urllib.request.build_opener(HTTPSOnly())
    with opener.open(URL,timeout=60) as response,target.open('wb') as output:
        if not response.geturl().startswith('https://'):raise ValueError('HTTPS download required')
        size=0
        while chunk:=response.read(1024*1024):
            size+=len(chunk)
            if size>MAX_DOWNLOAD:raise ValueError('Download exceeds 512 MiB')
            output.write(chunk)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('zip',nargs='?',help='Official offline ZIP; otherwise download it over HTTPS')
    args=parser.parse_args()
    for port in (8765,8877):
        with socket.socket() as probe:
            probe.settimeout(.5)
            if probe.connect_ex(('127.0.0.1',port))==0:parser.error('Stop library and capture before installing GeoGebra.')
    try:
        with tempfile.TemporaryDirectory(prefix='izzi-geogebra-download-') as temp:
            archive=Path(args.zip) if args.zip else Path(temp)/'geogebra.zip'
            if not args.zip:print('Downloading official GeoGebra offline bundle...',flush=True);download(archive)
            count=install(archive)
        print(f'Installed {count} GeoGebra runtime files. Restart library and capture.')
        return 0
    except (OSError,ValueError,zipfile.BadZipFile) as error:
        print('GeoGebra installation failed: '+str(error))
        print('You may supply a local official ZIP containing web3d/web3d.nocache.js.')
        return 1

if __name__=='__main__':raise SystemExit(main())
