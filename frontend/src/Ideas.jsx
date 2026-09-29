import React from 'react';
import {Lightbulb} from 'lucide-react';

// Three suggestions that change every week, so there's always something to make.
export default function Ideas({ideas, onUse}) {
  if (!ideas?.length) return null;
  return <section className="ideas" aria-label="Ideas this week">
    <div className="ideas-head"><span className="mini-icon"><Lightbulb size={16}/></span><strong>Ideas this week</strong><small>Fresh suggestions every Monday</small></div>
    <div className="ideas-grid">{ideas.map(idea => <button key={idea.id} className="idea-card" onClick={() => onUse(idea)}>
      <img src={idea.thumb} alt="" loading="lazy"/>
      <span><strong>{idea.title}</strong><small>{idea.tip}</small><em>{idea.style === 'ink' ? 'Ink' : 'Pencil'} · {idea.ratio}</em></span>
    </button>)}</div>
  </section>;
}
