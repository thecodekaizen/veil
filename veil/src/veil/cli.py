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


if __name__ == '__main__':
    app()
