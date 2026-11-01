import { useCallback, useMemo, useRef, useState } from 'react';
import { Compare, seekVideo } from './Compare';
import { RUNS, prettyConcept, useManifest, type Manifest } from './data';
import { Footer, Nav } from './Landing';

type Status = 'COVERED' | 'UNRESOLVED' | 'NOT_CHECKED';
const STATUSES: Status[] = ['COVERED', 'UNRESOLVED', 'NOT_CHECKED'];
const MEANING: Record<Status, string> = {
  COVERED: 'Code verified the cover in the exported file.',
  UNRESOLVED: 'A check found something it could not clear. Review before posting.',
  NOT_CHECKED: 'This item or check could not run. Nothing is claimed about it.',
};

function Tracks({ m, t, focus, onPick }: { m: Manifest; t: number; focus: string | null; onPick: (concept: string, s: number) => void }) {
  const dur = m.video.duration_s;
  const spans = useMemo(() => {
    const by = new Map<string, { label: string; source: string; a: number; b: number }>();
    m.regions.forEach(r => {
      const a = r.frames[0][0] / m.video.fps, b = (r.frames[r.frames.length - 1][0] + 1) / m.video.fps;
      const cur = by.get(r.concept_id);
      by.set(r.concept_id, cur ? { ...cur, a: Math.min(cur.a, a), b: Math.max(cur.b, b) } : { label: r.label, source: r.source, a, b });
    });
    return [...by.entries()];
  }, [m]);
  return (
    <div className="tracks" role="group" aria-label="Tracked regions and muted audio over time">
      {spans.map(([id, s]) => (
        <button key={id} type="button" className={`track-row ${focus === id ? 'on' : ''}`} onClick={() => onPick(id, s.a)}
          aria-label={`${s.source} ${s.label}, ${s.a.toFixed(1)} to ${s.b.toFixed(1)} seconds`}>
          <span className="track-label"><span className={`sw ${s.source}`} />{s.label}</span>
          <span className="track-bar"><i className={s.source} style={{ left: `${(s.a / dur) * 100}%`, width: `${((s.b - s.a) / dur) * 100}%` }} /></span>
        </button>
      ))}
      <div className="track-row static">
        <span className="track-label"><span className="sw mute" />audio muted</span>
        <span className="track-bar">{m.audio.muted_intervals.map(([a, b]) => <i key={a} className="mute" style={{ left: `${(a / dur) * 100}%`, width: `${((b - a) / dur) * 100}%` }} />)}</span>
      </div>
      <div className="playhead" style={{ left: `calc(var(--tl) + (100% - var(--tl)) * ${t / dur})` }} aria-hidden="true" />
    </div>
  );
}

export function Desk({ run }: { run: string }) {
  const { data: m, error } = useManifest(run);
  const [focus, setFocus] = useState<string | null>(null);
  const [filter, setFilter] = useState<Status | 'ALL'>('ALL');
  const [t, setT] = useState(0);
  const stageRef = useRef<HTMLDivElement>(null);
  const onTime = useCallback((s: number) => setT(s), []);
  const meta = RUNS.find(r => r.id === run) ?? RUNS[0];

  const pick = (concept: string | null, s?: number) => {
    setFocus(concept);
    if (s !== undefined) seekVideo(stageRef.current, s + 0.05);
  };
  const conceptFor = (label: string) => m?.regions.find(r => r.label === label)?.concept_id ?? null;

  return (
    <>
      <Nav desk />
      <main className="desk wrap" id="main">
        <div className="desk-head">
          <div>
            <span className="eyebrow">Review desk</span>
            <h1 className="h1 desk-title">{meta.title} <span className="muted">· {meta.kind}</span></h1>
            <p className="muted desk-blurb">{meta.blurb}</p>
          </div>
          <div className="run-tabs" role="tablist" aria-label="Choose a run">
            {RUNS.map(r => (
              <a key={r.id} role="tab" aria-selected={r.id === run} className={`run-tab ${r.id === run ? 'on' : ''}`} href={`#/desk?run=${r.id}`}>
                <span className="mono small">{r.id}</span> {r.title}
              </a>
            ))}
          </div>
        </div>

        {error && (
          <div className="card empty" role="alert">
            <h2 className="h2">This run isn't available.</h2>
            <p className="muted">The demo data for “{run}” couldn't be loaded ({error}). Exported runs live in <span className="mono">veil/web/public/demo/&lt;run&gt;/</span>; create one with <span className="mono">veil export-web &lt;run&gt;</span>.</p>
            <a className="btn btn-ghost" href="#/desk?run=c2">Open the street clip</a>
          </div>
        )}
        {!m && !error && <div className="desk-grid"><div className="cmp-skeleton" /><div className="card skeleton-panel" /></div>}

        {m && (
          <>
            <Verdict m={m} />
            <div className="desk-grid">
              <section className="desk-stage" ref={stageRef} aria-label="Input and exported video">
                <Compare m={m} run={run} focus={focus} onTime={onTime} />
                <Tracks m={m} t={t} focus={focus} onPick={(c, s) => pick(focus === c ? null : c, s)} />
                <Audio m={m} />
              </section>
              <aside className="desk-side" aria-label="Findings">
                <div className="side-head">
                  <h2 className="h2">Findings</h2>
                  <div className="filters" role="group" aria-label="Filter findings by status">
                    {(['ALL', ...STATUSES] as const).map(s => (
                      <button key={s} type="button" className={`filter ${filter === s ? 'on' : ''}`} aria-pressed={filter === s} onClick={() => setFilter(s)}>
                        {s === 'ALL' ? 'All' : s.replace('_', ' ').toLowerCase()} <span className="mono">{s === 'ALL' ? m.findings.length : m.findings.filter(f => f.status === s).length}</span>
                      </button>
                    ))}
                  </div>
                </div>
                <ul className="findings">
                  {m.findings.filter(f => filter === 'ALL' || f.status === filter).map(f => {
                    const c = f.kind === 'visual' ? conceptFor(f.label) : null;
                    const first = c ? m.regions.find(r => r.concept_id === c)!.frames[0][0] / m.video.fps : undefined;
                    return (
                      <li key={f.finding_id}>
                        <button type="button" className={`finding ${c && focus === c ? 'on' : ''}`} disabled={!c} onClick={() => c && pick(focus === c ? null : c, first)}
                          title={c ? 'Show this region in the video' : undefined}>
                          <span className={`status s-${f.status}`}>{f.status.replace('_', ' ')}</span>
                          <span className="finding-body">
                            <span className="finding-label">{f.label}</span>
                            <span className="mono small muted">{f.kind} · {f.source}</span>
                            <span className="small finding-reason">{f.reasons.join(' ')}</span>
                          </span>
                        </button>
                      </li>
                    );
                  })}
                </ul>
                <p className="small faint">{filter !== 'ALL' && MEANING[filter as Status]}</p>
              </aside>
            </div>

            {m.verify && m.verify.length > 0 && (
              <section className="panel card" aria-labelledby="mask-h">
                <div className="panel-head"><h2 className="h2" id="mask-h">Mask check</h2><span className="chip">post-gate · local OCR</span></div>
                <p className="muted">Does each SAM mask contain the text Spark claimed? A mask without the claimed text is removed before redaction.</p>
                <div className="rows">
                  {[...m.verify].sort((a, b) => (a.status === 'rejected' ? 0 : 1) - (b.status === 'rejected' ? 0 : 1)).map(v => (
                    <div key={v.track_id} className="row">
                      <span className={`status s-${v.status}`}>{v.status.toUpperCase()}</span>
                      <div><div>{prettyConcept(v.concept_id)} <span className="muted">· claimed “{v.claimed.join(', ')}”</span></div>
                        <div className="mono small muted">OCR inside mask: “{v.ocr_text.slice(0, 3).join(' / ')}” · frames {v.frames_checked.join(', ')}</div></div>
                    </div>
                  ))}
                </div>
              </section>
            )}

            <section className="panel card" aria-labelledby="checks-h">
              <div className="panel-head"><h2 className="h2" id="checks-h">Checks that ran on the exported file</h2><span className="chip">deterministic</span></div>
              <div className="rows">
                {m.checks.map(c => (
                  <div key={c.check_id} className="row">
                    <span className={`status s-${c.status === 'RAN' ? 'RAN' : 'NOT_CHECKED'}`}>{c.status.replace('_', ' ')}</span>
                    <div><div>{c.description}</div>{c.detail && <div className="mono small muted">{c.detail}</div>}</div>
                  </div>
                ))}
              </div>
              {m.concepts_without_masks.length > 0 && <p className="small muted">Proposed but not found in the video: {m.concepts_without_masks.join(', ')}.</p>}
            </section>

            <section className="panel card" aria-labelledby="lim-h">
              <div className="panel-head"><h2 className="h2" id="lim-h">Limits of this receipt</h2></div>
              <ul className="limits">{m.limitations.map(l => <li key={l} className="muted">{l}</li>)}</ul>
              <p className="small muted">Frames, video and audio were sent to Meta's model API ({m.models.discover}, {m.models.track}, {m.models.listen}): {m.cost.calls} calls, {m.cost.failed} failed, est. ${m.cost.estimated_usd.toFixed(2)}{m.cost.unpriced ? ` (${m.cost.unpriced} unpriced)` : ''}. Processing is not local.</p>
              <p className="small faint">Demo data: {m.provenance}.</p>
            </section>
          </>
        )}
      </main>
      <Footer />
    </>
  );
}

function Verdict({ m }: { m: Manifest }) {
  const n = (s: Status) => m.findings.filter(f => f.status === s).length;
  const total = m.findings.length || 1;
  const unresolved = n('UNRESOLVED');
  return (
    <section className={`verdict card ${unresolved ? 'warn' : ''}`} aria-live="polite">
      <div>
        <strong className="verdict-title">{unresolved ? `${unresolved} unresolved finding${unresolved > 1 ? 's' : ''}. Review before sharing.` : 'No unresolved risks found by the checks listed.'}</strong>
        <p className="small muted">Veil never says a video is “safe”. It reports what each listed check found on the exported file.</p>
      </div>
      <div className="verdict-bar" aria-hidden="true">
        {STATUSES.map(s => <i key={s} className={`s-${s}`} style={{ flexGrow: n(s) || 0 }} />)}
      </div>
      <div className="verdict-counts">{STATUSES.map(s => <span key={s} className={`status s-${s}`}>{n(s)} {s.replace('_', ' ')}</span>)}</div>
      <span className="sr-only">{`${n('COVERED')} covered, ${unresolved} unresolved, ${n('NOT_CHECKED')} not checked, of ${total}`}</span>
    </section>
  );
}

function Audio({ m }: { m: Manifest }) {
  if (!m.audio.pii.length && !m.audio.transcript) return null;
  return (
    <div className="audio card">
      <div className="panel-head"><span className="eyebrow">Muse Voice · spoken identifiers</span></div>
      {m.audio.pii.length ? (
        <p>Spoken number localized to <strong>{m.audio.pii.map(p => `${p.t_start.toFixed(1)}–${p.t_end.toFixed(1)} s`).join(', ')}</strong>, muted with {m.audio.bleep_pad_s} s padding. Heard digits: <span className="mono">{m.audio.pii.map(p => p.digits).join(' · ')}</span>.</p>
      ) : <p className="muted">No spoken number detected.</p>}
      {m.audio.transcript && <p className="transcript" lang="hi">“{m.audio.transcript}”</p>}
    </div>
  );
}
