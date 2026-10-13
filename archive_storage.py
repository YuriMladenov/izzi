"""Content addressed layout. Old flat keys remain valid until explicitly migrated."""
import re
from pathlib import PurePosixPath

def shard_key(key):
    p=PurePosixPath(key)
    if len(p.parts)==2 and p.parts[0] in ('blobs','assembled') and re.fullmatch(r'[a-f0-9]{64}\.[A-Za-z0-9]+',p.name):
        return f'{p.parts[0]}/{p.name[:2]}/{p.name[2:4]}/{p.name}'
    return key

def blob_key(digest,extension):return shard_key('blobs/'+digest+extension)

def assembled_key(digest):return shard_key('assembled/'+digest+'.mp4')
