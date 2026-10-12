"""PNG previews: realistic thread render with ruler, art overlay, per-colour views, density map, group preview."""
from __future__ import annotations

import io
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from . import geometry as G
from .colors import ColorGroup, hex_to_rgb, rgb_to_hex
from .stitchplan import JUMP, STITCH, StitchPlan

FONT_PATHS = ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/dejavu/DejaVuSans.ttf",
              "/Library/Fonts/Arial.ttf", "C:/Windows/Fonts/arial.ttf"]


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for p in FONT_PATHS:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def shade(hex_color: str, factor: float) -> tuple[int, int, int]:
    r, g, b = hex_to_rgb(hex_color)
    if factor >= 1:
        return tuple(int(round(min(255, c + (255 - c) * (factor - 1)))) for c in (r, g, b))
    return tuple(int(round(c * factor)) for c in (r, g, b))


class Canvas:
    """Image covering the design bounds plus margin, with mm <-> px mapping."""

    def __init__(self, bounds, ppm: float, margin_mm: float = 8.0, ruler: bool = True, background="#d9d4c7"):
        x0, y0, x1, y1 = bounds
        self.ppm = ppm
        self.margin = margin_mm
        self.ruler = ruler
        self.x0 = x0 - margin_mm
        self.y0 = y0 - margin_mm
        self.w = int(math.ceil((x1 - x0 + 2 * margin_mm) * ppm))
        self.h = int(math.ceil((y1 - y0 + 2 * margin_mm) * ppm))
        self.img = Image.new("RGB", (self.w, self.h), hex_to_rgb(background))
        self.draw = ImageDraw.Draw(self.img, "RGBA")

    def px(self, x: float, y: float) -> tuple[float, float]:
        return ((x - self.x0) * self.ppm, (y - self.y0) * self.ppm)

    def draw_ruler(self):
        f = font(max(10, int(self.ppm * 1.6)))
        ink = (40, 40, 40)
        x_start = math.ceil(self.x0)
        x_end = math.floor(self.x0 + self.w / self.ppm)
        base_y = self.h - 2
        for mm in range(x_start, x_end + 1):
            px, _ = self.px(mm, 0)
            tick = 3 if mm % 10 == 0 else (2 if mm % 5 == 0 else 1)
            self.draw.line([(px, base_y), (px, base_y - tick * self.ppm * 0.5)], fill=ink, width=1)
            if mm % 10 == 0:
                self.draw.text((px + 2, base_y - tick * self.ppm * 0.5 - f.size - 1), f"{mm}", fill=ink, font=f)
        y_start = math.ceil(self.y0)
        y_end = math.floor(self.y0 + self.h / self.ppm)
        for mm in range(y_start, y_end + 1):
            _, py = self.px(0, mm)
            tick = 3 if mm % 10 == 0 else (2 if mm % 5 == 0 else 1)
            self.draw.line([(2, py), (2 + tick * self.ppm * 0.5, py)], fill=ink, width=1)
            if mm % 10 == 0:
                self.draw.text((4 + tick * self.ppm * 0.5, py - f.size / 2), f"{mm}", fill=ink, font=f)
        self.draw.text((6, 4), "mm (0,0 = hoop centre)", fill=ink, font=f)

    def stitch_lines(self, plan: StitchPlan, thread_w_mm: float, only_block: int | None = None, dim_others: bool = False,
                     realistic: bool = True, jumps: bool = False):
        w = max(1.0, thread_w_mm * self.ppm)
        for bi, block in enumerate(plan.blocks):
            if only_block is not None and bi != only_block and not dim_others:
                continue
            color = block.color
            dim = only_block is not None and bi != only_block
            prev = None
            segs = []
            for s in block.stitches:
                if s.cmd == STITCH:
                    if prev is not None:
                        segs.append((prev, s))
                    prev = s
                elif s.cmd == JUMP:
                    if jumps and prev is not None:
                        self.draw.line([self.px(prev.x, prev.y), self.px(s.x, s.y)], fill=(200, 0, 0, 120), width=1)
                    prev = s
            if dim:
                c = shade(color, 1.0)
                c = tuple(int(v * 0.35 + 215 * 0.65) for v in c)
                for a, b in segs:
                    self.draw.line([self.px(a.x, a.y), self.px(b.x, b.y)], fill=c + (255,), width=int(w))
                continue
            if realistic:
                # a 40 wt thread flattens to a little more than its nominal width; draw a soft
                # shadow under each stitch, the thread body, then a highlight along one side
                dark = shade(color, 0.5) + (255,)
                mid = hex_to_rgb(color) + (255,)
                light = shade(color, 1.3) + (255,)
                r_dark = max(1.0, w * 0.72)
                r_mid = max(1.0, w * 0.6)
                dot = dark[:3] + (110,)
                for a, b in segs:
                    pa, pb = self.px(a.x, a.y), self.px(b.x, b.y)
                    self.draw.line([pa, pb], fill=dark, width=int(round(2 * r_dark)))
                    self.draw.ellipse([pb[0] - r_mid, pb[1] - r_mid, pb[0] + r_mid, pb[1] + r_mid], fill=dot)
                for a, b in segs:
                    pa, pb = self.px(a.x, a.y), self.px(b.x, b.y)
                    self.draw.line([pa, pb], fill=mid, width=int(round(2 * r_mid)))
                    self.draw.ellipse([pb[0] - r_mid, pb[1] - r_mid, pb[0] + r_mid, pb[1] + r_mid], fill=mid)
                if w >= 4:
                    off = w * 0.22
                    for a, b in segs:
                        pa, pb = self.px(a.x, a.y), self.px(b.x, b.y)
                        self.draw.line([(pa[0] - off, pa[1] - off), (pb[0] - off, pb[1] - off)], fill=light, width=max(1, int(w * 0.3)))
            else:
                for a, b in segs:
                    self.draw.line([self.px(a.x, a.y), self.px(b.x, b.y)], fill=hex_to_rgb(color) + (255,), width=int(w))


def render_realistic(plan: StitchPlan, params, path: Path, art: Image.Image | None = None, art_alpha: float = 0.4,
                     only_block: int | None = None, ruler: bool = True, ppm: float | None = None,
                     dim_others: bool = False, jumps: bool = False) -> Path:
    ppm = ppm or float(params["preview.render_dpi"]) / 25.4
    ss = 2  # supersampling for smoother thread edges
    canvas = Canvas(plan.bounds(), ppm * ss, background=params["preview.fabric_color"])
    if art is not None:
        art = art.resize((canvas.w, canvas.h), Image.LANCZOS)
        # art is already rendered at the same ppm and covers the same canvas
        base = canvas.img.convert("RGBA")
        art_rgba = art.convert("RGBA")
        alpha = art_rgba.split()[3].point(lambda a: int(a * art_alpha))
        art_rgba.putalpha(alpha)
        base.alpha_composite(art_rgba)
        canvas.img = base.convert("RGB")
        canvas.draw = ImageDraw.Draw(canvas.img, "RGBA")
    canvas.stitch_lines(plan, float(params["preview.thread_width_mm"]), only_block=only_block, dim_others=dim_others,
                        realistic=True, jumps=jumps)
    img = canvas.img.resize((canvas.w // ss, canvas.h // ss), Image.LANCZOS)
    canvas.img = img
    canvas.draw = ImageDraw.Draw(img, "RGBA")
    canvas.ppm = ppm
    canvas.w, canvas.h = img.size
    if ruler:
        canvas.draw_ruler()
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.img.save(path)
    return path


def render_art(svg_path: Path, layout, plan: StitchPlan, params, ppm: float | None = None) -> Image.Image | None:
    """Rasterise the original SVG so that it lines up with the stitch canvas."""
    try:
        import cairosvg
    except Exception:
        return None
    ppm = ppm or float(params["preview.render_dpi"]) / 25.4
    canvas = Canvas(plan.bounds(), ppm, background=params["preview.fabric_color"])
    # SVG user unit -> mm: (u - center) * scale ; pixel = (mm - x0) * ppm
    svg_ppu = layout.scale * ppm            # pixels per SVG unit
    try:
        from svgelements import SVG
        svg = SVG.parse(str(svg_path))
        vb = svg.viewbox
        if vb is not None:
            vx, vy, vw, vh = vb.x, vb.y, vb.width, vb.height
        else:
            vx, vy, vw, vh = 0, 0, float(svg.width), float(svg.height)
    except Exception:
        return None
    out_w = max(1, int(round(vw * svg_ppu)))
    out_h = max(1, int(round(vh * svg_ppu)))
    try:
        png = cairosvg.svg2png(url=str(svg_path), output_width=out_w, output_height=out_h)
    except Exception:
        return None
    art = Image.open(io.BytesIO(png)).convert("RGBA")
    # the SVG origin (vx, vy) maps to mm ((vx - cx) * scale, (vy - cy) * scale)
    cx, cy = layout.center_units
    ox = ((vx - cx) * layout.scale - canvas.x0) * ppm
    oy = ((vy - cy) * layout.scale - canvas.y0) * ppm
    base = Image.new("RGBA", (canvas.w, canvas.h), (0, 0, 0, 0))
    base.alpha_composite(art, (int(round(ox)), int(round(oy))))
    return base


def render_density(plan: StitchPlan, params, path: Path) -> dict:
    cell = float(params["preview.density_cell_mm"])
    hot = float(params["preview.density_hotspot_per_mm2"])
    x0, y0, x1, y1 = plan.bounds()
    nx = int(math.ceil((x1 - x0) / cell)) + 1
    ny = int(math.ceil((y1 - y0) / cell)) + 1
    grid = np.zeros((ny, nx), dtype=float)
    for b in plan.blocks:
        for s in b.stitches:
            if s.cmd == STITCH and not s.lock:
                i = int((s.y - y0) / cell)
                j = int((s.x - x0) / cell)
                grid[i, j] += 1
    per_mm2 = grid / (cell * cell)
    ppm = max(4.0, 1200.0 / max(x1 - x0, y1 - y0))
    canvas = Canvas(plan.bounds(), ppm, ruler=True, background="#ffffff")
    vmax = max(hot * 1.25, per_mm2.max(), 1.0)
    hotspots = []
    for i in range(ny):
        for j in range(nx):
            v = per_mm2[i, j]
            if v <= 0:
                continue
            t = min(1.0, v / vmax)
            # white -> yellow -> orange -> red
            if t < 0.5:
                col = (255, 255, int(255 * (1 - 2 * t)))
            else:
                col = (255, int(255 * (1 - (t - 0.5) * 2)), 0)
            px0, py0 = canvas.px(x0 + j * cell, y0 + i * cell)
            px1, py1 = canvas.px(x0 + (j + 1) * cell, y0 + (i + 1) * cell)
            canvas.draw.rectangle([px0, py0, px1, py1], fill=col)
            if v > hot:
                hotspots.append((x0 + (j + 0.5) * cell, y0 + (i + 0.5) * cell, float(v)))
    for hx, hy, v in hotspots:
        px0, py0 = canvas.px(hx - cell / 2, hy - cell / 2)
        px1, py1 = canvas.px(hx + cell / 2, hy + cell / 2)
        canvas.draw.rectangle([px0, py0, px1, py1], outline=(120, 0, 160), width=2)
    canvas.draw_ruler()
    f = font(max(12, int(ppm * 2)))
    canvas.draw.text((6, 4 + f.size + 2), f"needle penetrations per mm2 (cell {cell:g} mm, lock stitches excluded); purple = over {hot:g} (hot spot)",
                     fill=(40, 40, 40), font=f)
    # legend bar
    lx, ly = canvas.w - int(ppm * 30), 6
    for k in range(100):
        t = k / 99
        col = (255, 255, int(255 * (1 - 2 * t))) if t < 0.5 else (255, int(255 * (1 - (t - 0.5) * 2)), 0)
        canvas.draw.rectangle([lx + k * ppm * 0.25, ly, lx + (k + 1) * ppm * 0.25, ly + ppm * 2], fill=col)
    canvas.draw.text((lx, ly + ppm * 2 + 2), f"0 .. {vmax:.0f} /mm2", fill=(40, 40, 40), font=f)
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.img.save(path)
    hotspots.sort(key=lambda h: -h[2])
    return {"max_per_mm2": float(per_mm2.max()), "mean_per_mm2": float(per_mm2[per_mm2 > 0].mean()) if (per_mm2 > 0).any() else 0.0,
            "hotspots": hotspots, "threshold": hot}


def render_groups_preview(doc, groups: list[ColorGroup], member_to_group: dict[str, str], areas: dict[str, float],
                          path: Path, order: list[str] | None = None) -> Path:
    """Swatch strip (raw colours -> group) plus the artwork recoloured by group."""
    f = font(14)
    fs = font(11)
    raw_colors = sorted(areas, key=lambda c: -areas[c])
    sw = 44
    strip_h = sw + 40
    # artwork recoloured
    from shapely.ops import unary_union
    b = unary_union([s.geom for s in doc.shapes]).bounds
    aw, ah = b[2] - b[0], b[3] - b[1]
    scale = min(700 / aw, 700 / ah)
    art_w, art_h = int(aw * scale) + 20, int(ah * scale) + 20
    width = max(art_w + 20, 12 + len(raw_colors) * (sw + 8) + 10, 520)
    img = Image.new("RGB", (width, strip_h + art_h + 40 + 20 * len(groups)), (250, 250, 250))
    d = ImageDraw.Draw(img)
    d.text((10, 6), "Raw colours (largest area first) -> thread group", fill=(30, 30, 30), font=f)
    x = 12
    for c in raw_colors:
        gname = member_to_group.get(c, "?")
        g = next((g for g in groups if g.name == gname), None)
        d.rectangle([x, 26, x + sw, 26 + sw // 2], fill=hex_to_rgb(c), outline=(60, 60, 60))
        if g is not None:
            d.rectangle([x, 26 + sw // 2, x + sw, 26 + sw], fill=hex_to_rgb(g.color), outline=(60, 60, 60))
            if g.skip:
                d.line([x, 26 + sw // 2, x + sw, 26 + sw], fill=(200, 0, 0), width=2)
                d.line([x + sw, 26 + sw // 2, x, 26 + sw], fill=(200, 0, 0), width=2)
        d.text((x, 28 + sw), c, fill=(30, 30, 30), font=fs)
        d.text((x, 40 + sw), (gname[:9] if g else "?"), fill=(30, 30, 30), font=fs)
        x += sw + 8
    # recoloured art
    top = strip_h + 10
    d.text((10, top - 4), "Artwork recoloured by group (hatched = skipped)", fill=(30, 30, 30), font=f)
    top += 18
    for s in sorted(doc.shapes, key=lambda s: s.index):
        gname = member_to_group.get(s.color)
        g = next((g for g in groups if g.name == gname), None)
        if g is None:
            continue
        col = hex_to_rgb(g.color) if not g.skip else (235, 235, 235)
        for poly in G.polygons(s.geom):
            pts = [((px - b[0]) * scale + 10, (py - b[1]) * scale + top) for px, py in poly.exterior.coords]
            d.polygon(pts, fill=col)
            for ring in poly.interiors:
                pts = [((px - b[0]) * scale + 10, (py - b[1]) * scale + top) for px, py in ring.coords]
                d.polygon(pts, fill=(250, 250, 250))
    y = top + art_h + 6
    for i, g in enumerate(order and [next(gg for gg in groups if gg.name == n) for n in order if any(gg.name == n for gg in groups)] or groups):
        d.rectangle([10, y, 30, y + 14], fill=hex_to_rgb(g.color), outline=(60, 60, 60))
        label = f"{i + 1}. {g.name}  {g.color}  members: {', '.join(g.members)}" + ("  (skipped)" if g.skip else "")
        if g.thread:
            label += f"  thread: {g.thread.get('brand', '')} {g.thread.get('code', '')} {g.thread.get('name', '')}"
        d.text((36, y), label, fill=(30, 30, 30), font=fs)
        y += 20
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    return path


def thumbnail_for_block(plan: StitchPlan, params, index: int, path: Path, max_px: int = 420) -> Path:
    """Small image of the whole design with one block highlighted (others greyed)."""
    x0, y0, x1, y1 = plan.bounds()
    ppm = max_px / max(x1 - x0, y1 - y0, 1.0)
    canvas = Canvas(plan.bounds(), ppm, margin_mm=3, ruler=False, background=params["preview.fabric_color"])
    canvas.stitch_lines(plan, max(0.4, 1.6 / ppm), only_block=index, dim_others=True, realistic=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.img.save(path)
    return path
