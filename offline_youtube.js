/* Replace Vue-rendered YouTube components with the archived HTML5 player.
   Keep their titles/descriptions and never simulate the external player API. */
function fixYoutube(){
  for(const element of document.querySelectorAll('.youtube-player')){
    let component=element.__vue__;
    /* A component used as its parent's root shares the same DOM element. */
    for(let depth=0;depth<8;depth++){
      const child=component?.$children?.find(item=>item.$el===element);
      if(!child)break;
      component=child;
    }
    const fromUrl=component?.videoUrl?.match(/\/(?:external-media|embed|shorts|live)\/([A-Za-z0-9_-]{11})(?:[?&#/]|$)/)?.[1];
    const candidate=[component?.videoId,component?.youtubeId,fromUrl,element.querySelector('[id^="youtube-video-"]')?.id?.match(/-([A-Za-z0-9_-]{11})$/)?.[1]].find(value=>/^[A-Za-z0-9_-]{11}$/.test(value||''));
    if(!/^[A-Za-z0-9_-]{11}$/.test(candidate||''))continue;
    const wrap=element.querySelector('.video-inner-wrap');
    if(!wrap)continue;
    const parameters=new URLSearchParams();
    for(const key of ['start','end']){
      const number=Number(component?.playerVars?.[key]);
      if(Number.isFinite(number)&&number>0)parameters.set(key,String(number));
    }
    const src='/__offline__/external-media/'+candidate+(parameters.size?'?'+parameters:'');
    if(wrap.querySelector('iframe[data-izzi-youtube]')?.getAttribute('src')===src)continue;
    const frame=document.createElement('iframe');
    frame.setAttribute('data-izzi-youtube',candidate);
    frame.setAttribute('src',src);
    frame.setAttribute('title',component?.title||'Видео');
    frame.setAttribute('allowfullscreen','');
    frame.style.cssText='display:block;width:100%;aspect-ratio:16/9;border:0';
    wrap.replaceChildren(frame);
  }
}
