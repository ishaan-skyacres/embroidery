"""Coverage check: which parts of the artwork are not covered by stitches of their colour."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

from . import geometry as G
from .colors import hex_to_rgb
from .layering import Layout
from .stitchplan import STITCH, StitchPlan


@dataclass
class Gap:
    group: str
    area_mm2: float
    x: float
    y: float
    width_mm: float


@dataclass
class CoverageResult:
    gaps: list[Gap] = field(default_factory=list)
    uncovered_mm2: dict[str, float] = field(default_factory=dict)
    region_mm2: dict[str, float] = field(default_factory=dict)

    def fraction(self, group: str) -> float:
        r = self.region_mm2.get(group, 0.0)
        return self.uncovered_mm2.get(group, 0.0) / r if r > 0 else 0.0


def check_coverage(plan: StitchPlan, layout: Layout, thread_width_mm: float, path: Path | None,
                   ppm: float = 10.0, min_gap_mm2: float = 1.0) -> CoverageResult:
    """Rasterise each colour's region and its stitches; report uncovered patches."""
    sx, sy = plan.meta.get("shift", (0.0, 0.0))
    x0, y0, x1, y1 = plan.bounds()
    pad = 3.0
    W = int((x1 - x0 + 2 * pad) * ppm) + 1
    H = int((y1 - y0 + 2 * pad) * ppm) + 1
    ox, oy = x0 - pad, y0 - pad

    def px(x, y):
        return ((x - ox) * ppm, (y - oy) * ppm)

    res = CoverageResult()
    overlay = Image.new("RGB", (W, H), (245, 243, 238))
    odraw = ImageDraw.Draw(overlay)
    blocks = {b.group: b for b in plan.blocks}
    # thread covers a little more than its nominal width once it flattens; the mask is eroded
    # by one pixel afterwards so hairline edge slivers are ignored
    r_px = max(1.0, (thread_width_mm * 0.6) * ppm)
    for region in layout.regions:
        if region.region.is_empty:
            continue
        mask = Image.new("L", (W, H), 0)
        md = ImageDraw.Draw(mask)
        for poly in G.polygons(region.region):
            md.polygon([px(x - sx, y - sy) for x, y in poly.exterior.coords], fill=255)
            for ring in poly.interiors:
                md.polygon([px(x - sx, y - sy) for x, y in ring.coords], fill=0)
        region_mask = np.asarray(mask) > 0
        stitched = Image.new("L", (W, H), 0)
        sd = ImageDraw.Draw(stitched)
        block = blocks.get(region.name)
        if block is not None:
            prev = None
            for s in block.stitches:
                if s.cmd == STITCH:
                    if prev is not None:
                        a, b = px(prev.x, prev.y), px(s.x, s.y)
                        sd.line([a, b], fill=255, width=int(round(2 * r_px)))
                        sd.ellipse([b[0] - r_px, b[1] - r_px, b[0] + r_px, b[1] + r_px], fill=255)
                    prev = s
                else:
                    prev = s if s.cmd == "JUMP" else prev
        stitched_mask = np.asarray(stitched) > 0
        uncovered = region_mask & ~stitched_mask
        uncovered = ndimage.binary_erosion(uncovered, iterations=1)
        res.region_mm2[region.name] = float(region_mask.sum() / ppm ** 2)
        res.uncovered_mm2[region.name] = float(uncovered.sum() / ppm ** 2)
        # draw the region faintly, then the gaps in magenta
        col = hex_to_rgb(region.group.color)
        faint = tuple(int(c * 0.35 + 235 * 0.65) for c in col)
        for poly in G.polygons(region.region):
            odraw.polygon([px(x - sx, y - sy) for x, y in poly.exterior.coords], fill=faint)
            for ring in poly.interiors:
                odraw.polygon([px(x - sx, y - sy) for x, y in ring.coords], fill=(245, 243, 238))
        labels, n = ndimage.label(uncovered, structure=np.ones((3, 3)))
        if n:
            areas = ndimage.sum(uncovered, labels, index=np.arange(1, n + 1)) / ppm ** 2
            centers = ndimage.center_of_mass(uncovered, labels, index=np.arange(1, n + 1))
            dt = ndimage.distance_transform_edt(uncovered)
            widths = ndimage.maximum(dt, labels, index=np.arange(1, n + 1)) * 2 / ppm
            for k in range(n):
                if areas[k] >= min_gap_mm2:
                    cy, cx = centers[k]
                    res.gaps.append(Gap(region.name, float(areas[k]), float(cx / ppm + ox), float(cy / ppm + oy), float(widths[k])))
        arr = np.asarray(overlay).copy()
        arr[uncovered] = (220, 0, 160)
        overlay = Image.fromarray(arr)
        odraw = ImageDraw.Draw(overlay)
    res.gaps.sort(key=lambda g: -g.area_mm2)
    if path is not None:
        from .preview import font
        f = font(14)
        odraw.text((6, 4), "magenta = artwork of a colour not covered by that colour's stitches", fill=(40, 40, 40), font=f)
        for g in res.gaps[:30]:
            cx, cy = px(g.x, g.y)
            rad = max(6, (g.area_mm2 ** 0.5) * ppm)
            odraw.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], outline=(200, 0, 0), width=2)
        path.parent.mkdir(parents=True, exist_ok=True)
        overlay.save(path)
    return res
