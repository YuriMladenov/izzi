(()=>{
const input=document.getElementById('ui-search');if(!input)return;
const items=[...document.querySelectorAll('[data-search-item]')],count=document.getElementById('ui-count'),empty=document.getElementById('ui-no-results');
const update=()=>{const query=input.value.toLocaleLowerCase('bg').trim();let visible=0;for(const item of items){item.hidden=!item.textContent.toLocaleLowerCase('bg').includes(query);if(!item.hidden)visible++;}count.textContent=visible+' / '+items.length;empty.hidden=visible!==0;};
input.addEventListener('input',update);update();
})()
