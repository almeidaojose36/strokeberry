// Exact pixel capsule shared with StepFrames.sweep; only draw events expose ink.
export function sweep(mask, width, event, fraction, labels) {
  const a=event.a, b=a.map((v,k)=>v+(event.b[k]-v)*fraction), d=b.map((v,k)=>v-a[k]);
  const [cx0,cy0,cx1,cy1]=event.clip;
  const x0=Math.max(cx0,Math.floor(Math.min(a[0],b[0])-4)),y0=Math.max(cy0,Math.floor(Math.min(a[1],b[1])-4));
  const x1=Math.min(cx1,Math.ceil(Math.max(a[0],b[0])+4)+1),y1=Math.min(cy1,Math.ceil(Math.max(a[1],b[1])+4)+1);
  const length=Math.max(d[0]*d[0]+d[1]*d[1],1e-12);
  for(let y=y0;y<y1;y++)for(let x=x0;x<x1;x++){
    const t=Math.max(0,Math.min(1,((x-a[0])*d[0]+(y-a[1])*d[1])/length));
    if((!labels || labels[y*width+x]===event.color) && (x-a[0]-t*d[0])**2+(y-a[1]-t*d[1])**2<=16)mask[y*width+x]=1;
  }
}

export function advanceSweep(state, width, height, index, amount, events, labels) {
  if(!state.mask || state.index!==index || amount<state.amount){
    state.mask=new Uint8Array(width*height);state.cursor=0;
  }
  while(state.cursor<events.length){
    const event=events[state.cursor];
    if(event.start>=amount)break;
    if(event.kind==='draw')sweep(state.mask,width,event,Math.min(1,(amount-event.start)/(event.end-event.start)),labels);
    if(event.end>amount)break;
    state.cursor++;
  }
  state.index=index;state.amount=amount;
  return state.mask;
}
