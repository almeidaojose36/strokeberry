import {SuggestionBar, SuggestionDialog} from './LineSuggestion.jsx';
import React, {useEffect, useRef, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {Eraser, ArrowDownToLine, ArrowRight, Check, CircleHelp, Clapperboard, Clock3, Crown, Expand, Film, FolderOpen, Home, ImagePlus, LayoutGrid, Leaf, LoaderCircle, LogOut, Menu, Minimize2, Package, Palette, Pause, Pencil, Play, Plus, RotateCcw, Sparkles, Upload, X} from 'lucide-react';
import './style.css';
import {drawTimeline, hexToRgb} from './drawing.js';
import {takeHandoff} from './handoff.js';
import {BOARDS, CHALK, HAND_TONES, PAPER, boardSource, drawHand, frameSize, handArt, paintPoint} from './frame.js';
import StepEditor from './StepEditor.jsx';
import ImageEditor from './ImageEditor.jsx';
import StepCanvas, {stageAt} from './StepCanvas.jsx';
import {BRAND, BrandMark} from './brand.jsx';
import Gallery from './Gallery.jsx';
import Guide from './Guide.jsx';
import ProjectsView from './ProjectsView.jsx';
import ExportsView from './ExportsView.jsx';
import ExportResult from './ExportResult.jsx';
import BrandKit from './BrandKit.jsx';
import Presets from './Presets.jsx';
import Ideas from './Ideas.jsx';
import SignIn from './SignIn.jsx';
import {authEnabled, authHeaders, completeEmailLink, signOut, startGuest, watchUser} from './auth.js';

async function api(url, options = {}) {
  const response = await fetch(url, {...options, headers: {...(options.headers || {}), ...await authHeaders()}});
  if (!response.ok) {
    let message = 'Something went wrong. Please try again.';
    try { const body = await response.json(); message = typeof body.detail === 'string' ? body.detail : 'Please check your settings and try again.'; } catch {}
    throw Object.assign(new Error(message), {status: response.status});
  }
  return response.json();
}
function readSaved(key, fallback){try{return JSON.parse(localStorage.getItem(key))??fallback}catch{return fallback}}
function saveLocal(key,value){try{localStorage.setItem(key,JSON.stringify(value))}catch{}}
// First run: Ink (bolder, easier to read on a phone). Anyone who has already chosen a style keeps their own saved choice.
const defaults = {style:'ink',duration:15,ratio:'16:9',resolution:'1080p',color:true,pen:true,hand:'pencil',canvas:'paper'};
const RES_LABEL = {'720p':'720p','1080p':'1080p','4k':'4K'};
const RATIOS = [['16:9','Landscape'],['9:16','Portrait'],['1:1','Square'],['4:5','Feed post'],['auto','Fit image']];
const HANDS = [['none','None'],['pencil','Pencil'],['light','Light'],['medium','Medium'],['dark','Dark']];
const CANVASES = [['paper','Paper','#faf9f6'],['blackboard','Blackboard','#282c2a'],['greenboard','Greenboard','#264c3c']];
// The steps shown while a video renders, matched to the stage the server reports.
const RENDER_STEPS = [['Preparing the canvas',/prepar|queue/i],['Drawing the outlines',/draw|step|sketch|outline/i],['Painting the colour',/colou?r|reveal|paint/i],['Adding the end card',/end card/i],['Finishing your video',/finish|ready/i]];
const shortDate = iso => new Date(iso).toLocaleDateString(undefined,{day:'numeric',month:'short'});
const format = value => `${Math.floor(value / 60)}:${Math.floor(value % 60).toString().padStart(2,'0')}`;
function IconButton({label, children, ...props}) {return <button className="icon-button" aria-label={label} title={label} {...props}>{children}</button>}
function Toggle({value,onChange,label,description}) {return <button className="toggle-row" role="switch" aria-checked={value} onClick={()=>onChange(!value)}><span><strong>{label}</strong><small>{description}</small></span><span className={`switch ${value?'on':''}`}><i/></span></button>}

function DrawingCanvas({project,settings,time,original,onReady,inkColor}) {
 const canvas = useRef(null), assets = useRef(null), hands = useRef({});
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
     assets.current={source,ranks,pixels,original:new Uint8ClampedArray(pixels.data),scratch,ctx,boards:{}};setVersion(v=>v+1);onReady?.();
   }).catch(()=>{if(alive)onReady?.('Could not load the project image. Please reload the project.');});
   return ()=>{alive=false};
 },[project]);
 // The realistic hand artwork for the chosen skin tone (pencil for lines, brush for colour).
 useEffect(()=>{
   let alive=true;const tone=settings.hand;
   if(!HAND_TONES.includes(tone)||hands.current.tone===tone)return;
   Promise.all([handArt(tone,'pencil'),handArt(tone,'brush')]).then(([pencil,brush])=>{if(alive){hands.current={tone,pencil,brush};setVersion(v=>v+1)}});
   return ()=>{alive=false};
 },[settings.hand]);
 useEffect(()=>{
   const el=canvas.current, data=assets.current;if(!el||!data||!project)return;
   const [width,height]=frameSize(settings.ratio,project);
   const board=BOARDS[settings.canvas],ground=board||PAPER;
   el.width=width;el.height=height;const ctx=el.getContext('2d');ctx.fillStyle=`rgb(${ground.join(',')})`;ctx.fillRect(0,0,width,height);
   const scale=Math.min(width*.9/project.width,height*.9/project.height),ox=(width-project.width*scale)/2,oy=(height-project.height*scale)/2;
   ctx.save();ctx.translate(ox,oy);ctx.scale(scale,scale);
   if(original){ctx.drawImage(data.source,0,0);ctx.restore();return;}
   const progress=time/settings.duration,hold=Math.min(.08,2/Math.max(1,settings.duration)),reveal=settings.color?.27:0,lineEnd=1-hold-reveal;
   const unit = Math.min(width,height)/540/scale;
   const weight=project.line_width?Math.min(4,Math.max(1,.85*project.line_width/(unit*1.45))):1,markUnit=unit*weight;
   const tint=hexToRgb(inkColor)||(board?CHALK:null),strokeKey = `${width}:${height}:${settings.style}:${inkColor||''}:${weight}:${settings.canvas}`;
   if(data.strokeKey!==strokeKey){
     const buffer=document.createElement('canvas');buffer.width=width;buffer.height=height;
     const bufferCtx=buffer.getContext('2d');bufferCtx.setTransform(scale,0,0,scale,ox,oy);
     data.strokeCache={canvas:buffer,ctx:bufferCtx,index:0,progress:0};data.strokeKey=strokeKey;
   }
   const {tip,lift}=drawTimeline(ctx,project.timeline||[],Math.min(1,progress/lineEnd),settings.style,markUnit,data.strokeCache,tint,ground);
   const painting=settings.color&&progress>lineEnd;
   if(painting){
     const amount=Math.min(1,(progress-lineEnd)/reveal);
     if(board&&!data.boards[settings.canvas])data.boards[settings.canvas]=boardSource(data.original,project.width,project.height,board);
     const adjusted=board?data.boards[settings.canvas]:null,pixels=data.pixels.data;
     if(adjusted)pixels.set(adjusted.data);else pixels.set(data.original);
     for(let i=0,p=0;i<pixels.length;i+=4,p++){const a=Math.max(0,Math.min(1,(amount*270-data.ranks[i])/20));pixels[i+3]=255*(adjusted?a*adjusted.keep[p]:a)}
     data.ctx.putImageData(data.pixels,0,0);ctx.drawImage(data.scratch,0,0);
   }
   ctx.restore();
   const toScreen=([x,y])=>[x*scale+ox,y*scale+oy],short=Math.min(width,height),realHand=HAND_TONES.includes(settings.hand)&&hands.current.tone===settings.hand;
   if(settings.pen&&realHand&&painting&&progress<lineEnd+reveal&&project.paint_path?.length){
     const spot=paintPoint(project.paint_path,(progress-lineEnd)/reveal);if(spot)drawHand(ctx,hands.current.brush,...toScreen(spot),short);
   }else if(settings.pen&&realHand&&tip&&progress<lineEnd){
     drawHand(ctx,hands.current.pencil,...toScreen(tip),short,lift);
   }else if(settings.pen&&tip&&progress<lineEnd){
     ctx.save();ctx.translate(ox,oy);ctx.scale(scale,scale);
     let [x,y]=tip;
     if(lift>0){ctx.fillStyle='#dddfd6';ctx.beginPath();ctx.ellipse(x+8*unit,y+3*unit,7*unit,2*unit,0,0,Math.PI*2);ctx.fill();}
     x+=lift*3*unit;y-=lift*10*unit;
     ctx.fillStyle='#cfa257';ctx.beginPath();ctx.moveTo(x,y);ctx.lineTo(x+17*unit,y-46*unit);ctx.lineTo(x+28*unit,y-40*unit);ctx.lineTo(x+5*unit,y+2*unit);ctx.closePath();ctx.fill();
     ctx.fillStyle=inkColor||(board?'#f0f0e8':settings.style==='pencil'?'#3c413b':'#1d2c24');ctx.beginPath();ctx.arc(x,y,2*unit,0,Math.PI*2);ctx.fill();
     ctx.restore();
   }
 },[project,settings,time,original,version,inkColor]);
 const [w,h]=frameSize(settings.ratio,project);
 return <canvas ref={canvas} aria-label="Animated drawing preview" className={`drawing-canvas ${w>h?'ratio-wide':w<h?'ratio-tall':'ratio-square'}`} style={{aspectRatio:`${w} / ${h}`}}/>;
}

function App({onSignOut}){
 const [imageEditor,setImageEditor]=useState(false);
 const [account,setAccount]=useState(null),[gallery,setGallery]=useState(false),[upgrade,setUpgrade]=useState(false),[notice,setNotice]=useState(''),[checkout,setCheckout]=useState(false);
 const local=!account||account.auth==='local',guest=account?.plan?.id==='guest',free=account?.plan?.watermark&&!guest;
 const [signIn,setSignIn]=useState(''),[interval,setInterval_]=useState('year');
 const pro=account?.plan?.id==='pro',maxDuration=account?.plan?.max_duration||300;
 const [presets,setPresets]=useState([]),[ideas,setIdeas]=useState([]),[brandKit,setBrandKit]=useState({name:'',ink_color:'',logo_corner:'bottom-right',enabled:true,logo:null}),[presetBusy,setPresetBusy]=useState(false);
 const loadAccount=()=>api('/api/me').then(value=>{setAccount(value);return value});
 const [suggest,setSuggest]=useState(false),[suggestBusy,setSuggestBusy]=useState(false),[project,setProject]=useState(null),[projects,setProjects]=useState([]),[settings,setSettings]=useState(()=>({...defaults,...readSaved('speedpainter-settings',{})}));
 const [view,setView]=useState('studio'),[tab,setTab]=useState('drawing'),[time,setTime]=useState(()=>readSaved('speedpainter-settings',defaults).duration||15),[playing,setPlaying]=useState(false),[original,setOriginal]=useState(false);
 const [busy,setBusy]=useState(true),[error,setError]=useState(''),[job,setJob]=useState(null),[jobs,setJobs]=useState([]),[modal,setModal]=useState(false),[drag,setDrag]=useState(false),[menu,setMenu]=useState(false),[help,setHelp]=useState(false),[submitting,setSubmitting]=useState(false),[stepEditor,setStepEditor]=useState(false);
 const fileInput=useRef(null),preview=useRef(null),requestRef=useRef(0);
 const [expanded,setExpanded]=useState(false);
 useEffect(()=>{if(!expanded)return;const close=e=>{if(e.key==='Escape')setExpanded(false)};window.addEventListener('keydown',close);const previous=document.body.style.overflow;document.body.style.overflow='hidden';return()=>{window.removeEventListener('keydown',close);document.body.style.overflow=previous}},[expanded]);
 const update=(key,value)=>{setSettings(s=>({...s,[key]:value}));if(key==='duration')setTime(t=>Math.min(t,value));};
 const refresh=()=>Promise.all([loadAccount().catch(()=>{}),api('/api/projects').then(values=>{setProjects(values);return values}),api('/api/jobs').then(values=>{setJobs(values);return values})]);
 useEffect(()=>{
   // Arriving from the website: "Use this style" (?example=…&style=…) or an image dropped on the homepage (?upload=1).
   const params=new URLSearchParams(location.search),example=params.get('example'),dropped=params.has('upload');
   const picked={};for(const key of ['style','ratio','hand','canvas'])if(params.get(key))picked[key]=params.get(key);
   if(params.get('hand')==='none')Object.assign(picked,{pen:false,hand:'pencil'});else if(picked.hand)picked.pen=true;
   if(example||dropped||Object.keys(picked).length){history.replaceState(null,'',location.pathname);if(Object.keys(picked).length)setSettings(s=>({...s,...picked}));}
   const saved=readSaved('speedpainter-project',null),fallback=()=>saved?api(`/api/projects/${saved}`).catch(()=>api('/api/sample',{method:'POST'})):api('/api/sample',{method:'POST'});
   const initial=example?api(`/api/library/${encodeURIComponent(example)}/use`,{method:'POST'}).catch(fallback)
     :dropped?takeHandoff().then(file=>{if(!file)return fallback();const body=new FormData();body.append('file',file);return api('/api/projects',{method:'POST',body})}).catch(e=>{setError(e.message);return fallback()})
     :fallback();
   const fresh=example||dropped;
   initial.then(p=>{setProject(p);if(example?.startsWith('tutorial-'))setStepEditor(true);if(fresh||!readSaved('speedpainter-seen-draw',false)){saveLocal('speedpainter-seen-draw',true);setTime(0);setPlaying(p.mode!=='steps')}return refresh()}).then(([,,allJobs])=>{const active=allJobs?.find(j=>['queued','rendering'].includes(j.status));if(active)setJob(active)}).catch(e=>setError(e.message+' Is the backend running?')).finally(()=>setBusy(false));},[]);
 useEffect(()=>{saveLocal('speedpainter-settings',settings)},[settings]);
 useEffect(()=>{if(project?.mode!=='steps'&&settings.duration>maxDuration){setSettings(s=>({...s,duration:maxDuration}));setTime(t=>Math.min(t,maxDuration))}},[maxDuration,settings.duration,project?.mode]);
 useEffect(()=>{
   // Saved styles, this week's ideas and the brand kit; reloaded when the plan changes (e.g. after upgrading).
   api('/api/presets').then(setPresets).catch(()=>{});api('/api/ideas').then(setIdeas).catch(()=>{});api('/api/brand').then(setBrandKit).catch(()=>{});
 },[account?.plan?.id]);
 useEffect(()=>{if(!pro&&!local&&settings.resolution==='4k')setSettings(s=>({...s,resolution:'1080p'}))},[pro,local,settings.resolution]);
 useEffect(()=>{
   // "Get Pro" on the landing page: open the upgrade dialog (guests create an account first).
   const params=new URLSearchParams(location.search);
   if(!account||!params.has('upgrade'))return;
   if(['month','year'].includes(params.get('interval')))setInterval_(params.get('interval'));  // "Claim the founding price" opens on Monthly
   history.replaceState(null,'',location.pathname);
   if(account.plan.id==='guest')setSignIn('upgrade');else if(account.plan.id!=='pro'&&account.auth!=='local')setUpgrade(true);
 },[account?.plan?.id]);
 useEffect(()=>{
   // Back from checkout: the payment webhook can land a few seconds after the redirect, so check a few times.
   const params=new URLSearchParams(location.search);
   if(params.has('pack')){history.replaceState(null,'',location.pathname);setNotice('Thanks! Your video pack is being added…');let tries=0,alive=true,before=null;const check=()=>loadAccount().then(value=>{if(!alive)return;if(before===null)before=value.packs;if(value.packs>0&&(value.packs>before||tries>0))setNotice(`Your video pack is ready: ${value.packs} videos with no watermark, up to 5 minutes each.`);else if(++tries<15)setTimeout(check,2000);else setNotice('Your payment went through. The videos will appear shortly — refresh in a minute if they haven’t.');}).catch(()=>{});check();return()=>{alive=false};}
   if(!params.has('upgraded'))return;
   history.replaceState(null,'',location.pathname);setNotice('Thanks for upgrading! Activating Pro…');
   let tries=0,alive=true;const check=()=>loadAccount().then(value=>{if(!alive)return;if(value.plan.id==='pro')setNotice('Welcome to Pro! Up to 4K, no watermark, and 200 videos a month.');else if(++tries<15)setTimeout(check,2000);else setNotice('Your payment went through. Pro will switch on shortly — refresh in a minute if it hasn’t.');}).catch(()=>{});
   check();return()=>{alive=false};
 },[]);
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
   try{const p=await api('/api/projects',{method:'POST',body});if(token===requestRef.current){setProject(p);setTime(p.mode==='steps'?p.duration:0);setPlaying(p.mode!=='steps');setJob(null);setView('studio');}await refresh();const layout=await api(`/api/projects/${p.id}/step-layout`).catch(()=>null);if(token===requestRef.current&&layout?.detected)setStepEditor(true);}catch(e){setError(e.message)}finally{if(token===requestRef.current)setBusy(false);fileInput.current.value='';}
 }
async function chooseLines(accept){setSuggestBusy(true);try{const p=await api(`/api/projects/${project.id}/enhance`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({accept})});setProject(p);setTime(0);setPlaying(false);setSuggest(false);setJob(null);refresh().catch(()=>{})}catch(e){setError(e.message)}finally{setSuggestBusy(false)}}
  async function openProject(id){setBusy(true);setError('');setPlaying(false);try{const loaded=await api(`/api/projects/${id}`);setProject(loaded);setView('studio');if(loaded.mode==='steps')setSettings(current=>({...current,duration:loaded.duration}));setTime(loaded.mode==='steps'?loaded.duration:settings.duration);setJob(null);}catch(e){setError(e.message)}finally{setBusy(false)}}
 async function exportVideo(overrides={}){if(!project||submitting)return;const body={...settings,...overrides};if(Object.keys(overrides).length)setSettings(body);setError('');setJob(null);setSubmitting(true);setModal(true);try{setJob(await api(`/api/projects/${project.id}/jobs`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}));}catch(e){setModal(false);if(e.status===401&&guest)setSignIn('export');else if(e.status===402)setUpgrade(true);else setError(e.message)}finally{setSubmitting(false);loadAccount().catch(()=>{})}}
 function picked(p,item){requestRef.current++;setProject(p);setTime(0);setPlaying(!item.tutorial);setOriginal(false);setJob(null);setView('studio');setGallery(false);refresh().catch(()=>{});if(item.tutorial)setStepEditor(true);}
 async function goToCheckout(){setCheckout(true);setError('');try{location.href=(await api('/api/billing/checkout',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({interval:account.billing.yearly_enabled?interval:'month'})})).url}catch(e){setError(e.message);setUpgrade(false);setCheckout(false)}}
 async function buyPack(pack){setCheckout(true);setError('');try{location.href=(await api('/api/billing/pack',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({pack})})).url}catch(e){setError(e.message);setUpgrade(false);setCheckout(false)}}
 async function manageBilling(){setError('');try{window.open((await api('/api/billing/portal')).url,'_blank','noopener')}catch(e){setError(e.message)}}
 function batchQueued(jobs){setModal(false);setView('exports');refresh().catch(()=>{});setNotice(`Exporting ${jobs.length} video${jobs.length===1?'':'s'} — they’ll appear here as they finish.`)}
 async function exportAllFormats(){
   if(!project)return;if(guest){setSignIn('export');return}if(!pro){setUpgrade(true);return}
   setError('');try{batchQueued(await api('/api/batch',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({project_ids:[project.id],ratios:['16:9','9:16','1:1'],settings})}))}catch(e){setError(e.message)}
 }
 async function savePreset(name){
   if(guest){setSignIn('sidebar');return}
   setPresetBusy(true);try{await api('/api/presets',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,settings})});setPresets(await api('/api/presets'));setNotice(`Saved “${name}”.`)}
   catch(e){if(e.status===402)setUpgrade(true);setError(e.message)}finally{setPresetBusy(false)}
 }
 async function deletePreset(preset){try{await api(`/api/presets/${preset.id}`,{method:'DELETE'});setPresets(list=>list.filter(p=>p.id!==preset.id))}catch(e){setError(e.message)}}
 function applyPreset(values){setSettings(s=>({...s,...values}));setTime(t=>Math.min(t,values.duration||settings.duration))}
 async function useIdea(idea){setBusy(true);setError('');try{const p=await api(`/api/library/${idea.id}/use`,{method:'POST'});setSettings(s=>({...s,style:idea.style,ratio:idea.ratio}));picked(p,idea)}catch(e){setError(e.message)}finally{setBusy(false)}}
 function projectDeleted(id){if(project?.id===id){setProject(null);setJob(null);try{localStorage.removeItem('speedpainter-project')}catch{}}}
 function play(){setOriginal(false);if(time>=settings.duration)setTime(0);setPlaying(p=>!p)}
 const activeJob=job&&['queued','rendering'].includes(job.status);
 return <div className="app-shell">
  <input ref={fileInput} type="file" accept="image/png,image/jpeg,image/webp" className="hidden" onChange={e=>upload(e.target.files[0])}/>
  <aside className={`sidebar ${menu?'mobile-open':''}`}>
   <a className="brand" href="/" title="Back to the Strokeberry website" aria-label="Strokeberry website"><BrandMark/>{BRAND.name}</a>
   <div className="workspace-label">Studio</div>
   <nav>{[['studio',Sparkles,'Create a video'],['projects',FolderOpen,'Projects'],['exports',Film,'Exports'],['brand',Palette,'Brand kit']].map(([id,Icon,label])=><button key={id} className={`nav-item ${view===id?'active':''}`} onClick={()=>{setView(id);setMenu(false);if(id!=='studio')refresh().catch(e=>setError(e.message))}}><Icon size={18}/>{label}{id==='projects'&&<span className="nav-count">{projects.length}</span>}{id==='brand'&&!pro&&!local&&<span className="nav-pro">Pro</span>}</button>)}<a className="nav-item nav-website" href="/"><Home size={18}/>Website<ArrowUpRight/></a></nav>
   <div className="sidebar-note"><div className="note-art"><Leaf size={18}/><span>New here?</span></div><p>Three steps from a still image to a finished drawing video.</p><button onClick={()=>{setHelp(true);setMenu(false)}}>See how it works <ArrowUpRight/></button></div>
   <div className="sidebar-bottom">{guest&&<div className="plan-card"><div className="plan-row"><span className="plan-chip guest">Guest</span><small>Trying it out</small></div><p className="guest-note">Preview as much as you like. A free account lets you export — your work is kept.</p><button className="button primary upgrade-button" onClick={()=>{setSignIn('sidebar');setMenu(false)}}>Create free account</button></div>}{account&&!local&&!guest&&<div className="plan-card"><div className="plan-row"><span className={`plan-chip ${account.plan.id}`}>{account.plan.id==='pro'&&<Crown size={12}/>}{account.plan.name}</span><small>{account.usage.remaining} of {account.usage.limit} videos left{account.usage.period_days?' this month':''}</small></div><div className="usage-meter" role="meter" aria-label="Videos used" aria-valuemin={0} aria-valuemax={account.usage.limit} aria-valuenow={account.usage.used}><i style={{width:`${Math.min(100,account.usage.used/account.usage.limit*100)}%`}}/></div>{account.packs>0&&<p className="pack-balance"><Package size={13}/>{account.packs} pack {account.packs===1?'video':'videos'} · no watermark</p>}{account.plan.id==='pro'?(account.billing.can_manage&&<button className="plan-link" onClick={manageBilling}>Manage billing <ArrowUpRight/></button>):<button className="button primary upgrade-button" onClick={()=>{setUpgrade(true);setMenu(false)}}><Crown size={15}/>Upgrade to Pro</button>}</div>}<div className="user"><span className="avatar"><BrandMark size={16} compact/></span><div className="user-text"><strong>{local?'Personal studio':guest?'Guest':account.user.name||account.user.email}</strong><small>{local?<><i/>Private studio</>:guest?'Not signed in':account.user.name?account.user.email:'Signed in'}</small></div>{!local&&!guest&&authEnabled&&<IconButton label="Sign out" onClick={onSignOut}><LogOut size={16}/></IconButton>}</div></div>
  </aside>
  {menu&&<div className="sidebar-scrim" onClick={()=>setMenu(false)}/>}
  <main>
   <header className="topbar"><div className="breadcrumb"><IconButton label="Toggle navigation" onClick={()=>setMenu(!menu)}><Menu size={20}/></IconButton><span>Workspace</span><span className="slash">/</span><strong>{view==='studio'?'Create a video':view==='projects'?'Projects':view==='brand'?'Brand kit':'Exports'}</strong></div><div className="topbar-right"><span className="private-indicator"><i/>{local?'Private studio':'Private to your account'}</span><button className="button ghost" onClick={()=>setHelp(true)}><CircleHelp size={16}/>Guide</button></div></header>
   {notice&&<div className="notice-banner" role="status"><Crown size={16}/>{notice}<button aria-label="Dismiss" onClick={()=>setNotice('')}><X size={17}/></button></div>}
   {error&&<div className="error-banner" role="alert">{error}<button aria-label="Dismiss error" onClick={()=>setError('')}><X size={17}/></button></div>}
   {view==='studio'?<div className="studio-page">
    <div className="page-heading"><div className="eyebrow">New video</div><div className="heading-row"><div><h1>Turn any image into a <em>hand‑drawn</em> video</h1><p>Upload artwork, pick a style, and export a speed‑drawing MP4 ready for Reels, TikTok, and Shorts.</p></div><div className="heading-actions"><button className="button secondary" onClick={()=>setGallery(true)} disabled={busy}><LayoutGrid size={16}/>Examples</button><button className="button primary new-project" onClick={()=>fileInput.current.click()} disabled={busy}><Upload size={17}/>Upload image</button></div></div></div>
    <div className="editor-grid">
     <section className="preview-panel">
      <div className="panel-heading"><div><span className="mini-icon"><Clapperboard size={17}/></span><strong>Preview</strong><span className="subtle-chip">{settings.ratio}</span></div><span className="saved"><Check size={13}/>{busy?'Preparing…':'Saved'}</span></div>
      <div className={`preview-stage ${drag?'dragging':''} ${expanded?'expanded':''}`} ref={preview} onDragOver={e=>{e.preventDefault();setDrag(true)}} onDragLeave={()=>setDrag(false)} onDrop={e=>{e.preventDefault();setDrag(false);upload(e.dataTransfer.files[0])}}>
       <div className="canvas-topline"><span className="preview-badge"><i/>{original?'ORIGINAL IMAGE':'LIVE PREVIEW'}</span><button className={`original-button ${original?'selected':''}`} onClick={()=>{setOriginal(v=>!v);setPlaying(false)}} disabled={!project}> {original?'Show drawing':project?.mode==='steps'?'View final':'View original'}</button></div>
       {project&&(project.mode==='steps'?<StepCanvas project={project} settings={settings} time={time} original={original} onReady={message=>{if(message)setError(message)}}/>:<DrawingCanvas inkColor={pro&&brandKit?.enabled?brandKit.ink_color:''} project={project} settings={settings} time={time} original={original} onReady={message=>{if(message)setError(message)}}/>)}
       {(busy||!project)&&<div className="canvas-loading">{busy?<><LoaderCircle className="spin" size={26}/><span>Preparing your canvas…</span></>:<><ImagePlus size={32}/><strong>Drop an image to begin</strong><small>PNG, JPG or WebP · up to 15 MB</small><button className="button primary" onClick={()=>fileInput.current.click()}>Choose an image</button><button className="button ghost" onClick={()=>setGallery(true)}><LayoutGrid size={15}/>Or pick an example</button></>}</div>}
       {drag&&<div className="drop-overlay"><Upload size={32}/>Drop to start a new project</div>}
       <div className="canvas-caption"><span>{project?.mode==='steps'?`Step ${stageAt(project.stages,time/settings.duration).index+1} · ${project.stages[stageAt(project.stages,time/settings.duration).index].label}`:project?.name||''}</span><IconButton label={expanded?'Close large preview':'Expand preview'} onClick={()=>setExpanded(v=>!v)}>{expanded?<Minimize2 size={16}/>:<Expand size={16}/>}</IconButton></div>
       {expanded&&<div className="expanded-controls"><IconButton label={playing?'Pause preview':'Play preview'} onClick={play} disabled={!project||busy}>{playing?<Pause size={20} fill="currentColor"/>:<Play size={20} fill="currentColor"/>}</IconButton><span>{format(time)}</span><input aria-label="Preview timeline" type="range" min="0" max={settings.duration} step="0.01" value={time} onChange={e=>{setTime(Number(e.target.value));setPlaying(false);setOriginal(false)}} style={{'--progress':`${time/settings.duration*100}%`}}/><span>{format(settings.duration)}</span><button className="button secondary" onClick={()=>setExpanded(false)}><Minimize2 size={15}/>Close</button></div>}
      </div>
      <div className="playback"><IconButton label={playing?'Pause preview':'Play preview'} onClick={play} disabled={!project||busy}>{playing?<Pause size={17} fill="currentColor"/>:<Play size={17} fill="currentColor"/>}</IconButton><span className="time">{format(time)}</span><input aria-label="Preview timeline" type="range" min="0" max={settings.duration} step="0.01" value={time} onChange={e=>{setTime(Number(e.target.value));setPlaying(false);setOriginal(false)}} style={{'--progress':`${time/settings.duration*100}%`}}/><span className="time end">{format(settings.duration)}</span><span className="playback-divider"/><IconButton label="Restart preview" onClick={()=>{setTime(0);setOriginal(false);setPlaying(true)}} disabled={!project||busy}><RotateCcw size={16}/></IconButton></div>
      {project?.mode==='steps'&&<div className="sequence-strip">{project.stages.map((stage,i)=><button key={i} className={stageAt(project.stages,time/settings.duration).index===i?'active':''} onClick={()=>{setTime((stage.start+(stage.end-stage.start)*.96)*settings.duration);setPlaying(false);setOriginal(false)}} aria-label={`Preview completed step ${i+1}: ${stage.label}`}><img src={stage.source} alt=""/><span><strong>{i+1}. {stage.label}</strong><small>{Math.round((stage.end-stage.start)*settings.duration)} seconds{stage.alignment.confidence<.55?' · Check alignment':''}</small></span></button>)}</div>}
      <div className="source-row"><div className="source-thumbnail">{project?<img src={project.source} alt="Source image"/>:<ImagePlus size={20}/>}</div><div><strong>{project?`${project.name}.png`:'Add your image'}</strong><small>{project?`${project.width} × ${project.height} px · ${project.strokes.toLocaleString()} drawing strokes`:'PNG, JPG or WebP · Up to 15 MB'}</small></div><div className="source-actions"><button onClick={()=>{setPlaying(false);setImageEditor(true)}} disabled={!project||busy}><Eraser size={14}/>Edit image</button><button onClick={()=>fileInput.current.click()} disabled={busy}><Upload size={14}/>Replace</button></div></div>
      {project&&<SuggestionBar project={project} busy={suggestBusy||busy} onReview={()=>{setPlaying(false);setSuggest(true)}} onUndo={()=>chooseLines(false)}/>}
      <div className="steps-entry"><div><strong>{project?.mode==='steps'?'Your step-by-step sequence':'Image contains drawing steps?'}</strong><small>{project?.mode==='steps'?'Review crops, order, timing, and alignment.':'Turn a tutorial grid into one evolving drawing.'}</small></div><button className="button secondary" disabled={!project||busy} onClick={()=>setStepEditor(true)}>{project?.mode==='steps'?'Edit steps':'Set up steps'}<ArrowRight size={14}/></button></div>
     </section>
     <section className="settings-panel"><div className="panel-heading"><div><span className="mini-icon"><Sparkles size={16}/></span><strong>Settings</strong></div></div>
      <Presets presets={presets} settings={settings} busy={presetBusy} onApply={applyPreset} onSave={savePreset} onDelete={deletePreset}/>
      <div className="settings-tabs"><button className={tab==='drawing'?'active':''} onClick={()=>setTab('drawing')}>Drawing style</button><button className={tab==='video'?'active':''} onClick={()=>setTab('video')}>Video settings</button></div>
      <div className="settings-content">{tab==='drawing'?<>
       {project?.mode==='steps'?<div className="sequence-summary"><Sparkles size={22}/><strong>Follow the artist’s steps</strong><p>Preserves the marks, shading, and colors in each panel. Adjust the total duration below; stage timings scale proportionally.</p><button className="button secondary" onClick={()=>setStepEditor(true)}>Edit drawing steps</button></div>:<>
       <div className="field-label">Style</div>
       <div className="style-options">{[['pencil','Pencil','Soft, varied strokes'],['ink','Ink','Bold, confident lines']].map(([id,title,subtitle])=><button key={id} className={`style-card ${settings.style===id?'selected':''}`} onClick={()=>update('style',id)}><div className={`style-art ${id}`}><Botanical/><span className="radio-check">{settings.style===id&&<Check size={10}/>}</span></div><strong>{title}</strong><small>{subtitle}</small></button>)}</div>
       </>}
       <div className="settings-divider"/>
       <div className="field-label">Drawing hand</div>
       <div className="hand-options" role="radiogroup" aria-label="Drawing hand">{HANDS.map(([id,label])=>{const on=id==='none'?!settings.pen:settings.pen&&(settings.hand||'pencil')===id;return <button key={id} role="radio" aria-checked={on} className={on?'selected':''} onClick={()=>setSettings(s=>({...s,pen:id!=='none',hand:id==='none'?s.hand:id}))}>{id==='none'?<span className="hand-thumb none"><X size={16}/></span>:id==='pencil'?<span className="hand-thumb pencil"><Pencil size={16}/></span>:<span className="hand-thumb"><img src={`/hands/${id}-pencil.png`} alt="" loading="lazy"/></span>}<small>{label}</small></button>})}</div>
       <p className="setting-hint">A real hand draws the lines, then picks up a brush for the colour.</p>
       <div className="field-label">Canvas</div>
       <div className="canvas-options" role="radiogroup" aria-label="Canvas">{CANVASES.map(([id,label,color])=><button key={id} role="radio" aria-checked={(settings.canvas||'paper')===id} className={(settings.canvas||'paper')===id?'selected':''} onClick={()=>update('canvas',id)}><span style={{background:color}}/>{label}</button>)}</div>
       {project?.mode!=='steps'&&<Toggle value={settings.color} onChange={v=>update('color',v)} label="Bring in the color" description="Reveal original colors after the sketch"/>}
       <div className="settings-divider"/>
       <div className="field-label">Duration <span>{format(settings.duration)}</span></div><input className="duration-slider" aria-label="Video duration" type="range" min="5" max={maxDuration} step="5" value={settings.duration} onChange={e=>update('duration',Number(e.target.value))} style={{'--progress':`${(settings.duration-5)/(maxDuration-5)*100}%`}}/><div className="range-labels"><span>5s</span><span>{maxDuration>=300?'5 min':'1 min'}</span></div>{maxDuration<300&&<p className="setting-hint">Videos up to 5 minutes are part of <button className="inline-link" onClick={()=>guest?setSignIn('upgrade'):setUpgrade(true)}>Pro</button>.</p>}
      </>:<>
       <div className="field-label">Format</div><div className="ratio-options">{RATIOS.map(([r,label])=>{const [w,h]=frameSize(r,project);return <button className={settings.ratio===r?'selected':''} onClick={()=>update('ratio',r)} key={r}><span style={{aspectRatio:`${w}/${h}`}}/>{r==='auto'?'Auto':r}<small>{label}</small></button>})}</div>
       <div className="settings-divider"/><label className="field-label" htmlFor="resolution">Quality</label><div className="quality-options" role="radiogroup" aria-label="Quality">{[['720p','HD'],['1080p','Full HD'],['4k','Ultra HD']].map(([id,label])=>{const locked=id==='4k'&&!pro&&!local;return <button key={id} role="radio" aria-checked={settings.resolution===id} className={settings.resolution===id?'selected':''} onClick={()=>locked?(guest?setSignIn('upgrade'):setUpgrade(true)):update('resolution',id)}><strong>{RES_LABEL[id]}</strong><small>{label}</small>{locked&&<em><Crown size={10}/>Pro</em>}</button>})}</div><p className="setting-hint">MP4 video at 24 frames per second. Higher resolutions take a little longer to render.</p><div className="settings-divider"/><div className="format-note"><Film size={20}/><div><strong>No cropping</strong><p>Your image is fitted inside the frame, so nothing gets cut off.</p></div></div>
      </>}</div>
      <div className="export-section"><div className="export-summary"><span><Film size={13}/>{RES_LABEL[settings.resolution]} MP4</span><span>{settings.ratio==='auto'?'Auto':settings.ratio}</span><span><Clock3 size={13}/>{format(settings.duration)}</span></div><button className="button primary export-button" disabled={!project||busy||activeJob||submitting} onClick={()=>exportVideo()}>{activeJob?<LoaderCircle size={17} className="spin"/>:<Sparkles size={17}/>} {activeJob?`Rendering · ${job.progress}%`:'Export video'}<ArrowRight size={17}/></button>{!activeJob&&<button className="batch-link" onClick={exportAllFormats}>{pro?'Export all 3 formats':<>Export all 3 formats <em>Pro</em></>}</button>}{activeJob?<button className="export-footer link" onClick={()=>setModal(true)}>View export progress</button>:<p className="export-footer">{local?'Up to 4K · no watermark':guest?<>Free account needed to export · <button className="inline-link" onClick={()=>setSignIn('export')}>Create one</button></>:free&&account.packs>0?<>Uses 1 of your {account.packs} pack {account.packs===1?'video':'videos'} · no watermark</>:free?<>{account.usage.remaining} free {account.usage.remaining===1?'video':'videos'} left this month{account.usage.remaining===0&&account.usage.resets?` · back ${shortDate(account.usage.resets)}`:''} · watermark + end card · <button className="inline-link" onClick={()=>setUpgrade(true)}>Remove them</button></>:'Pro · up to 4K · no watermark'}</p>}</div>
     </section>
    </div>
    <Ideas ideas={ideas} onUse={useIdea}/>
    <section className="bottom-strip"><div className="tip-icon"><Leaf size={23}/></div><div><strong>Best results come from clean line art</strong><p>Illustrations, logos, and drawing tutorials with clear outlines on a plain background produce the crispest strokes.</p></div><button onClick={()=>{setHelp(true)}}>Tips for great videos <ArrowRight size={15}/></button></section>
    <footer className="page-footer"><span>{BRAND.name}</span><span>{BRAND.tagline}</span></footer>
   </div>:view==='projects'?<ProjectsView projects={projects} api={api} pro={pro} guest={guest} current={project?.id} settings={settings} onOpen={openProject} onNew={()=>fileInput.current.click()} onExamples={()=>setGallery(true)} onChanged={refresh} onDeleted={projectDeleted} onBatchQueued={batchQueued} onUpgrade={()=>guest?setSignIn('export'):setUpgrade(true)} onError={setError}/>
   :view==='exports'?<ExportsView jobs={jobs} projects={projects} api={api} onOpen={j=>{setJob(j);setModal(true)}} onRefresh={refresh} onStudio={()=>setView('studio')} onError={setError}/>
   :<BrandKit kit={brandKit} api={api} pro={pro||local} onSaved={setBrandKit} onUpgrade={()=>guest?setSignIn('upgrade'):setUpgrade(true)} onError={setError}/>}
  </main>
  {suggest&&project?.enhance&&<SuggestionDialog project={project} busy={suggestBusy} onChoose={chooseLines} onClose={()=>setSuggest(false)}/>}
  {imageEditor&&project&&<ImageEditor project={project} api={api} onClose={()=>setImageEditor(false)} onSaved={result=>{setProject(result);setTime(0);setPlaying(false);setOriginal(false);setJob(null);setImageEditor(false);refresh().catch(e=>setError(e.message));}}/>}
  {stepEditor&&project&&<StepEditor maxTotal={maxDuration} onUpgrade={()=>{setStepEditor(false);guest?setSignIn('upgrade'):setUpgrade(true)}} project={project} api={api} onClose={()=>setStepEditor(false)} onCreated={result=>{setProject(result);setSettings(current=>({...current,duration:result.duration}));setTime(0);setPlaying(false);setOriginal(false);setJob(null);setStepEditor(false);refresh().catch(e=>setError(e.message))}}/>}
  {view==='studio'&&project&&<div className="mobile-export"><button className="button secondary mobile-upload" aria-label="Upload image" onClick={()=>fileInput.current.click()} disabled={busy}><Upload size={17}/></button><span>{RES_LABEL[settings.resolution]} · {settings.ratio==='auto'?'Auto':settings.ratio} · {format(settings.duration)}</span><button className="button primary" disabled={busy||activeJob||submitting} onClick={()=>exportVideo()}>{activeJob?<LoaderCircle size={16} className="spin"/>:<Sparkles size={16}/>}{activeJob?`${job.progress}%`:'Export video'}</button></div>}
  {signIn&&<SignIn dialog onClose={()=>setSignIn('')} onSignedIn={()=>{setSignIn('');loadAccount().catch(()=>{});refresh().catch(()=>{})}} title={signIn==='export'?'Create a free account to export':signIn==='upgrade'?'Create your account to go Pro':'Create your free account'} intro="Your projects stay exactly as they are. Your first 3 videos are free, and there’s no card and no password."/>}
  {gallery&&<Gallery api={api} onClose={()=>setGallery(false)} onPicked={picked}/>}
  {upgrade&&account&&<div className="modal-backdrop" onClick={()=>setUpgrade(false)}><section className="modal upgrade-modal" role="dialog" aria-modal="true" aria-labelledby="upgrade-title" onClick={e=>e.stopPropagation()}><IconButton label="Close" onClick={()=>setUpgrade(false)}><X size={20}/></IconButton><span className="dialog-icon"><Crown size={26}/></span><div className="eyebrow">Strokeberry Pro</div><h2 id="upgrade-title">{account.usage.remaining===0&&free?'You’ve used your free videos':'Make it look pro'}</h2>{account.usage.remaining===0&&free&&account.usage.resets&&<p className="upgrade-reset">Your 3 free videos come back on <strong>{shortDate(account.usage.resets)}</strong>. Or go Pro and keep creating now.</p>}<ul className="pro-list"><li><Check size={16}/>200 videos every month</li><li><Check size={16}/>Videos up to 5 minutes</li><li><Check size={16}/>4K exports</li><li><Check size={16}/>No watermark or end card</li><li><Check size={16}/>Cancel anytime</li></ul>{account.billing.enabled?<>{account.billing.yearly_enabled&&<div className="interval-toggle" role="tablist"><button role="tab" aria-selected={interval==='month'} className={interval==='month'?'on':''} onClick={()=>setInterval_('month')}>Monthly</button><button role="tab" aria-selected={interval==='year'} className={interval==='year'?'on':''} onClick={()=>setInterval_('year')}>Yearly<em>Save {account.billing.yearly_saving}%</em></button></div>}{(()=>{const yearly=account.billing.yearly_enabled&&interval==='year',founder=!yearly&&account.billing.founder;return <><p className="upgrade-price">{founder&&<s>{account.billing.monthly}</s>}<strong>{yearly?account.billing.yearly:founder?founder.price:account.billing.monthly}</strong> / {yearly?'year':'month'}</p>{founder&&<p className="founder-note"><b>Founding member rate</b> — locked in for as long as you stay subscribed{founder.left!=null&&<> · {founder.left} of {founder.limit} spots left</>}</p>}</>})()}<button className="button primary download-button" onClick={goToCheckout} disabled={checkout}>{checkout?<LoaderCircle size={17} className="spin"/>:<Crown size={17}/>}Upgrade to Pro</button><p className="modal-note">Secure checkout by Lemon Squeezy. Cancel anytime.</p></>:<p className="modal-note">Pro is almost ready — upgrades open very soon.</p>}{account.billing.packs?.length>0&&<div className="pack-offer"><div className="pack-divider"><span>or pay once</span></div><p className="pack-intro">Video packs never expire. Each video has no watermark and can be up to 5 minutes in 1080p.</p><div className="pack-grid">{account.billing.packs.map(p=><button key={p.id} className={`pack-card ${p.label==='Best value'?'best':''}`} onClick={()=>buyPack(p.id)} disabled={checkout}>{p.label&&<em>{p.label}</em>}<strong>{p.videos} videos</strong><span className="pack-price">{p.price}</span>{p.per_video&&<small>{p.per_video} per video</small>}</button>)}</div><p className="modal-note">Making more than 10 a month? Pro is cheaper: 200 videos for {account.billing.monthly}.</p></div>}</section></div>}
  {(modal||help)&&<div className="modal-backdrop" onClick={()=>{setModal(false);setHelp(false)}}><section className={`modal ${help?'guide-modal':''} ${!help&&job?.status==='completed'?'ready-modal':''}`} role="dialog" aria-modal="true" aria-labelledby="dialog-title" onClick={e=>e.stopPropagation()}><IconButton label="Close dialog" onClick={()=>{setModal(false);setHelp(false)}}><X size={20}/></IconButton>{help?<Guide account={account} onExamples={()=>{setHelp(false);setGallery(true)}}/>:job?.status==='completed'?<ExportResult job={job} sameProject={job.project_id===project?.id} plan={local?'pro':account?.plan?.id} remaining={account?.usage?.remaining} onAgain={overrides=>exportVideo(overrides)} onAllFormats={exportAllFormats} onAnother={()=>{setModal(false);setGallery(true)}} onUpgrade={()=>{setModal(false);setUpgrade(true)}}/>:<><span className="dialog-icon">{job?.status==='completed'?<Check size={27}/>:job?.status==='failed'?<X size={27}/>:<Sparkles size={27}/>}</span><div className="eyebrow">Export</div><h2 id="dialog-title">{job?.status==='completed'?'Your video is ready':job?.status==='failed'?'Export failed':'Rendering your video'}</h2>{job?.status==='failed'?<><p className="failure-text">{job.error}</p><button className="button primary" onClick={()=>{setModal(false);setView('studio')}}>Back to studio</button></>:<><p className="render-stage" aria-live="polite">{job?.stage||'Adding your video to the queue…'}</p>{(()=>{const steps=RENDER_STEPS.filter(([label])=>label!=='Adding the end card'||job?.settings?.end_card),stage=job?.stage||'queue';let current=steps.findIndex(([,match])=>match.test(stage));if(current<0)current=1;if((job?.progress||0)>=100)current=steps.length;return <ol className="render-steps">{steps.map(([label],i)=><li key={label} className={i<current?'done':i===current?'active':''}>{i<current?<Check size={13}/>:<i/>}{label}</li>)}</ol>})()}<div className="progress-track"><div style={{width:`${job?.progress||0}%`}}/></div><div className="render-progress"><span>{job?.progress||0}% complete</span><span>{job?.settings?.resolution||settings.resolution} · MP4</span></div><p className="modal-note">You can close this and keep working — we’ll keep rendering in the background.</p></>}</>}</section></div>}
 </div>
}
function ArrowUpRight(){return <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7"><path d="M6 18 18 6M6 6h12v12"/></svg>}
function Botanical(){return <svg viewBox="0 0 120 70" fill="none" aria-hidden="true"><path d="M52 70C57 49 67 28 73 4M62 42 42 20M67 28 91 16M57 55 35 43"/><path d="M67 26C47 25 46 13 44 6c15 1 25 7 23 20ZM71 16C78 3 91 6 97 3c-3 14-12 19-26 13ZM61 43C74 27 91 32 96 30c-5 15-22 21-35 13ZM54 58C37 57 32 49 29 37c13 3 25 5 25 21ZM62 40C44 39 37 31 36 23c17 0 23 6 26 17Z"/><path d="m67 26-15-12m19 2L89 8M61 43l26-9m-33 24L35 43M62 40 43 28"/></svg>}
// Shown while the studio signs the visitor in and loads their work, so the first seconds are never a blank page.
function StudioLoading(){return <div className="sign-in-page studio-loading" role="status"><BrandMark size={56}/><strong>Opening your studio…</strong><small>Getting your canvas and examples ready</small><LoaderCircle className="spin" size={22}/></div>}

function Root(){
 const [user,setUser]=useState(authEnabled?undefined:{local:true}),[notice,setNotice]=useState(''),[failed,setFailed]=useState(false);
 useEffect(()=>{
   const finishing=completeEmailLink(async()=>window.prompt('Please confirm the email address you used to sign in:')).catch(e=>{setNotice(e.message);return false});
   return watchUser(value=>{
     if(value){setUser(value);return}
     // Nobody is signed in: start a guest session so visitors can try the studio straight away.
     finishing.then(done=>{if(!done)startGuest().catch(()=>{setFailed(true);setUser(null)})});
   });
 },[]);
 if(user===undefined)return <StudioLoading/>;
 if(!user&&failed)return <SignIn notice={notice}/>;
 if(!user)return <StudioLoading/>;
 return <App key={user.uid||'local'} onSignOut={()=>{setUser(undefined);signOut().catch(()=>{})}}/>;
}
createRoot(document.getElementById('root')).render(<Root/>);
