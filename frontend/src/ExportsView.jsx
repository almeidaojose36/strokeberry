import React, {useEffect, useState} from 'react';
import {ArrowDownToLine, ArrowRight, Film, LoaderCircle, Play, Trash2} from 'lucide-react';
import {Confirm} from './Dialogs.jsx';

const clock = seconds => seconds < 60 ? `${seconds} sec` : `${Math.floor(seconds / 60)} min${seconds % 60 ? ` ${seconds % 60} sec` : ''}`;
const STATUS = {completed: 'Ready', failed: 'Failed', queued: 'Queued', rendering: 'Rendering'};

export default function ExportsView({jobs, projects, api, onOpen, onRefresh, onStudio, onError}) {
  const [deleting, setDeleting] = useState(null), [busy, setBusy] = useState(false);
  const byProject = Object.fromEntries(projects.map(p => [p.id, p]));
  const active = jobs.some(j => ['queued', 'rendering'].includes(j.status));
  // Keep progress moving while anything is still rendering.
  useEffect(() => { if (!active) return; const timer = setInterval(() => onRefresh().catch(() => {}), 2000); return () => clearInterval(timer); }, [active]);

  async function remove() {
    setBusy(true);
    try { await api(`/api/jobs/${deleting.id}`, {method: 'DELETE'}); setDeleting(null); await onRefresh(); }
    catch (e) { onError(e.message); setDeleting(null); } finally { setBusy(false); }
  }
  return <div className="library-page">
    <div className="eyebrow">Exports</div>
    <div className="heading-row"><div><h1>Exported videos</h1><p>Your finished MP4s, ready to watch, download and post.</p></div></div>
    {jobs.length === 0 ? <div className="empty-state"><Film size={40}/><h2>No videos yet</h2><p>Export a video from the studio and it will appear here.</p><button className="button secondary" onClick={onStudio}>Go to studio <ArrowRight size={15}/></button></div> :
      <div className="export-list">{jobs.map(j => {
        const project = byProject[j.project_id], running = ['queued', 'rendering'].includes(j.status), done = j.status === 'completed';
        return <div className="export-card" key={j.id}>
          <button className="export-thumb" disabled={!done} onClick={() => onOpen(j)} aria-label={done ? 'Play video' : 'Not ready yet'}>
            {project ? <img src={project.source} alt="" loading="lazy"/> : <Film size={22}/>}
            {done && <span className="thumb-play"><Play size={16} fill="currentColor"/></span>}
            {running && <span className="thumb-play"><LoaderCircle size={18} className="spin"/></span>}
          </button>
          <div className="export-info">
            <strong>{project?.name || 'Deleted project'}</strong>
            <small>{j.settings.resolution} · {j.settings.ratio} · {clock(j.settings.duration)} · {j.settings.style === 'ink' ? 'Ink' : 'Pencil'} · {new Date(j.created).toLocaleDateString(undefined, {day: 'numeric', month: 'short'})}</small>
            {running && <div className="progress-track slim"><div style={{width: `${j.progress || 0}%`}}/></div>}
            {j.error && <small className="failure-text">{j.error}</small>}
          </div>
          <span className={`status ${j.status}`}>{running && j.progress ? `${j.progress}%` : STATUS[j.status] || j.status}</span>
          <div className="export-actions">
            {done && <button className="button secondary" onClick={() => onOpen(j)}><Play size={15}/>Play</button>}
            {done && <a className="button secondary" href={j.url} download><ArrowDownToLine size={15}/>Download</a>}
            {!running && <button className="icon-button" aria-label="Delete this video" title="Delete" onClick={() => setDeleting(j)}><Trash2 size={17}/></button>}
          </div>
        </div>;
      })}</div>}
    {deleting && <Confirm title="Delete this video?" text="The MP4 will be removed. You can always export it again from the project." busy={busy} onConfirm={remove} onCancel={() => setDeleting(null)}/>}
  </div>;
}
