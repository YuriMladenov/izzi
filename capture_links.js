/* Capture linked apps in their own frames and verify their GET dependencies. */
async function captureLessonLinks(frame,lesson,ping){
const found=new Map(),delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const add=(value,base)=>{try{const url=new URL(String(value).replace(/\\+/g,'/'),base);if(!['http:','https:'].includes(url.protocol)||url.username||url.password)return;if(/(?:^|\.)(?:googletagmanager\.com|google-analytics\.com|youtube\.com|youtube-nocookie\.com|doubleclick\.net)$/.test(url.hostname))return;if(url.pathname===lesson.pathname&&url.origin===lesson.origin)return;if(/^\/DOS\/\d+\/\d+\.html$/.test(url.pathname))return;url.hash='';found.set(url.href,url);}catch{}};
const scan=(doc,base)=>{for(const node of doc.querySelectorAll('a[href],iframe[src]')){if(node.closest?.('header,nav,aside'))continue;add(node.getAttribute(node.tagName==='IFRAME'?'src':'href'),base);}const textarea=document.createElement('textarea');textarea.innerHTML=doc.documentElement.outerHTML;const text=textarea.value.replace(/\\\//g,'/').replace(/\\"/g,'"');for(const match of text.matchAll(/<(?:a|iframe)\b[^>]*?\b(?:href|src)\s*=\s*["']([^"']+)["']/gi))add(match[1],base);for(const match of text.matchAll(/"src"\s*:\s*"([^"<>]+)"/g))add(match[1],base);};
scan(frame.contentDocument,lesson.href);
let failed=0;
for(const url of found.values()){
let child=null;
try{
await ping('link-register',lesson,{asset:url.href});
const request=await fetch(O+'/__offline_capture__/link_status?'+new URLSearchParams({url:url.href}),{cache:'no-store'});if(!request.ok)throw new Error('Регистрацията на връзката е отказана');
if(/\.(?:pdf|exe|zip|rar|7z|sb[23]|docx?|xlsx?|pptx?|png|jpe?g|mp[34]|webm)(?:$)/i.test(url.pathname)){
const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),240000);try{await fetch(url.href,{mode:'no-cors',credentials:'include',cache:'no-store',signal:controller.signal});}finally{clearTimeout(timer);}
}else{
child=document.createElement('iframe');child.style.cssText='position:fixed;width:1280px;height:900px;left:-1400px;top:0';document.body.appendChild(child);
await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(new Error('Връзката не се зареди')),30000);child.onload=()=>{clearTimeout(timer);resolve();};child.src=url.href;});
await delay(10000);
try{const doc=child.contentDocument;if(doc){const scroll=child.contentWindow;for(let y=0;y<Math.min(doc.documentElement.scrollHeight,90000);y+=700){scroll.scrollTo(0,y);await delay(150);}for(const nested of doc.querySelectorAll('iframe[src]'))add(nested.getAttribute('src'),url.href);}}catch{}
}
let checked;for(let attempt=0;attempt<20;attempt++){const response=await fetch(O+'/__offline_capture__/link_status?'+new URLSearchParams({url:url.href}),{cache:'no-store'});checked=await response.json();if(checked.available)break;for(const missing of (checked.missing||[]).slice(0,4)){const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),30000);try{await fetch(missing,{mode:'no-cors',credentials:'include',cache:'no-store',signal:controller.signal});}catch{}finally{clearTimeout(timer);}}await delay(500);}
if(checked?.limit_reached)throw new Error('Превишен е лимитът от 2000 зависимости на връзка');if(!checked?.available)throw new Error('Липсват зависимости: '+(checked?.missing||[]).join(', '));
await ping('link-checked',lesson,{asset:url.href,total:checked.total});
}catch(error){failed++;console.warn('IZZI LINK FAILED',url.href,error);await ping('link-failed',lesson,{asset:url.href,reason:error.message});}finally{child?.remove();}
}
return {failed,total:found.size};
}
