"""Veil command line. Currently: `veil label`. Pipeline commands arrive with their stages."""
import json
from pathlib import Path

import typer

from veil import label as label_module

app = typer.Typer(no_args_is_help=True, add_completion=False)


@app.callback()
def main():
    """Veil: open-vocabulary privacy-risk audit for creator videos."""


@app.command()
def label(clip: Path = typer.Argument(..., exists=True, dir_okay=False),
          out: Path = typer.Option(Path('gate/frames'), help='Frames root; output goes to OUT/<clip_id>/')):
    """Extract 4 fps frames, print the clip sha256 and write OUT/<clip_id>/labeler.html."""
    target = label_module.prepare(clip, out)
    typer.echo(f'clip sha256: {label_module.sha256_file(clip)}')
    typer.echo(f'open: {target.resolve()}')



@app.command()
def run(clip: Path = typer.Argument(..., exists=True, dir_okay=False),
        run_id: str = typer.Option(..., '--run-id'),
        stages: str = typer.Option('keyframes,discover,track,extend,listen', help='comma-separated: keyframes,discover,track,extend,listen,redact,audit,report'),
        runs_dir: Path = typer.Option(Path('runs')),
        bleep_pad: float = typer.Option(None, help='bleep padding in seconds (default: runner.BLEEP_PAD_S)'),
        refine_voiced: bool = typer.Option(False, '--refine-voiced', help='POST-GATE: narrow spoken-PII span with model-free voiced time')):
    """Run pipeline stages for CLIP; artifacts go to RUNS_DIR/RUN_ID/. Prints the concept table and spoken PII."""
    from veil import runner
    chosen = [s.strip() for s in stages.split(',') if s.strip()]
    bad = [s for s in chosen if s not in runner.STAGES]
    if bad:
        raise typer.BadParameter(f'unknown stages: {bad}')
    root = runner.run(clip, run_id, chosen, runs_dir, runner.BLEEP_PAD_S if bleep_pad is None else bleep_pad, refine_voiced)
    typer.echo(runner.summarize(root) + runner.summarize_audit(root))


@app.command('debug-overlay')
def debug_overlay(run_id: str, runs_dir: Path = typer.Option(Path('runs'))):
    """Render RUNS_DIR/RUN_ID/overlay.mp4 (masks, concept labels, source, frame number)."""
    from veil import overlay
    typer.echo(str(overlay.render(runs_dir / run_id)))


@app.command('export-web')
def export_web(run_id: str, out: Path = typer.Option(None, help='default: veil/web/public/demo/RUN_ID (the UI opens it with ?run=RUN_ID)'),
               provenance: str = typer.Option(..., help='who/what the footage is, e.g. "synthetic fixture, fictional data"'),
               runs_dir: Path = typer.Option(Path('runs'))):
    """Copy RUN_ID's input/output video and a compact manifest.json for the static demo UI."""
    from veil import export_web as ew
    typer.echo(str(ew.export(runs_dir / run_id, out or Path('veil/web/public/demo') / run_id, provenance)))


@app.command()
def naturalize(run_id: str, runs_dir: Path = typer.Option(Path('runs'))):
    """Opt-in natural export: re-render verified text surfaces with fictional text (others stay covered), then OCR-audit it."""
    from veil.stages import natural_text, verify
    rep = natural_text.run(runs_dir / run_id, verify.macos_ocr_rows(runs_dir / run_id / 'audit_cache'))
    typer.echo(json.dumps({k: rep[k] for k in ('replacements', 'text_surface_frames', 'fallback_cover_frames', 'cover_regions')}, ensure_ascii=False))
    typer.echo(f"audit: {rep['audit']['status']} ({rep['audit']['sampled_frames']} frames OCR'd, {len(rep['audit']['residual_original_words'])} residual words)")


if __name__ == '__main__':
    app()
