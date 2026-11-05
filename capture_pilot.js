/* Content-versioned capture coverage. No answers or account state are persisted. */
const capturePilotSessions=new WeakMap();
async function capturePilotRPC(data){
const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),30000);
try{const response=await fetch(O+'/__offline_capture__/pilot',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data),cache:'no-store',signal:controller.signal});let result;try{result=await response.json();}catch{throw new Error('Нужен е обновен capture proxy за отчета за интерактивностите.');}if(!response.ok||result.capture!==true)throw new Error(result.error||'Отчетът за интерактивностите е недостъпен. Нужен е обновен capture proxy.');return result;}
finally{clearTimeout(timer);}
}
async function capturePilotBegin(frame,lesson,resume){
let result,error;const metadata=typeof selectionMetadata!=='undefined'?selectionMetadata.get(lesson.pathname)?.flipbook:undefined;const pageNumber=metadata?.pageNumber,viewer=metadata?.viewer;
for(let i=0;i<4;i++){try{result=await capturePilotRPC({action:'begin',lesson:lesson.href,version:globalThis.__IZZI_CAPTURE_VERSION__,page_number:pageNumber,viewer,page_assets:[metadata?.image,metadata?.thumbnail].filter(Boolean)});break;}catch(e){error=e;await new Promise(r=>setTimeout(r,500));}}
if(!result)throw error;
const session={lesson,revision:result.revision,viewer,inventory:new Map(result.inventory.map(item=>[item.key,item])),verified:new Set(resume?result.verified:[]),resumed:0};
capturePilotSessions.set(frame,session);return session;
}
function capturePilotAssets(frame,lesson,extra=[]){
const values=[...(typeof captureResourceAssets==='function'?captureResourceAssets(frame,lesson):[]),...(capturePilotSessions.get(frame)?.linked||[]),...(capturePilotSessions.get(frame)?.viewer?[capturePilotSessions.get(frame).viewer]:[])];
const urls=new Set();
for(const value of [...values,...extra,lesson.href])try{const url=new URL(value,lesson.href);if(!/^https?:$/.test(url.protocol)||url.username||url.password||url.pathname.startsWith('/__offline_capture__/')||url.pathname.startsWith('/api/')||[...url.searchParams.keys()].some(k=>/token|jwt|password|session|secret|authorization/i.test(k)))continue;url.searchParams.delete('__izzi_offline_recover');url.hash='';urls.add(url.href);}catch{}
return [...urls];
}
async function capturePilotRecord(frame,key,state,details={}){
const s=capturePilotSessions.get(frame);if(!s)throw new Error('Липсва активен отчет за страницата.');
return capturePilotRPC({action:'item',lesson:s.lesson.href,revision:s.revision,key,state,...details});
}
function capturePilotPanelComplete(session,panel){
const rows=[...session.inventory.values()].filter(item=>item.panel===String(panel));return rows.length>0&&rows.every(item=>session.verified.has(item.key));
}
/* The loader's CSS flag means initialization started, not that the applet is ready. */
function capturePilotGeoHook(win){
if(win.__IZZI_PILOT_GEO__)return win.__IZZI_PILOT_GEO__;
const Original=win.GGBApplet;if(typeof Original!=='function')throw new Error('GeoGebra loader не е зареден.');
const registry={entries:new Map(),Original};
function Wrapped(parameters,...rest){
const params={...parameters},previous=params.appletOnLoad,id=String(params.id||'');
const entry={ready:false,api:null,applet:null};registry.entries.set(id,entry);
params.appletOnLoad=function(api){entry.api=api;try{entry.ready=typeof api?.getObjectNumber==='function'&&Number.isFinite(api.getObjectNumber());}catch{}if(typeof previous==='function')previous.apply(this,arguments);else if(typeof previous==='string'&&typeof win[previous]==='function')win[previous].apply(this,arguments);};
entry.applet=Reflect.construct(Original,[params,...rest]);return entry.applet;
}
Object.setPrototypeOf(Wrapped,Original);Wrapped.prototype=Original.prototype;registry.Wrapped=Wrapped;win.GGBApplet=Wrapped;win.__IZZI_PILOT_GEO__=registry;return registry;
}
async function capturePilotGeoReady(frame,block,{timeout=90000}={}){
const win=frame.contentWindow,registry=capturePilotGeoHook(win);
const roots=Array.from(block.$el.querySelectorAll('[id^="geogebra-"].int'));
if(block.$el.matches?.('[id^="geogebra-"].int'))roots.unshift(block.$el);
if(!roots.length)throw new Error('GeoGebra компонентът не е монтиран.');
const files=[];let embedded=false;
for(const root of roots){
const vm=root.__vue__,conf=vm?.conf||{};
if(conf.iframe)throw new Error('GeoGebra е външна рамка. Нужна е ръчна проверка на този вариант.');
if(conf.filename?.path){let path=conf.filename.path;if(/^\d+\/(?:publication|shared)\//.test(path))path='/datastore/'+path;files.push(new URL(path,win.document.baseURI).href);}
embedded=embedded||Boolean(conf.embed);
if(!root.classList.contains('ggc--loaded')&&!root.__izziGeoCaptureStarted){const button=root.querySelector('.int-overlay > button.cta');if(!button||button.disabled)throw new Error('Няма достъпен бутон за GeoGebra.');button.click();root.__izziGeoCaptureStarted=true;}
const holder=root.querySelector('[id^="geogebra-holder-"]');if(!holder?.id)throw new Error('Липсва GeoGebra контейнер.');
let ready=false;
for(let attempt=0;attempt<Math.ceil(timeout/250);attempt++){
const entry=registry.entries.get(holder.id);let api=entry?.api;
if(!entry)try{api=win[holder.id];}catch{}
try{if((entry?.ready||(!entry&&typeof api?.getXML==='function'&&api.getXML().includes('<geogebra')))&&typeof api?.getObjectNumber==='function'&&Number.isFinite(api.getObjectNumber())){ready=true;break;}}catch{}
await new Promise(resolve=>setTimeout(resolve,250));
}
if(!ready)throw new Error('GeoGebra не потвърди готовност в срока за изчакване.');
}
return {ready:true,embedded,files};
}
const capturePilotKinds={geogebra:'geogebra','objects-slider':'slider','fill-in':'exercise','multiple-choice':'exercise',dragndrop:'exercise',tinymce:'content',image:'content',video:'media',audio:'media',framer:'frame','go-to-link':'link','listen-and-read':'media',youtube:'media'};
function capturePilotChildren(root){
const result=[],seen=new Set();
const walk=vm=>{if(!vm||seen.has(vm))return;seen.add(vm);if(seen.size>2000)throw new Error('Прекалено голямо вложено съдържание.');for(const child of vm.$children||[]){if(child.$options?.name==='izzi-block')result.push(child);else walk(child);}};
walk(root);return result;
}
async function capturePilotVisit(frame,block,check,session,visited=new Set(),step=''){
const key='block:'+block.blockId;
if(visited.has(key))return [];visited.add(key);
const fail=async(message,state='failed')=>{await capturePilotRecord(frame,key,state,{reason:message});return [{kind:'page',url:session.lesson.href,reason:message+' [задача '+block.blockId+']'}];};
const kind=capturePilotKinds[block.blockType];
if(!kind)return fail('Непознат тип интерактивност: '+block.blockType,'manual');
if(session.verified.has(key)&&kind!=='slider'){session.resumed++;return [];}
const own=captureFlipbookComponents(block).find(vm=>vm.$options?.name===block.blockType||vm.$options?._componentTag===block.blockType);
await capturePilotRecord(frame,key,'opened',{title:block.pdfData?.title||own?.conf?.title||block.blockType+' #'+block.blockId,...(step?{parent:step}:{})});
let geo={ready:false,embedded:false,files:[]};
try{
if(kind==='geogebra')geo=await capturePilotGeoReady(frame,block);
if(kind==='slider'){
const slider=captureFlipbookComponents(block).find(vm=>vm.$options?.name==='objects-slider');
if(!slider||!Number.isInteger(slider.slideCount)||slider.slideCount<1||slider.slideCount>200||typeof slider.next!=='function'||typeof slider.prev!=='function')return fail('Слайдерът не се инициализира.');
const original=slider.currentSlide,count=slider.slideCount;
for(let step=0;slider.currentSlide>1&&step<count;step++){const old=slider.currentSlide;slider.prev();await new Promise(r=>setTimeout(r,100));if(slider.currentSlide!==old-1)return fail('Неуспешна навигация към началото на слайдера.');}
for(let index=1;index<=count;index++){
const slideKey='slide:'+slider.blockId+':'+index;
if(slider.currentSlide!==index)return fail('Не се отвори слайд '+index+'.');
await new Promise(r=>setTimeout(r,250));
if(!session.verified.has(slideKey)){
await capturePilotRecord(frame,slideKey,'opened');
const child=slider.slides?.[index-1]?.block||captureFlipbookComponents(slider).find(vm=>vm.$options?.name==='izzi-block'&&String(vm.blockId)===String(slider.slides?.[index-1]?.id));
if(!child)return fail('Не е разпозната задачата на слайд '+index+'.','manual');
const issues=await capturePilotVisit(frame,child,check,session,visited,slideKey);if(issues.length)return issues;
await capturePilotRecord(frame,slideKey,'verified',{proof:{assets:capturePilotAssets(frame,session.lesson)}});
}else session.resumed++;
if(index<count){if(slider.nextDisabled)return fail('Следващият слайд изисква отговор. Не изпращаме отговори автоматично.','manual');slider.next();await new Promise(r=>setTimeout(r,150));}
}
for(let step=0;slider.currentSlide>original&&step<count;step++){slider.prev();await new Promise(r=>setTimeout(r,50));}
}else{
for(const child of capturePilotChildren(block)){const issues=await capturePilotVisit(frame,child,check,session,visited);if(issues.length)return issues;}
}
const failures=await check();if(failures.length){await capturePilotRecord(frame,key,'failed',{reason:failures[0].reason});return failures;}
const state=['frame','link','media'].includes(kind)?'saved':'verified';
await capturePilotRecord(frame,key,state,{proof:{assets:capturePilotAssets(frame,session.lesson,geo.files),ready:geo.ready,embedded:geo.embedded}});
return [];
}catch(error){return fail(error.message);}
}
