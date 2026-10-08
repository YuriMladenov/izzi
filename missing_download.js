(()=>{
const start=document.getElementById('download-all'),stop=document.getElementById('download-stop'),status=document.getElementById('download-status');
let cancelled=false,controller=null;
stop.addEventListener('click',()=>{cancelled=true;controller?.abort();});
start.addEventListener('click',async()=>{
const urls=[...new Set([...document.querySelectorAll('a.download')].map(a=>a.href))];
if(!urls.length){status.textContent='Няма ресурси за изтегляне.';return;}
if(!confirm('Изтегли '+urls.length+' ресурса? Нужни са интернет и включен capture proxy към компютъра с библиотеката.'))return;
start.disabled=true;stop.disabled=false;cancelled=false;let verified=0,failed=0,completed=0;
try{
for(const target of urls){
if(cancelled)break;
status.textContent='Зареждане '+(completed+1)+' / '+urls.length;
const media=/\.(mp4|mp3|webm|ogg|m4a|wav)$/i.test(new URL(target).pathname);
controller=new AbortController();const timer=setTimeout(()=>controller.abort(),media?240000:30000);
try{
const original=new URL(target);original.searchParams.delete('__izzi_offline_recover');
const request=new URL(target);request.searchParams.set('__izzi_offline_recover',Date.now().toString(36)+'_'+completed);
const response=await fetch(request.href,{mode:'no-cors',credentials:'include',cache:'no-store',signal:controller.signal});
await response.blob();
let saved=false;
for(let attempt=0;attempt<(media?480:10)&&!cancelled;attempt++){
const result=await fetch('/__offline__/asset-status?'+new URLSearchParams({url:original.href}),{cache:'no-store',signal:controller.signal});
if(!result.ok)throw new Error('Проверката на архива не успя');
if((await result.json()).available){saved=true;break;}
await new Promise(resolve=>setTimeout(resolve,500));
}
if(cancelled)break;
saved?verified++:failed++;
}catch(error){if(cancelled)break;failed++;console.warn('IZZI resource download failed',error);}
finally{clearTimeout(timer);controller=null;}
completed++;
}
}finally{
start.disabled=false;stop.disabled=true;
status.textContent=(cancelled?'Спряно. ':'Готово. ')+'Проверени: '+completed+'/'+urls.length+'. Налични в архива: '+verified+'. Непотвърдени: '+failed+'. Презареди списъка.';
}
});
})()
