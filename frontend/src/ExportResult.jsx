import React, {useState} from 'react';
import {ArrowDownToLine, Check, Crown, LayoutGrid, LoaderCircle, Share2, Sparkles} from 'lucide-react';

const OTHER_RATIOS = {'16:9': ['9:16', '1:1'], '9:16': ['1:1', '16:9'], '1:1': ['9:16', '16:9']};
const RATIO_NAME = {'16:9': 'widescreen', '9:16': 'Reels & TikTok', '1:1': 'square post'};

// "Your video is ready": the video, download and share, then easy next steps so people keep making things.
export default function ExportResult({job, sameProject, plan, remaining, onAgain, onAllFormats, onAnother, onUpgrade, onClose}) {
  const [sharing, setSharing] = useState(false);
  const canShare = typeof navigator !== 'undefined' && !!navigator.canShare && !!navigator.share;
  const pro = plan === 'pro', free = plan === 'free';
  async function share() {
    setSharing(true);
    try {
      const blob = await (await fetch(job.url)).blob();
      const file = new File([blob], 'strokeberry-video.mp4', {type: 'video/mp4'});
      if (navigator.canShare({files: [file]})) await navigator.share({files: [file], title: 'Made with Strokeberry'});
    } catch { /* cancelled or unsupported */ }
    setSharing(false);
  }
  const ratio = job.settings.ratio, other = job.settings.style === 'ink' ? 'pencil' : 'ink';
  return <div className="ready">
    <span className="dialog-icon"><Check size={27}/></span>
    <div className="eyebrow">Export</div>
    <h2 id="dialog-title">Your video is ready</h2>
    <video src={job.url} controls playsInline className="result-video"/>
    <div className="ready-actions">
      <a className="button primary" href={job.url} download><ArrowDownToLine size={18}/>Download MP4</a>
      {canShare && <button className="button secondary" onClick={share} disabled={sharing}>{sharing ? <LoaderCircle size={16} className="spin"/> : <Share2 size={16}/>}Share</button>}
    </div>
    <p className="ready-tip">Post it as a Reel, TikTok or Short. Vertical 9:16 videos get the most reach.</p>
    {free && <div className="ready-upsell"><span><strong>Want it without the watermark?</strong> A video pack or Pro removes it and the end card.</span><button className="button primary" onClick={onUpgrade}><Crown size={15}/>See Pro</button></div>}
    {sameProject && <div className="ready-next">
      <p className="ready-next-title">Make it again</p>
      <div className="chips">
        {OTHER_RATIOS[ratio].map(r => <button key={r} className="chip" onClick={() => onAgain({ratio: r})}>As {r}<small>{RATIO_NAME[r]}</small></button>)}
        <button className="chip" onClick={() => onAgain({style: other})}>Try {other === 'ink' ? 'Ink' : 'Pencil'}<small>{other === 'ink' ? 'bold lines' : 'soft strokes'}</small></button>
        {pro && <button className="chip chip-pro" onClick={onAllFormats}><Sparkles size={14}/>All 3 formats<small>one click</small></button>}
      </div>
      {free && remaining != null && <small className="ready-next-note">Each new export uses 1 of your 3 free videos this month ({remaining} left).</small>}
    </div>}
    <button className="text-button" onClick={onAnother}><LayoutGrid size={15}/>Make another video</button>
  </div>;
}
