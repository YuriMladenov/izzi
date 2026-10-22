(()=>{
const root=document.getElementById('video-resume');if(!root)return;
const message=document.getElementById('video-message'),list=document.getElementById('videos-list');
let busy=false,running=false,refreshing=false;
const labels={idle:'Готово за изтегляне',running:'Изтеглянето работи',success:'Изтеглянето приключи',failed:'Има недовършени видеа или грешки — виж отчета',stopped:'Изтеглянето е спряно'};
async function refresh(){
if(refreshing)return;
refreshing=true;
try{
const r=await fetch('/__videos__/status',{cache:'no-store'});if(!r.ok)throw new Error('Проверката е недостъпна');
const data=await r.json();running=data.job.state==='running';
document.getElementById('videos-state').textContent=labels[data.job.state]||data.job.state;
document.getElementById('videos-log').textContent=data.job.log||'Все още няма лог.';
list.replaceChildren();
for(const error of data.report.errors){const p=document.createElement('p');p.textContent=error;list.append(p);}
if(!data.report.videos.length){const p=document.createElement('p');p.textContent='Няма открити недовършени IZZI MP4 видеа.';list.append(p);}
for(const video of data.report.videos){
const section=document.createElement('section');section.className='task-panel';
const text=document.createElement('p');text.textContent=video.label;section.append(text);
const progress=document.createElement('p');progress.textContent=video.total?`${video.percent}% · ${(video.covered/1048576).toFixed(1)} / ${(video.total/1048576).toFixed(1)} MiB`:'Размерът ще бъде установен при изтеглянето';section.append(progress);
const button=document.createElement('button');button.dataset.video=video.id;button.textContent='Довърши';button.disabled=busy||running||!!data.report.errors.length;section.append(button);list.append(section);
}
root.querySelector('[data-video="all"]').disabled=busy||running||!data.report.videos.length||!!data.report.errors.length;
document.getElementById('videos-stop').disabled=busy||!running;
}catch(error){message.textContent=error.message;}finally{refreshing=false;}}
async function action(action,id='all'){
busy=true;root.querySelectorAll('button').forEach(button=>button.disabled=true);message.textContent='Изпълнява се…';
try{const r=await fetch('/__videos__/action',{method:'POST',headers:{'Content-Type':'application/json','X-IZZI-Control':root.dataset.token},body:JSON.stringify({action,id})});const data=await r.json();if(!r.ok)throw new Error(data.error||'Грешка');message.textContent=action==='stop'?'Спира след текущата заявка. Записаните части остават.':'Изтеглянето е стартирано.';}
catch(error){message.textContent=error.message;}finally{busy=false;document.getElementById('videos-refresh').disabled=false;await refresh();}}
root.addEventListener('click',event=>{const button=event.target.closest('button[data-video]');if(button&&!button.disabled)action('start',button.dataset.video);});
document.getElementById('videos-stop').addEventListener('click',()=>action('stop'));
document.getElementById('videos-refresh').addEventListener('click',refresh);
refresh();setInterval(()=>{if(running&&!busy)refresh();},3000);
})();
