import { useEffect, useRef, useState } from 'react';
import { Compare } from './Compare';
import { BASE, REPO, prettyConcept, useManifest, useResults, type ExportFile, type Gate } from './data';
import { ExportToggle } from './ExportToggle';
import { Brand } from './Logo';

function useReveal() {
  useEffect(() => {
    const els = document.querySelectorAll('.reveal');
    const io = new IntersectionObserver(es => es.forEach(e => e.isIntersecting && e.target.classList.add('in')), { threshold: 0.12 });
    els.forEach(el => io.observe(el));
    return () => io.disconnect();
  });
}

export function Nav({ desk = false }: { desk?: boolean }) {
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const on = () => setScrolled(window.scrollY > 8);
    on(); window.addEventListener('scroll', on, { passive: true });
    return () => window.removeEventListener('scroll', on);
  }, []);
  return (
    <header className={`nav ${scrolled ? 'scrolled' : ''}`}>
      <div className="wrap nav-inner">
        <Brand />
        <nav className="nav-links" aria-label="Primary">
          {!desk && <a className="hide-sm" href="#how">How it works</a>}
          {!desk && <a className="hide-sm" href="#results">Results</a>}
          <a className="hide-sm" href={REPO} target="_blank" rel="noreferrer">GitHub</a>
          {desk ? <a className="btn btn-ghost" href="#/">Overview</a> : <a className="btn btn-primary" href="#/desk">Open the desk <span className="arrow">→</span></a>}
        </nav>
      </div>
    </header>
  );
}

const STEPS = [
  { n: '01', model: 'Muse Spark 1.3', title: 'Discover what identifies you', body: 'Spark reads keyframes and proposes what in this specific video could identify the creator, each with a reason. Not a fixed list of classes.', checks: 'Strict JSON schema · proposals merged by fuzzy match' },
  { n: '02', model: 'SAM 3.1 · Muse Voice', title: 'Track it, hear it', body: 'SAM 3.1 turns each proposal into masks tracked through every frame. Muse Voice hears spoken digits in Hindi, English or Hinglish.', checks: 'Track-gap check · OCR mask-vs-claim check · digit-run validator' },
  { n: '03', model: 'Deterministic code', title: 'Verify the file you post', body: 'Veil decodes its own export and checks every cover pixel, runs local OCR and a face detector, and re-transcribes the audio. Anything not cleared stays on the receipt.', checks: 'COVERED · UNRESOLVED · NOT_CHECKED, never a clean bill of health' },
];

function GateRow({ name, k, gates }: { name: string; k: keyof Omit<Gate, 'label' | 'verdict'>; gates: [string, Gate][] }) {
  return (
    <tr>
      <th scope="row">{name}</th>
      {gates.map(([id, g]) => (
        <td key={id}><span className={`status s-${g[k].ok ? 'PASS' : 'FAIL'}`}>{g[k].ok ? 'PASS' : 'FAIL'}</span> <span className="mono small muted">{g[k].value}</span></td>
      ))}
    </tr>
  );
}

export function Landing() {
  useReveal();
  const { data: m } = useManifest('c2');
  const { data: res } = useResults();
  const heroRef = useRef<HTMLDivElement>(null);
  const [exp, setExp] = useState<ExportFile>('output_natural.mp4');
  const gates = res ? (Object.entries(res.gates) as [string, Gate][]) : [];
  const repeats = gates.filter(([id]) => /^r\d$/.test(id));
  const g1All = repeats.filter(([, g]) => g.G1.ok).length;
  const spark = m?.regions.filter(r => r.source === 'spark') ?? [];
  const uniqueSpark = [...new Map(spark.map(r => [r.label, r])).values()];
  const rejected = m?.verify?.find(v => v.status === 'rejected');
  const counts = m ? (['COVERED', 'UNRESOLVED', 'NOT_CHECKED'] as const).map(s => [s, m.findings.filter(f => f.status === s).length] as const) : [];

  return (
    <>
      <Nav />
      <main id="main">
        {/* HERO */}
        <section className="hero">
          <div className="wrap hero-grid">
            <div className="hero-copy">
              <span className="eyebrow reveal">Redact without ruining the shot · built on Meta's Muse models</span>
              <h1 className="h-display reveal">See what your video gives away <em>before</em> you post it.</h1>
              <p className="lead reveal">Veil finds the name on a parcel, the flat number on a door and the phone number you said out loud. Then it fixes them <strong>naturally</strong>: instead of black boxes, verified text is re-rendered with fictional values in the original's colours, so the shot still looks like a real shot. Veil re-audits the exported file and tells you exactly what it could not clear.</p>
              <div className="hero-cta reveal">
                <a className="btn btn-primary" href="#/desk">Open the live desk <span className="arrow">→</span></a>
                <a className="btn btn-ghost" href={`${BASE}video/veil-demo.mp4`} target="_blank" rel="noreferrer">Watch the 2-min demo</a>
              </div>
              <p className="small muted reveal hero-note">Real pipeline output on a composited clip with fictional data. No sign-up; nothing to upload.</p>
            </div>
            <div className="hero-visual reveal" ref={heroRef}>
              {m ? <Compare m={m} run="c2" autoPlay controls={false} initialSplit={66} startAt={5} exportFile={m.natural ? exp : 'output.mp4'} /> : <div className="cmp-skeleton" />}
              <div className="hero-caption">
                {m?.natural && <ExportToggle value={exp} onChange={setExp} />}
                <span className="chip"><span className="dot" style={{ color: 'var(--signal)' }} />Drag to compare</span>
                {uniqueSpark.slice(0, 2).map(r => <span key={r.label} className="chip hide-xs">Spark · {r.label}</span>)}
              </div>
            </div>
          </div>
        </section>

        {/* PROBLEM */}
        <section className="section" id="problem">
          <div className="wrap split">
            <div className="section-head reveal">
              <span className="eyebrow">The problem</span>
              <h2 className="h1">A fixed list can't know what identifies <em>you</em>.</h2>
              <p className="lead">Redaction tools look for faces, plates, screens and documents. But what gives a creator away depends on the video: a notification banner, a society board, a door plate, a number said in Hindi.</p>
            </div>
            <div className="stat-pair reveal">
              <div className="stat card">
                <span className="mono small muted">Fixed classes only</span>
                <strong className="stat-num bad">{res?.heldout.baseline_only ?? '—'}</strong>
                <span className="muted small">planted leaks found on held-out clips</span>
              </div>
              <div className="stat card glow">
                <span className="mono small" style={{ color: 'var(--signal)' }}>With Muse Spark discovery</span>
                <strong className="stat-num">{res?.heldout.with_spark ?? '—'}</strong>
                <span className="muted small">in the frozen run · {repeats.length ? `${g1All}/${repeats.length} repeat runs pass discovery` : ''}</span>
              </div>
              <p className="mono small faint src">Source: {res?.heldout.source} · gate/repeats/</p>
            </div>
          </div>
        </section>

        {/* HOW */}
        <section className="section" id="how">
          <div className="wrap">
            <div className="section-head reveal">
              <span className="eyebrow">How it works</span>
              <h2 className="h1">Models propose. Code decides.</h2>
              <p className="lead">Three Meta models each do a job no fixed rule could. Then deterministic code checks their work on the file you're about to post.</p>
            </div>
            <ol className="steps">
              {STEPS.map(s => (
                <li key={s.n} className="step card reveal">
                  <div className="step-top"><span className="mono step-n">{s.n}</span><span className="chip">{s.model}</span></div>
                  <h3 className="h2">{s.title}</h3>
                  <p className="muted">{s.body}</p>
                  <p className="mono small step-checks">{s.checks}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        {/* PROOF */}
        <section className="section" id="proof">
          <div className="wrap split proof">
            <div className="section-head reveal">
              <span className="eyebrow">Proof, not promises</span>
              <h2 className="h1">It catches its own models' mistakes.</h2>
              <p className="lead">Sometimes SAM 3.1 grounds a proposal on the wrong object. Veil reads every mask that claims specific text with local OCR. If the claimed name isn't there, the mask is removed before redaction and listed on the receipt.</p>
              <a className="btn btn-ghost self-start" href="#/desk">Inspect the full receipt <span className="arrow">→</span></a>
            </div>
            <div className="receipt card reveal" aria-label="Excerpt of the real receipt for clip c2">
              {rejected && (
                <div className="receipt-row">
                  <span className="status s-rejected">REJECTED</span>
                  <div><div>{prettyConcept(rejected.concept_id)} <span className="muted">· claimed “{rejected.claimed.join(', ')}”</span></div>
                    <div className="mono small muted">OCR inside mask: “{rejected.ocr_text.slice(0, 2).join(' / ')}”</div></div>
                </div>
              )}
              {m && [...m.findings.filter(f => f.status === 'COVERED'), ...m.findings.filter(f => f.status === 'UNRESOLVED')].slice(0, 4).map(f => (
                <div key={f.finding_id} className="receipt-row">
                  <span className={`status s-${f.status}`}>{f.status}</span>
                  <div><div>{f.label} <span className="muted">· {f.source}</span></div><div className="mono small muted">{f.reasons[0]}</div></div>
                </div>
              ))}
              <div className="receipt-foot">
                {counts.map(([s, n]) => <span key={s} className={`status s-${s}`}>{n} {s}</span>)}
              </div>
            </div>
          </div>
        </section>

        {/* RESULTS */}
        <section className="section" id="results">
          <div className="wrap">
            <div className="section-head reveal">
              <span className="eyebrow">Results, including the ones we failed</span>
              <h2 className="h1">We pre-registered a gate. It failed. Here's everything.</h2>
              <p className="lead">Thresholds were frozen before any model saw the gate clips. The frozen verdict stays FAIL. Everything after it is labelled post-gate, and we re-ran the full pipeline three times to show run-to-run variance.</p>
            </div>
            <div className="table-wrap card reveal">
              <table className="gate">
                <thead><tr><th scope="col">Criterion</th>{gates.map(([id, g]) => <th scope="col" key={id}>{g.label}</th>)}</tr></thead>
                <tbody>
                  <GateRow name="G1 · discovery (≥ 3/4 leaks)" k="G1" gates={gates} />
                  <GateRow name="G2 · false flags (≤ 1/3 controls)" k="G2" gates={gates} />
                  <GateRow name="G3 · tracking (≥ 95% frames)" k="G3" gates={gates} />
                  <GateRow name="G4a · spoken number found" k="G4a" gates={gates} />
                  <GateRow name="G4b · mute window (≤ 2.5 s over)" k="G4b" gates={gates} />
                  <tr className="verdict-row"><th scope="row">Verdict</th>{gates.map(([id, g]) => <td key={id}><span className={`status s-${g.verdict}`}>{g.verdict}</span></td>)}</tr>
                </tbody>
              </table>
            </div>
            <p className="small muted reveal note">Clips are composited (licensed street footage, fictional graphics, Hindi text-to-speech), easier than real phone footage. Post-gate runs use the same clips, so they are not an untouched evaluation. Full method in <a href={`${REPO}/blob/main/EVALUATION.md`} target="_blank" rel="noreferrer">EVALUATION.md</a>.</p>
          </div>
        </section>

        {/* UNDER THE HOOD */}
        {res && res.models.length > 0 && (
          <section className="section" id="hood">
            <div className="wrap split">
              <div className="section-head reveal">
                <span className="eyebrow">Under the hood</span>
                <h2 className="h1">Every model call is on the ledger.</h2>
                <p className="lead">Each call is reserved before it is made, with model, latency, usage and estimated cost. Retries are explicit and named. Across {res.clip_runs} full clip runs:</p>
              </div>
              <div className="ledger reveal">
                {res.models.map(x => (
                  <div key={x.model} className="ledger-row card">
                    <div className="mono">{x.model}</div>
                    <div><strong>{x.calls}</strong><span className="muted small"> calls</span></div>
                    <div><strong>{x.median_latency_s}s</strong><span className="muted small"> median</span></div>
                    <div><strong>{x.failed}</strong><span className="muted small"> failed</span></div>
                  </div>
                ))}
                {res.usd_per_clip_run && <p className="mono small muted">Est. ${res.usd_per_clip_run.mean.toFixed(2)} per 25-second clip (range ${res.usd_per_clip_run.min.toFixed(2)}–${res.usd_per_clip_run.max.toFixed(2)}), from the ledgers, not billing.</p>}
              </div>
            </div>
          </section>
        )}

        {/* CTA */}
        <section className="section cta">
          <div className="wrap cta-inner reveal">
            <h2 className="h-display">Know before you post.</h2>
            <p className="lead">Open the desk to scrub through a real run: the regions the models found, the covered export, and a receipt that lists every check.</p>
            <div className="hero-cta">
              <a className="btn btn-primary" href="#/desk">Open the live desk <span className="arrow">→</span></a>
              <a className="btn btn-ghost" href={REPO} target="_blank" rel="noreferrer">Run it on your own clip</a>
            </div>
          </div>
        </section>
      </main>
      <Footer />
    </>
  );
}

export function Footer() {
  return (
    <footer className="footer">
      <div className="wrap footer-inner">
        <div><Brand /><p className="small muted">Built solo for the Meta Global AI Developer Hackathon 2026 · Indie track.</p></div>
        <p className="small faint">Street footage: Subhashish Panigrahi (Cuttack) and Fowler&amp;fowler (Delhi), Wikimedia Commons, CC BY-SA 3.0, composited with fictional graphics. All names and numbers are fictional. Veil is not a privacy guarantee: it reports what its listed checks found.</p>
      </div>
    </footer>
  );
}
