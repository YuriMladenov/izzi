(()=>{
const root=document.getElementById('maintenance');if(!root)return;
const message=document.getElementById('maintenance-message');let busy=false,refreshing=false,restarting=false,restartAfter=0;
async function refresh(){
if(refreshing||(restarting&&Date.now()<restartAfter))return;refreshing=true;
try{
const response=await fetch('/__maintenance__/status',{cache:'no-store'});if(restarting&&response.status===403){location.href='/__admin__/login';return;}if(!response.ok)throw new Error('Статусът е недостъпен. Провери администраторския вход.');
const data=await response.json(),job=data.update;
document.getElementById('update-state').textContent=({idle:'Готово за проверка',running:'Обновяването работи…',success:'Проверката приключи успешно',failed:'Обновяването е спряно'})[job.state]||job.state;
document.getElementById('update-log').textContent=job.log||'Все още няма лог.';
root.querySelector('[data-maintenance="update"]').disabled=busy||job.state==='running'||restarting;
root.querySelector('[data-maintenance="restart"]').disabled=busy||job.state==='running'||!data.managed||restarting;
if(!data.managed&&!restarting)document.getElementById('update-state').textContent+=' · След обновяване е нужен ръчен рестарт (или стартиране чрез project_launcher.py).';
if(data.startup)document.getElementById('startup-state').textContent=(data.startup.ok?'✓ ':'')+data.startup.message+' · '+data.startup.account;
if(restarting){message.textContent='Библиотеката отново е достъпна. Презареди страницата.';restarting=false;location.reload();}
}catch(error){message.textContent=restarting?'Изчакване на рестарта…':error.message;}finally{refreshing=false;}
}
root.querySelectorAll('button[data-maintenance]').forEach(button=>button.addEventListener('click',async()=>{
if(busy)return;busy=true;button.disabled=true;
try{
const response=await fetch('/__maintenance__/action',{method:'POST',headers:{'Content-Type':'application/json','X-IZZI-Control':root.dataset.token},body:JSON.stringify({action:button.dataset.maintenance})});
const text=await response.text();let data;try{data=JSON.parse(text);}catch{throw new Error(text||'Командата е отказана.');}
if(!response.ok)throw new Error(data.error||'Командата е отказана.');
message.textContent=data.message||'Командата е приета.';
if(button.dataset.maintenance==='restart'){restarting=true;restartAfter=Date.now()+2500;setTimeout(refresh,2500);}
}catch(error){message.textContent=error.message;}finally{busy=false;if(button.dataset.maintenance==='startup')button.disabled=false;if(!restarting)await refresh();}
}));
refresh();setInterval(refresh,2000);
})();
