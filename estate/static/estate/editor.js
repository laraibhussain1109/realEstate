/* Authenticated staff polygon editor. All writes are validated by Django. */
(() => {
  'use strict';
  const root=document.getElementById('plot-editor');if(!root)return;
  const config=JSON.parse(document.getElementById('editor-config').textContent);
  const clone=value=>JSON.parse(JSON.stringify(value));
  const stage=document.getElementById('editor-stage'),form=document.getElementById('plot-editor-form');
  const map=new window.MatrixMap(stage,config.layout); stage.append(map.controls());
  const NS='http://www.w3.org/2000/svg';
  const svgEl=(tag,attrs={})=>{const node=document.createElementNS(NS,tag);Object.entries(attrs).forEach(([key,value])=>node.setAttribute(key,value));return node;};
  let plots=config.plots || [], selected=null, points=[], label=null, tool='select', closed=false, undo=[],redo=[], vertexDrag=null, dirty=false;
  const draftKey=`plotmatrix-layout-draft-${config.layout.id}`;
  const message=(text,error=false)=>{const node=document.getElementById('editor-message');node.textContent=text;node.classList.toggle('pm-error',error);};
  const fields=['number','status','area','area_unit','length','width','facing','road_width','price','price_visible','corner','park_facing','description','note'];
  const formData=()=>Object.fromEntries(fields.map(name=>{const input=form.elements.namedItem(name);return [name,input.type==='checkbox'?input.checked:input.value];}));
  const fill=data=>fields.forEach(name=>{const input=form.elements.namedItem(name),v=data[name];if(input.type==='checkbox')input.checked=!!v;else input.value=v??(name==='status'?'available':name==='area_unit'?'sqyd':'');});
  const snapshot=()=>({selected:selected?.id||null,points:clone(points),label:clone(label),closed,fields:formData()});
  const push=()=>{undo.push(snapshot());if(undo.length>100)undo.shift();redo=[];dirty=true;};
  const restore=s=>{selected=plots.find(p=>p.id===s.selected)||null;points=clone(s.points);label=clone(s.label);closed=s.closed;fill(s.fields);render();};
  const saveDraft=()=>{if(!dirty)return;try{localStorage.setItem(draftKey,JSON.stringify({...snapshot(),layout_image:config.layout.image,saved_at:Date.now()}));}catch{message('Your browser cannot save a local draft. Save the plot to preserve your work.',true);}};
  const setTool=value=>{
    tool=value;map.drawing=value==='draw'||value==='label';
    root.querySelectorAll('[data-tool]').forEach(b=>b.classList.toggle('active',b.dataset.tool===value));
    if(value==='draw')message('Click each corner of the real plot boundary. Close the polygon when finished. Alt + drag to pan.');
    else if(value==='label')message('Click inside the selected plot to position its number label.');
  };
  function select(plot) {
    selected=plot;points=clone(plot.polygon||[]);label=clone(plot.label_position||null);closed=points.length>=3;fill({...plot,status:String(plot.status).toLowerCase(),note:''});undo=[];redo=[];dirty=false;setTool('select');render();
    message(`Editing Plot ${plot.number}. Drag a white corner handle to refine the boundary, then save.`);
  }
  function render() {
    const other=plots.filter(p=>p.id!==selected?.id);
    if(closed && points.length>=3)other.push({...formData(),id:selected?.id||'new',polygon:points,label_position:label});
    map.render(other,(plot,e)=>{
      if(e.shiftKey){const checkbox=document.querySelector(`.pm-editor-list input[value="${plot.id}"]`);if(checkbox)checkbox.checked=!checkbox.checked;return;}
      if(selected?.id===plot.id)return;
      if(dirty&&!confirm('Leave this unsaved plot? Save the plot first to preserve your changes.'))return;
      const saved=plots.find(p=>p.id===plot.id);if(saved)select(saved);
    },selected?.id||'new');
    const handles=svgEl('g');handles.classList.add('pm-handles');map.layer.append(handles);
    if(!closed&&points.length)handles.append(svgEl('polyline',{points:points.map(p=>p.join(',')).join(' '),class:'pm-draw-line'}));
    points.forEach((point,index)=>{
      const handle=svgEl('circle',{cx:point[0],cy:point[1],r:map.view.w*.005,class:'pm-vertex','data-no-pan':'true','aria-label':`Vertex ${index+1}`});
      handle.addEventListener('pointerdown',e=>{
        e.stopPropagation();
        if(tool==='draw'&&!closed&&index===0&&points.length>=3){e.preventDefault();closePolygon();return;}
        push();vertexDrag={index};map.svg.setPointerCapture(e.pointerId);
      });handles.append(handle);
    });
    if(label){const handle=svgEl('circle',{cx:label[0],cy:label[1],r:map.view.w*.004,class:'pm-label-handle','data-no-pan':'true'});handle.addEventListener('pointerdown',e=>{e.stopPropagation();push();vertexDrag={label:true};map.svg.setPointerCapture(e.pointerId);});handles.append(handle);}
    document.getElementById('editor-heading').textContent=selected?`EDIT PLOT ${selected.number}`:'NEW PLOT';
    document.getElementById('editor-delete').hidden=!selected;
    document.getElementById('editor-undo').disabled=!undo.length;
    document.getElementById('editor-redo').disabled=!redo.length;
    document.getElementById('close-polygon').disabled=closed||points.length<3;
  }
  function closePolygon() {
    if(points.length<3){message('A plot needs at least three corners.',true);return;}
    push();closed=true;setTool('select');render();saveDraft();message('Boundary closed. Enter the plot number and details, then Save plot.');
  }
  function point(e) {
    const p=map.point(e);return [Math.round(Math.max(0,Math.min(map.width,p.x))*100)/100,Math.round(Math.max(0,Math.min(map.height,p.y))*100)/100];
  }
  map.svg.addEventListener('click',e=>{
    if(map.dragged||vertexDrag||e.altKey||e.target.classList.contains('pm-vertex'))return;
    if(tool==='draw'&&!closed){push();points.push(point(e));render();saveDraft();}
    else if(tool==='label'&&points.length>=3){push();label=point(e);render();saveDraft();setTool('select');message('Label moved. Save the plot to publish the change.');}
  });
  map.svg.addEventListener('pointermove',e=>{
    if(!vertexDrag)return;e.preventDefault();map.dragged=true;
    if(vertexDrag.label)label=point(e);else points[vertexDrag.index]=point(e);render();
  });
  const finishDrag=e=>{if(vertexDrag){vertexDrag=null;saveDraft();try{map.svg.releasePointerCapture(e.pointerId);}catch{}}};
  map.svg.addEventListener('pointerup',finishDrag);map.svg.addEventListener('pointercancel',finishDrag);
  root.querySelectorAll('[data-tool]').forEach(b=>b.addEventListener('click',()=>{
    const next=b.dataset.tool;
    if(next==='draw'){
      if(dirty&&points.length&&!confirm('Start a new polygon? Save the current plot first to keep its changes.'))return;
      selected=null;points=[];label=null;closed=false;undo=[];redo=[];dirty=false;fill({});render();
    }
    setTool(next);
  }));
  document.getElementById('close-polygon').addEventListener('click',closePolygon);
  const history=(from,to)=>{if(!from.length)return;to.push(snapshot());restore(from.pop());dirty=true;saveDraft();};
  document.getElementById('editor-undo').addEventListener('click',()=>history(undo,redo));
  document.getElementById('editor-redo').addEventListener('click',()=>history(redo,undo));
  document.getElementById('editor-focus').addEventListener('click',()=>{map.focus(points);render();});
  document.getElementById('editor-draft').addEventListener('click',()=>{dirty=true;saveDraft();message('Local draft saved in this browser. Save plot to update the shared database.');});
  document.getElementById('editor-search').addEventListener('input',e=>{
    const q=e.target.value.trim().toLowerCase();if(!q)return;const plot=plots.find(p=>String(p.number).toLowerCase()===q);if(plot){select(plot);map.focus(plot.polygon);render();}
  });
  form.addEventListener('input',()=>{dirty=true;saveDraft();render();});
  document.addEventListener('keydown',e=>{
    if(['INPUT','TEXTAREA','SELECT'].includes(e.target.tagName))return;
    if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='z'){e.preventDefault();e.shiftKey?history(redo,undo):history(undo,redo);}
    if(e.key==='Escape'){setTool('select');message('Drawing paused. Select Draw a plot to start over, or close the current boundary.');}
  });
  const csrf=()=>decodeURIComponent(document.cookie.split('; ').find(row=>row.startsWith('csrftoken='))?.slice(10)||document.querySelector('[name=csrfmiddlewaretoken]')?.value||'');
  async function post(payload) {
    const response=await fetch(config.api,{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':csrf(),Accept:'application/json'},body:JSON.stringify(payload),credentials:'same-origin'});
    let data;try{data=await response.json();}catch{throw Error(`Save failed (${response.status}). Check your session and try again.`);}
    if(!response.ok){const detail=data.errors||data.error||data.detail||'The change could not be saved.';throw Error(typeof detail==='string'?detail:JSON.stringify(detail));}return data;
  }
  async function busy(button,fn) {button.disabled=true;try{await fn();}catch(error){message(error.message,true);}finally{button.disabled=false;}}
  form.addEventListener('submit',e=>{
    e.preventDefault();if(!form.reportValidity())return;
    if(!closed||points.length<3){message('Close a polygon with at least three corners before saving.',true);return;}
    const button=document.getElementById('editor-save');busy(button,async()=>{
      const plot={...formData(),polygon:points,label_position:label||null,...(selected?{id:selected.id}:{})};
      const data=await post({action:'save',plot});
      if(data.plots)plots=data.plots;
      const saved=data.plot||data;
      if(!saved.id&&!data.plots)throw Error('The server did not return the saved plot. Reload before editing further.');
      if(saved.id){const index=plots.findIndex(p=>p.id===saved.id);if(index>=0)plots[index]=saved;else plots.push(saved);select(saved);}
      dirty=false;localStorage.removeItem(draftKey);list();render();message(`Plot ${saved.number||plot.number} saved. Availability is now visible on the public website.`);
    });
  });
  document.getElementById('editor-delete').addEventListener('click',e=>{
    if(!selected||!confirm(`Permanently delete Plot ${selected.number} and its boundary?`))return;
    busy(e.currentTarget,async()=>{await post({action:'delete',id:selected.id});plots=plots.filter(p=>p.id!==selected.id);selected=null;points=[];label=null;closed=false;fill({});dirty=false;localStorage.removeItem(draftKey);list();render();message('Plot deleted.');});
  });
  function list() {
    const host=document.getElementById('editor-plot-list'),checked=new Set([...host.querySelectorAll('input:checked')].map(i=>i.value));host.replaceChildren();
    plots.forEach(p=>{const label=document.createElement('label'),checkbox=document.createElement('input');checkbox.type='checkbox';checkbox.value=p.id;checkbox.checked=checked.has(String(p.id));label.append(checkbox,document.createTextNode(`Plot ${p.number} · ${p.status}`));host.append(label);});
  }
  document.getElementById('editor-bulk').addEventListener('click',e=>{
    const ids=[...document.querySelectorAll('#editor-plot-list input:checked')].map(i=>Number(i.value));
    const status=document.getElementById('bulk-status').value;
    if(!ids.length){message('Select at least one plot for a bulk update.',true);return;}
    if(!confirm(`Change ${ids.length} plot(s) to ${status}? This updates public availability.`))return;
    busy(e.currentTarget,async()=>{const data=await post({action:'bulk',ids,status,note:form.elements.note.value});if(data.plots)plots=data.plots;else plots.forEach(p=>{if(ids.includes(p.id))p.status=status;});if(selected)select(plots.find(p=>p.id===selected.id));list();render();message(`${ids.length} plot(s) updated to ${status}.`);});
  });
  window.addEventListener('beforeunload',e=>{if(dirty){saveDraft();e.preventDefault();e.returnValue='';}});
  fill({});list();render();
  try {const draft=JSON.parse(localStorage.getItem(draftKey)||'null');if(draft&&draft.layout_image===config.layout.image&&confirm('Restore the unsaved local polygon draft from this browser?')){restore(draft);dirty=true;message('Local draft restored. Review it and Save plot to publish.');}}catch{}
})();
