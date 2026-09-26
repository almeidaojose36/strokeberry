import React, {useEffect, useRef, useState} from 'react';
import {ArrowDown, ArrowUp, LoaderCircle, ScanLine, X} from 'lucide-react';
import ImageEditor from './ImageEditor.jsx';

export default function StepEditor({project: sourceProject, api, onClose, onCreated}) {
  const [project, setProject] = useState(sourceProject), [editingImage, setEditingImage] = useState(false);
  const [stages, setStages] = useState([]), [active, setActive] = useState(0);
  const [align, setAlign] = useState(true), [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true), [error, setError] = useState('');
  const [detected, setDetected] = useState(false), [layout, setLayout] = useState('2x2'), [suggested, setSuggested] = useState(null);
  const defaultsFor = crops => crops.map((crop,i)=>({crop,label:crops.length===4?['Basic guides','Main outlines','Details & shading','Color'][i]:`Step ${i+1}`,seconds:Math.floor(120/crops.length)+(i===crops.length-1?120%crops.length:0),offset_x:0,offset_y:0,scale:1}));
  const sheet = useRef(null), drag = useRef(null), dialog = useRef(null);
  useEffect(() => {
    let alive = true;
    api(`/api/projects/${project.id}/step-layout`).then(data => {
      if (!alive) return;
      setDetected(data.detected);
      setSuggested(data);
      setStages(data.config?.stages || defaultsFor(data.crops));
      setLayout(data.config&&data.config.stages.length!==data.crops.length?'custom':`${data.columns}x${data.rows}`);
      setAlign(data.config?.align ?? true);
    }).catch(e => {if (alive) setError(e.message)}).finally(() => {if (alive) setLoading(false)});
    return () => {alive = false};
  }, [sourceProject.id]);
  useEffect(() => {
    const previous = document.activeElement;
    dialog.current?.focus();
    const keys = e => {
      if (editingImage) return;
      if (e.key === 'Escape' && !busy) onClose();
      if (e.key === 'Tab') {
        const items = dialog.current.querySelectorAll('button:not(:disabled),input:not(:disabled),select:not(:disabled)');
        if (!items.length) return;
        const first = items[0], last = items[items.length - 1];
        if (e.shiftKey && (document.activeElement === first || document.activeElement === dialog.current)) {e.preventDefault();last.focus()}
        else if (!e.shiftKey && document.activeElement === last) {e.preventDefault();first.focus()}
      }
    };
    window.addEventListener('keydown', keys);
    return () => {window.removeEventListener('keydown', keys);previous?.focus()};
  }, [busy, editingImage]);
  const update = (index, key, value) => setStages(items => items.map((stage, i) => i === index ? {...stage, [key]: value} : stage));
  function cropValue(key, number) {
    if (!Number.isFinite(number)) return;
    const c = {...stages[active].crop};
    if (key === 'x' || key === 'y') c[key] = Math.max(0, Math.min(1 - c[key === 'x' ? 'width' : 'height'], number / 100));
    else c[key] = Math.max(.02, Math.min(1 - c[key === 'width' ? 'x' : 'y'], number / 100));
    update(active, 'crop', c);
  }
  function startDrag(e, index, resize = false) {
    if (busy) return;
    e.preventDefault();e.stopPropagation();setActive(index);
    e.currentTarget.setPointerCapture(e.pointerId);
    drag.current = {index, resize, x: e.clientX, y: e.clientY, crop: {...stages[index].crop}};
  }
  function moveDrag(e) {
    const d = drag.current;if (!d) return;
    const box = sheet.current.getBoundingClientRect();
    const dx = (e.clientX - d.x) / box.width, dy = (e.clientY - d.y) / box.height;
    const c = {...d.crop};
    if (d.resize) {c.width = Math.max(.02, Math.min(1-c.x, c.width+dx));c.height = Math.max(.02, Math.min(1-c.y,c.height+dy))}
    else {c.x = Math.max(0,Math.min(1-c.width,c.x+dx));c.y = Math.max(0,Math.min(1-c.height,c.y+dy))}
    update(d.index,'crop',c);
  }
  function reorder(index, direction) {
    const next = [...stages], target = index + direction;
    [next[index], next[target]] = [next[target], next[index]];
    setStages(next);setActive(target);
  }
  function changeLayout(value) {
    const [columns,rows]=value.split('x').map(Number);
    const crops=Array.from({length:columns*rows},(_,i)=>({x:(i%columns)/columns,y:Math.floor(i/columns)/rows,width:1/columns,height:1/rows}));
    setStages(defaultsFor(crops));setLayout(value);setActive(0);setDetected(false);
  }
  const total = stages.reduce((sum, stage) => sum + stage.seconds, 0);
  const fourStepOrder = stages.length === 4;
  async function save() {
    setBusy(true);setError('');
    try {const result = await api(`/api/projects/${project.id}/steps`, {
      method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({stages,align:stages.length>1&&align})});onCreated(result)}
    catch (e) {setError(e.message)} finally {setBusy(false)}
  }
  return <div className="modal-backdrop"><section ref={dialog} tabIndex={-1} className="step-editor" role="dialog" aria-modal="true" aria-labelledby="steps-title">
    <header><div><div className="eyebrow">ONE DRAWING, ONE STEP AT A TIME</div><h2 id="steps-title">Build your drawing sequence</h2></div><button className="icon-button" aria-label="Close step editor" disabled={busy} onClick={onClose}><X size={20}/></button></header>
    {error && <p role="alert" className="failure-text">{error}</p>}
    {loading ? <div className="steps-loading"><LoaderCircle className="spin"/>Finding your panels…</div> : stages.length > 0 && <>
      <div className="image-tools"><button className="button secondary" disabled={busy} onClick={()=>setEditingImage(true)}>Edit image · eraser & brush</button><button className="button secondary" disabled={busy} aria-pressed={stages.length===1} onClick={()=>changeLayout('1x1')}>1 step · keep whole image</button></div>
      <p className="setting-hint">Choose 1 step to draw the full sheet with each panel in its original position. Choose multiple crops to combine them into one evolving drawing.</p>
      <div className="step-editor-grid">
        <div className="crop-workspace"><p>{detected ? `${suggested?.crops.length} panels found · ${stages.length} stages configured. Review the crops.` : 'Review the grid and adjust it to your panels.'}</p><label className="layout-picker">Panel layout<select aria-label="Panel layout" value={layout} disabled={busy} onChange={e=>changeLayout(e.target.value)}>{layout==='custom'&&<option value="custom">Saved custom crops</option>}{[['1x1','1 step · keep whole image'],['2x1','2 columns × 1 row'],['3x1','3 columns × 1 row'],['4x1','4 columns × 1 row'],['2x2','2 columns × 2 rows'],['3x2','3 columns × 2 rows'],['2x3','2 columns × 3 rows'],['4x2','4 columns × 2 rows'],['2x4','2 columns × 4 rows'],['1x2','1 column × 2 rows'],['1x3','1 column × 3 rows'],['1x4','1 column × 4 rows']].map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></label>{suggested?.detected&&<button className="button secondary detect-layout" disabled={busy} onClick={()=>{setStages(defaultsFor(suggested.crops));setActive(0);setLayout(`${suggested.columns}x${suggested.rows}`);setDetected(true)}}>Use detected {suggested.columns} × {suggested.rows} layout</button>}
          <div className="crop-sheet" ref={sheet}><img src={project.original || project.source} alt="Uploaded drawing tutorial with editable panel crops"/>
            {stages.map((stage,i) => <div key={i} role="button" tabIndex={0} aria-label={`Select crop for step ${i+1}`} onKeyDown={e=>{if(e.key==='Enter'||e.key===' ')setActive(i)}}
              className={`crop-box ${active===i?'active':''}`} style={{left:`${stage.crop.x*100}%`,top:`${stage.crop.y*100}%`,width:`${stage.crop.width*100}%`,height:`${stage.crop.height*100}%`}}
              onPointerDown={e=>startDrag(e,i)} onPointerMove={moveDrag} onPointerUp={()=>drag.current=null} onPointerCancel={()=>drag.current=null}>
              <span>{i+1}</span><i onPointerDown={e=>startDrag(e,i,true)} onPointerMove={moveDrag} onPointerUp={()=>drag.current=null}/>
            </div>)}
          </div>
          <small>Drag a crop to move it. Drag its lower-right corner to resize.</small>
        </div>
        <div className="stage-controls"><div className="field-label">ORDER & TIMING <span>{Math.floor(total/60)}:{String(total%60).padStart(2,'0')} total</span></div>
          {fourStepOrder&&<p className="setting-hint">Fixed reading order: top-left → top-right → bottom-left → bottom-right.</p>}
          <div className="stage-order">{stages.map((stage,i)=><div className={`stage-order-row ${active===i?'active':''}`} key={i}>
            <button className="stage-number" aria-label={`Edit step ${i+1}`} onClick={()=>setActive(i)}>{i+1}</button>
            <input aria-label={`Step ${i+1} name`} maxLength={40} value={stage.label} disabled={busy} onFocus={()=>setActive(i)} onChange={e=>update(i,'label',e.target.value)}/>
            <label><input aria-label={`Step ${i+1} seconds`} type="number" min={1} max={300} value={stage.seconds} disabled={busy} onChange={e=>update(i,'seconds',Math.max(1,Math.min(300,Number(e.target.value)||1)))}/>s</label>
            <div><button aria-label={`Move step ${i+1} earlier`} disabled={busy||fourStepOrder||i===0} onClick={()=>reorder(i,-1)}><ArrowUp size={12}/></button><button aria-label={`Move step ${i+1} later`} disabled={busy||fourStepOrder||i===stages.length-1} onClick={()=>reorder(i,1)}><ArrowDown size={12}/></button></div>
          </div>)}</div>
          <div className="field-label">STEP {active+1} CROP <span>Percent of uploaded image</span></div>
          <div className="crop-fields">{['x','y','width','height'].map(key=><label key={key}>{({x:'Left',y:'Top',width:'Width',height:'Height'})[key]}<input aria-label={`Crop ${key}`} type="number" min={0} max={100} step={.1} disabled={busy} value={Number((stages[active].crop[key]*100).toFixed(1))} onChange={e=>cropValue(key,Number(e.target.value))}/></label>)}</div>
          {stages.length>1&&<><label className="align-checkbox"><input type="checkbox" checked={align} disabled={busy} onChange={e=>setAlign(e.target.checked)}/><span><strong>Automatically align the drawings</strong><small>Matches earlier marks to the final stage.</small></span></label>
          <div className="field-label">STEP {active+1} ALIGNMENT CORRECTION</div><div className="crop-fields alignment-fields">
            {[['offset_x','Left / right',1,-25,25],['offset_y','Up / down',1,-25,25],['scale','Scale',.01,.7,1.3]].map(([key,label,step,min,max])=><label key={key}>{label}<input aria-label={`Stage ${key}`} type="number" step={step} min={min} max={max} disabled={busy} value={stages[active][key]} onChange={e=>update(active,key,Math.max(min,Math.min(max,Number(e.target.value))))}/></label>)}
          </div><p className="setting-hint">Offsets are percentages of the drawing canvas. Preview the aligned stages after saving; use Edit steps to make corrections.</p></>}
        </div>
      </div>
      <footer><div><strong>{stages.length===1?'1 step · original layout preserved':`${stages.length} stages · one continuous drawing`}</strong><small>{stages.length===1?'All panels stay separate on the same sheet.':'New marks appear progressively. Changed guides fade away.'}</small></div><button className="button primary" disabled={busy||total>300||total<5||stages.some(s=>!s.label.trim())} onClick={save}>{busy?<LoaderCircle className="spin" size={17}/>:<ScanLine size={17}/>} {busy?'Preparing your drawing…':'Prepare drawing steps'}</button></footer>
      {total>300&&<p role="alert" className="failure-text">Shorten the stages to a total of five minutes or less.</p>}
    </>}
  </section>{editingImage&&<ImageEditor project={{...project,config:undefined}} api={api} onClose={()=>setEditingImage(false)} onSaved={result=>{setProject(result);setEditingImage(false);}}/>}</div>;
}
