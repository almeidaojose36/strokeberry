import React, {useEffect, useRef, useState} from 'react';
import {LoaderCircle, X} from 'lucide-react';

function useEscape(onClose) {
  useEffect(() => { const close = e => { if (e.key === 'Escape') onClose(); }; window.addEventListener('keydown', close); return () => window.removeEventListener('keydown', close); }, []);
}

// "Are you sure?" for deleting things.
export function Confirm({title, text, confirm = 'Delete', danger = true, busy, onConfirm, onCancel}) {
  useEscape(onCancel);
  return <div className="modal-backdrop" onClick={onCancel}>
    <section className="modal small-modal" role="dialog" aria-modal="true" aria-labelledby="confirm-title" onClick={e => e.stopPropagation()}>
      <h2 id="confirm-title">{title}</h2>
      <p className="small-modal-text">{text}</p>
      <div className="small-modal-actions">
        <button className="button secondary" onClick={onCancel} disabled={busy}>Cancel</button>
        <button className={`button ${danger ? 'danger' : 'primary'}`} onClick={onConfirm} disabled={busy} autoFocus>{busy && <LoaderCircle size={16} className="spin"/>}{confirm}</button>
      </div>
    </section>
  </div>;
}

// A single text field in a dialog, e.g. to rename a project or name a saved style.
export function Prompt({title, label, value = '', confirm = 'Save', maxLength = 100, busy, onSubmit, onCancel}) {
  const [text, setText] = useState(value), input = useRef(null);
  useEscape(onCancel);
  useEffect(() => { input.current?.focus(); input.current?.select(); }, []);
  return <div className="modal-backdrop" onClick={onCancel}>
    <form className="modal small-modal" role="dialog" aria-modal="true" aria-labelledby="prompt-title" onClick={e => e.stopPropagation()}
      onSubmit={e => { e.preventDefault(); if (text.trim()) onSubmit(text.trim()); }}>
      <button type="button" className="icon-button" aria-label="Close" onClick={onCancel}><X size={20}/></button>
      <h2 id="prompt-title">{title}</h2>
      <label className="field-label" htmlFor="prompt-input">{label}</label>
      <input id="prompt-input" ref={input} className="text-input" value={text} maxLength={maxLength} onChange={e => setText(e.target.value)}/>
      <div className="small-modal-actions">
        <button type="button" className="button secondary" onClick={onCancel} disabled={busy}>Cancel</button>
        <button type="submit" className="button primary" disabled={busy || !text.trim()}>{busy && <LoaderCircle size={16} className="spin"/>}{confirm}</button>
      </div>
    </form>
  </div>;
}
