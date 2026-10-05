(()=>{
const root=document.getElementById('operations');if(!root)return;
let busy=false;
const message=document.getElementById('operation-message');
const labels={idle:'Не е стартирана',running:'Работи',stopped:'Спряна',success:'Приключи успешно',failed:'Приключи с грешки'};
async function refresh(){
try{const r=await fetch('/__ops__/status',{cache:'no-store'});if(!r.ok)throw new Error('Статусът е недостъпен');const data=await r.json();
for(const name of ['capture','checks']){const job=data[name];document.getElementById(name+'-state').textContent=labels[job.state]+(job.exit_code===null?'':' · код '+job.exit_code);document.getElementById(name+'-log').textContent=job.log||'Все още няма лог.';
root.querySelectorAll('[data-task="'+name+'"]').forEach(button=>button.disabled=busy||(button.dataset.action==='start'?job.state==='running':job.state!=='running'));}
}catch(error){message.textContent=error.message;}}
root.querySelectorAll('button[data-task]').forEach(button=>button.addEventListener('click',async()=>{
busy=true;root.querySelectorAll('button').forEach(x=>x.disabled=true);message.textContent='Изпълнява се…';
try{const r=await fetch('/__ops__/action',{method:'POST',headers:{'Content-Type':'application/json','X-IZZI-Control':root.dataset.token},body:JSON.stringify({task:button.dataset.task,action:button.dataset.action})});const data=await r.json();if(!r.ok)throw new Error(data.error||'Грешка');message.textContent='Командата е изпълнена.';}catch(error){message.textContent=error.message;}finally{busy=false;await refresh();}}));
refresh();setInterval(refresh,2000);
})()
