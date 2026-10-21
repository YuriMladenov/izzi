/* Linked datastore applications live on the API host; keep their relative assets together. */
function captureBlockURL(value,base){
const url=new URL(String(value).replace(/\\+/g,'/'),base);
if(!url.username&&!url.password&&['http:','https:'].includes(url.protocol)&&url.hostname==='bg.izzi.digital'&&['','80','443'].includes(url.port)&&/^\/(?:DOS\/\d+\/)?datastore\/blocks\/\d+(?:\/|$)/.test(url.pathname)){
url.protocol='https:';url.host='api.izzi.digital';url.pathname=url.pathname.replace(/^\/DOS\/\d+(?=\/datastore\/)/,'');
}
url.hash='';return url;
}
async function captureConfirmBlockPage(url){
const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),30000);
try{
const fresh=new URL(url.href);fresh.searchParams.set('__izzi_offline_recover',Date.now().toString(36));
const reply=await fetch(fresh.href,{mode:'no-cors',credentials:'include',cache:'no-store',signal:controller.signal});await reply.blob();
const proof=await fetch(O+'/__offline_capture__/image_status?'+new URLSearchParams({url:url.href,exact:'1'}),{cache:'no-store',signal:controller.signal});
if(!proof.ok||(await proof.json()).available!==true)throw new Error('Няма потвърден HTML отговор за приложението');
}finally{clearTimeout(timer);}
}
/* Capture linked apps in their own frames and verify their GET dependencies. */
async function captureLessonLinks(frame,lesson,ping,options={}){
const found=new Map(),originals=new Map(),delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const add=(value,base)=>{try{const url=captureBlockURL(value,base);if(!['http:','https:'].includes(url.protocol)||url.username||url.password)return;if(/(?:^|\.)(?:googletagmanager\.com|google-analytics\.com|doubleclick\.net)$/.test(url.hostname))return;if(url.pathname===lesson.pathname&&url.origin===lesson.origin)return;if((url.hostname==='izzi.digital'||url.hostname.endsWith('.izzi.digital'))&&/^\/DOS\/\d+\/\d+\.html$/.test(url.pathname))return;url.hash='';if(!originals.has(url.href)){const original=new URL(String(value).replace(/\\+/g,'/'),base);original.hash='';originals.set(url.href,original);}found.set(url.href,url);}catch{}};
const scan=(doc,base)=>{base=doc.baseURI||base;for(const node of doc.querySelectorAll('a[href],iframe[src]')){if(node.closest?.('header,nav,aside,footer,.breadcrumbs,.main-menu'))continue;add(node.getAttribute(node.tagName==='IFRAME'?'src':'href'),base);}const textarea=document.createElement('textarea');textarea.innerHTML=(doc.querySelector?.('main')||doc.querySelector?.('.xblocks')||doc.body||doc.documentElement).outerHTML;const text=textarea.value.replace(/\\\//g,'/').replace(/\\"/g,'"');for(const match of text.matchAll(/<(?:a|iframe)\b[^>]*?\b(?:href|src)\s*=\s*["']([^"']+)["']/gi))add(match[1],base);for(const match of text.matchAll(/"(?:src|href|referenceUrl|resourceUrl)"\s*:\s*"([^"<>]+)"/g))add(match[1],base);textarea.innerHTML=doc.documentElement.outerHTML;const youtubeText=textarea.value.replace(/\\\//g,'/').replace(/\\"/g,'"');for(const match of youtubeText.matchAll(/<youtube-player\b[^>]*?\bvideo-id\s*=\s*["']([A-Za-z0-9_-]{11})["']/gi))add('https://www.youtube.com/watch?v='+match[1],base);for(const match of youtubeText.matchAll(/"youtube"\s*:\s*\{[^{}]*?"videoId"\s*:\s*"([A-Za-z0-9_-]{11})"/g))add('https://www.youtube.com/watch?v='+match[1],base);for(const match of text.matchAll(/https?:\/\/(?:www\.|m\.)?(?:youtube\.com|youtube-nocookie\.com|youtu\.be)\/[^\s"'<>]+/g))add(match[0],base);};
scan(frame.contentDocument,lesson.href);
let failed=0;const issues=[];
for(const candidate of found.values()){
let url=candidate;
if(options.targets&&!options.targets.some(value=>{try{return captureBlockURL(value,lesson.href).href===url.href;}catch{return false;}}))continue;
let child=null;
try{
const youtube=/^(?:www\.|m\.)?(?:youtube\.com|youtube-nocookie\.com|youtu\.be)$/.test(url.hostname);
if(youtube){
const id=url.hostname.endsWith('youtu.be')?url.pathname.slice(1).split('/')[0]:url.searchParams.get('v')||url.pathname.match(/^\/(?:embed|shorts|live)\/([\w-]{11})/)?.[1];
if(!id||!/^[-\w]{11}$/.test(id))continue;
await ping('youtube-start',lesson,{asset:'https://www.youtube.com/watch?v='+id});
let state;for(let attempt=0;attempt<90;attempt++){const response=await fetch(O+'/__offline_capture__/youtube?'+new URLSearchParams({id,...(attempt===0?{start:'1'}:{})}),{cache:'no-store'});state=await response.json();if(state.available)break;if(state.state==='failed')throw new Error(state.error);await delay(10000);}
if(!state?.available)throw new Error('YouTube видеото не е записано в срока за изчакване');
await ping('youtube-checked',lesson,{asset:'https://www.youtube.com/watch?v='+id});continue;
}
await ping('link-register',lesson,{asset:url.href});
/* Confirm this exact API response: an archived bg alias must not mask an API error. */
if(url.hostname==='api.izzi.digital'&&/^\/datastore\/blocks\/\d+\//.test(url.pathname)&&(/\.html?$/i.test(url.pathname)||url.pathname.endsWith('/'))){
try{await captureConfirmBlockPage(url);}catch(error){
const original=originals.get(candidate.href);
if(!original||original.href===url.href)throw error;
url=original;await ping('link-register',lesson,{asset:url.href});await captureConfirmBlockPage(url);
}
}
const request=await fetch(O+'/__offline_capture__/link_status?'+new URLSearchParams({url:url.href}),{cache:'no-store'});if(!request.ok)throw new Error('Регистрацията на връзката е отказана');const initialStatus=await request.json();if(options.skipAvailable&&initialStatus.available){if(typeof rememberCaptureIssues==='function')rememberCaptureIssues(lesson,initialStatus.warnings||[]);await ping('link-checked',lesson,{asset:url.href});continue;}
if(/\.(?:pdf|exe|zip|rar|7z|sb[23]|docx?|xlsx?|pptx?|png|jpe?g|mp[34]|webm|ggb)(?:$)/i.test(url.pathname)){
const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),240000);try{await fetch(url.href,{mode:'no-cors',credentials:'include',cache:'no-store',signal:controller.signal});}finally{clearTimeout(timer);}
}else{
child=document.createElement('iframe');child.style.cssText='position:fixed;width:1280px;height:900px;left:-1400px;top:0';document.body.appendChild(child);
await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(new Error('Връзката не се зареди')),30000);child.onload=()=>{clearTimeout(timer);resolve();};child.src=url.href;});
await delay(10000);
try{const doc=child.contentDocument;if(doc){const scroll=child.contentWindow;for(let y=0;y<Math.min(doc.documentElement.scrollHeight,90000);y+=700){scroll.scrollTo(0,y);await delay(150);}scan(doc,url.href);}}catch{}
}
let checked;for(let attempt=0;attempt<20;attempt++){const response=await fetch(O+'/__offline_capture__/link_status?'+new URLSearchParams({url:url.href}),{cache:'no-store'});checked=await response.json();if(checked.available)break;for(const missing of (checked.missing||[]).slice(0,4)){const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),30000);try{await fetch(missing,{mode:'no-cors',credentials:'include',cache:'no-store',signal:controller.signal});}catch{}finally{clearTimeout(timer);}}await delay(500);}
if(typeof rememberCaptureIssues==='function'){rememberCaptureIssues(lesson,checked?.warnings||[]);rememberCaptureIssues(lesson,(checked?.missing||[]).map(value=>({kind:'asset',url:value,reason:'Липсва зависимост на '+url.href})));}if(checked?.limit_reached)throw new Error('Превишен е лимитът от 2000 зависимости на връзка');if(!checked?.available)throw new Error((checked?.problem?checked.problem+' ':'')+'Липсват зависимости: '+(checked?.missing||[]).join(', '));
await ping('link-checked',lesson,{asset:url.href,total:checked.total});
}catch(error){failed++;issues.push({kind:/^(?:www\.|m\.)?(?:youtube\.com|youtube-nocookie\.com|youtu\.be)$/.test(url.hostname)?'youtube':'link',url:url.href,reason:error.message});console.warn('IZZI LINK FAILED',url.href,error);await ping('link-failed',lesson,{asset:url.href,reason:error.message});}finally{child?.remove();}
}
return {failed,total:found.size,issues};
}
