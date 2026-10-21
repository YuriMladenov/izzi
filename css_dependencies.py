"""Read CSS resource tokens without entering comments, strings or data URLs."""
import re
from urllib.parse import urljoin

def unescape(value):
    def replace(match):
        if match[1]:
            code=int(match[1],16)
            return chr(code) if 0<code<=0x10ffff and not 0xd800<=code<=0xdfff else '\ufffd'
        return match[3] or ''
    return re.sub(r'\\([0-9a-fA-F]{1,6})(?:\r\n|[ \t\r\n\f])?|\\(\r\n|[\r\n\f])|\\(.)',replace,value,flags=re.S)

def references(text):
    size=len(text);i=0
    def quoted(start):
        quote=text[start];end=start+1
        while end<size:
            if text[end]=='\\':end+=2
            elif text[end]==quote:return text[start+1:end],end+1
            else:end+=1
        return text[start+1:],size
    while i<size:
        if text.startswith('/*',i):
            end=text.find('*/',i+2);i=size if end<0 else end+2;continue
        if text[i] in '\"\'':_,i=quoted(i);continue
        if text[i]=='\\':i+=2;continue
        match=re.match(r'url\s*\(',text[i:i+32],re.I) if text[i:i+3].lower()=='url' and (i==0 or not re.match(r'[\w-]',text[i-1])) else None
        if match:
            start=i+match.end()
            while start<size and text[start].isspace():start+=1
            if start<size and text[start] in '\"\'':
                value,end=quoted(start);i=end
                while i<size and text[i].isspace():i+=1
                if i<size and text[i]==')':i+=1;yield unescape(value)
            else:
                end=start;depth=1
                while end<size:
                    if text[end]=='\\':end+=2;continue
                    if text[end]=='(':depth+=1
                    if text[end]==')':
                        depth-=1
                        if not depth:break
                    end+=1
                i=min(size,end+1)
                if not depth:yield unescape(text[start:end].strip())
            continue
        if text[i:i+7].lower()=='@import' and (i+7==size or not re.match(r'[\w-]',text[i+7])):
            i+=7
            while i<size:
                if text[i].isspace():i+=1
                elif text.startswith('/*',i):
                    end=text.find('*/',i+2);i=size if end<0 else end+2
                else:break
            if i<size and text[i] in '\"\'':
                value,i=quoted(i);yield unescape(value)
            continue
        i+=1

def external_targets(text,base):
    return {urljoin(base,value.strip()) for value in references(text)
            if value.strip() and not value.strip().lower().startswith(('#','data:','blob:'))}

def legacy_targets(text,base):
    # Reconstruct only what the previous scanner actually added, for migration.
    values=[m[1].strip('\"\' ') for m in re.finditer(r'url\(\s*([^)]*)\)',text)]
    values.extend(re.findall(r'@import\s+[\"\']([^\"\']+)',text))
    return {urljoin(base,value) for value in values if value and not value.startswith(('#','data:','blob:'))}
