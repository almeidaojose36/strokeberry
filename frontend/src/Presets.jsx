import React, {useState} from 'react';
import {Bookmark, Trash2} from 'lucide-react';
import {Prompt} from './Dialogs.jsx';

const same = (a, b) => ['style', 'duration', 'ratio', 'resolution', 'color', 'pen'].every(k => a[k] === b[k]);

// Saved styles: one click to bring back a favourite combination of settings.
export default function Presets({presets, settings, limit, busy, onApply, onSave, onDelete}) {
  const [naming, setNaming] = useState(false);
  const active = presets.find(p => same(p.settings, settings));
  return <div className="preset-bar">
    <div className="preset-row">
      <Bookmark size={15}/>
      <select aria-label="Saved styles" value={active?.id || ''} onChange={e => { const p = presets.find(x => x.id === e.target.value); if (p) onApply(p.settings); }}>
        <option value="">{presets.length ? 'Saved styles' : 'No saved styles yet'}</option>
        {presets.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
      </select>
      {active ? <button className="icon-button" aria-label={`Delete ${active.name}`} title="Delete this saved style" onClick={() => onDelete(active)}><Trash2 size={15}/></button> :
        <button className="link-button" onClick={() => setNaming(true)}>Save current</button>}
    </div>
    {naming && <Prompt title="Save this style" label="Name" confirm="Save style" maxLength={40} busy={busy} value={`${settings.style === 'ink' ? 'Ink' : 'Pencil'} ${settings.ratio}`}
      onSubmit={name => { setNaming(false); onSave(name); }} onCancel={() => setNaming(false)}/>}
  </div>;
}
