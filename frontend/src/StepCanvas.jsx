import React, {useEffect, useRef, useState} from 'react';
import {eventPosition} from './drawing.js';
import {advanceSweep} from './sweep.js';

export function stageAt(stages, progress) {
  let index=stages.findIndex(stage=>progress<stage.end);
  if(index<0)index=stages.length-1;
  const stage=stages[index];
  return {index,local:Math.max(0,Math.min(1,(progress-stage.start)/(stage.end-stage.start)))};
}

export default function StepCanvas({project,settings,time,original,onReady}) {
  const ref=useRef(null),assets=useRef(null);const [version,setVersion]=useState(0);
  useEffect(()=>{
    let alive=true;assets.current=null;
    const load=src=>new Promise((resolve,reject)=>{const image=new Image();image.onload=()=>resolve(image);image.onerror=reject;image.src=src});
    Promise.all(project.stages.map(async stage=>{
      const [image,rank]=await Promise.all([load(stage.source),load(stage.reveal)]);
      const c=document.createElement('canvas');c.width=project.width;c.height=project.height;
      const ctx=c.getContext('2d',{willReadFrequently:true});ctx.drawImage(image,0,0);const pixels=ctx.getImageData(0,0,c.width,c.height).data;
      ctx.drawImage(rank,0,0);const ranks=ctx.getImageData(0,0,c.width,c.height).data;
      const labels=Uint8Array.from({length:project.width*project.height},(_,i)=>ranks[i*4]);
      return {image,pixels,ranks,labels};
    })).then(stages=>{if(!alive)return;const buffer=document.createElement('canvas');buffer.width=project.width;buffer.height=project.height;
      assets.current={stages,buffer,ctx:buffer.getContext('2d'),pixels:new ImageData(project.width,project.height)};setVersion(v=>v+1);onReady?.();
    }).catch(()=>{if(alive)onReady?.('Could not load the drawing stages. Reopen this project to try again.')});
    return()=>{alive=false};
  },[project]);
  useEffect(()=>{
    const canvas=ref.current,data=assets.current;if(!data||!canvas)return;
    const [width,height]=settings.ratio==='9:16'?[540,960]:settings.ratio==='1:1'?[720,720]:[960,540];canvas.width=width;canvas.height=height;
    const ctx=canvas.getContext('2d');ctx.fillStyle='#faf9f6';ctx.fillRect(0,0,width,height);
    const scale=Math.min(width*.9/project.width,height*.9/project.height),ox=(width-project.width*scale)/2,oy=(height-project.height*scale)/2;
    const {index,local}=stageAt(project.stages,time/settings.duration),stage=project.stages[index],amount=Math.min(1,local/(1-Math.min(.1,1.5/Math.max(.1,(stage.end-stage.start)*settings.duration))));
    if(original){ctx.drawImage(data.stages.at(-1).image,ox,oy,project.width*scale,project.height*scale);return}
    const target=data.stages[index],previous=index?data.stages[index-1].pixels:null,pixels=data.pixels.data,paper=[250,249,246];
    const mask=project.reveal_version>=2?advanceSweep(data,project.width,project.height,index,amount,stage.timeline,project.reveal_version>=3?target.labels:null):null;
    for(let i=0;i<pixels.length;i+=4){const alpha=mask?mask[i/4]:Math.max(0,Math.min(1,(amount*270-target.ranks[i])/20));
      for(let k=0;k<3;k++)pixels[i+k]=Math.floor((previous?previous[i+k]:paper[k])*(1-alpha)+target.pixels[i+k]*alpha);pixels[i+3]=255;}
    data.ctx.putImageData(data.pixels,0,0);ctx.drawImage(data.buffer,ox,oy,project.width*scale,project.height*scale);
    if(settings.pen&&amount<1){const event=stage.timeline.find(e=>e.end>amount);if(event){const {point,lift}=eventPosition(event,(amount-event.start)/(event.end-event.start));
      const unit=Math.min(width,height)/540;let x=point[0]*scale+ox,y=point[1]*scale+oy;
      if(lift>0){ctx.fillStyle='#dddfd6';ctx.beginPath();ctx.ellipse(x+8*unit,y+3*unit,7*unit,2*unit,0,0,Math.PI*2);ctx.fill()}
      x+=lift*3*unit;y-=lift*10*unit;ctx.fillStyle='#cfa257';ctx.beginPath();ctx.moveTo(x,y);ctx.lineTo(x+17*unit,y-46*unit);ctx.lineTo(x+28*unit,y-40*unit);ctx.lineTo(x+5*unit,y+2*unit);ctx.closePath();ctx.fill();ctx.fillStyle='#3c413b';ctx.beginPath();ctx.arc(x,y,2*unit,0,Math.PI*2);ctx.fill();}}
  },[project,settings,time,original,version]);
  return <canvas ref={ref} aria-label="Step-by-step drawing preview" className={`drawing-canvas ratio-${settings.ratio.replace(':','-')}`}/>;
}
