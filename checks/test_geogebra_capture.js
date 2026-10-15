const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const helper=fs.readFileSync(path.join(__dirname,'../capture_resources.js'),'utf8');
async function run(){
 const lesson=new URL('https://bg.izzi.digital/DOS/887348/102107.html'),requested=[],events=[];
 const text='<script>var clientData={"filename":{"path":"15/publication/887348/files/2024/01/15/hidden.ggb","filename":"hidden.ggb"}};</script>'+`<geogebra v-bind:config='{"config":{"filename":{"path":"./datastore/15/publication/887348/files/2024/01/15/hidden.ggb","src":"./datastore/15/publication/887348/files/2024/01/15/hidden.ggb"}}}'></geogebra>`+'<a href="https://evil.example/stolen.ggb">bad</a>';
 const frame={contentDocument:{baseURI:lesson.href,querySelectorAll:()=>[],documentElement:{outerHTML:text}},contentWindow:{fetch:async(url)=>{requested.push(new URL(url));return {blob:async()=>({})};}}};
 let installed=true;
 const context={O:lesson.origin,document:{createElement:()=>({innerHTML:'',get value(){return this.innerHTML;}})},URL,URLSearchParams,AbortController,console:{warn(){}},setTimeout(fn,ms){if(ms===500)queueMicrotask(fn);return 1;},clearTimeout(){},fetch:async url=>({ok:true,json:async()=>String(url).includes('geogebra_status')?{installed}:{available:true}})};
 const capture=vm.runInNewContext(helper+';captureLessonFiles',context);
 let result=await capture(frame,lesson,async(kind,_,extra)=>events.push({kind,extra}));
 assert.equal(result.failed,0);assert.equal(result.total,1);assert.equal(requested.length,1,'fetch equivalent datastore aliases only once');
 assert(requested.every(url=>url.hostname==='bg.izzi.digital'&&url.pathname.endsWith('hidden.ggb')));
 assert(requested.some(url=>url.pathname.startsWith('/DOS/887348/datastore/15/')));
 assert(events.some(e=>e.kind==='files-checked'));
 // The original lesson uses publication 30521 inside book 888413.
 // Raw metadata after a component must not replace its resolved ./datastore path.
 const originalQuery=frame.contentDocument.querySelectorAll;
 frame.contentDocument.documentElement.outerHTML='<script>{"path":"15/publication/30521/files/2021/01/11/1610365657_b7_u3_sabir.ggb"}</script>';
 const rendered={__vue__:{conf:{filename:{path:'./datastore/15/publication/30521/files/2021/01/11/1610365657_b7_u3_sabir.ggb'}}}};
 frame.contentDocument.querySelectorAll=selector=>selector.startsWith('geogebra,')?[rendered]:[];
 requested.length=0;result=await capture(frame,lesson,async()=>{});
 assert.equal(result.total,1);assert.equal(requested[0].pathname,'/DOS/887348/datastore/15/publication/30521/files/2021/01/11/1610365657_b7_u3_sabir.ggb');
 rendered.__vue__.conf.filename.path='https://api.izzi.digital/datastore/15/publication/30521/files/2021/01/11/1610365657_b7_u3_sabir.ggb';
 requested.length=0;result=await capture(frame,lesson,async()=>{});
 assert.equal(result.total,1);assert.equal(requested[0].hostname,'api.izzi.digital','explicit live URL wins over the raw metadata alias on another IZZI host');
 frame.contentDocument.querySelectorAll=originalQuery;
 frame.contentDocument.documentElement.outerHTML='<script>{"path":"15/publication/887348/files/standalone.ggb"}</script>';
 requested.length=0;result=await capture(frame,lesson,async()=>{});
 assert.equal(result.total,1);assert.equal(requested[0].pathname,'/datastore/15/publication/887348/files/standalone.ggb');
 frame.contentDocument.documentElement.outerHTML=text;
 requested.length=0;result=await capture(frame,lesson,async()=>{},{skipAvailable:true});
 assert.equal(result.failed,0);assert.equal(requested.length,0,'do not download available .ggb files during missing-only refresh');
 installed=false;result=await capture(frame,lesson,async()=>{},{skipAvailable:true});
 assert.equal(result.failed,1);assert.equal(result.issues[0].kind,'page','missing runtime must stop strict capture');
 frame.contentDocument.documentElement.outerHTML='<div class="ggc-holder"></div>';
 result=await capture(frame,lesson,async()=>{});assert.equal(result.failed,1,'embedded/base64 applets also require the runtime');
 // Failed bg file downloads fall back to the identical API datastore path.
 installed=true;
 const names=['1610377320_b7_u4_um_del_st.ggb','1610377263_b7_u4_del_st2.ggb'];
 const paths=names.map(name=>'/datastore/15/publication/30521/files/2021/01/11/'+name);
 frame.contentDocument.documentElement.outerHTML='<script>'+JSON.stringify(paths)+'</script>';
 let validApi=true;
 frame.contentWindow.fetch=async value=>{const url=new URL(value);requested.push(url);return {type:url.hostname==='api.izzi.digital'?'opaque':'basic',ok:false,status:url.hostname==='api.izzi.digital'?0:404,blob:async()=>({})};};
 context.fetch=async value=>{const url=new URL(value);if(url.pathname.endsWith('geogebra_status'))return {ok:true,json:async()=>({installed})};const target=new URL(url.searchParams.get('url'));if(url.searchParams.get('exact')==='1')return {ok:true,json:async()=>({available:validApi&&target.hostname==='api.izzi.digital'})};return {ok:true,json:async()=>({available:validApi})};};
 requested.length=0;result=await capture(frame,lesson,async()=>{});
 assert.equal(result.total,2);assert.equal(result.failed,0);assert.equal(requested.length,4);
 for(const path of paths)assert(requested.some(url=>url.hostname==='api.izzi.digital'&&url.pathname===path));
 requested.length=0;result=await capture(frame,lesson,async()=>{},{skipAvailable:true});
 assert.equal(result.failed,0);assert.equal(requested.length,0,'reuse an already archived API file through its original alias');
 validApi=false;result=await capture(frame,lesson,async()=>{});
 assert.equal(result.failed,2,'an HTTP response without a valid GGB archive cannot pass');
 assert(result.issues.every(issue=>issue.reason.includes('bg.izzi.digital: HTTP 404')&&issue.reason.includes('api.izzi.digital')));
 // Manual recovery uses the same fallback, restricted to the clicked file.
 validApi=true;requested.length=0;
 const strict=fs.readFileSync(path.join(__dirname,'../capture_strict.js'),'utf8');
 const recover=vm.runInNewContext(strict+';recoverCaptureResource',context);
 await recover({kind:'file',url:'https://bg.izzi.digital'+paths[0]},frame,lesson,async()=>{});
 assert.equal(requested.length,2);assert(requested.every(url=>url.pathname===paths[0]));
 validApi=false;await assert.rejects(()=>recover({kind:'file',url:'https://bg.izzi.digital'+paths[0]},frame,lesson,async()=>{}));
 // Only the known GeoGebra initialization button is activated, once per widget.
 const activate=vm.runInNewContext(helper+';captureGeoGebra',context);
 let clicks=0;
 const button={disabled:false,click(){clicks++;}};
 const root={classList:{contains:()=>false},querySelector:selector=>{assert.equal(selector,'.int-overlay > button.cta');return button;}};
 const loaded={classList:{contains:()=>true},querySelector:()=>{throw Error('already initialized');}};
 const geoFrame={contentDocument:{querySelectorAll:selector=>{assert.equal(selector,'[id^="geogebra-"].int');return [root,loaded];}}};
 context.setTimeout=fn=>{queueMicrotask(fn);return 1;};
 assert.equal((await activate(geoFrame,lesson)).length,0);await activate(geoFrame,lesson);assert.equal(clicks,1);
 console.log('PASS: hidden .ggb configs, datastore paths, no foreign hosts, archive confirmation, reuse and missing-engine pause.');
}
run().catch(error=>{console.error(error);process.exitCode=1;});
