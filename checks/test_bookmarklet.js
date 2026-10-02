const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(require('node:path').join(__dirname,'../auto_book_capture_bookmarklet.txt'),'utf8').replace(/^javascript:/,'');
class Element{
 constructor(tag){this.tag=tag;this.children=[];this.style={};this.listeners={};this.checked=false;this.disabled=false;this.attrs={};}
 appendChild(x){this.children.push(x);return x;}
 setAttribute(k,v){this.attrs[k]=v;}
 getAttribute(k){return this.attrs[k]||null;}
 addEventListener(k,f){this.listeners[k]=f;}
 attachShadow(){if(this.tag!=='div')throw new Error('NotSupportedError: unsupported shadow host');return this.shadow=new Element('shadow');}
 remove(){this.removed=true;}
 querySelector(){return null;}
 set src(value){this._src=value;this.contentWindow={location:new URL(value),innerHeight:900,scrollY:0,positions:[],scrollTo(x,y){this.scrollY=y;this.positions.push(y);}};this.contentDocument={baseURI:value,documentElement:{outerHTML:'',scrollHeight:900},querySelectorAll:()=>[]};}
 get src(){return this._src;}
 get value(){return this.innerHTML||'';}
 showModal(){this.shown=true;}
 click(){if(!this.disabled)this.listeners.click?.();}
}
function all(e){return [e,...e.children.flatMap(all),...(e.shadow?all(e.shadow):[])];}
async function run(cancel){
 const body=new Element('body'),events=[],alerts=[];
 const link=(id,name)=>Object.assign(new Element('a'),{href:'https://bg.izzi.digital/DOS/1/'+id+'.html',innerText:name});
 const links=[link('8',''),link('2','Втори урок <b>'),link('8','Първи урок'),Object.assign(link('9','Чужд'),{href:'https://bg.izzi.digital/DOS/9/9.html'})];
 const doc={body,createElement:t=>new Element(t),querySelectorAll:()=>links,getElementById:id=>body.children.find(x=>x.id===id&&!x.removed)||null};
 const task=vm.runInNewContext(source,{document:doc,location:new URL('https://bg.izzi.digital/DOS/1/index.html'),URL,URLSearchParams,AbortController,Map,Set,console:{warn:()=>{},error:()=>{}},clearTimeout:()=>{},alert:x=>alerts.push(x),fetch:async u=>{const q=new URL(u);if(q.pathname.endsWith('image_status'))return {ok:true,json:async()=>({capture:true,available:true})};events.push(q.searchParams);},setInterval:()=>1,clearInterval:()=>{},setTimeout:(f,ms)=>{if(ms!==20000)f();return 1;}});
 const dialog=body.children[0];assert.equal(dialog.shown,true);
 const nodes=all(dialog),inputs=nodes.filter(x=>x.tag==='input'),button=t=>nodes.find(x=>x.tag==='button'&&x.textContent===t);
 assert.equal(inputs.length,2);assert(nodes.some(x=>x.textContent==='1. Първи урок — Пропусни'));
 assert(nodes.some(x=>x.textContent==='2. Втори урок <b> — Пропусни'));
 if(cancel){button('Отказ').click();await task;assert.equal(events.length,0);assert.equal(dialog.removed,true);return;}
 button('Пропусни всички').click();assert.equal(button('Стартирай обхода').disabled,true);
 button('Обходи всички').click();assert.equal(button('Стартирай обхода').disabled,false);
 inputs[1].checked=true;inputs[1].listeners.change();button('Стартирай обхода').click();await task;
 assert.deepEqual(events.filter(x=>x.get('kind')==='lesson-start').map(x=>x.get('lesson')),['8']);
 assert.equal(dialog.removed,true);assert.equal(alerts.length,1);const iframe=body.children.find(x=>x.tag==='iframe');assert.equal(iframe.style.width,'1280px');assert.equal(iframe.style.height,'900px');assert(events.some(x=>x.get('kind')==='lesson-done'));assert(!events.some(x=>x.get('kind')==='lesson-incomplete'));
}
async function images(){
 const helper=source.slice(source.indexOf('async function captureLessonImages'),source.indexOf('const probe='));
 const urls=[],events=[];let archived=true;
 class Image{set src(value){urls.push(value);this.naturalWidth=100;queueMicrotask(()=>this.onload());}}
 const lesson=new URL('https://bg.izzi.digital/DOS/1/8.html');
 const frame={contentWindow:{location:lesson,Image,innerHeight:900,scrollY:0,positions:[],scrollTo(x,y){this.scrollY=y;this.positions.push(y);}},contentDocument:{baseURI:lesson.href,querySelectorAll:()=>[],documentElement:{scrollHeight:3000,outerHTML:String.raw`<img src="https://api.izzi.digital/datastore/picture.png"><pkc :config='{&quot;description&quot;:&quot;&lt;img src=\&quot;/datastore/config.png\&quot;&gt;&quot;}'></pkc>`}}};
 const textarea=()=>({set innerHTML(text){this.value=text.replaceAll('&quot;','"').replaceAll('&lt;','<').replaceAll('&gt;','>').replaceAll('&amp;','&');}});
 const capture=vm.runInNewContext(helper+';captureLessonImages',{O:lesson.origin,document:{createElement:textarea},URL,URLSearchParams,AbortController,console:{warn:()=>{}},setTimeout:(f,ms)=>{if(ms===1000||ms===500)queueMicrotask(f);return 1;},clearTimeout:()=>{},fetch:async url=>({ok:true,json:async()=>({available:new URL(url).searchParams.get('url').endsWith('.html')||archived})})});
 const result=await capture(frame,lesson,async(kind,u,extra)=>events.push({kind,extra}));
 assert(frame.contentWindow.positions.includes(2100));assert.equal(frame.contentWindow.scrollY,0);assert.equal(result.total,2);assert.equal(result.failed,0);
 assert(urls.includes('https://api.izzi.digital/datastore/picture.png'));
 assert(urls.includes('https://bg.izzi.digital/datastore/config.png'));
 archived=false;events.length=0;
 const failed=await capture(frame,lesson,async(kind,u,extra)=>events.push({kind,extra}));
 assert.equal(failed.failed,2);assert.equal(events.filter(x=>x.kind==='image-failed').length,2);
 assert(events.some(x=>x.extra.reason==='няма годен body в архива'));
}
(async()=>{await images();await run(false);await run(true);console.log('PASS: valid shadow host, named lessons, skip checkboxes, cancellation and traversal selection.');})().catch(e=>{console.error(e);process.exitCode=1;});
