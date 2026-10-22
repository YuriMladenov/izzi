"""Seed persistent application code once; keep archives on their existing mounts."""
import os,shutil,sys,tempfile
from pathlib import Path

def prepare(seed=Path('/app'),volume=Path('/opt/izzi')):
    seed=Path(seed);volume=Path(volume);volume.mkdir(parents=True,exist_ok=True)
    target=volume/'project'
    if not target.exists():
        with tempfile.TemporaryDirectory(prefix='.seed-',dir=volume) as temporary:
            stage=Path(temporary)/'project'
            shutil.copytree(seed,stage,ignore=shutil.ignore_patterns('archive','state','captures','capture','__pycache__','.venv','geogebra','geogebra-backups'))
            if not (stage/'.git').is_dir() or not (stage/'project_launcher.py').is_file():raise ValueError('Invalid image seed')
            os.replace(stage,target)
    for name in ('archive','state','captures','vendor/geogebra'):
        source=seed/name;source.mkdir(parents=True,exist_ok=True)
        link=target/name;link.parent.mkdir(parents=True,exist_ok=True)
        if link.is_symlink():
            if link.resolve()!=source.resolve():raise ValueError('Unexpected data link: '+str(link))
        elif link.exists():raise ValueError('Data path is not a mount link: '+str(link))
        else:link.symlink_to(source,target_is_directory=True)
    exclude=target/'.git/info/exclude'
    text=exclude.read_text() if exclude.exists() else ''
    rules=['/archive','/state','/captures','/capture','/vendor/geogebra']
    exclude.parent.mkdir(parents=True,exist_ok=True)
    missing=[rule for rule in rules if rule not in text.splitlines()]
    if missing:exclude.write_text(text+'\n'+'\n'.join(missing)+'\n')
    return target

if __name__=='__main__':
    root=prepare();os.chdir(root)
    os.execv(sys.executable,[sys.executable,'-u',str(root/'project_launcher.py')])
