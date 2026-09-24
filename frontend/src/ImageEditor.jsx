import React, {useEffect, useRef, useState} from 'react';
import {Eraser, Pencil, Undo2, Redo2, X, LoaderCircle} from 'lucide-react';

export default function ImageEditor({project, api, onClose, onSaved}) {
  const canvas = useRef(null), dialog = useRef(null), original = useRef(null), stroke = useRef(null);
  const history = useRef([]), future = useRef([]);
  const [tool, setTool] = useState('eraser'), [size, setSize] = useState(30), [color, setColor] = useState('#222222');
  const [paper, setPaper] = useState('#ffffff'), [zoom, setZoom] = useState(100);
  const [cleanup, setCleanup] = useState(50), [cleaning, setCleaning] = useState(false), [notice, setNotice] = useState('');
  const [ready, setReady] = useState(false), [busy, setBusy] = useState(false), [error, setError] = useState(''), [revision, setRevision] = useState(0);
  useEffect(() => {
    let alive = true;
    const image = new Image();
    image.onload = () => {
      if (!alive) return;
      const c = canvas.current;
      c.width = image.naturalWidth; c.height = image.naturalHeight;
      const ctx = c.getContext('2d', {willReadFrequently: true});
      ctx.drawImage(image, 0, 0);
      original.current = ctx.getImageData(0, 0, c.width, c.height);
      setReady(true);
    };
    image.onerror = () => {if (alive) setError('Could not load this image. Close and try again.');};
    image.src = project.original || project.source;
    return () => {alive = false;};
  }, [project.id]);
  useEffect(() => {
    const previous = document.activeElement; dialog.current?.focus();
    return () => previous?.focus();
  }, []);
  const snapshot = () => canvas.current.getContext('2d').getImageData(0, 0, canvas.current.width, canvas.current.height);
  function remember() {
    history.current.push(snapshot());
    // Keep history within roughly 80 MB for large uploads.
    const limit = Math.max(1, Math.min(20, Math.floor(80e6 / (canvas.current.width * canvas.current.height * 4))));
    if (history.current.length > limit) history.current.shift();
    future.current = []; setRevision(v => v + 1);
  }
  function point(e) {
    const c = canvas.current, box = c.getBoundingClientRect();
    return {x: (e.clientX - box.left) * c.width / box.width, y: (e.clientY - box.top) * c.height / box.height};
  }
  function paint(a, b) {
    const ctx = canvas.current.getContext('2d');
    ctx.strokeStyle = tool === 'eraser' ? paper : color;
    ctx.fillStyle = ctx.strokeStyle; ctx.lineWidth = size; ctx.lineCap = 'round'; ctx.lineJoin = 'round';
    ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
    ctx.beginPath(); ctx.arc(b.x, b.y, size / 2, 0, Math.PI * 2); ctx.fill();
  }
  function start(e) {
    if (!ready || busy || e.button !== 0) return;
    e.preventDefault(); canvas.current.setPointerCapture(e.pointerId);
    remember(); stroke.current = point(e); paint(stroke.current, stroke.current);
  }
  function move(e) {
    if (!stroke.current) return;
    const p = point(e); paint(stroke.current, p); stroke.current = p;
  }
  function undo(redo = false) {
    const from = redo ? future.current : history.current, to = redo ? history.current : future.current;
    if (!from.length) return;
    to.push(snapshot()); canvas.current.getContext('2d').putImageData(from.pop(), 0, 0); setRevision(v => v + 1);
  }
  async function enhance() {
    setBusy(true);setCleaning(true);setError('');setNotice('');
    try {
      const blob=await new Promise(resolve=>canvas.current.toBlob(resolve,'image/png'));
      if(!blob || blob.size>15*1024*1024)throw new Error('Please use an image smaller than 15 MB.');
      const body=new FormData();body.append('file',blob,'canvas.png');body.append('strength',String(cleanup));
      const response=await fetch('/api/images/clean-background',{method:'POST',body});
      if(!response.ok){let message='Could not clean the background. Please try again.';try{const data=await response.json();if(typeof data.detail==='string')message=data.detail;}catch{}throw new Error(message);}
      const bitmap=await createImageBitmap(await response.blob());
      try {remember();canvas.current.getContext('2d').drawImage(bitmap,0,0);}
      finally {bitmap.close();}
      setPaper('#faf9f6');setNotice('Cleanup preview applied. Use Undo to compare or restore your previous image. Save when you are happy with it.');
    } catch(e){setError(e.message);} finally {setBusy(false);setCleaning(false);}
  }
  async function save() {
    setBusy(true); setError('');
    try {
      const blob = await new Promise(resolve => canvas.current.toBlob(resolve, 'image/png'));
      if (!blob || blob.size > 15 * 1024 * 1024) throw new Error('The edited image exceeds 15 MB. Please use a smaller source image.');
      const body = new FormData(); body.append('file', blob, `${project.name} · edited.png`);
      let result = await api('/api/projects', {method: 'POST', body});
      if (project.config) result = await api(`/api/projects/${result.id}/steps`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(project.config)});
      onSaved(result);
    } catch (e) {setError(e.message);} finally {setBusy(false);}
  }
  return <div className="modal-backdrop image-editor-backdrop"><section ref={dialog} tabIndex={-1} className="step-editor image-editor" role="dialog" aria-modal="true" aria-labelledby="image-editor-title" onKeyDown={e => {
    if (e.key === 'Escape') {e.stopPropagation(); if (!busy) onClose();}
    if (e.key === 'Tab') {
      const items = dialog.current.querySelectorAll('button:not(:disabled),input:not(:disabled)');
      const first = items[0], last = items[items.length - 1];
      if (e.shiftKey && (document.activeElement === first || document.activeElement === dialog.current)) {e.preventDefault();last?.focus();}
      else if (!e.shiftKey && document.activeElement === last) {e.preventDefault();first?.focus();}
    }
  }}>
    <header><div><div className="eyebrow">MAKE IT YOURS</div><h2 id="image-editor-title">Edit your image</h2></div><button className="icon-button" aria-label="Close image editor" disabled={busy} onClick={onClose}><X/></button></header>
    <p>Erase numbers, borders, or unwanted marks, or draw with the brush. The eraser paints with your chosen paper color.</p>
    <div className="image-tools">
      <button className="button secondary" aria-pressed={tool==='eraser'} onClick={()=>setTool('eraser')} disabled={busy}><Eraser size={18}/>Eraser</button>
      <button className="button secondary" aria-pressed={tool==='brush'} onClick={()=>setTool('brush')} disabled={busy}><Pencil size={18}/>Brush</button>
      <label>Size · {size}px<input aria-label="Brush size" type="range" min="2" max="180" value={size} onChange={e=>setSize(Number(e.target.value))} disabled={busy}/></label>
      <label>{tool==='eraser'?'Paper color':'Brush color'}<input aria-label={tool==='eraser'?'Paper color':'Brush color'} type="color" value={tool==='eraser'?paper:color} onChange={e=>(tool==='eraser'?setPaper:setColor)(e.target.value)} disabled={busy}/></label>
      <button className="button secondary" aria-label="Undo edit" disabled={busy||!history.current.length} onClick={()=>undo()}><Undo2 size={18}/></button>
      <button className="button secondary" aria-label="Redo edit" disabled={busy||!future.current.length} onClick={()=>undo(true)}><Redo2 size={18}/></button>
      <button className="button secondary" disabled={busy||!ready||revision===0} onClick={()=>{remember();canvas.current.getContext('2d').putImageData(original.current,0,0);}}>Reset image</button>
      <label>Zoom · {zoom}%<input aria-label="Image zoom" type="range" min="100" max="300" step="25" value={zoom} disabled={busy} onChange={e=>setZoom(Number(e.target.value))}/></label>
    </div>
    <div className="image-tools cleanup-tools"><div><strong>Clean background</strong><p>Reduce paper grain and shadows so the video spends less time drawing background texture. Stronger cleanup can remove faint pencil shading.</p></div><label>Cleanup strength · {cleanup}%<input aria-label="Cleanup strength" type="range" min="0" max="100" value={cleanup} disabled={busy} onChange={e=>setCleanup(Number(e.target.value))}/></label><button className="button secondary" disabled={busy||!ready} onClick={enhance}>{cleaning&&<LoaderCircle className="spin" size={16}/>} {cleaning?'Cleaning background…':'Clean background'}</button></div>
    {notice&&<p role="status">{notice}</p>}
    {error&&<p className="failure-text" role="alert">{error}</p>}
    {!ready&&!error&&<p>Loading image…</p>}
    <div className="image-edit-viewport"><canvas ref={canvas} aria-label="Image editing canvas" style={{width:`${zoom}%`}} onPointerDown={start} onPointerMove={move} onPointerUp={()=>stroke.current=null} onPointerCancel={()=>stroke.current=null}/></div>
    <footer><small>Save creates an edited copy. Your original stays in My projects.</small><button className="button primary" disabled={busy||!ready} onClick={save}>{busy&&<LoaderCircle className="spin" size={17}/>} {cleaning?'Cleaning background…':busy?'Preparing edited image…':'Save edited image'}</button></footer>
  </section></div>;
}
