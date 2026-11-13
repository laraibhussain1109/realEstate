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
  let suggestions=[],reviewingCandidate=null,suspendedEditor=null,detectionBusy=false;
  const review=document.getElementById('detection-review');
  const draftKey=`plotmatrix-layout-draft-${config.layout.id}`;
  const message=(text,error=false)=>{const node=document.getElementById('editor-message');node.textContent=text;node.classList.toggle('pm-error',error);};
  const fields=['number','status','area','area_unit','length','width','facing','road_width','price','price_visible','corner','park_facing','description','note'];
  const formData=()=>Object.fromEntries(fields.map(name=>{const input=form.elements.namedItem(name);return [name,input.type==='checkbox'?input.checked:input.value];}));
  const fill=data=>fields.forEach(name=>{const input=form.elements.namedItem(name),v=data[name];if(input.type==='checkbox')input.checked=!!v;else input.value=v??(name==='status'?'available':name==='area_unit'?'sqyd':'');});
  const snapshot=()=>({selected:selected?.id||null,points:clone(points),label:clone(label),closed,fields:formData()});
  const push=()=>{undo.push(snapshot());if(undo.length>100)undo.shift();redo=[];dirty=true;};
  const restore=s=>{selected=plots.find(p=>p.id===s.selected)||null;points=clone(s.points);label=clone(s.label);closed=s.closed;fill(s.fields);render();};
  const saveDraft=()=>{if(!dirty||reviewingCandidate)return;try{localStorage.setItem(draftKey,JSON.stringify({...snapshot(),layout_image:config.layout.image,saved_at:Date.now()}));}catch{message('Your browser cannot save a local draft. Save the plot to preserve your work.',true);}};
  const setTool=value=>{
    tool=value;map.drawing=['draw','label','detect-point'].includes(value);
    root.querySelectorAll('[data-tool]').forEach(b=>b.classList.toggle('active',b.dataset.tool===value));
    if(value==='draw')message('Click each corner of the real plot boundary. Close the polygon when finished. Alt + drag to pan.');
    else if(value==='label')message('Click inside the selected plot to position its number label.');
    else if(value==='detect-point')message('Click inside a missed four-sided plot to suggest its boundary. Alt + drag to pan. The suggestion will stay unsaved.');
    document.getElementById('detection-point').classList.toggle('active',value==='detect-point');
  };
  function select(plot) {
    selected=plot;points=clone(plot.polygon||[]);label=clone(plot.label_position||null);closed=points.length>=3;fill({...plot,status:String(plot.status).toLowerCase(),note:''});undo=[];redo=[];dirty=false;setTool('select');render();
    message(`Editing Plot ${plot.number}. Drag a white corner handle to refine the boundary, then save.`);
  }
  function render() {
    const other=plots.filter(p=>p.id!==selected?.id);
    if(closed && points.length>=3)other.push({...formData(),id:selected?.id||'new',polygon:points,label_position:label});
    map.render(other,(plot,e)=>{
      if(reviewingCandidate){message('Keep your suggestion edits or return to the review list before selecting a saved plot.',true);return;}
      if(e.shiftKey){const checkbox=document.querySelector(`.pm-editor-list input[value="${plot.id}"]`);if(checkbox)checkbox.checked=!checkbox.checked;return;}
      if(selected?.id===plot.id)return;
      if(dirty&&!confirm('Leave this unsaved plot? Save the plot first to preserve your changes.'))return;
      const saved=plots.find(p=>p.id===plot.id);if(saved)select(saved);
    },selected?.id||'new');
    renderSuggestions();
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
    document.getElementById('editor-heading').textContent=reviewingCandidate?'EDIT UNSAVED SUGGESTION':selected?`EDIT PLOT ${selected.number}`:'NEW PLOT';
    document.getElementById('editor-delete').hidden=!selected||!!reviewingCandidate;
    document.getElementById('editor-save').textContent=reviewingCandidate?'Keep suggestion edits':'Save plot & availability';
    document.getElementById('detection-back').hidden=!reviewingCandidate;
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
    if(tool==='detect-point'){detectPoint(point(e));return;}
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
      if(reviewingCandidate){message('Keep your suggestion edits or return to the review list before drawing a new plot.',true);return;}
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
  document.getElementById('editor-draft').addEventListener('click',()=>{if(reviewingCandidate){keepCandidate();return;}dirty=true;saveDraft();message('Local draft saved in this browser. Save plot to update the shared database.');});
  document.getElementById('editor-search').addEventListener('input',e=>{
    const q=e.target.value.trim().toLowerCase();if(!q)return;if(reviewingCandidate){message('Finish editing your suggestion before searching saved plots.',true);return;}const plot=plots.find(p=>String(p.number).toLowerCase()===q);if(plot){if(dirty&&!confirm('Leave the unsaved plot draft?'))return;select(plot);map.focus(plot.polygon);render();}
  });
  form.addEventListener('input',()=>{dirty=true;saveDraft();render();});
  document.addEventListener('keydown',e=>{
    if(['INPUT','TEXTAREA','SELECT'].includes(e.target.tagName))return;
    if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='z'){e.preventDefault();e.shiftKey?history(redo,undo):history(undo,redo);}
    if(e.key==='Escape'){setTool('select');message('Drawing paused. Select Draw a plot to start over, or close the current boundary.');}
  });
  const csrf=()=>decodeURIComponent(document.cookie.split('; ').find(row=>row.startsWith('csrftoken='))?.slice(10)||document.querySelector('[name=csrfmiddlewaretoken]')?.value||'');
  async function post(payload,url=config.api) {
    const response=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':csrf(),Accept:'application/json'},body:JSON.stringify(payload),credentials:'same-origin'});
    let data;try{data=await response.json();}catch{throw Error(`Save failed (${response.status}). Check your session and try again.`);}
    if(!response.ok){const detail=data.errors||data.error||data.detail||'The change could not be saved.';throw Error(typeof detail==='string'?detail:JSON.stringify(detail));}return data;
  }
  async function busy(button,fn) {button.disabled=true;try{await fn();}catch(error){message(error.message,true);}finally{button.disabled=false;}}
  form.addEventListener('submit',e=>{
    e.preventDefault();if(!form.reportValidity())return;
    if(!closed||points.length<3){message('Close a polygon with at least three corners before saving.',true);return;}
    if(reviewingCandidate){keepCandidate();return;}
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

  // Detection is a review workspace. Suggestions never enter `plots` until
  // Django validates an explicit import; source colors never supply status.
  let layoutSignature=null;
  const detectionApi=config.detection_api||config.api.replace(/\/plots\/$/,'/detect/');
  const detectionStatuses=[['','Choose availability…'],['available','Available'],['booked','Booked'],['sold','Sold'],['blocked','Not for sale']];
  const node=(tag,cls,text)=>{const n=document.createElement(tag);if(cls)n.className=cls;if(text!=null)n.textContent=text;return n;};
  const confidence=c=>{const n=Number(c.confidence);return Number.isFinite(n)?Math.max(0,Math.min(1,n>1?n/100:n)):0;};
  const isFourSided=c=>Array.isArray(c?.polygon)&&c.polygon.length===4;
  const makeSuggestion=(c,forceIncluded=false)=>({key:String(c.key||`suggestion-${Date.now()}-${Math.random().toString(36).slice(2)}`),polygon:clone(c.polygon),confidence:confidence(c),reason:String(c.reason||'Check the boundary against the image.'),number:String(c.suggested_number||'').trim(),status:'',included:forceIncluded||confidence(c)>=.85,details:{}});
  function detectionSummary() {
    const included=suggestions.filter(c=>c.included),missingNumbers=included.filter(c=>!c.number.trim()).length,missingStatuses=included.filter(c=>!c.status).length;
    document.getElementById('detection-count').textContent=`(${suggestions.length})`;
    document.getElementById('detection-summary').textContent=`${included.length} selected · ${missingNumbers} need a number · ${missingStatuses} need availability. Nothing imported yet.`;
    document.getElementById('detection-import').disabled=detectionBusy||!included.length;
    document.getElementById('detection-empty').hidden=!!suggestions.length||detectionBusy;
  }
  function detectionWarnings(warnings=[]) {
    const host=document.getElementById('detection-warnings');host.replaceChildren();
    warnings.forEach(w=>host.append(node('li',null,String(w))));host.hidden=!warnings.length;
  }
  function detectionProgress(busy,text='Finding enclosed four-sided plots…') {
    detectionBusy=busy;review.setAttribute('aria-busy',String(busy));
    const progress=document.getElementById('detection-progress');progress.hidden=!busy;progress.textContent=text;
    ['editor-detect','detection-close','detection-point','detection-select-all','detection-select-none','detection-apply-status','detection-number'].forEach(id=>document.getElementById(id).disabled=busy);
    document.getElementById('detection-list').querySelectorAll('input,select,button').forEach(n=>n.disabled=busy);
    detectionSummary();
  }
  function renderReviewList() {
    const host=document.getElementById('detection-list');host.replaceChildren();
    suggestions.forEach((candidate,index)=>{
      const row=node('div',`pm-suggestion-row${candidate.key===reviewingCandidate?.key?' pm-review-active':''}`);
      const include=node('input');include.type='checkbox';include.checked=candidate.included;include.setAttribute('aria-label',`Include suggestion ${index+1}`);
      include.addEventListener('change',()=>{candidate.included=include.checked;detectionSummary();render();});
      const info=node('div','pm-suggestion-info');info.append(node('strong',null,`Suggestion ${index+1}`),node('small',null,candidate.confidence>=.85?'Clear outline · verify boundary':'Check this outline'));info.title=candidate.reason;
      const numberLabel=node('label','pm-suggestion-field','Plot number');const number=node('input');number.type='text';number.maxLength=30;number.value=candidate.number;number.placeholder='Enter number';number.setAttribute('aria-label',`Plot number for suggestion ${index+1}`);
      number.addEventListener('input',()=>{candidate.number=number.value;if(reviewingCandidate?.key===candidate.key)form.elements.namedItem('number').value=number.value;detectionSummary();render();});numberLabel.append(number);
      const statusLabel=node('label','pm-suggestion-field','Availability');const status=node('select');status.setAttribute('aria-label',`Availability for suggestion ${index+1}`);
      detectionStatuses.forEach(([value,text])=>status.add(new Option(text,value)));status.value=candidate.status;
      status.addEventListener('change',()=>{candidate.status=status.value;if(reviewingCandidate?.key===candidate.key)form.elements.namedItem('status').value=status.value;detectionSummary();render();});statusLabel.append(status);
      const edit=node('button','pm-button','Edit boundary');edit.type='button';edit.setAttribute('aria-label',`Edit boundary of suggestion ${index+1}`);edit.addEventListener('click',()=>editCandidate(candidate));
      const remove=node('button','pm-button pm-suggestion-remove','×');remove.type='button';remove.setAttribute('aria-label',`Remove suggestion ${index+1}`);remove.addEventListener('click',()=>{
        if(reviewingCandidate?.key===candidate.key)restoreEditor();suggestions=suggestions.filter(c=>c.key!==candidate.key);renderReviewList();render();message('Suggestion removed. Saved plots are unchanged.');
      });row.append(include,info,numberLabel,statusLabel,edit,remove);host.append(row);
    });detectionSummary();
  }
  function renderSuggestions() {
    if(!suggestions.length)return;
    const layer=svgEl('g',{'aria-label':'Unsaved boundary suggestions'});
    suggestions.forEach((candidate,index)=>{
      if(candidate.key===reviewingCandidate?.key)return;
      const group=svgEl('g',{class:`pm-suggestion${candidate.included?' pm-suggestion-included':''}`});
      const polygon=svgEl('polygon',{points:candidate.polygon.map(p=>p.join(',')).join(' '),role:'button',tabindex:'0','aria-label':`Review suggestion ${index+1}${candidate.number?', plot '+candidate.number:''}`});
      const title=svgEl('title');title.textContent=`Unsaved suggestion ${index+1}: ${candidate.confidence>=.85?'Clear outline — verify boundary.':'Check this outline.'} ${candidate.reason}`;polygon.append(title);
      const p=candidate.polygon.reduce((a,p)=>[a[0]+p[0]/candidate.polygon.length,a[1]+p[1]/candidate.polygon.length],[0,0]);
      const text=svgEl('text',{x:p[0],y:p[1],'font-size':map.width*.009,'text-anchor':'middle','dominant-baseline':'central'});text.textContent=candidate.number||`?${index+1}`;
      const choose=e=>{if(map.dragged||map.drawing)return;e.stopPropagation();editCandidate(candidate,false);};polygon.addEventListener('click',choose);polygon.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();editCandidate(candidate,false);}});
      group.append(polygon,text);layer.append(group);
    });map.layer.append(layer);
  }
  function editCandidate(candidate,focus=true) {
    if(detectionBusy)return;
    if(!isFourSided(candidate)){message('Automatic suggestions must have exactly four corners. Detect again or trace this plot manually.',true);return;}
    if(reviewingCandidate?.key===candidate.key)return;
    if(reviewingCandidate&&dirty&&!confirm('Discard the current unsaved suggestion edits? Choose Keep suggestion edits to retain them.'))return;
    if(!suspendedEditor){saveDraft();suspendedEditor={draft:snapshot(),undo:clone(undo),redo:clone(redo),dirty,view:{...map.view}};}
    reviewingCandidate=candidate;selected=null;points=clone(candidate.polygon);label=clone(candidate.details.label_position||null);closed=true;undo=[];redo=[];dirty=false;
    fill({...candidate.details,number:candidate.number,status:candidate.status});setTool('select');
    if(focus)map.focus(points);renderReviewList();render();
    if(focus)stage.scrollIntoView({behavior:'smooth',block:'center'});
    message('Editing an unsaved four-sided suggestion. Adjust its four corners, number and availability, then Keep suggestion edits.');
  }
  function restoreEditor() {
    reviewingCandidate=null;const old=suspendedEditor;suspendedEditor=null;
    if(old){restore(old.draft);undo=old.undo;redo=old.redo;dirty=old.dirty;map.view=old.view;map.update();}
    setTool('select');render();renderReviewList();
  }
  function keepCandidate() {
    if(!reviewingCandidate)return true;
    if(!form.reportValidity())return false;
    if(!closed||points.length!==4){message('Automatic suggestions must have exactly four corners. Keep all four corners when adjusting this boundary.',true);return false;}
    const data=formData();if(!detectionStatuses.some(([s])=>s&&s===data.status)){message('Choose Available, Booked, Sold or Not for sale for this suggestion.',true);return false;}
    reviewingCandidate.polygon=clone(points);reviewingCandidate.number=data.number.trim();reviewingCandidate.status=data.status;
    const {note,...details}=data;reviewingCandidate.details={...details,label_position:clone(label)};
    restoreEditor();message('Suggestion edits kept locally. Use Import selected plots to save reviewed suggestions to the database.');return true;
  }
  document.getElementById('detection-back').addEventListener('click',()=>{
    if(dirty&&!confirm('Discard the current unsaved suggestion edits?'))return;restoreEditor();message('Returned to suggestions. Saved plots are unchanged.');
  });
  document.getElementById('editor-detect').addEventListener('click',async()=>{
    if(detectionBusy)return;
    if(reviewingCandidate){message('Keep your suggestion edits or return to the review list before detecting again.',true);return;}
    if(dirty){saveDraft();if(!confirm('You have an unsaved manual plot draft. Detection will preserve it as a local draft and will not save it. Continue?'))return;}
    if(suggestions.length&&!confirm('Replace the current unsaved detection suggestions with a new scan?'))return;
    review.hidden=false;detectionWarnings();detectionProgress(true);message('Detecting four-sided plots. Review is required before anything can be imported.');
    try {
      const data=await post({action:'detect',options:{}},detectionApi);
      const candidates=Array.isArray(data.candidates)?data.candidates:[],accepted=candidates.filter(isFourSided),skipped=candidates.length-accepted.length;
      suggestions=accepted.map(c=>makeSuggestion(c));layoutSignature=data.layout_signature||null;
      const warnings=[...(data.warnings||[])];if(skipped)warnings.push(`${skipped} suggestion(s) without exactly four corners were skipped. Detect again for four-sided plots, or trace those plots manually.`);
      detectionWarnings(warnings);renderReviewList();render();
      message(suggestions.length?`${suggestions.length} four-sided plot suggestion(s) found. Review numbers and assign availability before importing.`:'No four-sided plots were detected. Try clicking inside a missed four-sided plot or draw its boundary manually.');
    }catch(error){detectionWarnings([error.message]);message(error.message,true);}finally{detectionProgress(false);}
  });
  document.getElementById('detection-select-all').addEventListener('click',()=>{suggestions.forEach(c=>c.included=true);renderReviewList();render();});
  document.getElementById('detection-select-none').addEventListener('click',()=>{suggestions.forEach(c=>c.included=false);renderReviewList();render();});
  document.getElementById('detection-apply-status').addEventListener('click',()=>{
    const status=document.getElementById('detection-bulk-status').value,included=suggestions.filter(c=>c.included);
    if(!status||!included.length){message('Select suggestions and explicitly choose their availability first.',true);return;}
    included.forEach(c=>{c.status=status;});if(reviewingCandidate?.included)form.elements.namedItem('status').value=status;renderReviewList();render();message(`Availability assigned to ${included.length} unsaved suggestion(s). Review before importing.`);
  });
  document.getElementById('detection-number').addEventListener('click',()=>{
    const prefix=document.getElementById('detection-prefix').value.trim();let next=Number(document.getElementById('detection-start').value);
    if(!Number.isInteger(next)||next<1||next>999999){message('Enter a whole-number starting value between 1 and 999999.',true);return;}
    const used=new Set([...plots.map(p=>String(p.number).toLowerCase()),...suggestions.map(c=>c.number.trim().toLowerCase()).filter(Boolean)]);let count=0;
    for(const candidate of suggestions.filter(c=>c.included&&!c.number.trim())){let number;do{number=`${prefix}${next++}`;}while(used.has(number.toLowerCase()));if(number.length>30){message('The resulting plot number is too long. Use a shorter prefix.',true);break;}candidate.number=number;used.add(number.toLowerCase());count++;}
    if(reviewingCandidate)form.elements.namedItem('number').value=reviewingCandidate.number;renderReviewList();render();message(`${count} missing number(s) assigned. Verify the sequence against the plan before importing.`);
  });
  document.getElementById('detection-point').addEventListener('click',()=>{
    if(reviewingCandidate){message('Keep your suggestion edits or return to the review list first.',true);return;}
    setTool(tool==='detect-point'?'select':'detect-point');stage.scrollIntoView({behavior:'smooth',block:'center'});
  });
  async function detectPoint([x,y]) {
    if(detectionBusy)return;review.hidden=false;detectionProgress(true,'Looking for a four-sided plot around the selected point…');
    try {
      const data=await post({action:'point',x,y},detectionApi),candidate=data.candidate||(data.candidates||[])[0];
      if(layoutSignature&&data.layout_signature&&layoutSignature!==data.layout_signature)throw Error('The layout image changed. Discard these suggestions and detect the new revision before importing.');
      layoutSignature=data.layout_signature||layoutSignature;detectionWarnings(data.warnings||[]);
      if(isFourSided(candidate)){
        const fingerprint=JSON.stringify(candidate.polygon);if(suggestions.some(c=>JSON.stringify(c.polygon)===fingerprint))message('That boundary is already in the review list.');
        else {const suggestion=makeSuggestion(candidate,true);if(suggestions.some(c=>c.key===suggestion.key))suggestion.key+=`-point-${Date.now()}`;suggestions.push(suggestion);renderReviewList();render();message('Four-sided plot suggestion added. Review it and explicitly assign its number and availability.');}
      }else if(candidate){const text='The detected region does not have exactly four corners and was skipped. Try another point inside a four-sided plot, or trace it manually.';message(text,true);detectionWarnings([...(data.warnings||[]),text]);}
      else message('No enclosed four-sided plot was found there. Click further inside the plot or trace it manually.',true);
    }catch(error){message(error.message,true);detectionWarnings([error.message]);}finally{setTool('select');detectionProgress(false);}
  }
  document.getElementById('detection-close').addEventListener('click',()=>{
    if(suggestions.length&&!confirm('Discard all unsaved detection suggestions? Saved plots will stay unchanged.'))return;
    if(reviewingCandidate)restoreEditor();suggestions=[];layoutSignature=null;review.hidden=true;setTool('select');render();message('Detection suggestions discarded. Saved plots are unchanged.');
  });
  document.getElementById('detection-import').addEventListener('click',async()=>{
    if(detectionBusy)return;if(reviewingCandidate&&!keepCandidate())return;
    const included=suggestions.filter(c=>c.included);if(!included.length){message('Select at least one suggestion to import.',true);return;}
    if(included.some(c=>!isFourSided(c))){message('Only suggestions with exactly four corners can be imported. Exclude other shapes and detect again or trace them manually.',true);return;}
    if(included.some(c=>!c.number.trim()||!c.status)){message('Every selected suggestion needs a plot number and an explicitly assigned availability status.',true);return;}
    const used=new Set(plots.map(p=>String(p.number).trim().toLowerCase()));
    for(const c of included){const number=c.number.trim().toLowerCase();if(used.has(number)){message(`Plot number ${c.number} is duplicated. Correct it or exclude that suggestion before importing.`,true);return;}used.add(number);}
    if(!layoutSignature){message('The detection signature is missing. Run detection again before importing.',true);return;}
    if(dirty){saveDraft();if(!confirm('Your manual plot draft is still unsaved and will remain separate from this import. Continue importing the selected suggestions?'))return;}
    if(!confirm(`Import ${included.length} reviewed plot(s) with the availability you assigned? Existing plots will not be replaced.`))return;
    detectionProgress(true,'Validating and importing reviewed plots…');
    try {
      const metadata=['area','area_unit','length','width','dimension_unit','facing','road_width','corner','park_facing','price','price_visible','description','public_remarks','label_position'];
      const candidates=included.map(c=>{const data={polygon:c.polygon,number:c.number.trim(),status:c.status};metadata.forEach(key=>{if(c.details[key]!==undefined)data[key]=c.details[key];});return data;});
      const data=await post({action:'import',layout_signature:layoutSignature,candidates},detectionApi);
      if(!Array.isArray(data.plots))throw Error('The server did not return the updated plots. Reload this editor before importing again.');
      plots=data.plots;const imported=new Set(included.map(c=>c.key));suggestions=suggestions.filter(c=>!imported.has(c.key));list();renderReviewList();render();if(!suggestions.length)review.hidden=true;
      message(`${included.length} reviewed plot(s) imported successfully. Existing plots were preserved. Public visibility follows this layout revision’s publication settings.`);
    }catch(error){message(error.message,true);detectionWarnings([error.message]);}finally{detectionProgress(false);}
  });
  window.addEventListener('beforeunload',e=>{if(dirty||suggestions.length){saveDraft();e.preventDefault();e.returnValue='';}});
  fill({});list();render();
  try {const draft=JSON.parse(localStorage.getItem(draftKey)||'null');if(draft&&draft.layout_image===config.layout.image&&confirm('Restore the unsaved local polygon draft from this browser?')){restore(draft);dirty=true;message('Local draft restored. Review it and Save plot to publish.');}}catch{}
})();
