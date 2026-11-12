/* Shared SVG view and the public plot explorer. Coordinates always use the
   original layout viewBox, never CSS pixels. No customer operation writes data. */
(() => {
  'use strict';
  const NS = 'http://www.w3.org/2000/svg';
  const svgEl = (tag, attrs = {}) => {
    const node = document.createElementNS(NS, tag);
    Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, value));
    return node;
  };
  const el = (tag, cls, text) => {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text != null) node.textContent = text;
    return node;
  };
  const status = value => String(value || 'blocked').toLowerCase();
  const title = value => String(value || '').replaceAll('_', ' ').replace(/\b\w/g, char => char.toUpperCase());
  const units = {sqyd: 'sq. yd.', sqft: 'sq. ft.', sqm: 'sq. m.', sq_yd: 'sq. yd.', sq_ft: 'sq. ft.', sq_m: 'sq. m.'};
  const areaText = p => p.area ? `${Number(p.area).toLocaleString()} ${units[p.area_unit] || p.area_unit || ''}` : '';
  const center = points => points.reduce((a, p) => [a[0] + p[0] / points.length, a[1] + p[1] / points.length], [0, 0]);
  const button = (text, label, action, cls = '') => {
    const b = el('button', `pm-button ${cls}`, text);
    b.type = 'button'; b.setAttribute('aria-label', label || text); b.title = label || text;
    b.addEventListener('click', action); return b;
  };

  class MatrixMap {
    constructor(host, layout) {
      this.host = host; this.layout = layout;
      this.width = Number(layout.width) || 1200; this.height = Number(layout.height) || 800;
      this.svg = svgEl('svg', {viewBox: `0 0 ${this.width} ${this.height}`, role: 'img', 'aria-label': 'Interactive society plan. Select a numbered plot to inspect details.'});
      this.svg.classList.add('pm-svg');
      this.svg.append(svgEl('image', {href: layout.image, width: this.width, height: this.height, preserveAspectRatio: 'xMidYMid meet'}));
      this.layer = svgEl('g'); this.svg.append(this.layer); host.append(this.svg);
      this.view = {x: 0, y: 0, w: this.width, h: this.height}; this.pointers = new Map(); this.dragged = false;
      this.svg.addEventListener('wheel', e => { e.preventDefault(); this.zoom(e.deltaY < 0 ? 0.85 : 1.18, this.point(e)); }, {passive: false});
      this.svg.addEventListener('pointerdown', e => this.pointerDown(e));
      this.svg.addEventListener('pointermove', e => this.pointerMove(e));
      ['pointerup', 'pointercancel'].forEach(name => this.svg.addEventListener(name, e => {this.pointers.delete(e.pointerId); this.pinch = null; this.pan = null;}));
      this.svg.addEventListener('keydown', e => {
        if (e.target !== this.svg) return;
        const shift = this.view.w * .08;
        if (['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(e.key)) {
          e.preventDefault(); this.view.x += e.key === 'ArrowLeft' ? -shift : e.key === 'ArrowRight' ? shift : 0;
          this.view.y += e.key === 'ArrowUp' ? -shift : e.key === 'ArrowDown' ? shift : 0; this.update();
        } else if (e.key === '+' || e.key === '=') this.zoom(.8);
        else if (e.key === '-') this.zoom(1.25);
        else if (e.key === '0') this.reset();
      });
      this.svg.setAttribute('tabindex', '0');
    }
    point(e) {
      const p = this.svg.createSVGPoint(); p.x = e.clientX; p.y = e.clientY;
      return p.matrixTransform(this.svg.getScreenCTM().inverse());
    }
    pointerDown(e) {
      this.dragged = false;
      this.pointers.set(e.pointerId, {x: e.clientX, y: e.clientY});
      if (this.pointers.size === 2) {
        const [a, b] = [...this.pointers.values()]; this.pinch = {d: Math.hypot(a.x-b.x,a.y-b.y), view: {...this.view}};
        this.dragged = true; this.pan = null;
      } else if (!e.target.closest('[data-no-pan]') && (!this.drawing || e.button === 1 || e.altKey)) {
        this.pan = {point: this.point(e), clientX: e.clientX, clientY: e.clientY, view: {...this.view}};
      }
    }
    pointerMove(e) {
      if (!this.pointers.has(e.pointerId)) return;
      this.pointers.set(e.pointerId, {x: e.clientX, y: e.clientY});
      if (this.pointers.size === 2 && this.pinch) {
        const [a, b] = [...this.pointers.values()], d = Math.hypot(a.x-b.x,a.y-b.y);
        const factor = this.pinch.d / Math.max(1, d), initial = this.pinch.view;
        this.view = {...initial}; this.zoom(factor, {x: initial.x + initial.w/2,y: initial.y + initial.h/2}); this.dragged = true;
      } else if (this.pan) {
        const distance = Math.hypot(e.clientX-this.pan.clientX,e.clientY-this.pan.clientY);
        if (distance > 5) {
          this.dragged = true;
          const p = this.point(e); this.view.x += this.pan.point.x-p.x; this.view.y += this.pan.point.y-p.y; this.update();
        }
      }
    }
    update() { this.svg.setAttribute('viewBox', `${this.view.x} ${this.view.y} ${this.view.w} ${this.view.h}`); }
    reset() { this.view = {x: 0, y: 0, w: this.width, h: this.height}; this.update(); }
    zoom(factor, point) {
      const v = this.view, p = point || {x: v.x+v.w/2, y:v.y+v.h/2};
      const next = Math.min(this.width * 1.3, Math.max(this.width / 12, v.w * factor)), f = next/v.w;
      this.view = {x:p.x-(p.x-v.x)*f,y:p.y-(p.y-v.y)*f,w:next,h:v.h*f}; this.update();
    }
    focus(points) {
      if (!points?.length) return;
      const xs = points.map(p=>p[0]), ys = points.map(p=>p[1]);
      const cx = (Math.max(...xs)+Math.min(...xs))/2, cy = (Math.max(...ys)+Math.min(...ys))/2;
      const w = Math.max(Math.max(...xs)-Math.min(...xs), this.width*.15)*2.5;
      this.view = {x:cx-w/2,y:cy-w*this.height/this.width/2,w,h:w*this.height/this.width}; this.update();
    }
    render(plots, onSelect, selected) {
      this.layer.replaceChildren();
      plots.forEach(plot => {
        if (!Array.isArray(plot.polygon) || plot.polygon.length < 3) return;
        const group = svgEl('g', {class:`pm-plot pm-status-${status(plot.status)}${String(selected) === String(plot.id ?? plot.number) ? ' pm-selected' : ''}`});
        const polygon = svgEl('polygon', {points:plot.polygon.map(p=>p.join(',')).join(' '), tabindex: '0',role:'button','aria-label':`Plot ${plot.number}, ${title(plot.status)}${plot.area ? ', '+areaText(plot) : ''}`});
        polygon.append(svgEl('title')); polygon.firstChild.textContent = `Plot ${plot.number} · ${title(plot.status)}`;
        group.append(polygon);
        const label = plot.label_position?.length === 2 ? plot.label_position : center(plot.polygon);
        const text = svgEl('text',{x:label[0],y:label[1],'text-anchor':'middle','dominant-baseline':'central','font-size':Math.max(10,this.width*.010)}); text.textContent = plot.number; group.append(text);
        polygon.addEventListener('click', e => {if (!this.dragged && !this.drawing) onSelect?.(plot,e);});
        polygon.addEventListener('keydown', e => {if (e.key === 'Enter' || e.key === ' ') {e.preventDefault();onSelect?.(plot,e);}});
        this.layer.append(group);
      });
    }
    controls() {
      const controls = el('div','pm-zoom-controls');
      controls.append(button('+','Zoom in',()=>this.zoom(.8)),button('−','Zoom out',()=>this.zoom(1.25)),button('↺','Reset view',()=>this.reset()),button('⛶','Fullscreen',()=>{
        const host = this.host.closest('.pm-explorer') || this.host;
        if (document.fullscreenElement) document.exitFullscreen?.(); else host.requestFullscreen?.();
      })); return controls;
    }
  }

  class Explorer {
    constructor(root) {
      this.root = root; this.filter='all'; this.query=''; this.selected=null; this.data=null;
      try {this.compare = JSON.parse(localStorage.getItem('plotmatrix-compare') || '[]'); if (!Array.isArray(this.compare)) this.compare=[];} catch {this.compare=[];}
      root.classList.add('pm-explorer'); this.build(); this.load();
      this.timer = setInterval(()=>{if (!document.hidden) this.load(true);},45000);
    }
    build() {
      const toolbar = el('div','pm-map-toolbar'), titleWrap = el('div','pm-map-title');
      titleWrap.append(el('span','pm-eyebrow','YOUR PLACE IN THE PLAN'),el('h3',null,'Find a plot. Make it yours.')); toolbar.append(titleWrap);
      const search = el('input','pm-search'); search.type='search'; search.placeholder='Search plot number'; search.setAttribute('aria-label','Search plot number');
      search.addEventListener('input',()=>{this.query=search.value.trim().toLowerCase();this.render();if (this.query && this.visible()?.length===1) this.map?.focus(this.visible()[0].polygon);});
      toolbar.append(search); this.root.append(toolbar);
      this.stats = el('div','pm-stats'); this.root.append(this.stats);
      const main = el('div','pm-map-main'); this.stage=el('div','pm-stage'); this.stage.append(el('div','pm-loading','Loading the society plan…')); main.append(this.stage);
      this.panel=el('aside','pm-details'); this.panel.setAttribute('aria-live','polite'); main.append(this.panel); this.root.append(main);
      const footer = el('div','pm-map-footer'); this.legend=el('div','pm-legend');
      [['all','All plots'],['available','Available'],['booked','Booked'],['sold','Sold']].forEach(([value,label])=>{
        const b = button(label,label,()=>{this.filter=value;this.render();}); b.dataset.status=value;b.classList.add('pm-filter'); if(value==='all')b.classList.add('active');this.legend.append(b);
      }); this.updated=el('span','pm-updated');footer.append(this.legend,this.updated);this.root.append(footer);
      this.compareBox=el('div','pm-compare');this.root.append(this.compareBox);
      this.root.append(el('p','pm-availability-note','Availability and pricing are subject to confirmation with the Plot Matrix sales team. Pinch or scroll to zoom; drag to explore.'));
      this.emptyPanel(); this.renderCompare();
    }
    async load(quiet=false) {
      try {
        const response = await fetch(this.root.dataset.api,{headers:{Accept:'application/json'},cache:'no-store'});
        if (!response.ok) throw Error('The plan is temporarily unavailable. Please try again.');
        this.data = await response.json();
        if (!this.data.layout?.image) {
          this.stage.replaceChildren(el('div','pm-empty-map','The master plan is being prepared. Contact our team to learn more.'));return;
        }
        if (!this.map) {this.stage.replaceChildren();this.map=new MatrixMap(this.stage,this.data.layout);this.stage.append(this.map.controls());}
        if (this.selected) this.selected=this.data.plots.find(p=>String(p.id??p.number)===String(this.selected.id??this.selected.number)) || null;
        if (!this.initialSelection) {
          this.initialSelection=true;
          const wanted=this.root.dataset.selectedPlot || (location.pathname.includes('/plots/') ? decodeURIComponent(location.pathname.split('/').filter(Boolean).pop()) : '');
          if(wanted){this.selected=this.data.plots.find(p=>p.slug===wanted||String(p.number)===wanted)||null;if(this.selected)this.map.focus(this.selected.polygon);}
        }
        this.render(); this.selected ? this.details(this.selected) : this.emptyPanel();
        const date = this.data.updated_at ? new Date(this.data.updated_at) : new Date();
        this.updated.textContent=`Updated ${Number.isNaN(date.getTime()) ? 'just now' : date.toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})}`;
      } catch(error) {
        this.updated.textContent='Refresh unavailable — showing last loaded status';
        if(!quiet){const msg=el('div','pm-empty-map',error.message);msg.append(button('Try again',null,()=>this.load()));this.stage.replaceChildren(msg);}
      }
    }
    visible() {return this.data?.plots?.filter(p=>status(p.status)!=='hidden'&&(this.filter==='all'||status(p.status)===this.filter)&&String(p.number).toLowerCase().includes(this.query)) || [];}
    render() {
      if (!this.data) return;
      this.map?.render(this.visible(),plot=>{this.selected=plot;this.render();this.details(plot);},this.selected?.id??this.selected?.number);
      this.stats.replaceChildren();
      const counts = this.data.counts || {};
      [['total','Total plots'],['available','Available'],['booked','Booked'],['sold','Sold']].forEach(([key,label])=>{
        const c=el('div',`pm-stat pm-stat-${key}`); c.append(el('strong',null,String(counts[key] ?? this.data.plots.filter(p=>key==='total'||status(p.status)===key).length)),el('span',null,label));this.stats.append(c);
      });
      this.legend.querySelectorAll('button').forEach(b=>{b.classList.toggle('active',b.dataset.status===this.filter);b.setAttribute('aria-pressed',String(b.dataset.status===this.filter));});
    }
    emptyPanel() {
      this.panel.replaceChildren();const icon=el('div','pm-panel-icon','⌖');this.panel.append(icon,el('span','pm-eyebrow','A LITTLE CLOSER TO HOME'),el('h3',null,'Every great beginning starts with a place.'),el('p',null,'Select a numbered plot on the plan to explore its details and current availability.'));
      const note=el('div','pm-panel-hint','↖  Choose a plot to explore');this.panel.append(note);
    }
    details(plot) {
      this.panel.replaceChildren();const head=el('div','pm-detail-head');head.append(el('span',`pm-status-pill pm-status-${status(plot.status)}`,title(plot.status)),button('×','Close plot details',()=>{this.selected=null;this.render();this.emptyPanel();}));
      this.panel.append(head,el('span','pm-eyebrow',this.data.project.name),el('h3',null,`Plot ${plot.number}`));
      const specs=el('dl','pm-plot-specs');
      const row=(label,value)=>{if(value!==undefined&&value!==null&&value!==''){specs.append(el('dt',null,label),el('dd',null,String(value)));}};
      row('Plot area',areaText(plot));
      if (plot.length && plot.width) row('Dimensions',`${plot.length} × ${plot.width} ${plot.dimension_unit||'ft'}`);
      row('Facing',plot.facing);row('Road width',plot.road_width?`${plot.road_width}${/[a-z]/i.test(plot.road_width)?'':' ft'}`:null);
      if(plot.corner)row('Corner plot','Yes');if(plot.park_facing)row('Park facing','Yes');
      row('Price',plot.price_visible&&plot.price?`₹ ${Number(plot.price).toLocaleString('en-IN')}`:null); this.panel.append(specs);
      if(plot.description||plot.public_remarks)this.panel.append(el('p','pm-plot-description',plot.public_remarks||plot.description));
      if(status(plot.status)==='sold') {
        this.panel.append(el('p','pm-plot-description','This plot has been sold. Discover other available plots in this community.'),button('Explore available plots →',null,()=>{this.filter='available';this.selected=null;this.render();this.emptyPanel();},'pm-primary'));
      } else {
        this.panel.append(button(status(plot.status)==='booked'?'Ask about availability →':'Enquire about this plot →',null,()=>this.enquire(plot),'pm-primary'));
        const phone=String(this.data.whatsapp||this.data.project.whatsapp||'919250608786').replace(/\D/g,'');
        const a=el('a','pm-whatsapp','Enquire on WhatsApp ↗');a.href=`https://wa.me/${phone}?text=${encodeURIComponent(`Hello Plot Matrix, I would like to enquire about Plot ${plot.number} at ${this.data.project.name}. Its current listed status is ${title(plot.status)}. ${location.origin+(plot.url||location.pathname)}`)}`;a.target='_blank';a.rel='noopener noreferrer';this.panel.append(a);
        this.panel.append(button('Schedule a site visit',null,()=>this.enquire(plot,true),'pm-text-button'));
      }
      const actions=el('div','pm-detail-actions');actions.append(button(this.compare.some(p=>p.url===plot.url)?'✓ Added to compare':'+ Compare',null,()=>this.toggleCompare(plot)),button('↗ Share',null,async()=>{
        const url = new URL(plot.url||location.pathname,location.origin).href;
        try {if(navigator.share)await navigator.share({title:`Plot ${plot.number} · ${this.data.project.name}`,url});else{await navigator.clipboard.writeText(url);actions.lastChild.textContent='Link copied';}}catch{}
      })); this.panel.append(actions);
    }
    enquire(plot,visit=false) {
      const payload={...plot,project:this.data.project.slug,project_name:this.data.project.name,site_visit:visit};
      if (typeof window.openEnquiry==='function')window.openEnquiry(payload,visit?'site_visit':'enquiry',this.data.project.slug);
      else window.location.href=`/contact/?project=${encodeURIComponent(this.data.project.slug)}&plot=${encodeURIComponent(plot.number)}${visit?'&type=site_visit':''}`;
    }
    toggleCompare(plot) {
      const url = plot.url || `${location.pathname}#plot-${encodeURIComponent(plot.number)}`;
      const existing=this.compare.findIndex(p=>p.url===url);
      if(existing>=0)this.compare.splice(existing,1);
      else if(this.compare.length<3)this.compare.push({number:plot.number,status:plot.status,area:areaText(plot),facing:plot.facing,price:plot.price_visible?plot.price:null,project:this.data.project.name,url});
      else {alert('Compare up to three plots. Remove one to add another.');return;}
      localStorage.setItem('plotmatrix-compare',JSON.stringify(this.compare));this.renderCompare();this.details(plot);
    }
    renderCompare() {
      this.compareBox.replaceChildren();this.compareBox.hidden=!this.compare.length;if(!this.compare.length)return;
      this.compareBox.append(el('h4',null,`Your comparison · ${this.compare.length}/3`));
      const wrap=el('div','pm-compare-cards');this.compare.forEach((p,i)=>{const c=el('div','pm-compare-card');c.append(button('×',`Remove plot ${p.number}`,()=>{this.compare.splice(i,1);localStorage.setItem('plotmatrix-compare',JSON.stringify(this.compare));this.renderCompare();}),el('strong',null,`Plot ${p.number}`),el('span',null,p.project),el('p',null,[p.area,p.facing,p.price?`₹${Number(p.price).toLocaleString('en-IN')}`:null].filter(Boolean).join(' · ')),el('small',null,`${title(p.status)} when added — open to confirm`));const a=el('a',null,'View current details ↗');a.href=p.url;c.append(a);wrap.append(c);});this.compareBox.append(wrap);
    }
  }
  window.MatrixMap = MatrixMap;
  const start=()=>document.querySelectorAll('#plot-explorer, [data-plot-explorer]').forEach(root=>{if(!root.dataset.initialized){root.dataset.initialized='true';new Explorer(root);}});
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start);else start();
})();
