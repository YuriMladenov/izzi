/* Resource mapping and pause controls, without a live site or browser dependency. */
const assert=require('node:assert/strict'),fs=require('fs'),vm=require('node:vm'),path=require('node:path');
const helper=fs.readFileSync(path.join(__dirname,'../capture_strict.js'),'utf8');
const bookmark=fs.readFileSync(path.join(__dirname,'../auto_book_capture_standalone.txt'),'utf8');
for(const [marker,file] of [['STRICT','capture_strict.js'],['RESOURCES','capture_resources.js']])assert.equal(bookmark.split('/*IZZI_'+marker+'_START*/')[1].split('/*IZZI_'+marker+'_END*/')[0],fs.readFileSync(path.join(__dirname,'../'+file),'utf8').split(/\r?\n/).join(''));
class Style{
constructor(){this.values={};this.cssText='original';}
getPropertyValue(name){return this.values[name]||'';}
getPropertyPriority(){return '';}
setProperty(name,value){this.values[name]=value;}
}
class Element{
constructor(tag,doc){this.tagName=tag.toUpperCase();this.ownerDocument=doc;this.style=new Style();this.children=[];this.events={};this.attrs={};this.disabled=false;this.className='';}
appendChild(node){this.children.push(node);return node;}
replaceChildren(){this.children=[];}
setAttribute(name,value){this.attrs[name]=value;}
getAttribute(name){return this.attrs[name]||null;}
get attributes(){return Object.entries(this.attrs).map(([name,value])=>({name,value}));}
getBoundingClientRect(){return {width:244,height:134,left:30,top:30};}
scrollIntoView(){this.scrolled=true;}
addEventListener(name,fn){this.events[name]=fn;}
removeEventListener(name,fn){if(this.events[name]===fn)delete this.events[name];}
attachShadow(){return this.shadow=new Element('shadow',this.ownerDocument);}
remove(){this.removed=true;}
querySelectorAll(selector){return all(this).filter(node=>selector==='button'&&node.tagName==='BUTTON');}
click(){if(!this.disabled)return this.events.click?.({preventDefault(){},stopPropagation(){}});}
}
function all(node){return [node,...node.children.flatMap(all),...(node.shadow?all(node.shadow):[])];}
async function run(){
let available=false,requests=0,confirmArchive=true;
const doc={baseURI:'https://bg.izzi.digital/DOS/1/8.html',createElement(tag){return new Element(tag,this);}};doc.body=new Element('body',doc);
const image=doc.createElement('img');image.src='https://api.izzi.digital/datastore/pic.png';image.style.setProperty('outline','1px dotted green');doc.querySelectorAll=()=>[image];
const lesson=new URL(doc.baseURI),frame=doc.createElement('iframe');frame.contentDocument=doc;
frame.contentWindow={document:doc,performance:{getEntriesByType:()=>[{name:image.src},{name:'https://google-analytics.com/log'}]},Image:class{set src(value){available=confirmArchive;requests++;this.naturalWidth=100;queueMicrotask(()=>this.onload());}}};
const events=[];
const context={document:doc,window:{innerWidth:1280,innerHeight:900},URL,URLSearchParams,AbortController,Map,Set,O:lesson.origin,fetch:async()=>({ok:true,json:async()=>({available})}),setTimeout:(fn,ms)=>{if(ms===500)queueMicrotask(fn);return 1;},clearTimeout:()=>{},console};
const api=vm.runInNewContext(helper+';({captureResourceTargets,captureResourceKey,captureResourceAssets,showCapturePause})',context);
assert.equal(api.captureResourceKey(image.src,doc.baseURI),api.captureResourceKey('https://bg.izzi.digital/DOS/1/datastore/pic.png?__izzi_offline_recover=x',doc.baseURI));
assert.equal(api.captureResourceAssets(frame,lesson).length,1);
const issue={kind:'image',url:image.src,reason:'Изображението не се зареди'};
assert.equal(api.captureResourceTargets(frame,issue)[0],image);
for(const empty of ['', ' ', undefined, null, '#section'])assert.equal(api.captureResourceKey(empty,doc.baseURI),'');
assert.equal(api.captureResourceTargets(frame,{kind:'asset',url:doc.baseURI}).length,0,'missing srcset must not resolve to the lesson URL');
assert.equal(api.captureResourceTargets(frame,{kind:'page',url:doc.baseURI})[0],frame,'page errors mark only the frame');
let task=api.showCapturePause(frame,lesson,[issue],async(kind,url,extra)=>events.push({kind,extra}));
let panel=doc.body.children.find(node=>!node.removed&&node.id==='izzi-offline-capture-pause');
const reason=all(panel).find(node=>node.tagName==='BUTTON'&&node.textContent===issue.reason);reason.events.pointerenter();
assert.equal(image.style.getPropertyValue('outline'),'4px solid #e02020');assert(image.scrolled);assert.equal(requests,0);
await image.click();assert.equal(await task,'retry');assert.equal(requests,1);assert.equal(image.style.getPropertyValue('outline'),'1px dotted green');assert(panel.removed);assert(events.some(event=>event.kind==='resource-recovered'));
confirmArchive=false;available=false;task=api.showCapturePause(frame,lesson,[issue],async()=>{});panel=doc.body.children.find(node=>!node.removed&&node.id==='izzi-offline-capture-pause');await all(panel).find(node=>node.tagName==='BUTTON'&&node.textContent===issue.reason).click();assert(!panel.removed,'An image load without archived body must leave capture paused');all(panel).find(node=>node.tagName==='BUTTON'&&node.textContent==='Прекрати обхода').click();assert.equal(await task,'stop');
for(const [label,result] of [['Продължи въпреки липсите','continue'],['Прекрати обхода','stop']]){
task=api.showCapturePause(frame,lesson,[issue],async()=>{});panel=doc.body.children.find(node=>!node.removed&&node.id==='izzi-offline-capture-pause');all(panel).find(node=>node.tagName==='BUTTON'&&node.textContent===label).click();assert.equal(await task,result);
}
const pageIssue={kind:'page',url:lesson.href,reason:'Превъртането не достигна края'};
task=api.showCapturePause(frame,lesson,[pageIssue],async()=>{});panel=doc.body.children.find(node=>!node.removed&&node.id==='izzi-offline-capture-pause');
const pageButton=all(panel).find(node=>node.tagName==='BUTTON'&&node.textContent===pageIssue.reason);pageButton.events.pointerenter();
assert.equal(frame.style.getPropertyValue('outline'),'4px solid #e02020');
assert.equal(image.style.getPropertyValue('outline'),'1px dotted green');
assert(!all(doc.body).some(node=>!node.removed&&node.textContent==='↧ Изтегли отново'),'page errors must not create download badges');
await pageButton.click();assert.equal(await task,'retry');assert.equal(frame.style.getPropertyValue('outline'),'');
console.log('PASS: strict helper embedding, URL aliases, visible red marking, direct click recovery, archive confirmation, style restoration, page-only marking, continue and stop.');
}
async function readiness(){
const lesson=new URL('https://bg.izzi.digital/DOS/1/8.html');
const ready={readyState:'complete',body:{},querySelector:()=>({classList:{contains:()=>true}})};
const fresh={readyState:'loading',body:{},querySelector:()=>({classList:{contains:()=>mounted}}),querySelectorAll:()=>[]};
let mounted=false,ticks=0;
const frame={contentDocument:ready,contentWindow:{location:lesson}};
const context={URL,URLSearchParams,AbortController,Map,Set,O:lesson.origin,console,clearTimeout(){},setTimeout(fn){queueMicrotask(()=>{ticks++;frame.contentDocument=fresh;if(ticks===2)fresh.readyState='interactive';if(ticks===3)mounted=true;fn();});return 1;}};
const api=vm.runInNewContext(helper+';({captureLoadLesson,captureStrictChecks})',context);
await api.captureLoadLesson(frame,lesson);assert.equal(ticks,3,'a same-URL retry must wait for its new document and mounted application');
const requested=new URL(frame.src);assert.equal(requested.pathname,lesson.pathname);assert(requested.searchParams.get('__izzi_offline_recover'),'every lesson navigation must bypass a previously cached HTML body');assert.equal(lesson.searchParams.has('__izzi_offline_recover'),false,'canonical lesson identity stays unchanged');
mounted=false;
let issues=await api.captureStrictChecks(frame,lesson,async()=>{});
assert.equal(issues.length,1);assert.equal(issues[0].kind,'page','an unmounted lesson must never pass capture');
mounted=true;frame.contentWindow.location=new URL('https://bg.izzi.digital/login');
issues=await api.captureStrictChecks(frame,lesson,async()=>{});assert.equal(issues[0].kind,'page','a login redirect must never pass capture');
const started=[],releases=[];
frame.contentWindow.location=lesson;frame.contentWindow.document=fresh;
for(const [name,label] of [['captureLessonImages','images'],['captureLessonFiles','files'],['captureLessonMedia','media']])context[name]=(f,u,p,options)=>{started.push(label);assert(options.skipAvailable);return new Promise(resolve=>releases.push(()=>resolve({issues:[]})));};
context.captureLessonLinks=async()=>{started.push('links');return {issues:[]};};
context.fetch=async()=>({ok:true,json:async()=>({capture:true,available:true})});
context.setTimeout=()=>1;
const task=api.captureStrictChecks(frame,lesson,async()=>{},true);
assert.deepEqual(started,['images','files','media'],'independent resource checks start together');
for(const release of releases)release();issues=await task;
assert.equal(issues.length,0);assert.equal(started[3],'links','wait for every parallel check before dependencies and final archive confirmation');
console.log('PASS: fresh document navigation, Vue readiness, wrong-page rejection, parallel checks and archive barrier.');
}
async function report(){
const lesson=new URL('https://bg.izzi.digital/DOS/1/8.html'),requests=[];
let available=false;
const doc={createElement(tag){return new Element(tag,this);}};doc.body=new Element('body',doc);
const context={document:doc,URL,URLSearchParams,AbortController,Map,Set,O:lesson.origin,Date,console,clearTimeout(){},setTimeout(fn,ms){if(ms===500)queueMicrotask(fn);return 1;},fetch:async value=>{const url=new URL(value);requests.push(url);if(url.pathname.endsWith('image_status'))return {ok:true,json:async()=>({capture:true,available})};if(url.pathname.endsWith('/event'))return {ok:true};return {blob:async()=>{available=true;}};}};
const api=vm.runInNewContext(helper+';({showCaptureReport,rememberCaptureIssues,captureDeferredResources,checkDeferredResource})',context);
const row={kind:'asset',url:'https://api.izzi.digital/exercise.js',reason:'HTTP 404'};
api.rememberCaptureIssues(lesson,[row]);api.rememberCaptureIssues(lesson,[{kind:'asset',url:'https://api.izzi.digital/app.js.map',reason:'Missing',severity:'warning',policy_reason:'Diagnostic'}]);
const task=api.showCaptureReport({},'Finished',async()=>{}),panel=doc.body.children[0];
const buttons=label=>all(panel).filter(node=>node.tagName==='BUTTON'&&node.textContent===label);
assert.equal(buttons('Провери файла').length,2);assert.equal(buttons('Провери урока отново').length,2);
await buttons('Провери файла')[0].click();assert.equal(api.captureDeferredResources.values().next().value.confirmed,false);
await buttons('Изтегли отново')[0].click();assert.equal(api.captureDeferredResources.values().next().value.confirmed,true);
assert.equal(api.captureDeferredResources.size,2,'file confirmation must not mark the lesson complete or remove its review row');
assert(requests.some(url=>url.searchParams.get('exact')==='1'));
assert(requests.some(url=>url.hostname==='api.izzi.digital'&&url.searchParams.has('__izzi_offline_recover')));
buttons('Затвори')[0].click();await task;assert(panel.removed);
available=false;context.fetch=async()=>({ok:true,blob:async()=>{},json:async()=>({capture:true,available:false})});
assert.equal(await api.checkDeferredResource({...row,lesson:lesson.href},true),false,'a successful network response without an archived body must fail');
console.log('PASS: deferred report, independent checks/downloads, exact archive confirmation and explicit close.');
}
async function automaticRecovery(){
const lesson=new URL('https://bg.izzi.digital/DOS/1/8.html'),asset='https://api.izzi.digital/exercise.js';let available=false,downloads=0;
const doc={readyState:'complete',body:{},querySelector:()=>null,querySelectorAll:()=>[]};
const frame={contentDocument:doc,contentWindow:{document:doc,location:lesson}};
const context={URL,URLSearchParams,AbortController,Map,Set,O:lesson.origin,console,clearTimeout(){},setTimeout(fn,ms){if(ms===500)queueMicrotask(fn);return 1;},captureLessonImages:async()=>({issues:[]}),captureLessonFiles:async()=>({issues:[]}),captureLessonMedia:async()=>({issues:[]}),captureLessonLinks:async()=>({issues:[]}),fetch:async value=>{
const url=new URL(value);if(url.pathname.endsWith('lesson_status'))return {ok:true,json:async()=>({capture:true,available,tracked:true,quiet_ms:1500,pending:[],missing:available?[]:[{kind:'asset',url:asset,reason:'Missing'}],warnings:[{kind:'asset',url:asset+'.map',severity:'warning',reason:'Missing map'}]})};
if(url.pathname.endsWith('image_status'))return {ok:true,json:async()=>({capture:true,available})};
if(url.pathname.endsWith('/event'))return {ok:true};downloads++;return {blob:async()=>{available=true;}};
}};
const api=vm.runInNewContext(helper+';({captureStrictChecks,captureDeferredResources})',context);
const issues=await api.captureStrictChecks(frame,lesson,async()=>{},true);
assert.equal(issues.length,0);assert.equal(downloads,1);assert.equal(api.captureDeferredResources.size,1);assert.equal(api.captureDeferredResources.values().next().value.severity,'warning');
console.log('PASS: automatic asset recovery rechecks archive barrier and preserves optional warnings.');
}
run().then(readiness).then(report).then(automaticRecovery).catch(error=>{console.error(error);process.exitCode=1;});
