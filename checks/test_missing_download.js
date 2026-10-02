const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const script=fs.readFileSync(path.join(__dirname,'../missing_download.js'),'utf8');
async function test(accept,cancel){
 const node=()=>({disabled:false,textContent:'',addEventListener(k,f){this[k]=f;}});
 const nodes={'download-all':node(),'download-stop':node(),'download-status':node()},requests=[];
 const links=[{href:'https://api.izzi.digital/datastore/good.png?__izzi_offline_recover=old'},{href:'https://api.izzi.digital/datastore/bad.png?__izzi_offline_recover=old'}];
 vm.runInNewContext(script,{document:{getElementById:id=>nodes[id],querySelectorAll:()=>links},Set,URL,URLSearchParams,AbortController,confirm:()=>accept,console:{warn:()=>{}},setTimeout:(f,ms)=>{if(ms===500)queueMicrotask(f);return 1;},clearTimeout:()=>{},fetch:async(url,options)=>{
 requests.push([url,options]);
 if(url.startsWith('/')){const target=new URL(url,'http://localhost').searchParams.get('url');assert(!target.includes('__izzi_offline_recover'));return {ok:true,json:async()=>({available:target.includes('good.png')})};}
 assert.equal(options.mode,'no-cors');assert.equal(options.credentials,'include');
 if(cancel)nodes['download-stop'].click();
 return {blob:async()=>({})};
 }});
 await nodes['download-all'].click();
 if(!accept){assert.equal(requests.length,0);return;}
 assert.equal(nodes['download-all'].disabled,false);assert.equal(nodes['download-stop'].disabled,true);
 if(cancel){assert(nodes['download-status'].textContent.startsWith('Спряно.'));return;}
 assert(nodes['download-status'].textContent.includes('Налични в архива: 1. Непотвърдени: 1.'));
 assert.equal(requests.filter(([url])=>!url.startsWith('/')).length,2);
}
(async()=>{await test(true,false);await test(false,false);await test(true,true);console.log('PASS bulk download: sequential requests, archive verification, cancellation and confirmation.');})().catch(error=>{console.error(error);process.exitCode=1;});
