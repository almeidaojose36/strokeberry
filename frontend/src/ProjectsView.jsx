import React, {useEffect, useState} from 'react';
import {ArrowRight, Check, Copy, Crown, Film, LayoutGrid, LoaderCircle, MoreHorizontal, Pencil, Plus, Trash2} from 'lucide-react';
import {Confirm, Prompt} from './Dialogs.jsx';

const RATIOS = [['16:9', 'Landscape'], ['9:16', 'Portrait'], ['1:1', 'Square']];
const when = iso => new Date(iso).toLocaleDateString(undefined, {day: 'numeric', month: 'short', year: 'numeric'});

export default function ProjectsView({projects, api, pro, guest, current, settings, onOpen, onNew, onExamples, onChanged, onDeleted, onBatchQueued, onUpgrade, onError}) {
  const [menu, setMenu] = useState(null), [renaming, setRenaming] = useState(null), [deleting, setDeleting] = useState(null), [busy, setBusy] = useState(false);
  const [selecting, setSelecting] = useState(false), [picked, setPicked] = useState([]), [ratios, setRatios] = useState(['16:9', '9:16', '1:1']), [query, setQuery] = useState('');
  useEffect(() => { const close = () => setMenu(null); window.addEventListener('click', close); return () => window.removeEventListener('click', close); }, []);

  async function run(work) {
    setBusy(true);
    try { await work(); } catch (e) { onError(e.message); } finally { setBusy(false); }
  }
  const rename = name => run(async () => { await api(`/api/projects/${renaming.id}`, {method: 'PATCH', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({name})}); setRenaming(null); await onChanged(); });
  const duplicate = project => run(async () => { await api(`/api/projects/${project.id}/duplicate`, {method: 'POST'}); await onChanged(); });
  const remove = () => run(async () => { await api(`/api/projects/${deleting.id}`, {method: 'DELETE'}); onDeleted(deleting.id); setDeleting(null); await onChanged(); });
  const total = picked.length * ratios.length;
  const batch = () => run(async () => {
    const jobs = await api('/api/batch', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({project_ids: picked, ratios, settings})});
    setSelecting(false); setPicked([]); onBatchQueued(jobs);
  }).catch(() => {});
  const toggle = id => setPicked(list => list.includes(id) ? list.filter(x => x !== id) : list.length < 6 ? [...list, id] : list);
  const shown = projects.filter(p => p.name.toLowerCase().includes(query.trim().toLowerCase()));

  return <div className="library-page">
    <div className="eyebrow">Library</div>
    <div className="heading-row"><div><h1>Projects</h1><p>Pick up where you left off, or start something new.</p></div>
      <div className="heading-actions">
        {projects.length > 1 && <button className={`button secondary ${selecting ? 'pressed' : ''}`} onClick={() => { setSelecting(v => !v); setPicked([]); }}>{selecting ? 'Cancel' : 'Select'}</button>}
        <button className="button secondary" onClick={onExamples}><LayoutGrid size={16}/>Examples</button>
        <button className="button primary" onClick={onNew}><Plus size={17}/>New project</button>
      </div></div>
    {projects.length > 8 && <input className="text-input search-input" type="search" placeholder="Search your projects" aria-label="Search projects" value={query} onChange={e => setQuery(e.target.value)}/>}
    {projects.length === 0 ? <div className="empty-state"><Film size={40}/><h2>No projects yet</h2><p>Upload an image or start from an example.</p><button className="button secondary" onClick={onExamples}>Browse examples <ArrowRight size={15}/></button></div> :
      <div className="project-grid">{shown.map(p => <div className={`project-card ${picked.includes(p.id) ? 'picked' : ''}`} key={p.id}>
        <button className="project-open" onClick={() => selecting ? toggle(p.id) : onOpen(p.id)} aria-label={selecting ? `Select ${p.name}` : `Open ${p.name}`}>
          <img src={p.source} alt="" loading="lazy"/>
          <div><strong>{p.name}</strong><span>{when(p.created)}{current === p.id ? ' · open now' : ''}</span></div>
        </button>
        {selecting ? <span className="pick-box" aria-hidden="true">{picked.includes(p.id) && <Check size={14}/>}</span> :
          <div className="project-menu" onClick={e => e.stopPropagation()}>
            <button className="icon-button" aria-label={`More for ${p.name}`} aria-haspopup="menu" onClick={e => { e.stopPropagation(); setMenu(menu === p.id ? null : p.id); }}><MoreHorizontal size={18}/></button>
            {menu === p.id && <div className="menu-pop" role="menu">
              <button role="menuitem" onClick={() => { setMenu(null); setRenaming(p); }}><Pencil size={15}/>Rename</button>
              <button role="menuitem" onClick={() => { setMenu(null); duplicate(p); }}><Copy size={15}/>Duplicate</button>
              <button role="menuitem" className="danger-item" onClick={() => { setMenu(null); setDeleting(p); }}><Trash2 size={15}/>Delete</button>
            </div>}
          </div>}
      </div>)}</div>}
    {selecting && <div className="batch-bar" role="region" aria-label="Batch export">
      <div><strong>{picked.length ? `${picked.length} selected` : 'Choose up to 6 projects'}</strong>
        <div className="batch-ratios">{RATIOS.map(([r, name]) => <button key={r} className={ratios.includes(r) ? 'on' : ''} aria-pressed={ratios.includes(r)} onClick={() => setRatios(list => list.includes(r) ? (list.length > 1 ? list.filter(x => x !== r) : list) : [...list, r])}>{r}<small>{name}</small></button>)}</div>
      </div>
      {pro ? <button className="button primary" disabled={!picked.length || busy} onClick={batch}>{busy ? <LoaderCircle size={17} className="spin"/> : <Film size={17}/>}Export {total || ''} video{total === 1 ? '' : 's'}</button> :
        <button className="button primary" onClick={guest ? onUpgrade : onUpgrade}><Crown size={16}/>Batch export is Pro</button>}
    </div>}
    {renaming && <Prompt title="Rename project" label="Project name" value={renaming.name} busy={busy} onSubmit={rename} onCancel={() => setRenaming(null)}/>}
    {deleting && <Confirm title={`Delete “${deleting.name}”?`} text="This removes the project and any videos you exported from it. It can’t be undone." busy={busy} onConfirm={remove} onCancel={() => setDeleting(null)}/>}
  </div>;
}
