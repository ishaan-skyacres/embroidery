#!/usr/bin/env python3
"""Turn a line of text set in a font file into a flat-colour SVG for `digitize`.

    python scripts/text_to_svg.py FONT.otf "Sky" input/sky.svg --fill "#679943"

The text is shaped with HarfBuzz (kerning, ligatures and the font's default
features apply), every glyph is written as one filled path in font units with
the y axis flipped, and the viewBox is the tight bounding box of the ink plus a
small margin, so `digitize --height-mm` scales the letters themselves.
"""
import argparse
import sys

import uharfbuzz as hb
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("font")
    ap.add_argument("text")
    ap.add_argument("out")
    ap.add_argument("--fill", default="#000000", help="fill colour (hex)")
    ap.add_argument("--features", default="", help='comma list, e.g. "liga=0,ss01=1"')
    ap.add_argument("--margin", type=float, default=0.02, help="margin as a fraction of the ink height")
    args = ap.parse_args()

    font = TTFont(args.font)
    glyph_set = font.getGlyphSet()
    order = font.getGlyphOrder()
    upm = font["head"].unitsPerEm

    with open(args.font, "rb") as fh:
        blob = hb.Blob(fh.read())
    hb_font = hb.Font(hb.Face(blob))
    buf = hb.Buffer()
    buf.add_str(args.text)
    buf.guess_segment_properties()
    features = {}
    for item in filter(None, args.features.split(",")):
        tag, _, val = item.partition("=")
        features[tag.strip()] = bool(int(val)) if val else True
    hb.shape(hb_font, buf, features)

    paths = []
    bounds = None
    x = y = 0.0
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        name = order[info.codepoint]
        gx, gy = x + pos.x_offset, y + pos.y_offset
        glyph = glyph_set[name]
        bp = BoundsPen(glyph_set)
        glyph.draw(TransformPen(bp, (1, 0, 0, -1, gx, -gy)))
        if bp.bounds:
            sp = SVGPathPen(glyph_set)
            glyph.draw(TransformPen(sp, (1, 0, 0, -1, gx, -gy)))
            paths.append((name, sp.getCommands()))
            b = bp.bounds
            bounds = b if bounds is None else (min(bounds[0], b[0]), min(bounds[1], b[1]),
                                               max(bounds[2], b[2]), max(bounds[3], b[3]))
        x += pos.x_advance
        y += pos.y_advance

    if bounds is None:
        print("no ink", file=sys.stderr)
        return 1
    x0, y0, x1, y1 = bounds
    m = (y1 - y0) * args.margin
    x0, y0, x1, y1 = x0 - m, y0 - m, x1 + m, y1 + m
    w, h = x1 - x0, y1 - y0
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1" viewBox="{x0:.1f} {y0:.1f} {w:.1f} {h:.1f}" '
        f'width="{w:.1f}" height="{h:.1f}">',
        f'  <!-- "{args.text}" set in {font["name"].getDebugName(4)} ({upm} units/em), shaped with HarfBuzz -->',
    ]
    for name, d in paths:
        lines.append(f'  <path id="{name}" fill="{args.fill}" d="{d}"/>')
    lines.append("</svg>")
    with open(args.out, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"{args.out}: {len(paths)} glyph(s), ink {w:.0f} x {h:.0f} units, aspect {w / h:.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
