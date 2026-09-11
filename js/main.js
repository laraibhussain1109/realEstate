const $ = (s, root=document) => root.querySelector(s);
const $$ = (s, root=document) => [...root.querySelectorAll(s)];

function applyConfig(){
  $$('[data-config="company"]').forEach(el=>el.textContent=SITE_CONFIG.companyName);
  $$('[data-config="phone"]').forEach(el=>{el.textContent=SITE_CONFIG.phone; if(el.tagName==='A') el.href=`tel:${SITE_CONFIG.phone.replace(/\s/g,'')}`});
  $$('[data-config="email"]').forEach(el=>{el.textContent=SITE_CONFIG.email; if(el.tagName==='A') el.href=`mailto:${SITE_CONFIG.email}`});
  $$('[data-config="address"]').forEach(el=>el.textContent=SITE_CONFIG.address);
  $$('[data-social]').forEach(el=>el.href=SITE_CONFIG[el.dataset.social]);
  const wa=$('.floating-wa'); if(wa) wa.href=`https://wa.me/${SITE_CONFIG.whatsapp}`;
}
function initNavigation(){
  const header=$('.site-header'), toggle=$('.menu-toggle'), menu=$('.mobile-menu');
  const close=()=>{toggle?.classList.remove('open');menu?.classList.remove('open');toggle?.setAttribute('aria-expanded','false');document.body.classList.remove('menu-open')};
  toggle?.addEventListener('click',()=>{const open=!menu.classList.contains('open');toggle.classList.toggle('open',open);menu.classList.toggle('open',open);toggle.setAttribute('aria-expanded',String(open));document.body.classList.toggle('menu-open',open)});
  $$('.mobile-menu a').forEach(a=>a.addEventListener('click',close));
  document.addEventListener('keydown',e=>{if(e.key==='Escape') close()});
  const scroll=()=>{header?.classList.toggle('scrolled',scrollY>40);$('.floating-wa')?.classList.toggle('visible',scrollY>280);const max=document.documentElement.scrollHeight-innerHeight;$('.scroll-progress')?.style.setProperty('--progress',`${max?scrollY/max*100:0}%`)};
  addEventListener('scroll',scroll,{passive:true});scroll();
}
function initForms(){
  $$('[data-whatsapp-form]').forEach(form=>form.addEventListener('submit',e=>{e.preventDefault();if(!form.reportValidity())return;if(SITE_CONFIG.whatsapp.includes('X')){alert('Please replace the WhatsApp number in js/config.js before using this form.');return}const data=new FormData(form);const message=`Property enquiry — ${SITE_CONFIG.companyName}\nName: ${data.get('name')}\nPhone: ${data.get('phone')}\nEmail: ${data.get('email')}\nInterest: ${data.get('interest')}\nMessage: ${data.get('message')}`;window.open(`https://wa.me/${SITE_CONFIG.whatsapp}?text=${encodeURIComponent(message)}`,'_blank','noopener')}));
  const interest=new URLSearchParams(location.search).get('interest');if(interest&&$('[name="message"]')) $('[name="message"]').value=`I would like to know more about ${interest}.`;
}
function initAccordion(){ $$('.faq-button').forEach(button=>button.addEventListener('click',()=>{const item=button.closest('.faq-item'), open=item.classList.toggle('open');button.setAttribute('aria-expanded',String(open));$('.faq-answer',item).style.maxHeight=open?$('.faq-answer',item).scrollHeight+'px':'0'})); }
function initCursor(){if(!matchMedia('(pointer:fine)').matches)return;const cursor=document.createElement('div');cursor.className='cursor';document.body.append(cursor);addEventListener('mousemove',e=>{cursor.style.transform=`translate3d(${e.clientX}px,${e.clientY}px,0)`});$$('a,button,input,textarea,select,.property-card').forEach(el=>{el.addEventListener('mouseenter',()=>cursor.classList.add('active'));el.addEventListener('mouseleave',()=>cursor.classList.remove('active'))});}
function initPageTransitions(){ $$('a[href]').filter(a=>a.origin===location.origin&&!a.hash&&!a.target).forEach(a=>a.addEventListener('click',e=>{if(matchMedia('(prefers-reduced-motion: reduce)').matches)return;e.preventDefault();document.body.classList.add('page-leaving');setTimeout(()=>location.href=a.href,220)})); }
document.addEventListener('DOMContentLoaded',()=>{applyConfig();initNavigation();initForms();initAccordion();initCursor();initPageTransitions();});
