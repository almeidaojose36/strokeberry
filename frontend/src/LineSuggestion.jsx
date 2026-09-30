import React, {useEffect, useState} from 'react';
import {LoaderCircle, Sparkles, X} from 'lucide-react';

// Offers the extra lines the artwork was missing (fur tufts, tail tips, folds). Nothing changes until the user accepts.
function Overlay({project, lines}) {
  return <div className="suggest-frame" style={{aspectRatio: `${project.width} / ${project.height}`}}>
    <img src={project.source} alt=""/>
    {lines && <svg viewBox={`0 0 ${project.width} ${project.height}`} preserveAspectRatio="none" aria-hidden="true">
      {lines.map((line, i) => <polyline key={i} points={line.map(p => p.join(',')).join(' ')} fill="none" stroke="var(--accent, #e0245e)" strokeWidth={Math.max(2, project.width / 260)} strokeLinecap="round" strokeLinejoin="round"/>)}
    </svg>}
  </div>;
}

export function SuggestionDialog({project, busy, onChoose, onClose}) {
  useEffect(() => { const close = e => { if (e.key === 'Escape') onClose(); }; window.addEventListener('keydown', close); return () => window.removeEventListener('keydown', close); }, []);
  const {count, lines} = project.enhance;
  return <div className="modal-backdrop" onClick={onClose}>
    <section className="modal suggest-modal" role="dialog" aria-modal="true" aria-labelledby="suggest-title" onClick={e => e.stopPropagation()}>
      <button className="icon-button" aria-label="Close" onClick={onClose}><X size={20}/></button>
      <h2 id="suggest-title">Improve your lines?</h2>
      <p className="small-modal-text">We found {count} place{count === 1 ? '' : 's'} where your image has a colour edge but no drawn line. Adding them makes the drawing look more finished. Your image itself is never changed.</p>
      <div className="suggest-compare">
        <figure><Overlay project={project}/><figcaption>Your image</figcaption></figure>
        <figure><Overlay project={project} lines={lines}/><figcaption>With {count} added line{count === 1 ? '' : 's'}</figcaption></figure>
      </div>
      <div className="small-modal-actions">
        <button className="button secondary" onClick={() => onChoose(false)} disabled={busy}>Keep my original</button>
        <button className="button primary" onClick={() => onChoose(true)} disabled={busy} autoFocus>{busy && <LoaderCircle size={16} className="spin"/>}Add these lines</button>
      </div>
    </section>
  </div>;
}

// The one-line prompt under the preview.
export function SuggestionBar({project, busy, onReview, onUndo}) {
  const state = project.enhance?.state;
  if (!project.enhance || project.mode === 'steps') return null;
  if (state === 'accepted') return <div className="suggest-bar done"><Sparkles size={16}/><span>{project.enhance.count} extra line{project.enhance.count === 1 ? '' : 's'} added to your drawing.</span><button onClick={() => onUndo()} disabled={busy}>Undo</button></div>;
  return <div className="suggest-bar"><Sparkles size={16}/><span>{state === 'rejected' ? 'Extra lines are available for this image.' : `We can add ${project.enhance.count} missing line${project.enhance.count === 1 ? '' : 's'} to make this drawing look more finished.`}</span><button onClick={onReview} disabled={busy}>Preview</button></div>;
}
