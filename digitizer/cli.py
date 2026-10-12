"""Command line: digitize INPUT --size-mm 120 --hoop 280x200 --fabric woven --out out/"""
from __future__ import annotations

import sys
from pathlib import Path

import click

from .pipeline import RunOptions, run
from .validate import ValidationError


@click.command(context_settings={"help_option_names": ["-h", "--help"], "max_content_width": 110})
@click.argument("input", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--size-mm", type=float, default=120.0, show_default=True, help="Longest side of the design in mm.")
@click.option("--hoop", type=str, default=None, help="Hoop WxH in mm (280x200, 200x200, 140x140 or custom). Default from params.yaml.")
@click.option("--fabric", type=click.Choice(["woven", "knit", "pique", "terry", "fleece"]), default="woven", show_default=True)
@click.option("--out", type=click.Path(path_type=Path), default=Path("out"), show_default=True, help="Output folder.")
@click.option("--engine", type=click.Choice(["auto", "inkstitch", "python"]), default="auto", show_default=True,
              help="auto = Ink/Stitch headless if installed, else pure Python.")
@click.option("--colors", type=int, default=None, help="Merge down to exactly N thread colours (refuses merges over the refuse threshold).")
@click.option("--merge-threshold", type=float, default=None, help="CIEDE2000 distance under which colours share a thread (default 8).")
@click.option("--groups", "groups_file", type=click.Path(exists=True, path_type=Path), default=None, help="groups.yaml with manual groups/order.")
@click.option("--group", "group_args", multiple=True, help='Manual group, e.g. --group "#1a3c6e,#1b3d70=navy" or "#fcfcfb=skip". Repeatable.')
@click.option("--review-groups", is_flag=True, help="Stop after colour grouping so you can check groups_preview.png.")
@click.option("--fabric-color", type=str, default=None, help="Hex colour of the fabric; matching artwork colours are not stitched.")
@click.option("--stitch-background", is_flag=True, help="Stitch the detected background colour instead of skipping it.")
@click.option("--params", "params_file", type=click.Path(exists=True, path_type=Path), default=None, help="YAML overriding params.yaml values.")
@click.option("--set", "sets", multiple=True, help="Override one value, e.g. --set fill.row_spacing_mm=0.45. Repeatable.")
@click.option("--knockdown", is_flag=True, help="Add a low-density knockdown layer under the whole design (terry, fleece).")
@click.option("--name", type=str, default=None, help="Design name used in the documents (default: input file name).")
@click.option("--quiet", is_flag=True)
def main(input, size_mm, hoop, fabric, out, engine, colors, merge_threshold, groups_file, group_args, review_groups,
         fabric_color, stitch_background, params_file, sets, knockdown, name, quiet):
    """Digitize a flat-colour vector file (SVG/AI/EPS/PDF) into a Tajima DST for the Poolin EOC06, with previews,
    a thread sheet, a stitching procedure and a quality report."""
    opts = RunOptions(input=input, size_mm=size_mm, hoop=hoop, fabric=fabric, out=out, engine=engine, colors=colors,
                      merge_threshold=merge_threshold, groups_file=groups_file, group_args=list(group_args),
                      review_groups=review_groups, fabric_color=fabric_color, stitch_background=stitch_background,
                      params_file=params_file, sets=list(sets), knockdown=knockdown, name=name, quiet=quiet)
    try:
        res = run(opts)
    except ValidationError as exc:
        click.echo(str(exc), err=True)
        sys.exit(2)
    except (ValueError, RuntimeError) as exc:
        click.echo(f"ERROR: {exc}", err=True)
        sys.exit(1)
    if res.warnings:
        click.echo("Warnings:")
        for w in dict.fromkeys(res.warnings):
            click.echo(f"  - {w}")


if __name__ == "__main__":
    main()
