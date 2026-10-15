/* Strict completion, targeted recovery and visible resource markers. Embedded in the bookmarklet. */
async function captureLoadLesson(frame,lesson){
let previous;try{previous=frame.contentDocument;}catch{}
/* A deleted archive cannot be repopulated from the browser's memory cache. */
const fresh=new URL(lesson.href);fresh.searchParams.set('__izzi_offline_recover',Date.now().toString(36)+'_'+Math.random().toString(36).slice(2));
let loaded=false;frame.onload=()=>{loaded=true;};frame.src=fresh.href;
for(let attempt=0;attempt<100;attempt++){
try{
const doc=frame.contentDocument,win=frame.contentWindow,app=doc?.querySelector?.('.app-main');
if(win?.location.pathname===lesson.pathname&&doc?.readyState!=='loading'&&doc?.body&&(!app||app.classList?.contains('app-main--ready'))&&(loaded||doc!==previous))return;
}catch{}
await new Promise(resolve=>setTimeout(resolve,250));
}
/* Strict checks report a page failure instead of marking an unmounted lesson done. */
}
function captureResourceKey(value,base){
try{const u=new URL(String(value).replace(/\\+/g,'/'),base);u.hash='';u.searchParams.delete('__izzi_offline_recover');
const id=/^(?:www\.|m\.)?(?:youtube\.com|youtube-nocookie\.com|youtu\.be)$/.test(u.hostname)?(u.searchParams.get('v')||u.pathname.match(/\/(?:embed|shorts|live)\/([\w-]{11})/)?.[1]||(u.hostname.endsWith('youtu.be')?u.pathname.slice(1):'')):'';
if(id)return 'youtube:'+id;
const path=u.pathname.replace(/^\/DOS\/\d+\/(datastore|profil|_nuxt)\//,'/$1/');
return (/(^|\.)izzi\.digital$/.test(u.hostname)?'izzi':u.origin)+path;
}catch{return '';}
}
function captureResourceTargets(frame,issue){
const found=[],visited=new Set(),wanted=captureResourceKey(issue.url,issue.url);
const walk=(doc,depth=0)=>{
if(!doc||visited.has(doc)||depth>3)return;visited.add(doc);
const nodes=doc.querySelectorAll('img,video,audio,source,iframe,a,script,link,block-image,block-video,block-audio,youtube-player,pkc,[style],[data-src],[data-original],[data-lazy-src]');
for(const node of nodes){
let match=false;
for(const value of [node.currentSrc,node.src,...['src','href','data-src','data-original','data-lazy-src'].map(name=>node.getAttribute(name))])if(value&&captureResourceKey(value,doc.baseURI||issue.url)===wanted)match=true;
for(const name of ['srcset','data-srcset'])for(const part of (node.getAttribute(name)||'').split(','))if(captureResourceKey(part.trim().split(/\s+/)[0],doc.baseURI||issue.url)===wanted)match=true;
if(node.tagName==='YOUTUBE-PLAYER'&&wanted==='youtube:'+node.getAttribute('video-id'))match=true;
for(const attr of Array.from(node.attributes||[]))if(attr.name.includes('config')&&attr.value.includes(new URL(issue.url).pathname))match=true;
for(const part of (node.getAttribute('style')||'').matchAll(/url\(\s*["']?([^"')]+)["']?\s*\)/g))if(captureResourceKey(part[1],doc.baseURI||issue.url)===wanted)match=true;
const target=node.tagName==='SOURCE'?(node.closest('video,audio')||node):node;
if(match){const rect=target.getBoundingClientRect();if(rect.width>0&&rect.height>0&&!found.includes(target))found.push(target);}
if(node.tagName==='IFRAME')try{walk(node.contentDocument,depth+1);}catch{}
}
};
try{walk(frame.contentDocument);}catch{}
return found;
}
function captureResourceAssets(frame,lesson){
const urls=new Set(),visited=new Set();
const add=value=>{try{const u=new URL(value,lesson.href);if(/^https?:$/.test(u.protocol)&&/(^|\.)izzi\.digital$/.test(u.hostname)&&!u.pathname.startsWith('/__offline_capture__/')){u.hash='';u.searchParams.delete('__izzi_offline_recover');urls.add(u.href);}}catch{}};
const scan=(win,depth=0)=>{
try{if(!win||visited.has(win)||depth>3)return;visited.add(win);const doc=win.document;
for(const item of win.performance?.getEntriesByType('resource')||[])add(item.name);
for(const node of doc.querySelectorAll('script[src],link[rel="stylesheet"][href],img[src],video[src],audio[src],source[src],iframe[src]')){add(node.currentSrc||node.src||node.href);if(node.tagName==='IFRAME')scan(node.contentWindow,depth+1);}
}catch{}
};scan(frame.contentWindow);return [...urls];
}
async function captureArchiveBarrier(frame,lesson){
let last;
for(let attempt=0;attempt<20;attempt++){
const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),20000);
try{const response=await fetch(O+'/__offline_capture__/lesson_status',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({lesson:lesson.href,assets:captureResourceAssets(frame,lesson)}),cache:'no-store',signal:controller.signal});
if(!response.ok)throw new Error('Capture proxy не потвърди пълнотата на урока');last=await response.json();if(last.capture!==true)throw new Error('Нужен е обновен capture proxy');if(last.available)return [];
if((last.missing||[]).length&&!last.pending?.length&&last.quiet_ms>=1000)break;
}finally{clearTimeout(timer);}
await new Promise(resolve=>setTimeout(resolve,500));
}
const issues=[...(last?.missing||[])];
for(const url of last?.pending||[])issues.push({kind:'asset',url,reason:'Заявката още не е приключила'});
if(!last?.tracked)issues.push({kind:'page',url:lesson.href,reason:'Capture proxy не следи текущия урок. Провери връзката и повтори зареждането.'});
if(last?.limit_reached)issues.push({kind:'page',url:lesson.href,reason:'Превишен е лимитът от 2000 проследявани ресурса'});
if(!issues.length)issues.push({kind:'page',url:lesson.href,reason:'Зареждането още не се е установило'});
return issues;
}
async function recoverCaptureResource(issue,frame,lesson,ping){
if(issue.kind==='page')throw new Error('Използвай „Повтори проверката“, за да заредиш урока отново.');
if(issue.kind==='link'||issue.kind==='youtube'){
const result=await captureLessonLinks(frame,lesson,ping,{targets:[issue.url]});
if(result.failed)throw new Error(result.issues[0]?.reason||'Препратката не е записана');
if(!result.total)throw new Error('Препратката вече не присъства в урока');
const id=captureResourceKey(issue.url,lesson.href).replace(/^youtube:/,'');
const endpoint=issue.kind==='youtube'?'/__offline_capture__/youtube?'+new URLSearchParams({id}):'/__offline_capture__/link_status?'+new URLSearchParams({url:issue.url});
const response=await fetch(O+endpoint,{cache:'no-store'});if(!response.ok||(await response.json()).available!==true)throw new Error('Препратката още не е потвърдена в архива');
return;
}
if(issue.kind==='file'&&/\.ggb$/i.test(new URL(issue.url).pathname)){
const result=await captureLessonFiles(frame,lesson,ping,{targets:[issue.url]});
if(!result.total)throw new Error('GeoGebra файлът вече не присъства в урока');
if(result.failed)throw new Error(result.issues[0]?.reason||'GeoGebra файлът още не е записан');
await ping('resource-recovered',lesson,{asset:issue.url});return;
}
const url=new URL(issue.url),external=!/(^|\.)izzi\.digital$/.test(url.hostname);
if(external)await ping('link-register',lesson,{asset:url.href});
const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),issue.kind==='media'||issue.kind==='file'?240000:30000);
try{
const fresh=new URL(url.href);fresh.searchParams.set('__izzi_offline_recover',Date.now().toString(36));
if(issue.kind==='image'){
await new Promise((resolve,reject)=>{
const image=new frame.contentWindow.Image(),finish=error=>{image.onload=image.onerror=null;controller.signal.removeEventListener('abort',abort);error?reject(error):resolve();},abort=()=>finish(new Error('Изтече времето за изображението'));
controller.signal.addEventListener('abort',abort,{once:true});image.onload=()=>finish(image.naturalWidth?null:new Error('Невалидно изображение'));image.onerror=()=>finish(new Error('Изображението не се зареди'));image.src=fresh.href;
});
}else{const response=await frame.contentWindow.fetch(fresh.href,{mode:'no-cors',credentials:'include',cache:'no-store',signal:controller.signal});await response.blob();}
let available=false;
for(let attempt=0;attempt<40&&!available;attempt++){
const response=await fetch(O+'/__offline_capture__/image_status?'+new URLSearchParams({url:url.href}),{cache:'no-store',signal:controller.signal});if(!response.ok)throw new Error('Capture proxy е недостъпен');available=(await response.json()).available===true;if(!available)await new Promise(resolve=>setTimeout(resolve,500));
}
if(!available)throw new Error('Ресурсът още няма годен запис в архива');
/* Refresh only the selected rendered resource; never run downloaded attachments. */
for(const node of captureResourceTargets(frame,issue)){
if(node.tagName==='IMG'){node.src=fresh.href;for(const name of ['srcset','data-srcset'])if(node.getAttribute(name))node.setAttribute(name,node.getAttribute(name).split(',').map(part=>{const fields=part.trim().split(/\s+/);if(captureResourceKey(fields[0],node.ownerDocument.baseURI)===captureResourceKey(issue.url,lesson.href))fields[0]=fresh.href;return fields.join(' ');}).join(', '));}
else if(node.tagName==='VIDEO'||node.tagName==='AUDIO'){node.src=fresh.href;node.load();}
else if(node.tagName==='IFRAME')node.src=fresh.href;
else if(issue.kind==='image'&&node.style.backgroundImage)node.style.backgroundImage=node.style.backgroundImage.replace(/url\(\s*["']?([^"')]+)["']?\s*\)/g,(whole,value)=>captureResourceKey(value,node.ownerDocument.baseURI)===captureResourceKey(issue.url,lesson.href)?'url('+JSON.stringify(fresh.href)+')':whole);
}
await ping('resource-recovered',lesson,{asset:issue.url});
}finally{clearTimeout(timer);}
}
async function captureStrictChecks(frame,lesson,ping,skipAvailable=typeof missingOnly!=='undefined'&&missingOnly){
const issues=[];
try{
const doc=frame.contentDocument,app=doc?.querySelector?.('.app-main');
if(!doc||frame.contentWindow?.location?.pathname!==lesson.pathname||(doc.readyState==='loading')||(app&&!app.classList?.contains('app-main--ready')))return [{kind:'page',url:lesson.href,reason:'Приложението на урока не завърши зареждането. Провери грешките и достъпа в оригиналния сайт.'}];
}catch(error){return [{kind:'page',url:lesson.href,reason:error.message}];}
if(typeof captureGeoGebra==='function')issues.push(...await captureGeoGebra(frame,lesson));
const checks=await Promise.allSettled([captureLessonImages(frame,lesson,ping,{skipAvailable}),captureLessonFiles(frame,lesson,ping,{skipAvailable}),captureLessonMedia(frame,lesson,ping,{skipAvailable})]);
for(const result of checks){
if(result.status==='fulfilled')issues.push(...(result.value.issues||[]));
else issues.push({kind:'page',url:lesson.href,reason:result.reason.message});
}
try{const result=await captureLessonLinks(frame,lesson,ping,{skipAvailable});issues.push(...(result.issues||[]));}catch(error){issues.push({kind:'page',url:lesson.href,reason:error.message});}
try{
const missing=await captureArchiveBarrier(frame,lesson);
for(const issue of missing){const existing=issues.find(row=>captureResourceKey(row.url,lesson.href)===captureResourceKey(issue.url,lesson.href));if(!existing)issues.push(issue);else if(issue.reason.startsWith('HTTP ')&&!existing.reason.includes('HTTP '))existing.reason+=' · '+issue.reason;}
}catch(error){issues.push({kind:'page',url:lesson.href,reason:error.message});}
return issues;
}
function showCapturePause(frame,lesson,issues,ping){
return new Promise(resolve=>{
const host=document.createElement('div');host.id='izzi-offline-capture-pause';host.setAttribute('role','region');host.setAttribute('aria-label','Обходът е спрян за липсващи ресурси');
Object.assign(host.style,{position:'fixed',left:'12px',top:'12px',width:'min(380px,92vw)',maxHeight:'calc(100vh - 24px)',zIndex:'2147483647'});
const shadow=host.attachShadow({mode:'open'}),style=document.createElement('style');style.textContent=':host{font:15px system-ui;color:#17212b}*{box-sizing:border-box}.panel{background:white;border:2px solid #bb2633;border-radius:12px;box-shadow:0 8px 32px #0005;padding:16px;max-height:calc(100vh - 24px);overflow:auto}h2{font-size:20px;margin:0 0 12px}p{line-height:1.4}.issue{border-top:1px solid #ddd;padding:12px 0}.issue button{width:100%;text-align:left;overflow-wrap:anywhere}.issue small{display:block;overflow-wrap:anywhere;margin-top:6px;color:#64748b}.buttons{display:grid;gap:8px;margin-top:16px}button{font:inherit;border:1px solid #ccd3dd;background:white;border-radius:7px;padding:10px;cursor:pointer}button:focus,button:hover{border-color:#bb2633}button:disabled{opacity:.6}.ok{color:#26713a}.status{font-weight:bold}';shadow.appendChild(style);
const panel=document.createElement('div');panel.className='panel';shadow.appendChild(panel);
const heading=document.createElement('h2');heading.textContent='Обходът е спрян';panel.appendChild(heading);
const name=document.createElement('p');name.textContent=typeof selectionMetadata!=='undefined'?(selectionMetadata.get(lesson.pathname)?.name||lesson.pathname):lesson.pathname;panel.appendChild(name);
const hint=document.createElement('p');hint.textContent='Посочи причина за червена маркировка. Кликни върху причината или маркирания ресурс за повторно изтегляне.';panel.appendChild(hint);
const list=document.createElement('div');panel.appendChild(list);
const status=document.createElement('p');status.className='status';status.setAttribute('role','status');panel.appendChild(status);
const original=frame.style.cssText;const scale=Math.max(.2,Math.min(1,(window.innerWidth-420)/1280,(window.innerHeight-30)/900));
Object.assign(frame.style,{right:'8px',bottom:'12px',transform:'scale('+scale+')',transformOrigin:'bottom right'});
let closed=false,busy=false,marked=[];
const clear=()=>{for(const item of marked){item.node.style.setProperty('outline',item.outline,item.outlinePriority);item.node.style.setProperty('outline-offset',item.offset,item.offsetPriority);item.node.removeEventListener('click',item.click,true);item.badge.remove();}marked=[];};
const finish=action=>{if(closed)return;closed=true;clear();frame.style.cssText=original;host.remove();resolve(action);};
const mark=(issue,click)=>{
clear();let targets=captureResourceTargets(frame,issue);
if(!targets.length&&issue.kind==='page')targets=[frame];
for(const node of targets){
const item={node,outline:node.style.getPropertyValue('outline'),outlinePriority:node.style.getPropertyPriority('outline'),offset:node.style.getPropertyValue('outline-offset'),offsetPriority:node.style.getPropertyPriority('outline-offset'),click};
node.style.setProperty('outline','4px solid #e02020','important');node.style.setProperty('outline-offset','3px','important');node.scrollIntoView({block:'center',inline:'nearest'});node.addEventListener('click',click,true);
const badge=node.ownerDocument.createElement('button');badge.type='button';badge.textContent='↧ Изтегли отново';const rect=node.getBoundingClientRect();Object.assign(badge.style,{position:'fixed',left:Math.max(0,rect.left)+'px',top:Math.max(0,rect.top)+'px',zIndex:'2147483647',background:'#c52020',color:'white',border:'1px solid white',padding:'8px',font:'16px system-ui',cursor:'pointer'});badge.addEventListener('click',click);node.ownerDocument.body.appendChild(badge);item.badge=badge;marked.push(item);
}
status.textContent=targets.length?'Маркирани елементи: '+targets.length:'Няма видим елемент за този ресурс. Кликни върху причината за повторен опит.';
};
const buttons=document.createElement('div');buttons.className='buttons';panel.appendChild(buttons);
const button=(text,action)=>{const node=document.createElement('button');node.type='button';node.textContent=text;node.addEventListener('click',action);buttons.appendChild(node);return node;};
const retryAll=button('Повтори проверката',()=>finish('retry'));
const continueButton=button('Продължи въпреки липсите',()=>finish('continue'));
button('Прекрати обхода',()=>finish('stop'));
const pending=new Set(issues);
for(const issue of issues){
const row=document.createElement('div');row.className='issue';list.appendChild(row);
const action=document.createElement('button');action.type='button';action.textContent=issue.reason||'Липсващ ресурс';row.appendChild(action);
const url=document.createElement('small');try{const parsed=new URL(issue.url);url.textContent=parsed.hostname+parsed.pathname;}catch{url.textContent=issue.url;}row.appendChild(url);
const retry=async event=>{
event?.preventDefault();event?.stopPropagation();if(busy||closed||!pending.has(issue))return;
if(issue.kind==='page'){finish('retry');return;}
busy=true;retryAll.disabled=continueButton.disabled=true;list.querySelectorAll('button').forEach(node=>node.disabled=true);clear();status.textContent='Изтегляне и проверка на ресурса…';
try{await recoverCaptureResource(issue,frame,lesson,ping);if(closed)return;pending.delete(issue);action.textContent='✓ Записан в архива';action.className='ok';status.textContent='Ресурсът е записан. Оставащи причини: '+pending.size;if(!pending.size){finish('retry');return;}}
catch(error){if(closed)return;action.textContent=error.message;issue.reason=error.message;mark(issue,retry);status.textContent='Неуспешно изтегляне. Можеш да повториш.';await ping('resource-retry-failed',lesson,{asset:issue.url,reason:error.message}).catch(()=>{});}
finally{if(!closed){busy=false;retryAll.disabled=continueButton.disabled=false;list.querySelectorAll('button').forEach(node=>node.disabled=node.className==='ok');}}
};
action.addEventListener('pointerenter',()=>{if(!busy&&pending.has(issue))mark(issue,retry);});action.addEventListener('focus',()=>{if(!busy&&pending.has(issue))mark(issue,retry);});action.addEventListener('click',retry);
}
document.body.appendChild(host);list.querySelectorAll('button')[0]?.focus?.();
});
}
