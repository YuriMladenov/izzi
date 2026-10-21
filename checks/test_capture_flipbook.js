/* Page metadata, lazy PDF panels, slider navigation and truthful failure reporting. */
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const helper=fs.readFileSync(path.join(__dirname,'../capture_flipbook.js'),'utf8');
const standalone=fs.readFileSync(path.join(__dirname,'../auto_book_capture_standalone.txt'),'utf8');
assert.equal(standalone.split('/*IZZI_FLIPBOOK_START*/')[1].split('/*IZZI_FLIPBOOK_END*/')[0],helper.split(/\r?\n/).join(''));
const page=(id,number)=>({id,template:'pdf_page',name:'Untitled '+number,pdfPicture:[{pageNumber:number,image:'./datastore/book/p'+number+'.png',thumbnail:'./datastore/book/t'+number+'.png'}]});
async function navigation(){
 const collect=vm.runInNewContext(helper+';collectFlipbookCapture',{URL,Map,Set});
 const tree=[page(100,1),{template:'pdf_chapter',name:'Рационални числа',childrens:[{template:'pdf_lesson',name:'1.1. Рационални числа',childrens:[page(101,12),page(102,13),page(101,12)]}]},page(103,146)];
 const root={querySelector:()=>({getAttribute:name=>name===':pages'?JSON.stringify(tree):null})};
 const base='https://bg.izzi.digital/DOS/1/10.html?page=12&centrespread=1';
 const rows=await collect(root,base,'1',async groups=>groups);
 assert.deepEqual(Array.from(rows,row=>row.url.pathname),['/DOS/1/100.html','/DOS/1/101.html','/DOS/1/102.html','/DOS/1/103.html']);
 assert.equal(rows[1].module,'Рационални числа');assert.equal(rows[1].section,'1.1. Рационални числа');
 assert.equal(rows[1].number,'12.');assert.equal(rows[1].flipbook.image,'https://bg.izzi.digital/DOS/1/datastore/book/p12.png');
 assert.equal(rows[1].flipbook.viewer,'https://bg.izzi.digital/DOS/1/10.html');
 assert.deepEqual(Array.from(await collect(root,base,'1',async groups=>[groups[1]]),row=>row.number),['12.','13.']);
 assert.equal((await collect(root,base,'1',async()=>null)).length,0);
 assert.equal(await collect({querySelector:()=>null},base,'1',async()=>{}),null);
 await assert.rejects(()=>collect({querySelector:()=>({getAttribute:()=>'{bad'})},base,'1',async()=>{}),/Невалидно/);
 tree[0].pdfPicture[0].image='https://example.org/escape.png';
 await assert.rejects(()=>collect(root,base,'1',async groups=>groups),/Непознат адрес/);
}
async function panels({blocked=false,missing=false,empty=false}={}){
 const actions=[],checked=[],events=[];
 let panel,slider;
 const node={querySelectorAll:()=>[button]},button={closest:()=>node,click:()=>{actions.push('open');panel.isPDFBlockOpen=true;panel.$children=[slider];}};
 slider={$options:{name:'objects-slider'},$children:[],currentSlide:1,slideCount:3,blockId:2,nextDisabled:blocked,
  next(){actions.push('next');this.currentSlide++;},prev(){actions.push('prev');this.currentSlide--;}};
 panel={$options:{name:'izzi-block'},$el:node,$children:[],canClose:true,isPDFBlockOpen:false,blockType:'objects-slider',blockId:1,
  openPDFBlock(){throw Error('must use the known open button')},closePDFBlock(){actions.push('close');this.isPDFBlockOpen=false;this.$children=[];}};
 node.__vue__=panel;
 const doc={querySelectorAll:()=>empty?[]:[node],querySelector:()=>null};
 const layout={data:{fields:{config:{blocks:empty?[1]:[]}}}};
 const frame={contentDocument:doc,contentWindow:{clientData:{'pdf-layout':layout}}};
 const capture=vm.runInNewContext(helper+';captureFlipbookPage',{
  URL,Map,Set,setTimeout:fn=>{queueMicrotask(fn);return 1;},
  captureGeoGebra:async()=>[],
  captureStrictChecks:async(f,l,p,skip,inside)=>{assert(inside);checked.push(panel.isPDFBlockOpen?slider.currentSlide:'closed');return missing?[{kind:'image',url:l.href,reason:'missing image'}]:[];}
 });
 const result=await capture(frame,new URL('https://bg.izzi.digital/DOS/1/101.html'),async(kind,l,extra)=>events.push({kind,extra}),false);
 if(empty){assert.equal(result.length,1);assert(result[0].reason.includes('няма разпознати'));return;}
 if(blocked){assert.equal(result.length,1);assert(result[0].reason.includes('изисква отговор'));assert(!actions.includes('next'));assert(!actions.includes('close'));return;}
 if(missing){assert.equal(result.length,1);assert.equal(result[0].reason,'missing image');assert(!actions.includes('next'));assert(!actions.includes('close'));return;}
 assert.equal(result.length,0);assert.deepEqual(checked.slice(0,3),[1,2,3]);assert.equal(checked.at(-1),'closed');
 assert.equal(slider.currentSlide,1);assert.deepEqual(actions,['open','next','next','prev','prev','close']);
 assert(events.some(row=>row.kind==='flipbook-checked'&&row.extra.total===1));
}
(async()=>{await navigation();await panels();await panels({blocked:true});await panels({missing:true});await panels({empty:true});console.log('PASS: flipbook page selection, task mounting, all slider pages, no grading, blocking and archive failures.');})().catch(error=>{console.error(error);process.exitCode=1;});
