import React, {useEffect, useRef, useState} from 'react';
import {Crown, ImagePlus, LoaderCircle, Trash2} from 'lucide-react';

const CORNERS = [['top-left', 'Top left'], ['top-right', 'Top right'], ['bottom-left', 'Bottom left'], ['bottom-right', 'Bottom right']];
const SWATCHES = ['#1b2c24', '#1b1b1b', '#1f3a8a', '#b4321b', '#0a7a75', '#6d28d9'];

// A small business's look, applied to every export: the colour of the drawn lines and a logo in the corner.
export default function BrandKit({kit, api, pro, onSaved, onUpgrade, onError}) {
  const [draft, setDraft] = useState(kit), [saving, setSaving] = useState(false), [uploading, setUploading] = useState(false), file = useRef(null);
  useEffect(() => setDraft(kit), [kit]);
  const locked = !pro, set = patch => setDraft(d => ({...d, ...patch}));
  const dirty = ['name', 'ink_color', 'logo_corner', 'enabled'].some(k => draft[k] !== kit[k]);
  const ink = draft.ink_color || '#1d2c24';

  async function save() {
    setSaving(true);
    try { onSaved(await api('/api/brand', {method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({name: draft.name, ink_color: draft.ink_color, logo_corner: draft.logo_corner, enabled: draft.enabled})})); }
    catch (e) { onError(e.message); } finally { setSaving(false); }
  }
  async function upload(chosen) {
    if (!chosen) return;
    setUploading(true);
    const body = new FormData(); body.append('file', chosen);
    try { onSaved(await api('/api/brand/logo', {method: 'POST', body})); } catch (e) { onError(e.message); } finally { setUploading(false); if (file.current) file.current.value = ''; }
  }
  async function removeLogo() {
    try { onSaved(await api('/api/brand/logo', {method: 'DELETE'})); } catch (e) { onError(e.message); }
  }
  const corner = draft.logo_corner;

  return <div className="library-page brand-page">
    <div className="eyebrow">Pro</div>
    <div className="heading-row"><div><h1>Brand kit</h1><p>Make every video look like yours: your colour for the drawn lines and your logo in the corner.</p></div>
      {locked && <button className="button primary" onClick={onUpgrade}><Crown size={16}/>Upgrade to Pro</button>}</div>
    <div className={`brand-grid ${locked ? 'locked' : ''}`}>
      <section className="brand-form" aria-disabled={locked}>
        <label className="field-label" htmlFor="brand-name">Brand name <span>optional</span></label>
        <input id="brand-name" className="text-input" value={draft.name} maxLength={60} placeholder="Little Crumb Coffee Co." disabled={locked} onChange={e => set({name: e.target.value})}/>
        <div className="settings-divider"/>
        <div className="field-label">Drawing colour <span>{draft.ink_color || 'Default ink'}</span></div>
        <div className="swatches">
          <button className={`swatch default ${!draft.ink_color ? 'on' : ''}`} disabled={locked} onClick={() => set({ink_color: ''})} aria-label="Default colour">Default</button>
          {SWATCHES.map(c => <button key={c} className={`swatch ${draft.ink_color === c ? 'on' : ''}`} style={{background: c}} disabled={locked} onClick={() => set({ink_color: c})} aria-label={`Use ${c}`}/>)}
          <label className="swatch custom" title="Pick any colour"><input type="color" value={ink} disabled={locked} onChange={e => set({ink_color: e.target.value})} aria-label="Custom colour"/></label>
        </div>
        <div className="settings-divider"/>
        <div className="field-label">Logo <span>PNG, JPG or WebP · up to 5 MB</span></div>
        <input ref={file} type="file" accept="image/png,image/jpeg,image/webp" className="hidden" onChange={e => upload(e.target.files[0])}/>
        <div className="logo-row">
          <div className="logo-box">{kit.logo ? <img src={kit.logo} alt="Your logo"/> : <ImagePlus size={22}/>}</div>
          <div className="logo-actions">
            <button className="button secondary" disabled={locked || uploading} onClick={() => file.current.click()}>{uploading && <LoaderCircle size={15} className="spin"/>}{kit.logo ? 'Replace logo' : 'Upload logo'}</button>
            {kit.logo && <button className="icon-button" aria-label="Remove logo" title="Remove logo" disabled={locked} onClick={removeLogo}><Trash2 size={16}/></button>}
          </div>
        </div>
        <div className="field-label">Logo position</div>
        <div className="corner-options">{CORNERS.map(([id, label]) => <button key={id} className={corner === id ? 'on' : ''} disabled={locked} onClick={() => set({logo_corner: id})} aria-pressed={corner === id}>{label}</button>)}</div>
        <small className="setting-hint">On vertical (9:16) videos the logo moves to the top so it isn’t hidden by Reels and TikTok buttons.</small>
        <div className="settings-divider"/>
        <button className="toggle-row" role="switch" aria-checked={draft.enabled} disabled={locked} onClick={() => set({enabled: !draft.enabled})}>
          <span><strong>Apply to my exports</strong><small>Turn off to export without the brand kit</small></span><span className={`switch ${draft.enabled ? 'on' : ''}`}><i/></span>
        </button>
        <button className="button primary save-brand" disabled={locked || !dirty || saving} onClick={save}>{saving && <LoaderCircle size={16} className="spin"/>}Save brand kit</button>
      </section>
      <section className="brand-preview" aria-label="Preview">
        <div className="frame">
          <svg viewBox="0 0 320 180" role="img" aria-label="A drawing in your colour with your logo">
            <rect width="320" height="180" fill="#faf9f6"/>
            <path d="M92 132c-6-38 8-70 36-82 22-10 50-4 62 18 14 26 2 62-24 74-24 12-64 8-74-10z" fill="none" stroke={ink} strokeWidth="4" strokeLinecap="round"/>
            <path d="M120 66c6-14 22-22 38-18M140 92c10-4 24-2 32 6M118 112c14 8 34 8 48-2" fill="none" stroke={ink} strokeWidth="3" strokeLinecap="round" opacity=".85"/>
          </svg>
          {draft.enabled && kit.logo && <img className={`preview-logo ${corner}`} src={kit.logo} alt=""/>}
        </div>
        <p className="setting-hint">{draft.enabled ? 'This is roughly how your exports will look.' : 'Brand kit is off for your exports.'}{draft.name && <> · <strong>{draft.name}</strong></>}</p>
      </section>
    </div>
    {locked && <p className="brand-lock"><Crown size={15}/>The brand kit is part of Strokeberry Pro.</p>}
  </div>;
}
