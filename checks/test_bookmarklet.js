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
 for(let tick=0;tick<10&&!body.children.length;tick++)await Promise.resolve();
 const dialog=body.children[0];assert.equal(dialog.shown,true);
 const nodes=all(dialog),inputs=nodes.filter(x=>x.tag==='input'),button=t=>nodes.find(x=>x.tag==='button'&&x.textContent===t);
 assert.equal(inputs.length,2);assert(nodes.some(x=>x.textContent==='1. Първи урок — Пропусни'));
 assert(nodes.some(x=>x.textContent==='2. Втори урок — Пропусни'));
 if(cancel){button('Отказ').click();await task;assert.equal(events.length,0);assert.equal(dialog.removed,true);return;}
 button('Пропусни всички').click();assert.equal(button('Стартирай обхода').disabled,true);
 button('Обходи всички').click();assert.equal(button('Стартирай обхода').disabled,false);
 inputs[1].checked=true;inputs[1].listeners.change();button('Стартирай обхода').click();await task;
 assert.deepEqual(events.filter(x=>x.get('kind')==='lesson-start').map(x=>x.get('lesson')),['8']);
 assert.equal(dialog.removed,true);assert.equal(alerts.length,1);const iframe=body.children.find(x=>x.tag==='iframe');assert.equal(iframe.style.width,'1280px');assert.equal(iframe.style.height,'900px');assert(events.some(x=>x.get('kind')==='lesson-done'));assert(!events.some(x=>x.get('kind')==='lesson-incomplete'));
}
async function navigation(){
 const helper=fs.readFileSync(require('node:path').join(__dirname,'../capture_navigation.js'),'utf8');
 assert.equal(source.split('/*IZZI_NAV_START*/')[1].split('/*IZZI_NAV_END*/')[0],helper.split(/\r?\n/).join(''));
 const row=(id,name,number,kind='unit')=>({id,name,prettyPosition:number,systemType:kind,isVisible:1});
 const modules=[row(10,'Раздел А','1','module'),row(20,'Раздел Б','2','module')];
 const roots={
  initial:{modules,entries:[]},
  chapter:{modules,entries:[row(11,'Първи','1.1.'),row(12,'Секция','1.2.','section'),{...row(99,'Скрит','1.9.'),isVisible:0}]},
  section:{modules:[],entries:[row(13,'Втори','1.2.1.'),row(11,'Повторение','1.1.')]}
 };
 const element=(item,attrs={})=>({getAttribute:name=>name===':item'?JSON.stringify(item):attrs[name]||null});
 const root=data=>({querySelectorAll:selector=>selector==='breadcrumbs'?[{getAttribute:()=>JSON.stringify([{...row(10,'Раздел А','1','module'),siblings:data.modules}])}]:selector.startsWith('units-list-item')?data.entries.map(item=>element(item)):[]});
 const doc={querySelector:()=>null,createElement:()=>({set innerHTML(value){this.content=root(roots[value]);}})};
 const paths=[];
 const collect=vm.runInNewContext(helper+';collectCaptureLessons',{URL,Map,Set});
 const fetchPage=async url=>{paths.push(url.pathname);return url.pathname.endsWith('/10.html')?'chapter':url.pathname.endsWith('/12.html')?'section':'initial';};
 const lessons=await collect(doc,'https://bg.izzi.digital/DOS/1/0.html','1',fetchPage,async found=>{assert.equal(found.length,2);return [found[0]];});
 assert.deepEqual(Array.from(lessons,x=>x.name),['1.1. Първи','1.2.1. Втори']);
 assert.deepEqual(paths,['/DOS/1/0.html','/DOS/1/10.html','/DOS/1/12.html']);
 assert.equal(lessons[1].section,'Секция');
 const cancelled=await collect(doc,'https://bg.izzi.digital/DOS/1/0.html','1',fetchPage,async()=>null);
 assert.equal(cancelled.length,0);
}
async function images(){
 const helper=source.slice(source.indexOf('async function captureLessonImages'),source.indexOf("await ping('book-start',location);"));
 const urls=[],events=[];let archived=true;
 class Image{set src(value){urls.push(value);this.naturalWidth=100;queueMicrotask(()=>this.onload());}}
 const lesson=new URL('https://bg.izzi.digital/DOS/1/8.html');
 const frame={contentWindow:{location:lesson,Image,innerHeight:900,scrollY:0,positions:[],scrollTo(x,y){this.scrollY=y;this.positions.push(y);}},contentDocument:{baseURI:lesson.href,querySelectorAll:()=>[],documentElement:{scrollHeight:3000,outerHTML:String.raw`<img src="https://api.izzi.digital/datastore/picture.png"><pkc :config='{&quot;description&quot;:&quot;&lt;img src=\&quot;/datastore/config.png\&quot;&gt;&quot;}'></pkc><script>const path="/publication/1/pictures/false.png";</script><svg><use href="/profil/sprite.symbol.svg#icon"></use></svg>`}}};
 const textarea=()=>({set innerHTML(text){this.value=text.replaceAll('&quot;','"').replaceAll('&lt;','<').replaceAll('&gt;','>').replaceAll('&amp;','&');}});
 const capture=vm.runInNewContext(helper+';captureLessonImages',{O:lesson.origin,document:{createElement:textarea},URL,URLSearchParams,AbortController,console:{warn:()=>{}},setTimeout:(f,ms)=>{if(ms===1000||ms===500)queueMicrotask(f);return 1;},clearTimeout:()=>{},fetch:async url=>({ok:true,json:async()=>({available:new URL(url).searchParams.get('url').endsWith('.html')||archived})})});
 const result=await capture(frame,lesson,async(kind,u,extra)=>events.push({kind,extra}));
 assert(frame.contentWindow.positions.includes(2100));assert.equal(frame.contentWindow.scrollY,0);assert.equal(result.total,2);assert.equal(result.failed,0);
 assert(urls.some(u=>u.startsWith('https://api.izzi.digital/datastore/picture.png?__izzi_offline_recover=')));
 assert(urls.some(u=>u.startsWith('https://bg.izzi.digital/datastore/config.png?__izzi_offline_recover=')));
 archived=false;events.length=0;
 const failed=await capture(frame,lesson,async(kind,u,extra)=>events.push({kind,extra}));
 assert.equal(failed.failed,2);assert.equal(events.filter(x=>x.kind==='image-failed').length,2);
 assert(events.some(x=>x.extra.reason==='няма годен body в архива'));
}
async function attachments(){
 const helper=source.slice(source.indexOf('async function captureLessonFiles'),source.indexOf("await ping('book-start',location);"));
 const lesson=new URL('https://bg.izzi.digital/DOS/128031/8.html'),requested=[],events=[];
 const links=['./datastore/15/publication/128031/files/cParts.exe','./datastore/15/publication/128031/files/inpDevices.sb3?v=1782308254','javascript:alert(1)'];
 const frame={contentDocument:{baseURI:lesson.href,querySelectorAll:()=>links.map(href=>({getAttribute:()=>href})),documentElement:{outerHTML:''}},contentWindow:{fetch:async(url,options)=>{requested.push(new URL(url));assert.equal(options.mode,'no-cors');return {blob:async()=>({})};}}};
 let saved=true;
 const capture=vm.runInNewContext(helper+';captureLessonFiles',{O:lesson.origin,document:{createElement:()=>({innerHTML:'',value:''})},URL,URLSearchParams,AbortController,console:{warn:()=>{}},setTimeout:(f,ms)=>{if(ms===500)queueMicrotask(f);return 1;},clearTimeout:()=>{},fetch:async()=>({ok:true,json:async()=>({available:saved})})});
 const result=await capture(frame,lesson,async(kind,u,extra)=>events.push({kind,extra}));
 assert.equal(result.total,2);assert.equal(result.failed,0);assert.equal(requested.length,2);
 assert.equal(requested[1].searchParams.get('v'),'1782308254');assert(requested[0].pathname.startsWith('/DOS/128031/datastore/'));
 saved=false;events.length=0;
 assert.equal((await capture(frame,lesson,async(kind,u,extra)=>events.push({kind,extra}))).failed,2);
 assert.equal(events.filter(x=>x.kind==='file-failed').length,2);
}
async function media(){
 const helper=source.slice(source.indexOf('async function captureLessonMedia'),source.indexOf("await ping('book-start',location);"));
 const lesson=new URL('https://bg.izzi.digital/DOS/412693/9.html'),requested=[],events=[];
 const direct='https://bg.izzi.digital/DOS/412693/datastore/15/publication/3931/video/geo.mp4?v=17';
 const config='/datastore/15/publication/4043/video/sun.mp4';
 const frame={contentDocument:{baseURI:lesson.href,querySelectorAll:()=>[{src:direct,getAttribute:()=>null}],documentElement:{outerHTML:'<block-video src="'+config+'"></block-video>'}},contentWindow:{fetch:async(url,options)=>{requested.push(new URL(url));assert.equal(options.mode,'no-cors');assert.equal(options.credentials,'include');assert(!options.headers?.Range);return {blob:async()=>({})};}}};
 let available=false,success=true;
 const capture=vm.runInNewContext(helper+';captureLessonMedia',{O:lesson.origin,document:{createElement:()=>({set innerHTML(value){this.value=value;}})},URL,URLSearchParams,AbortController,console:{warn:()=>{}},setTimeout:(f,ms)=>{if(ms===500)queueMicrotask(f);return 1;},clearTimeout:()=>{},fetch:async(url)=>{const asset=new URL(url).searchParams.get('url');return {ok:true,json:async()=>({available:available||success&&requested.some(u=>u.origin+u.pathname===new URL(asset).origin+new URL(asset).pathname)})};}});
 const result=await capture(frame,lesson,async(kind,u,extra)=>events.push({kind,extra}));
 assert.equal(result.total,2);assert.equal(result.failed,0);assert.equal(requested.length,2);assert.equal(requested[0].searchParams.get('v'),'17');assert(requested.every(u=>u.searchParams.has('__izzi_offline_recover')));assert(events.some(e=>e.kind==='media-checked'));
 available=true;requested.length=0;await capture(frame,lesson,async()=>{});assert.equal(requested.length,0,'usable archived media is not downloaded again');
 available=false;success=false;requested.length=0;events.length=0;
 assert.equal((await capture(frame,lesson,async(kind,u,extra)=>events.push({kind,extra}))).failed,2);
 assert.equal(events.filter(e=>e.kind==='media-failed').length,2);
}
(async()=>{await media();await attachments();await images();await run(false);await navigation();await run(true);console.log('PASS: valid shadow host, named lessons, skip checkboxes, cancellation and traversal selection.');})().catch(e=>{console.error(e);process.exitCode=1;});
