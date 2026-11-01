"""Veil command line. Currently: `veil label`. Pipeline commands arrive with their stages."""
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
        stages: str = typer.Option('keyframes,discover,track,listen', help='comma-separated: keyframes,discover,track,listen,redact,audit,report'),
        runs_dir: Path = typer.Option(Path('runs')),
        bleep_pad: float = typer.Option(None, help='bleep padding in seconds (default: runner.BLEEP_PAD_S)')):
    """Run pipeline stages for CLIP; artifacts go to RUNS_DIR/RUN_ID/. Prints the concept table and spoken PII."""
    from veil import runner
    chosen = [s.strip() for s in stages.split(',') if s.strip()]
    bad = [s for s in chosen if s not in runner.STAGES]
    if bad:
        raise typer.BadParameter(f'unknown stages: {bad}')
    root = runner.run(clip, run_id, chosen, runs_dir, runner.BLEEP_PAD_S if bleep_pad is None else bleep_pad)
    typer.echo(runner.summarize(root) + runner.summarize_audit(root))


@app.command('debug-overlay')
def debug_overlay(run_id: str, runs_dir: Path = typer.Option(Path('runs'))):
    """Render RUNS_DIR/RUN_ID/overlay.mp4 (masks, concept labels, source, frame number)."""
    from veil import overlay
    typer.echo(str(overlay.render(runs_dir / run_id)))


if __name__ == '__main__':
    app()
