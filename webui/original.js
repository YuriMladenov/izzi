(()=>{
const menu=document.createElement('details');menu.id='izzi-local-menu';
menu.innerHTML='<summary>☰ Меню</summary><nav aria-label="Локална навигация"><a href="/__library__">Библиотека</a><a href="/__missing__">Липсващи ресурси</a><a href="/__journal__">Локален журнал</a><a href="/__operations__">Capture и проверки</a><a href="/__help__">Как да използвам</a></nav>';
document.body.append(menu);
const note=document.createElement('p');note.id='izzi-local-note';note.textContent='Локален архив • Показват се записаните учебници. Входът и онлайн функциите не са достъпни.';document.body.prepend(note);
document.addEventListener('click',event=>{
 const link=event.target.closest('a');if(!link||menu.contains(link))return;
 const url=new URL(link.href,location.href),match=url.pathname.match(/^\/DOS\/(\d+)(?:\/|$)/);
 if(match){event.preventDefault();event.stopImmediatePropagation();location.href='/__book__/'+match[1];return;}
 if(url.origin!==location.origin||/\/(login|logout|register)(\/|$)/.test(url.pathname)||(/#\//.test(url.href)&&!['#/','#'].includes(url.hash))){event.preventDefault();event.stopImmediatePropagation();note.textContent='Тази онлайн функция не е достъпна. Избери учебник или използвай локалното меню.';}
},true);
})()
