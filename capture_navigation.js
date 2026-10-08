/* Read navigation metadata without running the scripts or media of those pages. */
async function collectCaptureLessons(doc,base,book,fetchPage,chooseModules){
const sameBook=value=>{try{const url=new URL(value,base);return url.origin===new URL(base).origin&&new RegExp('^/DOS/'+book+'/\\d+\\.html$').test(url.pathname)?url:null;}catch{return null;}};
const clean=value=>String(value||'').replace(/<[^>]*>/g,' ').replace(/\s+/g,' ').trim();
const numbered=(number,name)=>number&&!name.startsWith(number+' ')?number+' '+name:name;
const kind=row=>({module:'module',modul:'module',section:'section',sekcija:'section',unit:'unit',jedinica:'unit',lesson:'unit'}[row.systemType||row.tmplLabel||row.template]||'');
const visible=row=>row.isVisible!==0&&row.isVisible!=='0'&&row.isVisible!==false&&!row.disabled;
const node=(row,attributes={})=>{if(!row||!visible(row)||!kind(row))return null;const url=sameBook(attributes.href||row.href||('/DOS/'+book+'/'+row.id+'.html'));if(!url)return null;const number=clean(attributes.number||row.prettyPosition||'');return {url,name:clean(attributes.name||row.name||row.title)||'Урок '+row.id,number,kind:kind(row),children:row.childrens||row.children||[]};};
const parse=(root,page)=>{
const modules=new Map(),entries=[],headings=[...root.querySelectorAll('.xblocks > .block-title h2,.mu-item h2,.xblocks .js-dropdown-heading')];
const addModule=row=>{const item=node(row);if(item?.kind==='module'&&!modules.has(item.url.pathname))modules.set(item.url.pathname,item);};
for(const element of root.querySelectorAll('breadcrumbs')){let rows;try{rows=JSON.parse(element.getAttribute(':items')||'[]');}catch{continue;}for(const row of rows){if(kind(row)==='module'){if(Array.isArray(row.siblings)&&row.siblings.length)row.siblings.forEach(addModule);else addModule(row);}}}
const sectionFor=element=>{let title='';for(const heading of headings){if(heading.compareDocumentPosition(element)&4)title=clean(heading.textContent);}return title;};
const addEntry=(row,attributes={})=>{const item=node(row,attributes);if(!item)return;if(item.kind==='module'){addModule(row);return;}entries.push({...item,section:attributes.section||''});};
for(const element of root.querySelectorAll('units-list-item,unit-list-item,modules-list-item,module-list-item,sections-list-item,section-list-item')){
let row;try{row=JSON.parse(element.getAttribute(':item')||'null');}catch{continue;}const item=node(row);if(!item)continue;
if(item.kind==='module'){addModule(row);continue;}
const position=element.getAttribute('position')||row.prettyPosition||'';
addEntry(row,{href:element.getAttribute('unit-link')||element.getAttribute('section-link')||row.href,number:position,name:element.getAttribute('title')||row.name,section:sectionFor(element)});
}
for(const link of root.querySelectorAll('.app-goto-page a[href],.units-list a[href],.units-list__link')){
const url=sameBook(link.getAttribute('href'));if(!url)continue;const section=sectionFor(link);const number=clean(link.querySelector('.position,.unit-position,.book-position')?.textContent||'');entries.push({url,kind:'unit',name:clean(link.textContent),number,section});
}
return {modules:[...modules.values()],entries};
};
const parsePage=text=>{const template=doc.createElement('template');template.innerHTML=text;return parse(template.content,base);};
const fallback=()=>{const found=new Map();for(const link of doc.querySelectorAll('a[href]')){if(link.closest?.('header,nav,aside'))continue;const url=sameBook(link.href);if(!url)continue;const name=clean(link.innerText||link.textContent||link.getAttribute('aria-label')||link.getAttribute('title')||link.querySelector('img')?.getAttribute('alt'));const old=found.get(url.pathname);const number=name.match(/^([0-9]+(?:\.[0-9]+)*\.?)\s/)?.[1]||'';if(!old)found.set(url.pathname,{url,name,number});else if(!old.name&&name){old.name=name;old.number=number;}}return [...found.values()];};
if(!doc.querySelector)return fallback();
let initial=await fetchPage(new URL(base));
const structure=parsePage(initial);
if(!structure.modules.length){if(structure.entries.length)return structure.entries.map(item=>({...item,name:numbered(item.number,item.name)}));return fallback();}
const modules=await chooseModules(structure.modules);if(!modules)return [];
const lessons=new Map();
for(const module of modules){const content=module.url.pathname===new URL(base).pathname?initial:await fetchPage(module.url);const page=parsePage(content);
if(!page.entries.length)throw new Error('Няма разпознати секции/уроци в раздел „'+module.name+'“. Отвори го и провери съдържанието.');
const queue=page.entries.map(entry=>({...entry,module:module.name,section:entry.section})),visited=new Set();
while(queue.length){const entry=queue.shift();if(visited.has(entry.url.pathname))continue;visited.add(entry.url.pathname);
if(entry.kind==='section'){
const nested=parsePage(await fetchPage(entry.url));if(!nested.entries.length)throw new Error('Няма връзки към уроци в секция „'+entry.name+'“.');
queue.unshift(...nested.entries.map(child=>({...child,module:module.name,section:entry.name})));continue;
}
if(entry.kind!=='unit')continue;
if(!lessons.has(entry.url.pathname))lessons.set(entry.url.pathname,{...entry,name:numbered(entry.number,entry.name)});
}
}
return [...lessons.values()];
}
async function chooseCaptureModules(doc,modules){
return new Promise(resolve=>{
const dialog=doc.createElement('dialog');dialog.id='izzi-offline-lesson-picker';Object.assign(dialog.style,{padding:'0',border:'1px solid #aaa',borderRadius:'12px',width:'min(720px,92vw)',maxHeight:'85vh'});
const host=doc.createElement('div');dialog.appendChild(host);const shadow=host.attachShadow({mode:'open'});
const style=doc.createElement('style');style.textContent=':host{font:16px system-ui}*{box-sizing:border-box}.panel{padding:20px}.list{max-height:48vh;overflow:auto}.row{display:flex;gap:12px;padding:12px;border-bottom:1px solid #ddd}.row input{width:20px;height:20px}.buttons{display:flex;gap:8px;flex-wrap:wrap;margin-top:16px}button{font:inherit;padding:10px}';shadow.appendChild(style);
const panel=doc.createElement('div');panel.className='panel';shadow.appendChild(panel);const heading=doc.createElement('h2');heading.textContent='Избор на раздели';panel.appendChild(heading);const hint=doc.createElement('p');hint.textContent='Остави отметка само на разделите, които искаш. След това ще се покажат секциите и номерираните уроци. PDF, видеотека и материали за учителя не се включват.';panel.appendChild(hint);
const list=doc.createElement('div');list.className='list';panel.appendChild(list);const inputs=modules.map(module=>{const label=doc.createElement('label');label.className='row';const input=doc.createElement('input');input.type='checkbox';input.checked=true;label.appendChild(input);const name=doc.createElement('span');name.textContent=(module.number?module.number+' ':'')+module.name;label.appendChild(name);list.appendChild(label);return input;});
const buttons=doc.createElement('div');buttons.className='buttons';panel.appendChild(buttons);const button=(text,action)=>{const item=doc.createElement('button');item.type='button';item.textContent=text;item.addEventListener('click',action);buttons.appendChild(item);return item;};
const finish=value=>{dialog.remove();resolve(value);};const start=button('Покажи секциите и уроците',()=>finish(modules.filter((_,i)=>inputs[i].checked)));const update=()=>{start.disabled=!inputs.some(input=>input.checked);};inputs.forEach(input=>input.addEventListener('change',update));button('Всички раздели',()=>{inputs.forEach(input=>input.checked=true);update();});button('Нито един',()=>{inputs.forEach(input=>input.checked=false);update();});button('Отказ',()=>finish(null));dialog.addEventListener('cancel',event=>{event.preventDefault();finish(null);});doc.body.appendChild(dialog);dialog.showModal();
});
}
