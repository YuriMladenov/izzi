const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(require('node:path').join(__dirname,'../auto_book_capture_bookmarklet.txt'),'utf8').replace(/^javascript:/,'');
class Element{
 constructor(tag){this.tag=tag;this.children=[];this.style={};this.listeners={};this.checked=false;this.disabled=false;this.attrs={};}
 appendChild(x){this.children.push(x);return x;}
 setAttribute(k,v){this.attrs[k]=v;}
 getAttribute(k){return this.attrs[k]||null;}
 addEventListener(k,f){this.listeners[k]=f;}
 attachShadow(){return this.shadow=new Element('shadow');}
 remove(){this.removed=true;}
 querySelector(){return null;}
 showModal(){this.shown=true;}
 click(){if(!this.disabled)this.listeners.click?.();}
}
function all(e){return [e,...e.children.flatMap(all),...(e.shadow?all(e.shadow):[])];}
async function run(cancel){
 const body=new Element('body'),events=[],alerts=[];
 const link=(id,name)=>Object.assign(new Element('a'),{href:'https://bg.izzi.digital/DOS/1/'+id+'.html',innerText:name});
 const links=[link('8',''),link('2','Втори урок <b>'),link('8','Първи урок'),Object.assign(link('9','Чужд'),{href:'https://bg.izzi.digital/DOS/9/9.html'})];
 const doc={body,createElement:t=>new Element(t),querySelectorAll:()=>links,getElementById:()=>null};
 const task=vm.runInNewContext(source,{document:doc,location:new URL('https://bg.izzi.digital/DOS/1/index.html'),URL,URLSearchParams,Map,Set,alert:x=>alerts.push(x),fetch:async u=>{events.push(new URL(u).searchParams);},setInterval:()=>1,clearInterval:()=>{},setTimeout:f=>{f();return 1;}});
 const dialog=body.children[0];assert.equal(dialog.shown,true);
 const nodes=all(dialog),inputs=nodes.filter(x=>x.tag==='input'),button=t=>nodes.find(x=>x.tag==='button'&&x.textContent===t);
 assert.equal(inputs.length,2);assert(nodes.some(x=>x.textContent==='1. Първи урок — Пропусни'));
 assert(nodes.some(x=>x.textContent==='2. Втори урок <b> — Пропусни'));
 if(cancel){button('Отказ').click();await task;assert.equal(events.length,0);assert.equal(dialog.removed,true);return;}
 button('Пропусни всички').click();assert.equal(button('Стартирай обхода').disabled,true);
 button('Обходи всички').click();assert.equal(button('Стартирай обхода').disabled,false);
 inputs[1].checked=true;inputs[1].listeners.change();button('Стартирай обхода').click();await task;
 assert.deepEqual(events.filter(x=>x.get('kind')==='lesson-start').map(x=>x.get('lesson')),['8']);
 assert.equal(dialog.removed,true);assert.equal(alerts.length,1);
}
(async()=>{await run(false);await run(true);console.log('PASS: named lessons, deduplication, skip checkboxes, cancellation and traversal selection.');})().catch(e=>{console.error(e);process.exitCode=1;});
