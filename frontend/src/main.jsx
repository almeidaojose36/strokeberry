import React, {useEffect, useRef, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {Eraser, ArrowDownToLine, ArrowRight, Check, CircleHelp, Clapperboard, Clock3, Expand, Film, FolderOpen, ImagePlus, Leaf, LoaderCircle, Menu, Pause, Pencil, Play, Plus, RotateCcw, Sparkles, Upload, X} from 'lucide-react';
import './style.css';
import {drawTimeline} from './drawing.js';
import StepEditor from './StepEditor.jsx';
import ImageEditor from './ImageEditor.jsx';
import StepCanvas, {stageAt} from './StepCanvas.jsx';
import {BRAND, BrandMark} from './brand.jsx';

async function api(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    let message = 'Something went wrong. Please try again.';
    try { const body = await response.json(); message = typeof body.detail === 'string' ? body.detail : 'Please check your settings and try again.'; } catch {}
    throw new Error(message);
  }
  return response.json();
}
function readSaved(key, fallback){try{return JSON.parse(localStorage.getItem(key))??fallback}catch{return fallback}}
function saveLocal(key,value){try{localStorage.setItem(key,JSON.stringify(value))}catch{}}
const defaults = {style:'pencil',duration:15,ratio:'16:9',resolution:'720p',color:true,pen:true};
const format = value => `${Math.floor(value / 60)}:${Math.floor(value % 60).toString().padStart(2,'0')}`;
function IconButton({label, children, ...props}) {return <button className="icon-button" aria-label={label} title={label} {...props}>{children}</button>}
function Toggle({value,onChange,label,description}) {return <button className="toggle-row" role="switch" aria-checked={value} onClick={()=>onChange(!value)}><span><strong>{label}</strong><small>{description}</small></span><span className={`switch ${value?'on':''}`}><i/></span></button>}

function DrawingCanvas({project,settings,time,original,onReady}) {
 const canvas = useRef(null), assets = useRef(null);
 const [version,setVersion] = useState(0);
 useEffect(()=>{
   let alive = true; assets.current=null;
   if(!project) return;
   const load = src => new Promise((resolve,reject)=>{const img=new Image();img.onload=()=>resolve(img);img.onerror=reject;img.src=src;});
   Promise.all([load(project.source),load(project.reveal)]).then(([source,reveal])=>{
     if(!alive) return;
     const scratch=document.createElement('canvas');scratch.width=project.width;scratch.height=project.height;
     const ctx=scratch.getContext('2d',{willReadFrequently:true});ctx.drawImage(reveal,0,0);
     const ranks=ctx.getImageData(0,0,scratch.width,scratch.height).data;
     ctx.clearRect(0,0,scratch.width,scratch.height);ctx.drawImage(source,0,0);
     const pixels=ctx.getImageData(0,0,scratch.width,scratch.height);
     assets.current={source,ranks,pixels,scratch,ctx};setVersion(v=>v+1);onReady?.();
   }).catch(()=>{if(alive)onReady?.('Could not load the project image. Please reload the project.');});
   return ()=>{alive=false};
 },[project]);
 useEffect(()=>{
   const el=canvas.current, data=assets.current;if(!el||!data||!project)return;
   const [width,height]=settings.ratio==='9:16'?[540,960]:settings.ratio==='1:1'?[720,720]:[960,540];
   el.width=width;el.height=height;const ctx=el.getContext('2d');ctx.fillStyle='#faf9f6';ctx.fillRect(0,0,width,height);
   const scale=Math.min(width*.9/project.width,height*.9/project.height),ox=(width-project.width*scale)/2,oy=(height-project.height*scale)/2;
   ctx.save();ctx.translate(ox,oy);ctx.scale(scale,scale);
   if(original){ctx.drawImage(data.source,0,0);ctx.restore();return;}
   const progress=time/settings.duration,lineEnd=settings.color?.65:.92;
   const unit = Math.min(width,height)/540/scale;
   const strokeKey = `${width}:${height}:${settings.style}`;
   if(data.strokeKey!==strokeKey){
     const buffer=document.createElement('canvas');buffer.width=width;buffer.height=height;
     const bufferCtx=buffer.getContext('2d');bufferCtx.setTransform(scale,0,0,scale,ox,oy);
     data.strokeCache={canvas:buffer,ctx:bufferCtx,index:0,progress:0};data.strokeKey=strokeKey;
   }
   const {tip,lift}=drawTimeline(ctx,project.timeline||[],Math.min(1,progress/lineEnd),settings.style,unit,data.strokeCache);
   if(settings.color&&progress>lineEnd){
     const amount=Math.min(1,(progress-lineEnd)/.27);
     const pixels=data.pixels.data;
     for(let i=0;i<pixels.length;i+=4)pixels[i+3]=Math.max(0,Math.min(255,(amount*270-data.ranks[i])/20*255));
     data.ctx.putImageData(data.pixels,0,0);ctx.drawImage(data.scratch,0,0);
   }
   if(settings.pen&&tip&&progress<lineEnd){
     let [x,y]=tip;
     if(lift>0){ctx.fillStyle='#dddfd6';ctx.beginPath();ctx.ellipse(x+8*unit,y+3*unit,7*unit,2*unit,0,0,Math.PI*2);ctx.fill();}
     x+=lift*3*unit;y-=lift*10*unit;
     ctx.fillStyle='#cfa257';ctx.beginPath();ctx.moveTo(x,y);ctx.lineTo(x+17*unit,y-46*unit);ctx.lineTo(x+28*unit,y-40*unit);ctx.lineTo(x+5*unit,y+2*unit);ctx.closePath();ctx.fill();
     ctx.fillStyle=settings.style==='pencil'?'#3c413b':'#1d2c24';ctx.beginPath();ctx.arc(x,y,2*unit,0,Math.PI*2);ctx.fill();
   }
   ctx.restore();
 },[project,settings,time,original,version]);
 return <canvas ref={canvas} aria-label="Animated drawing preview" className={`drawing-canvas ratio-${settings.ratio.replace(':','-')}`}/>;
}

function App(){
 const [imageEditor,setImageEditor]=useState(false);
 const [project,setProject]=useState(null),[projects,setProjects]=useState([]),[settings,setSettings]=useState(()=>({...defaults,...readSaved('speedpainter-settings',{})}));
 const [view,setView]=useState('studio'),[tab,setTab]=useState('drawing'),[time,setTime]=useState(()=>readSaved('speedpainter-settings',defaults).duration||15),[playing,setPlaying]=useState(false),[original,setOriginal]=useState(false);
 const [busy,setBusy]=useState(true),[error,setError]=useState(''),[job,setJob]=useState(null),[jobs,setJobs]=useState([]),[modal,setModal]=useState(false),[drag,setDrag]=useState(false),[menu,setMenu]=useState(false),[help,setHelp]=useState(false),[submitting,setSubmitting]=useState(false),[stepEditor,setStepEditor]=useState(false);
 const fileInput=useRef(null),preview=useRef(null),requestRef=useRef(0);
 const update=(key,value)=>{setSettings(s=>({...s,[key]:value}));if(key==='duration')setTime(t=>Math.min(t,value));};
 const refresh=()=>Promise.all([api('/api/projects').then(values=>{setProjects(values);return values}),api('/api/jobs').then(values=>{setJobs(values);return values})]);
 useEffect(()=>{const saved=readSaved('speedpainter-project',null);const initial=saved?api(`/api/projects/${saved}`).catch(()=>api('/api/sample',{method:'POST'})):api('/api/sample',{method:'POST'});initial.then(p=>{setProject(p);return refresh()}).then(([,allJobs])=>{const active=allJobs?.find(j=>['queued','rendering'].includes(j.status));if(active)setJob(active)}).catch(e=>setError(e.message+' Is the backend running?')).finally(()=>setBusy(false));},[]);
 useEffect(()=>{saveLocal('speedpainter-settings',settings)},[settings]);
 useEffect(()=>{if(project)saveLocal('speedpainter-project',project.id)},[project]);
 useEffect(()=>{if(!playing)return;let frame,last=performance.now();const tick=now=>{const delta=(now-last)/1000;last=now;setTime(t=>{if(t+delta>=settings.duration){setPlaying(false);return settings.duration;}return t+delta;});frame=requestAnimationFrame(tick);};frame=requestAnimationFrame(tick);return()=>cancelAnimationFrame(frame);},[playing,settings.duration]);
 useEffect(()=>{
   if(!job||!['queued','rendering'].includes(job.status))return;
   let alive=true;const timer=setInterval(()=>{api(`/api/jobs/${job.id}`).then(value=>{if(!alive)return;setJob(value);if(value.status==='completed'||value.status==='failed')refresh().catch(()=>{});}).catch(e=>{if(alive)setError(e.message);});},1000);
   return()=>{alive=false;clearInterval(timer)};
 },[job?.id,job?.status]);
 useEffect(()=>{if(!modal&&!help)return;const previous=document.activeElement;const dialog=document.querySelector('[role=dialog]');dialog?.querySelector('button')?.focus();const close=e=>{if(e.key==='Escape'){setModal(false);setHelp(false)}if(e.key==='Tab'){const items=dialog?.querySelectorAll('button,a[href],video[controls]');if(!items?.length)return;const first=items[0],last=items[items.length-1];if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus()}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus()}}};window.addEventListener('keydown',close);return()=>{window.removeEventListener('keydown',close);previous?.focus()}},[modal,help]);
 async function upload(file){
   if(!file)return;if(!['image/jpeg','image/png','image/webp'].includes(file.type)){setError('Choose a PNG, JPG, or WebP image.');return;}
   if(file.size>15*1024*1024){setError('Please choose an image smaller than 15 MB.');return;}
   const token=++requestRef.current;setBusy(true);setPlaying(false);setError('');const body=new FormData();body.append('file',file);
   try{const p=await api('/api/projects',{method:'POST',body});if(token===requestRef.current){setProject(p);setTime(settings.duration);setJob(null);setView('studio');}await refresh();const layout=await api(`/api/projects/${p.id}/step-layout`).catch(()=>null);if(token===requestRef.current&&layout?.detected)setStepEditor(true);}catch(e){setError(e.message)}finally{if(token===requestRef.current)setBusy(false);fileInput.current.value='';}
 }
 async function openProject(id){setBusy(true);setError('');setPlaying(false);try{const loaded=await api(`/api/projects/${id}`);setProject(loaded);setView('studio');if(loaded.mode==='steps')setSettings(current=>({...current,duration:loaded.duration}));setTime(loaded.mode==='steps'?loaded.duration:settings.duration);setJob(null);}catch(e){setError(e.message)}finally{setBusy(false)}}
 async function exportVideo(){if(!project||submitting)return;setError('');setJob(null);setSubmitting(true);setModal(true);try{setJob(await api(`/api/projects/${project.id}/jobs`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(settings)}));}catch(e){setError(e.message);setModal(false)}finally{setSubmitting(false)}}
 function play(){setOriginal(false);if(time>=settings.duration)setTime(0);setPlaying(p=>!p)}
 const activeJob=job&&['queued','rendering'].includes(job.status);
 return <div className="app-shell">
  <input ref={fileInput} type="file" accept="image/png,image/jpeg,image/webp" className="hidden" onChange={e=>upload(e.target.files[0])}/>
  <aside className={`sidebar ${menu?'mobile-open':''}`}>
   <a className="brand" href="#" onClick={e=>{e.preventDefault();setView('studio');setMenu(false)}}><BrandMark/>{BRAND.name}</a>
   <div className="workspace-label">Studio</div>
   <nav>{[['studio',Sparkles,'Create a video'],['projects',FolderOpen,'Projects'],['exports',Film,'Exports']].map(([id,Icon,label])=><button key={id} className={`nav-item ${view===id?'active':''}`} onClick={()=>{setView(id);setMenu(false);if(id!=='studio')refresh().catch(e=>setError(e.message))}}><Icon size={18}/>{label}{id==='projects'&&<span className="nav-count">{projects.length}</span>}</button>)}</nav>
   <div className="sidebar-note"><div className="note-art"><Leaf size={18}/><span>New here?</span></div><p>Three steps from a still image to a finished drawing video.</p><button onClick={()=>{setHelp(true);setMenu(false)}}>See how it works <ArrowUpRight/></button></div>
   <div className="sidebar-bottom"><div className="user"><span className="avatar"><BrandMark size={16} compact/></span><div><strong>Personal studio</strong><small><i/>Private · on this device</small></div></div></div>
  </aside>
  {menu&&<div className="sidebar-scrim" onClick={()=>setMenu(false)}/>}
  <main>
   <header className="topbar"><div className="breadcrumb"><IconButton label="Toggle navigation" onClick={()=>setMenu(!menu)}><Menu size={20}/></IconButton><span>Workspace</span><span className="slash">/</span><strong>{view==='studio'?'Create a video':view==='projects'?'Projects':'Exports'}</strong></div><div className="topbar-right"><span className="private-indicator"><i/>Files stay on your device</span><button className="button ghost" onClick={()=>setHelp(true)}><CircleHelp size={16}/>Guide</button></div></header>
   {error&&<div className="error-banner" role="alert">{error}<button aria-label="Dismiss error" onClick={()=>setError('')}><X size={17}/></button></div>}
   {view==='studio'?<div className="studio-page">
    <div className="page-heading"><div className="eyebrow">New video</div><div className="heading-row"><div><h1>Turn any image into a <em>hand‑drawn</em> video</h1><p>Upload artwork, pick a style, and export a speed‑drawing MP4 ready for Reels, TikTok, and Shorts.</p></div><button className="button primary new-project" onClick={()=>fileInput.current.click()} disabled={busy}><Plus size={17}/>New project</button></div></div>
    <div className="editor-grid">
     <section className="preview-panel">
      <div className="panel-heading"><div><span className="mini-icon"><Clapperboard size={17}/></span><strong>Preview</strong><span className="subtle-chip">{settings.ratio}</span></div><span className="saved"><Check size={13}/>{busy?'Preparing…':'Saved'}</span></div>
      <div className={`preview-stage ${drag?'dragging':''}`} ref={preview} onDragOver={e=>{e.preventDefault();setDrag(true)}} onDragLeave={()=>setDrag(false)} onDrop={e=>{e.preventDefault();setDrag(false);upload(e.dataTransfer.files[0])}}>
       <div className="canvas-topline"><span className="preview-badge"><i/>{original?'ORIGINAL IMAGE':'LIVE PREVIEW'}</span><button className={`original-button ${original?'selected':''}`} onClick={()=>{setOriginal(v=>!v);setPlaying(false)}} disabled={!project}> {original?'Show drawing':project?.mode==='steps'?'View final':'View original'}</button></div>
       {project&&(project.mode==='steps'?<StepCanvas project={project} settings={settings} time={time} original={original} onReady={message=>{if(message)setError(message)}}/>:<DrawingCanvas project={project} settings={settings} time={time} original={original} onReady={message=>{if(message)setError(message)}}/>)}
       {(busy||!project)&&<div className="canvas-loading">{busy?<><LoaderCircle className="spin" size={26}/><span>Preparing your canvas…</span></>:<><ImagePlus size={32}/><strong>Drop an image to begin</strong><small>PNG, JPG or WebP · up to 15 MB</small><button className="button primary" onClick={()=>fileInput.current.click()}>Choose an image</button></>}</div>}
       {drag&&<div className="drop-overlay"><Upload size={32}/>Drop to start a new project</div>}
       <div className="canvas-caption"><span>{project?.mode==='steps'?`Step ${stageAt(project.stages,time/settings.duration).index+1} · ${project.stages[stageAt(project.stages,time/settings.duration).index].label}`:project?.name||''}</span><IconButton label="Expand preview" onClick={()=>{const result=preview.current.requestFullscreen?.();result?.catch(()=>setError('Fullscreen is unavailable in this browser.'))}}><Expand size={16}/></IconButton></div>
      </div>
      <div className="playback"><IconButton label={playing?'Pause preview':'Play preview'} onClick={play} disabled={!project||busy}>{playing?<Pause size={17} fill="currentColor"/>:<Play size={17} fill="currentColor"/>}</IconButton><span className="time">{format(time)}</span><input aria-label="Preview timeline" type="range" min="0" max={settings.duration} step="0.01" value={time} onChange={e=>{setTime(Number(e.target.value));setPlaying(false);setOriginal(false)}} style={{'--progress':`${time/settings.duration*100}%`}}/><span className="time end">{format(settings.duration)}</span><span className="playback-divider"/><IconButton label="Restart preview" onClick={()=>{setTime(0);setOriginal(false);setPlaying(true)}} disabled={!project||busy}><RotateCcw size={16}/></IconButton></div>
      {project?.mode==='steps'&&<div className="sequence-strip">{project.stages.map((stage,i)=><button key={i} className={stageAt(project.stages,time/settings.duration).index===i?'active':''} onClick={()=>{setTime((stage.start+(stage.end-stage.start)*.96)*settings.duration);setPlaying(false);setOriginal(false)}} aria-label={`Preview completed step ${i+1}: ${stage.label}`}><img src={stage.source} alt=""/><span><strong>{i+1}. {stage.label}</strong><small>{Math.round((stage.end-stage.start)*settings.duration)} seconds{stage.alignment.confidence<.55?' · Check alignment':''}</small></span></button>)}</div>}
      <div className="source-row"><div className="source-thumbnail">{project?<img src={project.source} alt="Source image"/>:<ImagePlus size={20}/>}</div><div><strong>{project?`${project.name}.png`:'Add your image'}</strong><small>{project?`${project.width} × ${project.height} px · ${project.strokes.toLocaleString()} drawing strokes`:'PNG, JPG or WebP · Up to 15 MB'}</small></div><div className="source-actions"><button onClick={()=>{setPlaying(false);setImageEditor(true)}} disabled={!project||busy}><Eraser size={14}/>Edit image</button><button onClick={()=>fileInput.current.click()} disabled={busy}><Upload size={14}/>Replace</button></div></div>
      <div className="steps-entry"><div><strong>{project?.mode==='steps'?'Your step-by-step sequence':'Image contains drawing steps?'}</strong><small>{project?.mode==='steps'?'Review crops, order, timing, and alignment.':'Turn a tutorial grid into one evolving drawing.'}</small></div><button className="button secondary" disabled={!project||busy} onClick={()=>setStepEditor(true)}>{project?.mode==='steps'?'Edit steps':'Set up steps'}<ArrowRight size={14}/></button></div>
     </section>
     <section className="settings-panel"><div className="panel-heading"><div><span className="mini-icon"><Sparkles size={16}/></span><strong>Settings</strong></div></div>
      <div className="settings-tabs"><button className={tab==='drawing'?'active':''} onClick={()=>setTab('drawing')}>Drawing style</button><button className={tab==='video'?'active':''} onClick={()=>setTab('video')}>Video settings</button></div>
      <div className="settings-content">{tab==='drawing'?<>
       {project?.mode==='steps'?<div className="sequence-summary"><Sparkles size={22}/><strong>Follow the artist’s steps</strong><p>Preserves the marks, shading, and colors in each panel. Adjust the total duration below; stage timings scale proportionally.</p><button className="button secondary" onClick={()=>setStepEditor(true)}>Edit drawing steps</button></div>:<>
       <div className="field-label">Style</div>
       <div className="style-options">{[['pencil','Pencil','Soft, varied strokes'],['ink','Ink','Bold, confident lines']].map(([id,title,subtitle])=><button key={id} className={`style-card ${settings.style===id?'selected':''}`} onClick={()=>update('style',id)}><div className={`style-art ${id}`}><Botanical/><span className="radio-check">{settings.style===id&&<Check size={10}/>}</span></div><strong>{title}</strong><small>{subtitle}</small></button>)}</div>
       </>}
       <div className="settings-divider"/>
       <Toggle value={settings.pen} onChange={v=>update('pen',v)} label="Show drawing pencil" description="Follows strokes and lifts between them"/>
       {project?.mode!=='steps'&&<Toggle value={settings.color} onChange={v=>update('color',v)} label="Bring in the color" description="Reveal original colors after the sketch"/>}
       <div className="settings-divider"/>
       <div className="field-label">Duration <span>{format(settings.duration)}</span></div><input className="duration-slider" aria-label="Video duration" type="range" min="5" max="300" step="5" value={settings.duration} onChange={e=>update('duration',Number(e.target.value))} style={{'--progress':`${(settings.duration-5)/295*100}%`}}/><div className="range-labels"><span>5s</span><span>5 min</span></div>
      </>:<>
       <div className="field-label">Format</div><div className="ratio-options">{['16:9','9:16','1:1'].map(r=><button className={settings.ratio===r?'selected':''} onClick={()=>update('ratio',r)} key={r}><span style={{aspectRatio:r.replace(':','/')}}/>{r}<small>{r==='16:9'?'Landscape':r==='9:16'?'Portrait':'Square'}</small></button>)}</div>
       <div className="settings-divider"/><label className="field-label" htmlFor="resolution">Quality</label><select id="resolution" value={settings.resolution} onChange={e=>update('resolution',e.target.value)}><option value="720p">HD · 720p</option><option value="1080p">Full HD · 1080p</option></select><p className="setting-hint">MP4 video at 24 frames per second. Higher resolutions take a little longer to render.</p><div className="settings-divider"/><div className="format-note"><Film size={20}/><div><strong>No cropping</strong><p>Your image is fitted inside the frame, so nothing gets cut off.</p></div></div>
      </>}</div>
      <div className="export-section"><div className="export-summary"><span><Film size={13}/>{settings.resolution} MP4</span><span>{settings.ratio}</span><span><Clock3 size={13}/>{format(settings.duration)}</span></div><button className="button primary export-button" disabled={!project||busy||activeJob||submitting} onClick={exportVideo}>{activeJob?<LoaderCircle size={17} className="spin"/>:<Sparkles size={17}/>} {activeJob?`Rendering · ${job.progress}%`:'Export video'}<ArrowRight size={17}/></button>{activeJob?<button className="export-footer link" onClick={()=>setModal(true)}>View export progress</button>:<p className="export-footer">Rendered on your device · no watermark</p>}</div>
     </section>
    </div>
    <section className="bottom-strip"><div className="tip-icon"><Leaf size={23}/></div><div><strong>Best results come from clean line art</strong><p>Illustrations, logos, and drawing tutorials with clear outlines on a plain background produce the crispest strokes.</p></div><button onClick={()=>{setHelp(true)}}>Tips for great videos <ArrowRight size={15}/></button></section>
    <footer className="page-footer"><span>{BRAND.name}</span><span>{BRAND.tagline}</span></footer>
   </div>:<div className="library-page"><div className="eyebrow">{view==='projects'?'Library':'Exports'}</div><div className="heading-row"><div><h1>{view==='projects'?'Projects':'Exported videos'}</h1><p>{view==='projects'?'Pick up where you left off, or start something new.':'Your finished MP4s, ready to download and post.'}</p></div><button className="button primary" onClick={()=>fileInput.current.click()}><Plus size={17}/>New project</button></div>
    {view==='projects'?<div className="project-grid">{projects.map(p=><button className="project-card" key={p.id} onClick={()=>openProject(p.id)}><img src={p.source} alt={p.name}/><div><strong>{p.name}</strong><span>{p.strokes} strokes <ArrowRight size={15}/></span></div></button>)}</div>:<div className="export-list">{jobs.length===0?<div className="empty-state"><Film size={40}/><h2>No videos yet</h2><p>Export a video from the studio and it will appear here.</p><button className="button secondary" onClick={()=>setView('studio')}>Go to studio <ArrowRight size={15}/></button></div>:jobs.map(j=><div className="export-card" key={j.id}><Film size={23}/><div><strong>{projects.find(p=>p.id===j.project_id)?.name||'Speedpaint video'}</strong><small>{j.settings.resolution} · {j.settings.ratio} · {format(j.settings.duration)} · {new Date(j.created).toLocaleDateString()}</small>{j.error&&<small className="failure-text">{j.error}</small>}</div><span className={`status ${j.status}`}>{({completed:'Ready',failed:'Failed',queued:'Queued',rendering:'Rendering'})[j.status]||j.status}</span>{j.status==='completed'?<a className="button secondary" href={j.url} download><ArrowDownToLine size={15}/>Download</a>:<button className="button secondary" onClick={()=>{setJob(j);setModal(true)}}>Details</button>}</div>)}</div>}
   </div>}
  </main>
  {imageEditor&&project&&<ImageEditor project={project} api={api} onClose={()=>setImageEditor(false)} onSaved={result=>{setProject(result);setTime(0);setPlaying(false);setOriginal(false);setJob(null);setImageEditor(false);refresh().catch(e=>setError(e.message));}}/>}
  {stepEditor&&project&&<StepEditor project={project} api={api} onClose={()=>setStepEditor(false)} onCreated={result=>{setProject(result);setSettings(current=>({...current,duration:result.duration}));setTime(0);setPlaying(false);setOriginal(false);setJob(null);setStepEditor(false);refresh().catch(e=>setError(e.message))}}/>}
  {(modal||help)&&<div className="modal-backdrop" onClick={()=>{setModal(false);setHelp(false)}}><section className="modal" role="dialog" aria-modal="true" aria-labelledby="dialog-title" onClick={e=>e.stopPropagation()}><IconButton label="Close dialog" onClick={()=>{setModal(false);setHelp(false)}}><X size={20}/></IconButton>{help?<><span className="dialog-icon"><Pencil size={26}/></span><div className="eyebrow">Guide</div><h2 id="dialog-title">How it works</h2><ol className="guide"><li><strong>Start with an image</strong><p>Upload a PNG, JPG, or WebP. Clear outlines and simple backgrounds make the strongest drawings.</p></li><li><strong>Choose a style</strong><p>Choose pencil or ink, add a color reveal, and set the pace. Play or scrub through the canvas to preview.</p></li><li><strong>Export and post</strong><p>Export a 720p or 1080p MP4 in landscape, portrait, or square. Finished videos are saved under Exports.</p></li></ol><div className="local-note">Everything is processed on your device. Your images are never uploaded to a third‑party AI service.</div></>:<><span className="dialog-icon">{job?.status==='completed'?<Check size={27}/>:job?.status==='failed'?<X size={27}/>:<Sparkles size={27}/>}</span><div className="eyebrow">Export</div><h2 id="dialog-title">{job?.status==='completed'?'Your video is ready':job?.status==='failed'?'Export failed':'Rendering your video'}</h2>{job?.status==='completed'?<><video src={job.url} controls playsInline className="result-video"/><a className="button primary download-button" href={job.url} download><ArrowDownToLine size={18}/>Download MP4</a></>:job?.status==='failed'?<><p className="failure-text">{job.error}</p><button className="button primary" onClick={()=>{setModal(false);setView('studio')}}>Back to studio</button></>:<><p className="render-stage" aria-live="polite">{job?.stage||'Adding your video to the queue…'}</p><div className="progress-track"><div style={{width:`${job?.progress||0}%`}}/></div><div className="render-progress"><span>{job?.progress||0}% complete</span><span>{job?.settings?.resolution||settings.resolution} · MP4</span></div><p className="modal-note">You can close this and keep working — we’ll keep rendering in the background.</p></>}</>}</section></div>}
 </div>
}
function ArrowUpRight(){return <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7"><path d="M6 18 18 6M6 6h12v12"/></svg>}
function Botanical(){return <svg viewBox="0 0 120 70" fill="none" aria-hidden="true"><path d="M52 70C57 49 67 28 73 4M62 42 42 20M67 28 91 16M57 55 35 43"/><path d="M67 26C47 25 46 13 44 6c15 1 25 7 23 20ZM71 16C78 3 91 6 97 3c-3 14-12 19-26 13ZM61 43C74 27 91 32 96 30c-5 15-22 21-35 13ZM54 58C37 57 32 49 29 37c13 3 25 5 25 21ZM62 40C44 39 37 31 36 23c17 0 23 6 26 17Z"/><path d="m67 26-15-12m19 2L89 8M61 43l26-9m-33 24L35 43M62 40 43 28"/></svg>}
createRoot(document.getElementById('root')).render(<App/>);
