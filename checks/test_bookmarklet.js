const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(require('node:path').join(__dirname,'../auto_book_capture_bookmarklet.txt'),'utf8').replace(/^javascript:/,'');
class Element{
 constructor(tag){this.tag=tag;this.children=[];this.style={};this.listeners={};this.checked=false;this.disabled=false;this.attrs={};}
 appendChild(x){this.children.push(x);return x;}
 replaceChildren(){this.children=[];}
 querySelectorAll(selector){return all(this).filter(x=>selector==='button'&&x.tag==='button');}
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
 const task=vm.runInNewContext(source,{document:doc,location:new URL('https://bg.izzi.digital/DOS/1/index.html'),URL,URLSearchParams,AbortController,Map,Set,confirm:()=>true,console:{warn:()=>{},error:()=>{}},clearTimeout:()=>{},alert:x=>alerts.push(x),fetch:async u=>{const q=new URL(u);if(q.pathname.endsWith('image_status'))return {ok:true,json:async()=>({capture:true,available:true})};if(q.pathname.endsWith('lesson_status'))return {ok:true,json:async()=>({capture:true,available:true})};events.push(q.searchParams);return {ok:true};},setInterval:()=>1,clearInterval:()=>{},setTimeout:(f,ms)=>{if(ms!==20000)f();return 1;}});
 for(let tick=0;tick<10&&!body.children.length;tick++)await Promise.resolve();
 const dialog=body.children[0];assert.equal(dialog.shown,true);
 const nodes=all(dialog),inputs=nodes.filter(x=>x.tag==='input'),button=t=>nodes.find(x=>x.tag==='button'&&x.textContent===t);
 assert.equal(inputs.length,2);assert(nodes.some(x=>x.textContent==='1. Първи урок — Пропусни'));
 assert(nodes.some(x=>x.textContent==='2. Втори урок — Пропусни'));
 if(cancel){button('Отказ').click();await task;assert.equal(events.length,0);assert.equal(dialog.removed,true);return;}
 button('Пропусни всички').click();assert.equal(button('Стартирай обхода').disabled,true);
 button('Обходи всички').click();assert.equal(button('Стартирай обхода').disabled,false);
 inputs[1].checked=true;inputs[1].listeners.change();button('Стартирай обхода').click();
 for(let tick=0;tick<2000&&!doc.getElementById('izzi-offline-capture-report');tick++)await Promise.resolve();
 const report=doc.getElementById('izzi-offline-capture-report');assert(report,'completion report must open');
 assert(all(report).some(x=>x.textContent==='Няма пропуснати ресурси в отчета.'));
 all(report).find(x=>x.tag==='button'&&x.textContent==='Затвори').click();await task;
 assert.deepEqual(events.filter(x=>x.get('kind')==='lesson-start').map(x=>x.get('lesson')),['8']);
 assert.equal(dialog.removed,true);assert.equal(alerts.length,0);const iframe=body.children.find(x=>x.tag==='iframe');assert.equal(iframe.style.width,'1280px');assert.equal(iframe.style.height,'900px');assert(events.some(x=>x.get('kind')==='lesson-done'));assert(!events.some(x=>x.get('kind')==='lesson-incomplete'));
}
async function navigation(){
 const helper=fs.readFileSync(require('node:path').join(__dirname,'../capture_navigation.js'),'utf8');
 assert.equal(source.split('/*IZZI_NAV_START*/')[1].split('/*IZZI_NAV_END*/')[0],helper.split(/\r?\n/).join(''));
 const row=(id,name,number,kind='unit')=>({id,name,prettyPosition:number,systemType:kind,isVisible:1});
 const modules=[{...row(10,'Раздел А','1','module'),status:2,isVisible:0},row(20,'Раздел Б','2','module')];
 const roots={
  initial:{modules,entries:[]},
  chapter:{modules,entries:[{...row(11,'Първи','1.1.'),status:2,isVisible:0},row(12,'Секция','1.2.','section'),{...row(99,'Скрит','1.9.'),isVisible:0}]},
  section:{modules:[],entries:[row(13,'Втори','1.2.1.'),row(11,'Повторение','1.1.')]}
 };
 const element=(item,attrs={})=>({getAttribute:name=>name===':item'?JSON.stringify(item):attrs[name]||null});
 const root=data=>({querySelector:()=>data.hasContent?{}:null,querySelectorAll:selector=>selector==='breadcrumbs'?[{getAttribute:()=>JSON.stringify([{...row(10,'Раздел А','1','module'),siblings:data.modules}])}]:selector.startsWith('units-list-item')?data.entries.map(item=>element(item)):[]});
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
async function linkedApps(){
 const helper=fs.readFileSync(require('node:path').join(__dirname,'../capture_links.js'),'utf8');
 assert.equal(source.split('/*IZZI_LINKS_START*/')[1].split('/*IZZI_LINKS_END*/')[0],helper.split(/\r?\n/).join(''));
 const body=new Element('body'),events=[],requests=[],navigated=[];let exactAvailable=true,bgAvailable=true;
 class Frame extends Element{set src(value){navigated.push(value);this.contentDocument=null;queueMicrotask(()=>this.onload());}}
 const capture=vm.runInNewContext(helper+';captureLessonLinks',{URL,URLSearchParams,Map,AbortController,O:'https://bg.izzi.digital',console:{warn:()=>{}},document:{body,createElement:tag=>tag==='iframe'?new Frame(tag):new Element(tag)},fetch:async url=>{requests.push(new URL(url));return {ok:true,blob:async()=>({}),json:async()=>({available:String(url).includes('exact=1')?(new URL(new URL(url).searchParams.get('url')).hostname==='api.izzi.digital'?exactAvailable:bgAvailable):true,total:3})};},setTimeout:(f,ms)=>{if(ms!==30000)queueMicrotask(f);return 1;},clearTimeout:()=>{}});
 const html='<a href="./9.html">Related lesson</a><a href="./datastore/notes/explanation.html">Explanation</a><a href="https://api.izzi.digital/datastore/15/publication/1/pictures/detail.png">Detail</a><pkc v-bind:config=\'{"src":"./datastore/blocks/123/app.html","text":"<a href=\\"https://resources.example.org/app/index.html\\">Open</a>"}\'></pkc><script src="./not-a-linked-page.js"></script>';
 const frame={contentDocument:{querySelectorAll:()=>[],documentElement:{outerHTML:html}}};
 const result=await capture(frame,new URL('https://bg.izzi.digital/DOS/1/8.html'),async(kind,u,extra)=>events.push({kind,extra}));
 assert.equal(result.total,4);assert.equal(result.failed,0);
 assert.equal(events.filter(e=>e.kind==='link-register').length,4);
 assert(events.some(e=>e.extra.asset==='https://api.izzi.digital/datastore/blocks/123/app.html'));
 assert(events.some(e=>e.extra.asset==='https://resources.example.org/app/index.html'));
 assert(!events.some(e=>e.extra.asset==='https://bg.izzi.digital/DOS/1/9.html'));
 assert(events.some(e=>e.extra.asset.endsWith('/datastore/notes/explanation.html')));
 assert(events.some(e=>e.extra.asset.endsWith('/pictures/detail.png')));
 assert(body.children.every(e=>e.removed));
 assert(navigated.includes('https://api.izzi.digital/datastore/blocks/123/app.html'));
 assert(requests.some(url=>url.hostname==='api.izzi.digital'&&url.searchParams.has('__izzi_offline_recover')));
 assert(requests.some(url=>url.pathname==='/__offline_capture__/image_status'&&url.searchParams.get('exact')==='1'));
 // A real API failure cannot be masked by an already captured bg HTML alias.
 frame.contentDocument.documentElement.outerHTML='<a href="./datastore/blocks/657825/index.html">Application</a>';
 exactAvailable=false;bgAvailable=false;const beforeFailed=navigated.length;
 let failure=await capture(frame,new URL('https://bg.izzi.digital/DOS/1/8.html'),async()=>{});
 assert.equal(failure.failed,1);assert(failure.issues[0].reason.includes('HTML'));assert.equal(navigated.length,beforeFailed);

 bgAvailable=true;events.length=0;
 const fallback=await capture(frame,new URL('https://bg.izzi.digital/DOS/1/8.html'),async(kind,u,extra)=>events.push({kind,extra}));
 assert.equal(fallback.failed,0);assert(events.some(e=>e.kind==='link-checked'&&e.extra.asset==='https://bg.izzi.digital/DOS/1/datastore/blocks/657825/index.html'),'keep a working original app if API is unavailable');
 exactAvailable=true;events.length=0;
 failure=await capture(frame,new URL('https://bg.izzi.digital/DOS/1/8.html'),async(kind,u,extra)=>events.push({kind,extra}),{targets:['https://bg.izzi.digital/DOS/1/datastore/blocks/657825/index.html']});
 assert.equal(failure.failed,0);assert(events.some(e=>e.kind==='link-checked'&&e.extra.asset==='https://api.izzi.digital/datastore/blocks/657825/index.html'));

 // A downloadable GeoGebra worksheet must use fetch, not an HTML iframe.
 const before=body.children.length;
 frame.contentDocument.baseURI='https://bg.izzi.digital/datastore/blocks/657825/';
 frame.contentDocument.documentElement.outerHTML='<a href="example.ggb">GeoGebra file</a>';
 events.length=0;await capture(frame,new URL('https://bg.izzi.digital/DOS/1/8.html'),async(kind,u,extra)=>events.push({kind,extra}));
 assert.equal(body.children.length,before);assert(events.some(e=>e.extra.asset==='https://api.izzi.digital/datastore/blocks/657825/example.ggb'));
 delete frame.contentDocument.baseURI;

 frame.contentDocument.documentElement.outerHTML='<youtube-player video-id="abcdefghijk"></youtube-player>';
 events.length=0;const youtubeResult=await capture(frame,new URL('https://bg.izzi.digital/DOS/1/8.html'),async(kind,u,extra)=>events.push({kind,extra}));
 assert.equal(youtubeResult.failed,0);assert(events.some(e=>e.kind==='youtube-checked'&&e.extra.asset.endsWith('abcdefghijk')));
 frame.contentDocument.querySelector=()=>({outerHTML:'<div>visible content</div>'});frame.contentDocument.documentElement.outerHTML='<script>{"youtube":{"videoId":"abcdefghijk"}}</script>';events.length=0;
 await capture(frame,new URL('https://bg.izzi.digital/DOS/1/8.html'),async(kind,u,extra)=>events.push({kind,extra}));
 assert(events.some(e=>e.kind==='youtube-checked'));
}
async function images(){
 const helper=fs.readFileSync(require('node:path').join(__dirname,'../capture_resources.js'),'utf8');
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
async function scrollReadiness(){
 const helper=fs.readFileSync(require('node:path').join(__dirname,'../capture_resources.js'),'utf8');
 const lesson=new URL('https://bg.izzi.digital/DOS/888413/888434.html');
 async function scenario({height,clamp=true,blocked=false,grow=false}){
  const values=new Map([['scroll-behavior',['smooth','']],['scroll-snap-type',['y mandatory','important']]]);
  const style={getPropertyValue:n=>values.get(n)?.[0]||'',getPropertyPriority:n=>values.get(n)?.[1]||'',setProperty:(n,v,p)=>values.set(n,[v,p]),removeProperty:n=>values.delete(n)};
  const root={scrollHeight:height,clientHeight:899,scrollTop:0,style,outerHTML:''};let steps=0,grown=false;
  const frame={contentDocument:{baseURI:lesson.href,documentElement:root,scrollingElement:root,body:{style},querySelectorAll:()=>[]},contentWindow:{location:lesson,innerHeight:900,scrollX:0,scrollY:0,scrollTo(x,y){
    steps++;if(blocked)return;
    assert.equal(style.getPropertyValue('scroll-behavior'),'auto');assert.equal(style.getPropertyValue('scroll-snap-type'),'none');
    let top=Math.min(y,root.scrollHeight-root.clientHeight);if(clamp)top=Math.floor(top);root.scrollTop=Math.max(0,top);this.scrollY=root.scrollTop;
    if(grow&&!grown&&root.scrollTop>=root.scrollHeight-root.clientHeight-2){grown=true;root.scrollHeight+=1000;}
  }}};
  const capture=vm.runInNewContext(helper+';captureLessonImages',{O:lesson.origin,document:{createElement:()=>({set innerHTML(v){this.value=v;}})},URL,URLSearchParams,AbortController,Date,console:{warn:()=>{}},setTimeout:(f,ms)=>{if(ms===500||ms===1000)queueMicrotask(f);return 1;},clearTimeout:()=>{},fetch:async()=>({ok:true,json:async()=>({available:true})})});
  const result=await capture(frame,lesson,async()=>{});
  assert.equal(style.getPropertyValue('scroll-behavior'),'smooth');assert.equal(style.getPropertyPriority('scroll-snap-type'),'important');
  return {result,steps,grown};
 }
 assert.equal((await scenario({height:3000.75})).result.failed,0,'fractional bottom is reachable');
 const long=await scenario({height:95000.25});assert.equal(long.result.failed,0,'long lesson exceeds the old 120-step budget');assert(long.steps>120);
 const growing=await scenario({height:3000.75,grow:true});assert(growing.grown);assert.equal(growing.result.failed,0,'recheck height after lazy content expands');
 const stuck=await scenario({height:3000,blocked:true});assert.equal(stuck.result.failed,1,'a genuinely stuck page must still block traversal');
 assert(stuck.result.issues.some(row=>row.reason.startsWith('Превъртането не достигна края (0 / 2101 px)')));
}
async function attachments(){
 const helper=fs.readFileSync(require('node:path').join(__dirname,'../capture_resources.js'),'utf8');
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
(async()=>{await media();await attachments();await images();await scrollReadiness();await run(false);await navigation();await linkedApps();await run(true);console.log('PASS: valid shadow host, named lessons, skip checkboxes, cancellation and traversal selection.');})().catch(e=>{console.error(e);process.exitCode=1;});
