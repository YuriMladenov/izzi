/* Real readiness signals, exact applet IDs and checkpoint decisions; no grading. */
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../capture_pilot.js'),'utf8');
async function geo({callback=true,already=false,other=false}={}){
 const calls=[],api={getObjectNumber:()=>7,getXML:()=>'<geogebra></geogebra>'};let tick=0;
 const win={document:{baseURI:'https://bg.izzi.digital/DOS/1/8.html'}};
 class Applet{constructor(params){this.params=params;calls.push(this);}getAppletObject(){return api;}}
 win.GGBApplet=Applet;
 const holder={id:'geogebra-holder-5'};
 const button={disabled:false,click(){root.loaded=true;const app=new win.GGBApplet({id:holder.id,appletOnLoad(){calls.push('previous-callback')}});if(callback)queueMicrotask(()=>app.params.appletOnLoad(api));}};
 const root={loaded:already,classList:{contains(){return root.loaded;}},__vue__:{conf:{filename:{path:'15/publication/1/files/task.ggb'}}},querySelector:s=>s.includes('geogebra-holder')?holder:button};
 if(already&&!other)win[holder.id]=api;
 if(other)win.ggbApplet=api;
 const block={$el:{querySelectorAll:()=>[root]}};
 const context={URL,URLSearchParams,Map,Set,WeakMap,Reflect,Number,setTimeout:fn=>{tick++;queueMicrotask(fn);return 1;}};
 const ready=vm.runInNewContext(source+';capturePilotGeoReady',context);
 const action=ready({contentWindow:win},block,{timeout:1000});
 if(!callback&&!already||other){await assert.rejects(()=>action,/не потвърди/);assert(tick>=4,'a getAppletObject stub is insufficient before appletOnLoad');return;}
 const result=await action;assert(result.ready);assert.equal(result.files[0],'https://bg.izzi.digital/datastore/15/publication/1/files/task.ggb');
 if(!already)assert(calls.includes('previous-callback'),'preserve the site callback');
}
async function unknownAndResume(){
 const rows=[],frame={},lesson=new URL('https://bg.izzi.digital/DOS/1/8.html');
 const context={URL,URLSearchParams,Map,Set,WeakMap,Reflect,Number,rows,frame,lesson,captureResourceAssets:()=>[]};
 const visit=vm.runInNewContext(source+';capturePilotRPC=async data=>{rows.push(data);return {capture:true};};capturePilotSessions.set(frame,{lesson,revision:"v",inventory:new Map(),verified:new Set(["block:2"]),resumed:0});capturePilotVisit',context);
 const fail=await visit(frame,{blockId:1,blockType:'unknown-game'},()=>{throw Error('unknown handler must not submit or inspect answers')},{lesson,verified:new Set()});
 assert.equal(fail.length,1);assert.equal(rows[0].state,'manual');
 let checks=0;const resumed=await visit(frame,{blockId:2,blockType:'fill-in'},()=>checks++,{lesson,verified:new Set(['block:2']),resumed:0});
 assert.equal(resumed.length,0);assert.equal(checks,0);assert.equal(rows.length,1);
}
(async()=>{await geo();await geo({callback:false});await geo({already:true});await geo({already:true,other:true});await unknownAndResume();console.log('PASS: exact GeoGebra readiness, preserved callbacks, no premature CSS/API-stub success, manual unknowns and verified-only resume.');})().catch(e=>{console.error(e);process.exitCode=1;});
