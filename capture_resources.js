/* Activate only the GeoGebra start controls, never arbitrary lesson buttons. */
async function captureGeoGebra(frame,lesson){
const issues=[];
for(const root of frame.contentDocument.querySelectorAll('[id^="geogebra-"].int')){
if(root.classList.contains('ggc--loaded')||root.__izziGeoCaptureStarted)continue;
const button=root.querySelector('.int-overlay > button.cta');
if(!button||button.disabled)continue;
try{button.click();root.__izziGeoCaptureStarted=true;await new Promise(resolve=>setTimeout(resolve,300));}
catch(error){issues.push({kind:'page',url:lesson.href,reason:'GeoGebra не се активира: '+error.message});}
}
return issues;
}
async function captureLessonImages(frame,lesson,ping,options={}){const doc=frame.contentDocument;if(!doc||frame.contentWindow.location.pathname!==lesson.pathname)throw new Error('Урокът не е достъпен в iframe: '+lesson.pathname);
const win=frame.contentWindow,scrollRoot=doc.scrollingElement||doc.documentElement;
const startX=win.scrollX||0,startY=win.scrollY||0;let scrollIncomplete=false,scrollFailure='';
const wait=()=>new Promise(resolve=>setTimeout(resolve,500));
const styles=[];
/* Disable CSS smooth scrolling/snapping only while collecting lazy resources. */
for(const node of new Set([scrollRoot,doc.documentElement,doc.body]))if(node?.style){
for(const name of ['scroll-behavior','scroll-snap-type']){styles.push([node,name,node.style.getPropertyValue(name),node.style.getPropertyPriority(name)]);node.style.setProperty(name,name==='scroll-behavior'?'auto':'none','important');}}
const viewport=()=>Math.max(1,scrollRoot.clientHeight||win.innerHeight||900);
const position=()=>Number.isFinite(scrollRoot.scrollTop)?scrollRoot.scrollTop:(win.scrollY||0);
const bottom=()=>Math.max(0,scrollRoot.scrollHeight-viewport());
try{
win.scrollTo(0,0);await wait();let reached=false;
const deadline=Date.now()+180000;
for(let step=0;step<400&&Date.now()<deadline;step++){
const current=position(),end=bottom();
/* Firefox can clamp to an integer below a fractional layout height. */
if(current>=end-2){
await wait();
if(position()>=bottom()-2){reached=true;break;}
}
win.scrollTo(0,Math.min(bottom(),position()+Math.max(200,Math.floor(viewport()*0.75))));await wait();
}
scrollIncomplete=!reached;
if(scrollIncomplete)scrollFailure='Превъртането не достигна края ('+Math.round(position())+' / '+Math.ceil(bottom())+' px)';
}finally{
win.scrollTo(startX,startY);
for(const [node,name,value,priority] of styles.reverse()){if(value)node.style.setProperty(name,value,priority);else node.style.removeProperty(name);}
}
const seen=new Map(),failed=new Map();let inline=0;
const decode=text=>{const area=document.createElement('textarea');area.innerHTML=text;return area.value.replace(/\\u002[fF]/g,'/').replace(/\\\//g,'/').replace(/\\["']/g,'"');};
const add=value=>{if(!value)return;if(/^(data:|blob:)/i.test(value)){inline++;return;}let url;try{url=new URL(value,doc.baseURI||lesson.href)}catch{return}if(!/\.(png|jpe?g|gif|webp|svg|avif|bmp|ico)(?:$|[?#])/i.test(url.href))return;if(!/^https?:$/.test(url.protocol))return;url.hash='';seen.set(url.href,url);};
const discover=()=>{for(const node of doc.querySelectorAll('img,source,block-image')){if(node.currentSrc)add(node.currentSrc);for(const attr of ['src','data-src','data-original','data-lazy-src'])add(node.getAttribute(attr));for(const attr of ['srcset','data-srcset'])for(const part of (node.getAttribute(attr)||'').split(','))add(part.trim().split(/\s+/)[0]);}
const text=decode(doc.documentElement.outerHTML);for(const match of text.matchAll(/<(?:img|block-image)\b[^>]*?\bsrc\s*=\s*["']([^"']+)["']/gi))add(match[1]);};
const status=async url=>{const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),20000);try{const reply=await fetch(O+'/__offline_capture__/image_status?'+new URLSearchParams({url:url.href}),{cache:'no-store',signal:controller.signal});if(!reply.ok)throw new Error('Capture proxy не потвърди архива');
const result=await reply.json();return result.available===true;}finally{clearTimeout(timer)}};
const load=async url=>{if(!/(^|\.)izzi\.digital$/i.test(url.hostname)){if(await status(url)){failed.delete(url.href);return;}failed.set(url.href,'външен ресурс: нужен е повторен опит от панела');return;}if(options.skipAvailable&&await status(url))return;let reason='';for(let attempt=0;attempt<2;attempt++){try{await new Promise((resolve,reject)=>{const image=new frame.contentWindow.Image();let settled=false;
const finish=error=>{if(settled)return;settled=true;clearTimeout(timer);image.onload=null;image.onerror=null;error?reject(error):resolve()};
const timer=setTimeout(()=>finish(new Error('image timeout')),20000);image.onload=()=>finish(image.naturalWidth>0?null:new Error('невалидно изображение'));image.onerror=()=>finish(new Error('изображението не се зареди'));
const fresh=new URL(url.href);fresh.searchParams.set('__izzi_offline_recover',Date.now().toString(36)+'_'+attempt);image.src=fresh.href;});if(!await status(url))throw new Error('няма годен body в архива');failed.delete(url.href);return;}catch(error){reason=error.message;}}failed.set(url.href,reason);};if(!await status(lesson))throw new Error('HTML на урока не е записан в архива');let checked=new Set(),stable=0;for(let round=0;round<6&&stable<2;round++){discover();
const pending=[...seen.values()].filter(url=>!checked.has(url.href));stable=pending.length?0:stable+1;let index=0;await Promise.all(Array.from({length:Math.min(4,pending.length)},async()=>{while(index<pending.length){const url=pending[index++];checked.add(url.href);await load(url);}}));await new Promise(resolve=>setTimeout(resolve,1000));}discover();for(const url of seen.values())if(!checked.has(url.href))failed.set(url.href,'появи се след проверката');if(scrollIncomplete){await ping('scroll-incomplete',lesson,{reason:scrollFailure});}for(const [url,reason] of failed){console.warn('IZZI IMAGE MISSING',lesson.pathname,url,reason);await ping('image-failed',lesson,{asset:url,reason});}await ping('images-checked',lesson,{total:seen.size,failed:failed.size});return {total:seen.size,failed:failed.size+(scrollIncomplete?1:0),issues:[...[...failed].map(([url,reason])=>({kind:'image',url,reason})),...(scrollIncomplete?[{kind:'page',url:lesson.href,reason:scrollFailure}]:[])]};}
function captureFileKey(url){return /\.ggb$/i.test(url.pathname)?'izzi'+url.pathname.replace(/^\/DOS\/\d+(?=\/datastore\/)/,'')+url.search:url.href;}
function captureGgbCandidates(url){
const result=[url];
const path=url.pathname.replace(/^\/DOS\/\d+(?=\/datastore\/)/,'');
if(/\.ggb$/i.test(path)&&['bg.izzi.digital','api.izzi.digital'].includes(url.hostname)&&/^\/datastore\/\d+\/(?:publication\/\d+|shared)\/files\//.test(path)){
const api=new URL(path+url.search,'https://api.izzi.digital');
if(api.href!==url.href)result.push(api);
}
return result;
}
async function captureLessonFiles(frame,lesson,ping,options={}){const doc=frame.contentDocument,urls=new Map();
const add=value=>{if(/^\d+\/(?:publication|shared)\//.test(value))value='/datastore/'+value;let url;try{url=new URL(value,doc.baseURI||lesson.href)}catch{return}if(!/^https?:$/.test(url.protocol)||url.username||url.password||!/(^|\.)izzi\.digital$/i.test(url.hostname))return;if(!url.pathname.includes('/files/')&&!/\.(ggb|sb3|sb2|sb|exe|zip|7z|rar|pdf|docx?|xlsx?|pptx?|odt|ods|odp|txt|csv)$/i.test(url.pathname))return;url.hash='';urls.set(captureFileKey(url),url);};for(const node of doc.querySelectorAll('a[href],a[download]'))add(node.getAttribute('href'));
const area=document.createElement('textarea');area.innerHTML=doc.documentElement.outerHTML;
const text=area.value.replace(/\\u002[fF]/g,'/').replace(/\\\//g,'/').replace(/\\["']/g,'"');for(const match of text.matchAll(/<a\b[^>]*?\bhref\s*=\s*["']([^"']+)["']/gi))add(match[1]);
/* Include GeoGebra files inside hidden component configs and clientData. */
for(const match of text.matchAll(/(?:https?:\/\/[^"'\s<>\\]+|\/\/[^"'\s<>\\]+|\/(?:DOS\/\d+\/)?datastore\/[^"'\s<>\\]+|\.\/datastore\/[^"'\s<>\\]+|\d+\/(?:publication|shared)\/[^"'\s<>\\]+)\.ggb(?:\?[^"'\s<>\\]*)?/gi))add(match[0]);
/* Live component configuration wins over raw clientData resource paths. */
for(const node of doc.querySelectorAll('geogebra,[id^="geogebra-"].int')){
let config=node.__vue__?.conf;
if(!config){try{const raw=node.getAttribute?.('v-bind:config')||node.getAttribute?.(':config');if(raw){area.innerHTML=raw;config=JSON.parse(area.value).config;}}catch{}}
for(const value of [config?.filename?.path,config?.filename?.src])if(value)add(value);
}
const selected=[...urls.values()].filter(url=>!options.targets||options.targets.some(value=>{try{return captureFileKey(new URL(value,doc.baseURI||lesson.href))===captureFileKey(url);}catch{return false;}}));
let failed=0;
const issues=[];for(const url of selected){
let saved=false;const reasons=[],ggb=/\.ggb$/i.test(url.pathname);
if(options.skipAvailable){const response=await fetch(O+'/__offline_capture__/image_status?'+new URLSearchParams({url:url.href}),{cache:'no-store'});saved=response.ok&&(await response.json()).available===true;}
const candidates=captureGgbCandidates(url);
const attempts=candidates.length>1?candidates:[url,url];
for(let attempt=0;attempt<attempts.length&&!saved;attempt++){
const candidate=attempts[attempt],controller=new AbortController(),timer=setTimeout(()=>controller.abort(),120000);
try{
const fresh=new URL(candidate.href);fresh.searchParams.set('__izzi_offline_recover',Date.now().toString(36)+'_'+attempt);
const reply=await frame.contentWindow.fetch(fresh.href,{mode:'no-cors',credentials:'include',cache:'no-store',signal:controller.signal});await reply.blob();
if(ggb&&reply.type!=='opaque'&&reply.ok===false)throw new Error('HTTP '+reply.status);
for(let check=0;check<(ggb?3:20)&&!saved;check++){
const proof={url:candidate.href,...(ggb?{exact:'1'}:{})};
const response=await fetch(O+'/__offline_capture__/image_status?'+new URLSearchParams(proof),{cache:'no-store',signal:controller.signal});
if(!response.ok)throw new Error('capture status unavailable');
saved=(await response.json()).available===true;
if(!saved&&check<(ggb?2:19))await new Promise(resolve=>setTimeout(resolve,500));
}
if(!saved)throw new Error('няма годен файл в архива');
}catch(error){reasons.push(candidate.hostname+': '+error.message);}finally{clearTimeout(timer);}
}
if(!saved){const reason=reasons.join('; ');failed++;issues.push({kind:'file',url:url.href,reason});await ping('file-failed',lesson,{asset:url.href,reason});console.warn('IZZI FILE MISSING',url.href,reason);}
}
if(/<geogebra\b|block-type=["']geogebra["']|\bggc-holder\b|"template"\s*:\s*"geogebra"/i.test(text)||[...urls.values()].some(url=>/\.ggb$/i.test(url.pathname))){
const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),20000);
try{const response=await fetch(O+'/__offline_capture__/geogebra_status',{cache:'no-store',signal:controller.signal});if(!response.ok||!(await response.json()).installed)throw new Error('Нужен е локален GeoGebra web3d двигател. Спри capture и изпълни install_geogebra.py с официалния ZIP, после повтори обхода.');}
catch(error){failed++;issues.push({kind:'page',url:lesson.href,reason:error.message});}finally{clearTimeout(timer);}}
await ping('files-checked',lesson,{total:selected.length,failed});return {total:selected.length,failed,issues};}
async function captureLessonMedia(frame,lesson,ping,options={}){const doc=frame.contentDocument,urls=new Map();
const add=value=>{if(!value)return;let url;try{url=new URL(value,doc.baseURI||lesson.href)}catch{return}if(!/^https?:$/.test(url.protocol)||!/(^|\.)izzi\.digital$/i.test(url.hostname)||!/\.(mp4|mp3|webm|ogg|m4a|wav)$/i.test(url.pathname))return;url.hash='';urls.set(url.href,url);};for(const node of doc.querySelectorAll('video,audio,source,block-video,block-audio,a[href]')){add(node.currentSrc);add(node.src);for(const name of ['src','data-src','href'])add(node.getAttribute(name));}
const area=document.createElement('textarea');area.innerHTML=doc.documentElement.outerHTML;
const text=(area.value||'').replace(/\\\//g,'/').replace(/\\["']/g,'"');for(const match of text.matchAll(/(?:https?:\/\/[^"'\s<>\\]+|\/\/[^"'\s<>\\]+|\/(?:DOS\/\d+\/)?datastore\/[^"'\s<>\\]+|\.\/datastore\/[^"'\s<>\\]+)\.(?:mp4|mp3|webm|ogg|m4a|wav)(?:\?[^"'\s<>\\]*)?/gi))add(match[0]);let failed=0;
const issues=[];for(const url of urls.values()){let saved=false,reason='';for(let attempt=0;attempt<2&&!saved;attempt++){const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),240000);try{const status=()=>fetch(O+'/__offline_capture__/image_status?'+new URLSearchParams({url:url.href}),{cache:'no-store',signal:controller.signal});let reply=await status();if(!reply.ok)throw new Error('capture status unavailable');saved=(await reply.json()).available===true;if(!saved){const fresh=new URL(url.href);fresh.searchParams.set('__izzi_offline_recover',Date.now().toString(36)+'_'+attempt);reply=await frame.contentWindow.fetch(fresh.href,{mode:'no-cors',credentials:'include',cache:'no-store',signal:controller.signal});await reply.blob();for(let check=0;check<480&&!saved;check++){reply=await status();if(!reply.ok)throw new Error('capture status unavailable');saved=(await reply.json()).available===true;if(!saved)await new Promise(resolve=>setTimeout(resolve,500));}if(!saved)throw new Error('няма пълно видео/аудио в архива');}}catch(error){reason=error.message;}finally{clearTimeout(timer)}}if(!saved){failed++;issues.push({kind:'media',url:url.href,reason});await ping('media-failed',lesson,{asset:url.href,reason});console.warn('IZZI MEDIA MISSING',url.href,reason);}}await ping('media-checked',lesson,{total:urls.size,failed});return {total:urls.size,failed,issues};}
