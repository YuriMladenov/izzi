/* Flipbooks contain separate page documents; turning a spread does not mount its tasks. */
async function collectFlipbookCapture(root,base,book,chooseModules){
const wrapper=root.querySelector?.('pdf-wrapper');
if(!wrapper)return null;
let tree;try{tree=JSON.parse(wrapper.getAttribute(':pages')||wrapper.getAttribute('v-bind:pages')||'null');}catch{throw new Error('Невалидно съдържание на прелистващия се учебник.');}
if(!Array.isArray(tree)||!tree.length)throw new Error('Няма страници в прелистващия се учебник.');
const origin=new URL(base).origin,clean=value=>String(value||'').replace(/<[^>]*>/g,' ').replace(/\s+/g,' ').trim();
const meaningful=value=>{const title=clean(value);return /^Untitled(?:\s+\d+)?$/i.test(title)?'':title;};
const viewer=new URL(base);viewer.search='';viewer.hash='';
const groups=[],seen=new Set();let count=0;
const pictureURL=value=>{if(typeof value!=='string'||!value)return '';const url=new URL(value,base);if(url.origin!==origin||!/^\/DOS\/\d+\/datastore\//.test(url.pathname)&&!url.pathname.startsWith('/datastore/'))throw new Error('Непознат адрес на страница: '+url.pathname);url.hash='';return url.href;};
for(const item of tree){
const group={name:meaningful(item.name)||'Страници',number:'',pages:[]};
const walk=(row,module='',section='',depth=0)=>{
if(++count>10000||depth>12)throw new Error('Прекалено голяма или вложена структура на учебника.');
if(row.disabled||row.isVisible===false||row.isVisible===0||row.isVisible==='0'){if(Number(row.status)!==2)return;}
if(row.template==='pdf_chapter')module=meaningful(row.name)||module;
if(row.template==='pdf_lesson')section=meaningful(row.name)||section;
if(row.template==='pdf_page'){
if(!/^\d+$/.test(String(row.id)))throw new Error('Невалиден идентификатор на страница.');
const picture=row.pdfPicture?.[0],number=Number(picture?.pageNumber),url=new URL('/DOS/'+book+'/'+row.id+'.html',origin);
if(!Number.isInteger(number)||number<0||!picture?.image)throw new Error('Липсва изображение или номер на страница '+row.id);
if(seen.has(url.pathname))return;seen.add(url.pathname);
const title=section||meaningful(row.name);
group.pages.push({url,kind:'unit',name:'Стр. '+number+(title&&!/^стр\./i.test(title)?' — '+title:''),number:String(number)+'.',module:module||'Други страници',section,
flipbook:{viewer:viewer.href,pageNumber:number,image:pictureURL(picture.image),thumbnail:pictureURL(picture.thumbnail)}});
}
for(const child of row.childrens||row.children||[])walk(child,module,section,depth+1);
};walk(item);
if(group.pages.length){group.url=group.pages[0].url;groups.push(group);}
}
if(!groups.length)throw new Error('Не са разпознати страници за обход.');
const chosen=await chooseModules(groups);if(!chosen)return [];
const selected=new Set(chosen);return groups.filter(group=>selected.has(group)).flatMap(group=>group.pages);
}
function captureFlipbookComponents(root){
const result=[],seen=new Set();
const walk=vm=>{if(!vm||seen.has(vm)||seen.size>=2000)return;seen.add(vm);result.push(vm);for(const child of vm.$children||[])walk(child);};
walk(root);return result;
}
/* Only known PDF open/close and slider navigation controls; never answers, submit or finish. */
async function captureFlipbookPage(frame,lesson,ping,skipAvailable){
const doc=frame.contentDocument,wait=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const issue=reason=>({kind:'page',url:lesson.href,reason});
let blocks=[];
for(let attempt=0;attempt<60;attempt++){
blocks=Array.from(doc.querySelectorAll('.izzi-block')).map(node=>node.__vue__).filter(vm=>vm?.$options?.name==='izzi-block'&&vm.canClose===true);
if(blocks.length||!doc.querySelector('izzi-block'))break;
await wait(250);
}
if(doc.querySelector('izzi-block'))return [issue('Интерактивните панели на страницата не се инициализираха.')];
const layout=frame.contentWindow.clientData?.['pdf-layout'],expected=layout?.data?.fields?.config?.blocks;
if(!blocks.length&&((Array.isArray(expected)&&expected.length)||Object.keys(layout?.subBlocks?.items||{}).length))return [issue('Страницата има задачи, но няма разпознати интерактивни панели.')];
let opened=0,slidesVisited=0,checkedOnce=false;
const check=()=>{const skip=checkedOnce||skipAvailable;checkedOnce=true;return captureStrictChecks(frame,lesson,ping,skip,true);};
for(const block of blocks){
if(block.blockType==='go-to-link')continue;
const button=Array.from(block.$el.querySelectorAll('button.cta-floater')).find(node=>node.closest('.izzi-block')===block.$el);
if(typeof block.openPDFBlock!=='function'||typeof block.closePDFBlock!=='function'||!button)return [issue('Непознат контрол за задача '+block.blockId+'. Нужна е ръчна проверка.')];
if(!block.isPDFBlockOpen)button.click();
await wait(400);
if(!block.isPDFBlockOpen)return [issue('Задача '+block.blockId+' не се отвори.')];
opened++;
/* Children of a PDF panel exist only after opening it. Rediscover after each navigation. */
const seenSliders=new Set();
const visitSliders=async root=>{
for(const slider of captureFlipbookComponents(root).filter(vm=>vm.$options?.name==='objects-slider')){
if(seenSliders.has(slider))continue;seenSliders.add(slider);
const original=slider.currentSlide,count=slider.slideCount;
if(!Number.isInteger(count)||count<1||count>200||typeof slider.next!=='function'||typeof slider.prev!=='function')return [issue('Непознат слайдер в задача '+block.blockId)];
/* Navigation methods only; blocking steps stay blocked and are reported. */
for(let step=0;slider.currentSlide>1&&step<count;step++){const old=slider.currentSlide;slider.prev();await wait(100);if(slider.currentSlide!==old-1)return [issue('Неуспешна навигация в слайдер '+slider.blockId)];}
for(let index=1;index<=count;index++){
if(slider.currentSlide!==index)return [issue('Не е отворен слайд '+index+' в задача '+block.blockId)];
slidesVisited++;
await wait(250);
if(typeof captureGeoGebra==='function'){const failures=await captureGeoGebra(frame,lesson);if(failures.length)return failures;}
const nested=await visitSliders(slider);if(nested.length)return nested;
/* Capture resources while each slide's frame is still mounted. */
const failures=await check();if(failures.length)return failures;
if(index<count){if(slider.nextDisabled)return [issue('Следващият слайд в задача '+block.blockId+' изисква отговор. Нужна е ръчна намеса.')];slider.next();await wait(150);}
}
/* Restore with prev(), which never submits answers. */
for(let step=0;slider.currentSlide>original&&step<count;step++){slider.prev();await wait(50);}
}
return [];
};
const failures=await visitSliders(block);if(failures.length)return failures;
const checked=await check();if(checked.length)return checked;
block.closePDFBlock();await wait(150);
if(block.isPDFBlockOpen)return [issue('Задача '+block.blockId+' не се затвори след проверката.')];
}
/* Includes the page image and thumbnails even for pages without task panels. */
const failures=await check();
await ping('flipbook-checked',lesson,{total:opened,failed:failures.length,reason:'Панели: '+opened+'; слайдове: '+slidesVisited});
return failures;
}
