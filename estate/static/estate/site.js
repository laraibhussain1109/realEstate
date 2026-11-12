(() => {
  'use strict';
  const $ = (s, root = document) => root.querySelector(s);
  const $$ = (s, root = document) => [...root.querySelectorAll(s)];
  const header = $('.site-header');
  addEventListener('scroll', () => header?.classList.toggle('compact', scrollY > 40), {passive:true});
  const menu = $('.menu-toggle'), nav = $('#navigation');
  menu?.addEventListener('click', () => {const open = nav.classList.toggle('open');menu.setAttribute('aria-expanded',open);menu.setAttribute('aria-label',open?'Close navigation':'Open navigation');menu.textContent = open?'×':'☰';});
  document.addEventListener('keydown', e => {if(e.key==='Escape' && nav?.classList.contains('open')) menu.click();});
  const projectToggle=$('.project-menu-toggle'),projectMenu=$('#project-menu');
  projectToggle?.addEventListener('click',()=>{const open=projectToggle.getAttribute('aria-expanded')!=='true';projectToggle.setAttribute('aria-expanded',open);projectMenu.hidden=!open;});
  document.addEventListener('click',e=>{if(projectMenu&&!e.target.closest('.nav-project-group')){projectMenu.hidden=true;projectToggle.setAttribute('aria-expanded','false');}});
  document.addEventListener('keydown',e=>{if(e.key==='Escape'&&projectMenu&&!projectMenu.hidden){projectMenu.hidden=true;projectToggle.setAttribute('aria-expanded','false');projectToggle.focus();}});
  const dialog = $('#enquiry-dialog');
  function openEnquiry(plot = null, kind = 'site_visit', project = '') {
    if (!dialog) return;
    const form = $('form',dialog);
    $('[name=kind]',form).value = kind;
    const currentProject = $('#plot-explorer')?.dataset.api?.split('/')[3] || '';
    $('[name=project]',form).value = project || plot?.project_slug || currentProject;
    $('[name=plot]',form).value = plot?.number || '';
    $('.visit-date',form).hidden = kind !== 'site_visit';
    $('[name=visit_date]',form).required = kind === 'site_visit';
    $('#enquiry-title').textContent = plot ? `Let’s talk about Plot ${plot.number}.` : kind === 'site_visit' ? 'Come see the possibilities.' : 'Your next chapter starts here.';
    $('.form-feedback',form).textContent = '';
    if (!dialog.open) dialog.showModal();
  }
  window.openEnquiry = openEnquiry;
  $$('[data-enquiry]').forEach(button => button.addEventListener('click',()=>openEnquiry(null,button.dataset.enquiry,button.dataset.project||'')));
  $('[data-close-dialog]')?.addEventListener('click',()=>dialog.close());
  dialog?.addEventListener('click',e=>{if(e.target===dialog){const r=dialog.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)dialog.close();}});
  $$('.enquiry-form').forEach(form=>{
    const date = $('[name=visit_date]',form);if(date) date.min = new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Kolkata',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
    if (form.closest('.contact-form-card')) {$('[name=kind]',form).value='general';$('.visit-date',form).hidden=true;}
    form.addEventListener('submit',async e=>{
      e.preventDefault(); if(!form.reportValidity())return;
      const button=$('[type=submit]',form), feedback=$('.form-feedback',form),old=button.textContent;
      button.disabled=true;button.textContent='Sending your request…';feedback.textContent='';feedback.className='form-feedback';
      try {
        const response=await fetch(form.action,{method:'POST',body:new FormData(form),headers:{'X-CSRFToken':$('[name=csrfmiddlewaretoken]',form).value,'Accept':'application/json'},credentials:'same-origin'});
        const data=await response.json();
        if(!response.ok){const messages=[];for(const [field,errors] of Object.entries(data.errors||{}))messages.push(`${field.replaceAll('_',' ')}: ${Array.isArray(errors)?errors.map(x=>typeof x==='object'?x.message:x).join(' '):errors}`);throw new Error(messages.join(' · ')||data.error||'Your request could not be sent. Please try again.');}
        feedback.classList.add('success');feedback.textContent=data.message||'Thank you. Your request has been saved. Our team will be in touch.';const context={};['kind','project','plot'].forEach(key=>context[key]=$(`[name=${key}]`,form).value);form.reset();Object.entries(context).forEach(([key,value])=>$(`[name=${key}]`,form).value=value);
      } catch(error) {feedback.classList.add('error');feedback.textContent=error.message||'Unable to connect. Please call our team or try again.';}
      finally {button.disabled=false;button.textContent=old;}
    });
  });
  const homeArea=$('#home-area'),homeProject=$('#home-project');
  homeArea?.addEventListener('change',async()=>{
    homeProject.disabled=true;homeProject.replaceChildren(new Option('Loading projects…',''));
    try{const res=await fetch('/api/projects/?area='+encodeURIComponent(homeArea.value));if(!res.ok)throw Error();const data=await res.json();homeProject.replaceChildren(new Option('All projects',''));(data.projects||data.results||[]).forEach(p=>homeProject.add(new Option(p.name,p.slug)));}
    catch {homeProject.replaceChildren(new Option('Select a project on the next page',''));}finally{homeProject.disabled=false;}
  });
  $('.discovery-bar')?.addEventListener('submit',e=>{if(homeProject.value){e.preventDefault();location.href='/projects/'+encodeURIComponent(homeProject.value)+'/';}});
  const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
  if(!reduced && 'IntersectionObserver' in window){const observer=new IntersectionObserver(entries=>entries.forEach(entry=>{if(entry.isIntersecting){entry.target.classList.add('revealed');observer.unobserve(entry.target);}}),{threshold:.08});$$('.section-heading,.value-item,.project-card,.location-card').forEach(el=>{el.classList.add('reveal');observer.observe(el);});}
  const images=$$('[data-lightbox]');
  if(images.length){
    const lightbox=document.createElement('dialog');lightbox.className='lightbox';lightbox.innerHTML='<button class="icon-button lightbox-close" aria-label="Close image">×</button><button class="icon-button lightbox-prev" aria-label="Previous image">←</button><figure><img alt=""><figcaption></figcaption></figure><button class="icon-button lightbox-next" aria-label="Next image">→</button>';document.body.append(lightbox);let index=0,touchX=0;
    const show=i=>{index=(i+images.length)%images.length;const img=$('img',lightbox),source=images[index];img.src=source.dataset.lightbox;img.alt=$('img',source)?.alt||source.dataset.caption||'';$('figcaption',lightbox).textContent=source.dataset.caption||'';};
    images.forEach((el,i)=>el.addEventListener('click',()=>{show(i);lightbox.showModal();}));$('.lightbox-close',lightbox).onclick=()=>lightbox.close();$('.lightbox-prev',lightbox).onclick=()=>show(index-1);$('.lightbox-next',lightbox).onclick=()=>show(index+1);
    lightbox.addEventListener('keydown',e=>{if(e.key==='ArrowLeft')show(index-1);if(e.key==='ArrowRight')show(index+1);});lightbox.addEventListener('touchstart',e=>{touchX=e.changedTouches[0].clientX;},{passive:true});lightbox.addEventListener('touchend',e=>{const d=e.changedTouches[0].clientX-touchX;if(Math.abs(d)>45)show(index+(d<0?1:-1));},{passive:true});
  }
  $$('.testimonial-carousel').forEach(carousel=>{
    const slides=$$('.testimonial-slide',carousel);let index=0,paused=false,touchX=0;
    function show(i){if(!slides.length)return;index=(i+slides.length)%slides.length;slides.forEach((slide,j)=>slide.hidden=j!==index);$('.carousel-position',carousel).textContent=`${index+1} / ${slides.length}`;}
    $$('[data-slide]',carousel).forEach(b=>b.onclick=()=>show(index+Number(b.dataset.slide)));
    carousel.addEventListener('mouseenter',()=>paused=true);carousel.addEventListener('mouseleave',()=>paused=false);carousel.addEventListener('focusin',()=>paused=true);carousel.addEventListener('focusout',()=>paused=false);
    carousel.addEventListener('touchstart',e=>touchX=e.changedTouches[0].clientX,{passive:true});carousel.addEventListener('touchend',e=>{let d=e.changedTouches[0].clientX-touchX;if(Math.abs(d)>40)show(index+(d<0?1:-1));},{passive:true});
    if(!reduced&&slides.length>1)setInterval(()=>{if(!paused&&!document.hidden)show(index+1);},6500);
  });
  $$('[data-counter]').forEach(el=>{const target=Number(el.dataset.counter);if(!Number.isFinite(target))return;if(reduced||!('IntersectionObserver' in window)){el.textContent=target.toLocaleString();return;}const obs=new IntersectionObserver(entries=>{if(!entries[0].isIntersecting)return;obs.disconnect();const start=performance.now();const tick=now=>{const progress=Math.min(1,(now-start)/950);el.textContent=Math.round(target*(1-(1-progress)**3)).toLocaleString();if(progress<1)requestAnimationFrame(tick);};requestAnimationFrame(tick);});obs.observe(el);});
})();
