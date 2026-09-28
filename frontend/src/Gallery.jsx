import React, {useEffect, useState} from 'react';
import {LoaderCircle, X} from 'lucide-react';

// "Start from an example": ready-made illustrations that make good drawing videos.
export default function Gallery({api, onClose, onPicked}) {
  const [library, setLibrary] = useState(null), [category, setCategory] = useState('all'), [picking, setPicking] = useState(''), [error, setError] = useState('');
  useEffect(() => { api('/api/library').then(setLibrary).catch(e => setError(e.message)); }, []);
  useEffect(() => { const close = e => { if (e.key === 'Escape') onClose(); }; window.addEventListener('keydown', close); return () => window.removeEventListener('keydown', close); }, []);
  async function pick(item) {
    if (picking) return;
    setPicking(item.id); setError('');
    try { onPicked(await api(`/api/library/${item.id}/use`, {method: 'POST'}), item); }
    catch (e) { setError(e.message); setPicking(''); }
  }
  const items = (library?.items || []).filter(item => category === 'all' || item.category === category);
  return <div className="modal-backdrop" onClick={onClose}>
    <section className="modal gallery-modal" role="dialog" aria-modal="true" aria-labelledby="gallery-title" onClick={e => e.stopPropagation()}>
      <button className="icon-button" aria-label="Close examples" onClick={onClose}><X size={20}/></button>
      <div className="eyebrow">Examples</div>
      <h2 id="gallery-title">Start from an example</h2>
      <p className="gallery-intro">No image handy? Pick one of these and make it your own.</p>
      {library?.categories?.length > 1 && <div className="gallery-filters" role="tablist">
        {[{id: 'all', name: 'All'}, ...library.categories].map(c => <button key={c.id} role="tab" aria-selected={category === c.id} className={category === c.id ? 'active' : ''} onClick={() => setCategory(c.id)}>{c.name}</button>)}
      </div>}
      {error && <p className="failure-text">{error}</p>}
      {!library && !error ? <div className="gallery-loading"><LoaderCircle className="spin" size={24}/></div> :
        <div className="gallery-grid">{items.map(item => <button key={item.id} className="gallery-item" onClick={() => pick(item)} disabled={Boolean(picking)}>
          <img src={item.thumb} alt="" loading="lazy"/>
          <span>{item.title}</span>
          {item.tutorial && <em>Steps</em>}
          {picking === item.id && <i className="gallery-picking"><LoaderCircle className="spin" size={22}/></i>}
        </button>)}</div>}
    </section>
  </div>;
}
