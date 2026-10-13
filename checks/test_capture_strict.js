/* Resource mapping and pause controls, without a live site or browser dependency. */
const assert=require('node:assert/strict'),fs=require('fs'),vm=require('node:vm'),path=require('node:path');
const helper=fs.readFileSync(path.join(__dirname,'../capture_strict.js'),'utf8');
const bookmark=fs.readFileSync(path.join(__dirname,'../auto_book_capture_bookmarklet.txt'),'utf8');
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
let task=api.showCapturePause(frame,lesson,[issue],async(kind,url,extra)=>events.push({kind,extra}));
let panel=doc.body.children.find(node=>!node.removed&&node.id==='izzi-offline-capture-pause');
const reason=all(panel).find(node=>node.tagName==='BUTTON'&&node.textContent===issue.reason);reason.events.pointerenter();
assert.equal(image.style.getPropertyValue('outline'),'4px solid #e02020');assert(image.scrolled);assert.equal(requests,0);
await image.click();assert.equal(await task,'retry');assert.equal(requests,1);assert.equal(image.style.getPropertyValue('outline'),'1px dotted green');assert(panel.removed);assert(events.some(event=>event.kind==='resource-recovered'));
confirmArchive=false;available=false;task=api.showCapturePause(frame,lesson,[issue],async()=>{});panel=doc.body.children.find(node=>!node.removed&&node.id==='izzi-offline-capture-pause');await all(panel).find(node=>node.tagName==='BUTTON'&&node.textContent===issue.reason).click();assert(!panel.removed,'An image load without archived body must leave capture paused');all(panel).find(node=>node.tagName==='BUTTON'&&node.textContent==='Прекрати обхода').click();assert.equal(await task,'stop');
for(const [label,result] of [['Продължи въпреки липсите','continue'],['Прекрати обхода','stop']]){
task=api.showCapturePause(frame,lesson,[issue],async()=>{});panel=doc.body.children.find(node=>!node.removed&&node.id==='izzi-offline-capture-pause');all(panel).find(node=>node.tagName==='BUTTON'&&node.textContent===label).click();assert.equal(await task,result);
}
console.log('PASS: strict helper embedding, URL aliases, visible red marking, direct click recovery, archive confirmation, style restoration, continue and stop.');
}
run().catch(error=>{console.error(error);process.exitCode=1;});
