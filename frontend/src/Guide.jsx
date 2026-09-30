import React, {useState} from 'react';
import {Check, LayoutGrid, Pencil, Play, X} from 'lucide-react';

const STEPS = [
  {image: 'step-1-image', title: 'Add an image', text: 'Upload a PNG, JPG or WebP — or pick one from Examples.'},
  {image: 'step-2-style', title: 'Choose a style', text: 'Pencil or Ink, with the drawing pencil and colour reveal on or off.'},
  {image: 'step-3-preview', title: 'Preview it', text: 'Press play or drag the timeline to watch it draw.'},
  {image: 'step-4-export', title: 'Export', text: 'Pick a format and quality in Video settings, then download your MP4.'},
];

// The "How it works" guide: a one-minute tutorial, the four steps with real screenshots, and image tips.
export default function Guide({account, onExamples}) {
  const [playing, setPlaying] = useState(false);
  const free = account?.plan?.watermark;
  return <div className="guide-body">
    <span className="dialog-icon"><Pencil size={26}/></span>
    <div className="eyebrow">Guide</div>
    <h2 id="dialog-title">How it works</h2>
    <div className="guide-video">
      {playing ? <video src="/guide/tutorial.mp4" poster="/guide/tutorial-poster.webp" controls autoPlay playsInline/> :
        <button className="guide-video-start" onClick={() => setPlaying(true)}>
          <img src="/guide/tutorial-poster.webp" alt=""/>
          <span className="guide-play"><Play size={22} fill="currentColor"/></span>
          <span className="guide-video-label"><strong>Watch the 1-minute tutorial</strong><small>With sound · from upload to download</small></span>
        </button>}
    </div>
    <ol className="guide-steps">
      {STEPS.map((step, i) => <li key={step.image}>
        <img src={`/guide/${step.image}.webp`} alt="" loading="lazy"/>
        <div><span className="guide-number">{i + 1}</span><strong>{step.title}</strong><p>{step.text}</p></div>
      </li>)}
    </ol>
    <button className="guide-callout" onClick={onExamples}><LayoutGrid size={18}/><span><strong>No image handy?</strong> Browse 50+ ready-made examples</span></button>
    <div className="guide-callout static"><span className="guide-steps-icon">1–4</span><span><strong>Got a how-to-draw sheet?</strong> Tap <em>Set up steps</em> under the preview to turn its panels into one video.</span></div>
    <h3 className="guide-subhead">What works best</h3>
    <div className="guide-tips">
      <figure className="good"><img src="/guide/tip-good.webp" alt="A fox illustration with bold outlines on a white background"/><figcaption><Check size={15}/>Bold outlines, plain background</figcaption></figure>
      <figure className="bad"><img src="/guide/tip-busy.webp" alt="The same fox on a cluttered background"/><figcaption><X size={15}/>Busy backgrounds and photos</figcaption></figure>
    </div>
    {free && <p className="guide-plan">Free plan: {account.usage.limit} videos every month, up to 1 minute, in 720p with a small watermark. Pro adds Full HD, longer videos and no watermark.</p>}
    <div className="local-note">Your images and videos stay private to you. Strokeberry draws them itself — they’re never sent to a third‑party AI service.</div>
    <p className="modal-note">Need a hand? Email <a className="inline-link" href="mailto:support@strokeberry.com">support@strokeberry.com</a></p>
  </div>;
}
