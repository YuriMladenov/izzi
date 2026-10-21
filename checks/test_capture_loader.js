const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const bookmark=fs.readFileSync(path.join(__dirname,'../auto_book_capture_bookmarklet.txt'),'utf8').trim();
assert(bookmark.startsWith('javascript:'));assert(bookmark.length<2000);assert(encodeURI(bookmark).length<8000);
function setup(href='https://bg.izzi.digital/DOS/888413/888434.html'){
 const elements=[],alerts=[],timers=[];
 const context={location:new URL(href),Date,alert:s=>alerts.push(s),setTimeout:f=>(timers.push(f),timers.length),clearTimeout:()=>{},document:{createElement:()=>({remove(){this.removed=true}}),head:{appendChild:s=>elements.push(s)}}};
 const run=()=>vm.runInNewContext(bookmark.slice('javascript:'.length),context);
 return {context,elements,alerts,timers,run};
}
let x=setup();x.run();assert.equal(x.elements.length,1);assert.equal(x.context.__IZZI_CAPTURE_LOADING__,true);
assert(x.elements[0].src.startsWith('https://bg.izzi.digital/__offline_capture__/book_capture.js?t='));
x.run();assert.equal(x.elements.length,1,'prevent duplicate downloads');
x.context.__IZZI_CAPTURE_RUNTIME_LOADED__=true;x.elements[0].onload();assert.equal(x.context.__IZZI_CAPTURE_LOADING__,false);assert(x.elements[0].removed);
x=setup();x.run();x.elements[0].onerror();assert.equal(x.alerts.length,1);assert.equal(x.context.__IZZI_CAPTURE_LOADING__,false);x.run();assert.equal(x.elements.length,2,'retry after failure');
x=setup();x.run();x.elements[0].onload();assert.equal(x.alerts.length,1,'HTML or wrong proxy response cannot claim runtime loaded');
x=setup();x.run();x.timers[0]();assert.equal(x.alerts.length,1);assert.equal(x.context.__IZZI_CAPTURE_LOADING__,false);x.elements[0].onerror();assert.equal(x.alerts.length,1,'only one timeout/failure alert');
x=setup('https://example.com/');x.run();assert.equal(x.elements.length,0);assert.equal(x.alerts.length,1);
x=setup();x.context.__IZZI_CAPTURE_ACTIVE__=true;x.run();assert.equal(x.elements.length,0);
const standalone=fs.readFileSync(path.join(__dirname,'../auto_book_capture_standalone.txt'),'utf8').trim().slice('javascript:'.length);
const runtime=fs.readFileSync(path.join(__dirname,'../capture_book_runtime.js'),'utf8');assert(runtime.endsWith(standalone+'\n'));
assert(runtime.includes('globalThis.__IZZI_CAPTURE_RUNTIME_LOADED__=true;'));
console.log('PASS: short loader, same-origin script, duplicate guard, no-proxy/invalid-response/timeout recovery, generated runtime matches standalone.');
