// The backend supplies normalized timing and pressure, so scrubbing, replaying,
// and exporting all use the same deterministic drawing performance.
export function eventPosition(event, fraction) {
  fraction = Math.max(0, Math.min(1, fraction));
  let lift = 0;
  if (event.kind === 'lift') {
    const t = Math.max(0, Math.min(1, (fraction - .15) / .7));
    fraction = t * t * (3 - 2 * t);
    lift = Math.sin(Math.PI * fraction);
  }
  return {
    point: event.a.map((value, k) => value + (event.b[k] - value) * fraction),
    lift,
  };
}

export function drawMark(ctx, a, b, pressure, style, unit) {
  const pencil = style === 'pencil';
  const opacity = pencil ? .35 + .45 * pressure : .65 + .3 * pressure;
  const paper = [250, 249, 246], ink = pencil ? [60, 65, 59] : [29, 44, 36];
  const color = paper.map((value, k) => Math.round(value * (1 - opacity) + ink[k] * opacity));
  ctx.strokeStyle = `rgb(${color.join(',')})`;
  ctx.lineWidth = unit * (pencil ? .5 + .95 * pressure : .7 + 1.5 * pressure);
  ctx.lineCap = 'round';
  ctx.beginPath();
  ctx.moveTo(...a);
  ctx.lineTo(...b);
  ctx.stroke();
}

export function drawTimeline(ctx, events, progress, style, unit, cache) {
  if (cache) {
    // Accumulate completed marks once during playback; rewind rebuilds them.
    if (!cache.initialized || progress < cache.progress) {
      cache.ctx.save();
      cache.ctx.resetTransform();
      cache.ctx.fillStyle = '#faf9f6';
      cache.ctx.fillRect(0, 0, cache.canvas.width, cache.canvas.height);
      cache.ctx.restore();
      cache.index = 0;
      cache.initialized = true;
    }
    while (cache.index < events.length && events[cache.index].end <= progress) {
      const event = events[cache.index++];
      if (event.kind === 'draw') drawMark(cache.ctx, event.a, event.b, event.pressure, style, unit);
    }
    cache.progress = progress;
    ctx.save();
    ctx.resetTransform();
    ctx.drawImage(cache.canvas, 0, 0);
    ctx.restore();
    const event = events[cache.index];
    if (!event || event.start > progress) return {tip: null, lift: 0};
    const position = eventPosition(event, (progress - event.start) / (event.end - event.start));
    if (event.kind === 'draw') drawMark(ctx, event.a, position.point, event.pressure, style, unit);
    return {tip: position.point, lift: position.lift};
  }
  let tip = null, lift = 0;
  for (const event of events) {
    if (event.start > progress) break;
    const fraction = Math.min(1, (progress - event.start) / (event.end - event.start));
    const position = eventPosition(event, fraction);
    if (event.kind === 'draw') drawMark(ctx, event.a, position.point, event.pressure, style, unit);
    if (fraction < 1) {
      tip = position.point;
      lift = position.lift;
      break;
    }
  }
  return {tip, lift};
}
