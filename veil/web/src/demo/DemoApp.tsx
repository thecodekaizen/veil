import { useEffect, useMemo, useRef, useState } from 'react';
import type { Manifest, Status } from './types';
import './demo.css';

const RUN = new URLSearchParams(location.search).get('run')?.replace(/[^a-z0-9-]/gi, '') || 'c2';
const BASE = import.meta.env.BASE_URL + 'demo/' + RUN + '/';

export default function DemoApp() {
  const [m, setM] = useState<Manifest | null>(null);
  const [err, setErr] = useState('');
  const [t, setT] = useState(0);
  const inV = useRef<HTMLVideoElement>(null);
  const outV = useRef<HTMLVideoElement>(null);
  const cv = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    fetch(BASE + 'manifest.json').then(r => r.json()).then(setM).catch(e => setErr(String(e)));
  }, []);

  const byFrame = useMemo(() => {
    const d = new Map<number, { box: number[]; label: string; source: string }[]>();
    m?.regions.forEach(r => r.frames.forEach(([f, ...box]) => {
      d.set(f, [...(d.get(f) ?? []), { box, label: r.label, source: r.source }]);
    }));
    return d;
  }, [m]);

  useEffect(() => {
    if (!m || !cv.current) return;
    const c = cv.current, ctx = c.getContext('2d')!;
    c.width = m.video.width; c.height = m.video.height;
    ctx.clearRect(0, 0, c.width, c.height);
    const frame = Math.min(m.video.frames - 1, Math.floor(t * m.video.fps));
    ctx.lineWidth = Math.max(2, c.width / 320); ctx.font = `${Math.round(c.width / 50)}px monospace`;
    (byFrame.get(frame) ?? []).forEach(({ box: [x1, y1, x2, y2], label, source }, i) => {
      ctx.strokeStyle = ctx.fillStyle = source === 'spark' ? '#e8b04a' : '#9a968d';
      ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
      ctx.fillText(`${source}: ${label}`, x1 + 3, y1 - 4 - (i % 3) * Math.round(c.width / 45));
    });
  }, [t, m, byFrame]);

  const seek = (s: number) => { [inV.current, outV.current].forEach(v => { if (v) v.currentTime = s; }); setT(s); };
  const play = () => { inV.current?.play(); outV.current?.play(); };
  const pause = () => { inV.current?.pause(); outV.current?.pause(); };

  if (err) return <main className="demo"><p>Could not load demo data: {err}</p></main>;
  if (!m) return <main className="demo"><p className="dim">Loading…</p></main>;
  const n = (s: Status) => m.findings.filter(f => f.status === s).length;
  const notRun = m.checks.filter(c => c.status === 'NOT_CHECKED').length;
  const headline = n('UNRESOLVED')
    ? `${n('UNRESOLVED')} unresolved finding(s). Review them before sharing.`
    : 'No unresolved risks found by the checks listed below.';
  const dur = m.video.duration_s;
  const spans = m.regions.map(r => ({ r, a: r.frames[0][0] / m.video.fps, b: (r.frames[r.frames.length - 1][0] + 1) / m.video.fps }));

  return (
    <main className="demo">
      <h1>Veil</h1>
      <p className="dim">Open-vocabulary privacy-risk audit for creator videos. Demo data: {m.provenance}.</p>
      <div className="panel headline"><b>{headline}</b>
        {(n('NOT_CHECKED') > 0 || notRun > 0) && <> {n('NOT_CHECKED')} item(s) and {notRun} check(s) were not checked.</>}
        <div className="dim">COVERED {n('COVERED')} · UNRESOLVED {n('UNRESOLVED')} · NOT_CHECKED {n('NOT_CHECKED')}</div></div>

      <div className="videos">
        <figure><figcaption>Input with model-proposed regions</figcaption>
          <div className="stack"><video ref={inV} src={BASE + 'input.mp4#t=0.1'} preload="auto" muted playsInline onTimeUpdate={e => setT(e.currentTarget.currentTime)} />
            <canvas ref={cv} /></div></figure>
        <figure><figcaption>Output (covers applied, number muted)</figcaption>
          <video ref={outV} src={BASE + 'output.mp4#t=0.1'} preload="auto" playsInline /></figure>
      </div>
      <div className="controls">
        <button onClick={play}>Play both</button><button onClick={pause}>Pause</button>
        <input type="range" min={0} max={dur} step={0.05} value={t} onChange={e => seek(Number(e.target.value))} aria-label="Seek" />
        <span className="dim">{t.toFixed(1)} / {dur.toFixed(1)} s</span>
      </div>

      <h2>Timeline</h2>
      <div className="timeline" role="img" aria-label="Timeline of covered regions and muted audio">
        {spans.map(({ r, a, b }) => (
          <div key={r.concept_id + a} className="row"><span className="lbl">{r.source}: {r.label}</span>
            <div className="track"><i className={r.source} style={{ left: `${a / dur * 100}%`, width: `${(b - a) / dur * 100}%` }} /></div></div>))}
        <div className="row"><span className="lbl">audio muted</span><div className="track">
          {m.audio.muted_intervals.map(([a, b]) => <i key={a} className="mute" style={{ left: `${a / dur * 100}%`, width: `${(b - a) / dur * 100}%` }} />)}</div></div>
        <div className="cursor" style={{ left: `calc(var(--lbl) + (100% - var(--lbl)) * ${t / dur})` }} />
      </div>
      <p className="dim">Spoken number localized to {m.audio.pii.map(p => `${p.t_start.toFixed(1)}–${p.t_end.toFixed(1)} s`).join(', ') || 'none'} at
        {' '}{m.audio.window_s} s window precision{m.audio.pii.some(p => p.precision === 'window_voiced') ? ' (narrowed to voiced audio, post-gate)' : ''}, then padded by {m.audio.bleep_pad_s} s. Transcript: “{m.audio.transcript}”.</p>

      {m.verify && m.verify.length > 0 && <>
        <h2>Mask check (post-gate)</h2>
        <p className="dim">Does each SAM mask contain the text Spark said it would? Local OCR reads the masked box; a mask without the claimed text is removed before redaction.</p>
        <table><tbody>{m.verify.map(v => (
          <tr key={v.track_id} className="verify"><td className={v.status === 'verified' ? 'COVERED' : 'UNRESOLVED'}>{v.status.toUpperCase()}</td>
            <td>{v.concept_id.replace(/^spark-/, '').replace(/-/g, ' ')}<div className="dim">claimed: {v.claimed.join(', ')}</div></td>
            <td>OCR in mask: “{v.ocr_text.slice(0, 3).join(' / ')}”<div className="dim">frames {v.frames_checked.join(', ')}</div></td></tr>))}</tbody></table>
      </>}

      <h2>Findings</h2>
      <table><tbody>{m.findings.map(f => (
        <tr key={f.finding_id}><td className={f.status}>{f.status}</td>
          <td>{f.label}<div className="dim">{f.kind} · {f.source}</div></td><td>{f.reasons.join(' ')}</td></tr>))}</tbody></table>

      <h2>Checks listed</h2>
      <table><tbody>{m.checks.map(c => (
        <tr key={c.check_id}><td className={c.status === 'RAN' ? 'COVERED' : 'NOT_CHECKED'}>{c.status}</td>
          <td>{c.description}<div className="dim">{c.detail}</div></td></tr>))}</tbody></table>
      {m.concepts_without_masks.length > 0 && <p className="dim">Proposed but not found in the video: {m.concepts_without_masks.join(', ')}.</p>}

      <h2>Limitations</h2>
      <ul>{m.limitations.map(l => <li key={l}>{l}</li>)}</ul>
      <p className="dim">Frames, video and audio were sent to Meta model APIs ({m.models.discover}, {m.models.track}, {m.models.listen});
        {' '}{m.cost.calls} calls, {m.cost.failed} failed, est. ${m.cost.estimated_usd.toFixed(2)}{m.cost.unpriced ? ` (${m.cost.unpriced} without a price estimate)` : ''}. Processing is not local.</p>
      <footer>{m.footer}</footer>
    </main>
  );
}
