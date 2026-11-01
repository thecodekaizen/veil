import { useCallback, useEffect, useRef, useState } from 'react';
import { media, regionsAt, type Manifest } from './data';

/**
 * The product's core capability as one surface: the real input (with the regions models proposed) and Veil's real
 * exported file, frame-synced, split by a draggable divider. Left of the divider = input, right = export.
 */
export function Compare({ m, run, autoPlay = false, focus, onTime, controls = true, initialSplit = 52, playing: playingProp, startAt = 0 }: {
  m: Manifest; run: string; autoPlay?: boolean; focus?: string | null; onTime?: (t: number) => void; controls?: boolean;
  initialSplit?: number; playing?: boolean; startAt?: number;
}) {
  const inV = useRef<HTMLVideoElement>(null);
  const outV = useRef<HTMLVideoElement>(null);
  const cv = useRef<HTMLCanvasElement>(null);
  const stage = useRef<HTMLDivElement>(null);
  const [split, setSplit] = useState(initialSplit);
  const [t, setT] = useState(0);
  const [playing, setPlaying] = useState(autoPlay);
  const dragging = useRef(false);

  // keep the export locked to the input clock and draw evidence frames every animation frame
  useEffect(() => {
    let raf = 0;
    const tick = () => {
      const a = inV.current, b = outV.current, c = cv.current;
      if (a && b) {
        if (Math.abs(b.currentTime - a.currentTime) > 0.08) b.currentTime = a.currentTime;
        if (a.paused !== b.paused) { if (a.paused) b.pause(); else b.play().catch(() => {}); }
        setT(a.currentTime);
        onTime?.(a.currentTime);
      }
      if (c && a) {
        const ctx = c.getContext('2d')!;
        if (c.width !== m.video.width) { c.width = m.video.width; c.height = m.video.height; }
        ctx.clearRect(0, 0, c.width, c.height);
        const frame = Math.min(m.video.frames - 1, Math.floor(a.currentTime * m.video.fps));
        const lw = Math.max(2, c.width / 360);
        ctx.font = `600 ${Math.round(c.width / 64)}px "JetBrains Mono", monospace`;
        regionsAt(m, frame).forEach(({ box: [x1, y1, x2, y2], label, source, concept }) => {
          const hot = !focus || focus === concept;
          const col = source === 'spark' ? '232,176,74' : '154,150,141';
          ctx.globalAlpha = hot ? 1 : 0.25;
          ctx.strokeStyle = `rgb(${col})`; ctx.lineWidth = lw;
          ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
          const tag = `${source === 'spark' ? 'Spark' : 'baseline'} · ${label}`;
          const tw = ctx.measureText(tag).width + 12, th = Math.round(c.width / 44);
          const ty = y1 - th - 2 > 0 ? y1 - th - 2 : y2 + 2;
          ctx.fillStyle = `rgb(${col})`; ctx.fillRect(x1, ty, tw, th);
          ctx.fillStyle = '#0b0d10'; ctx.fillText(tag, x1 + 6, ty + th * 0.72);
        });
        ctx.globalAlpha = 1;
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [m, focus, onTime]);

  useEffect(() => {
    if (playingProp === undefined) return;
    if (playingProp) inV.current?.play().catch(() => {}); else inV.current?.pause();
  }, [playingProp]);

  const setFromX = useCallback((clientX: number) => {
    const r = stage.current!.getBoundingClientRect();
    setSplit(Math.max(4, Math.min(96, ((clientX - r.left) / r.width) * 100)));
  }, []);

  const toggle = () => {
    const a = inV.current!;
    if (a.paused) { a.play().catch(() => {}); setPlaying(true); } else { a.pause(); setPlaying(false); }
  };
  const seek = (s: number) => { if (inV.current) inV.current.currentTime = s; };
  const dur = m.video.duration_s;

  return (
    <div className="cmp">
      <div
        ref={stage}
        className="cmp-stage"
        style={{ aspectRatio: `${m.video.width} / ${m.video.height}` }}
        onPointerDown={e => { dragging.current = true; (e.target as Element).setPointerCapture?.(e.pointerId); setFromX(e.clientX); }}
        onPointerMove={e => dragging.current && setFromX(e.clientX)}
        onPointerUp={() => { dragging.current = false; }}
      >
        <video ref={inV} src={media(run, 'input.mp4')} muted playsInline loop autoPlay={autoPlay} preload="auto"
          onLoadedMetadata={e => { if (startAt) e.currentTarget.currentTime = startAt; }} />
        <canvas ref={cv} aria-hidden="true" />
        <div className="cmp-out" style={{ clipPath: `inset(0 0 0 ${split}%)` }}>
          <video ref={outV} src={media(run, 'output.mp4')} muted playsInline loop preload="auto" />
        </div>
        <div className="cmp-label l"><span className="dot" /> Input · what the models found</div>
        <div className="cmp-label r" style={{ opacity: split > 80 ? 0 : 1 }}>Export · what Veil wrote</div>
        <div className="cmp-handle" style={{ left: `${split}%` }}>
          <button
            type="button"
            aria-label="Drag to compare input and exported video"
            role="slider" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(split)}
            onKeyDown={e => {
              if (e.key === 'ArrowLeft') setSplit(s => Math.max(4, s - 4));
              if (e.key === 'ArrowRight') setSplit(s => Math.min(96, s + 4));
            }}
          >
            <svg width="22" height="22" viewBox="0 0 22 22" aria-hidden="true"><path d="M8 6l-4 5 4 5M14 6l4 5-4 5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg>
          </button>
        </div>
      </div>
      {controls && (
        <div className="cmp-transport">
          <button type="button" className="icon-btn" onClick={toggle} aria-label={playing ? 'Pause' : 'Play'}>
            {playing
              ? <svg width="16" height="16" viewBox="0 0 16 16"><rect x="3" y="2" width="4" height="12" rx="1" fill="currentColor" /><rect x="9" y="2" width="4" height="12" rx="1" fill="currentColor" /></svg>
              : <svg width="16" height="16" viewBox="0 0 16 16"><path d="M4 2.5v11l9.5-5.5z" fill="currentColor" /></svg>}
          </button>
          <input type="range" min={0} max={dur} step={0.04} value={t} aria-label="Seek" onChange={e => seek(Number(e.target.value))} style={{ ['--p' as string]: `${(t / dur) * 100}%` }} />
          <span className="mono small muted tc">{t.toFixed(1)} / {dur.toFixed(1)} s</span>
        </div>
      )}
    </div>
  );
}

export function seekVideo(container: HTMLElement | null, s: number) {
  const v = container?.querySelector('video');
  if (v) v.currentTime = s;
}
