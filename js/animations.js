(function(){
  const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
  addEventListener('load',()=>{document.querySelector('.preloader')?.classList.add('done');document.body.classList.add('loaded')});
  setTimeout(()=>document.querySelector('.preloader')?.classList.add('done'),1600);
  const reveals=document.querySelectorAll('.reveal');
  if(reduced){revealFallback();return;}
  const observer=new IntersectionObserver(entries=>entries.forEach(entry=>{if(entry.isIntersecting){entry.target.classList.add('in-view');observer.unobserve(entry.target)}}),{threshold:.12,rootMargin:'0px 0px -40px'});
  reveals.forEach(el=>observer.observe(el));
  if(window.gsap&&window.ScrollTrigger){gsap.registerPlugin(ScrollTrigger);gsap.to('[data-parallax] img',{yPercent:12,ease:'none',scrollTrigger:{trigger:'.hero',start:'top top',end:'bottom top',scrub:true}})}
  function revealFallback(){reveals.forEach(el=>el.classList.add('in-view'))}
  // If IntersectionObserver is unavailable, content still remains readable.
  if(!('IntersectionObserver' in window)) revealFallback();
})();
