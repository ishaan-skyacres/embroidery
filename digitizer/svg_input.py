"""Vector input: AI/EPS/PDF conversion, SVG parsing and cleanup into shapely shapes.

Output coordinates are SVG user units, y down. Scaling to mm happens later.
"""
from __future__ import annotations

import math
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from lxml import etree
from shapely.geometry import LineString, MultiLineString, MultiPolygon
from shapely.ops import unary_union
from svgelements import SVG, Arc, Close, CubicBezier, Line, Move, Path as SvgPath, QuadraticBezier, Shape, Group

from . import geometry as G

CONTAINER_SKIP = {"Defs", "Pattern", "Marker", "Symbol", "LinearGradient", "RadialGradient", "Filter"}


@dataclass
class RawShape:
    index: int
    id: str
    color: str
    kind: str                       # 'fill' or 'stroke'
    geom: MultiPolygon
    centerline: MultiLineString | None = None
    stroke_width: float = 0.0       # user units
    source_class: str = ""

    @property
    def area(self) -> float:
        return self.geom.area


@dataclass
class Document:
    source: Path
    width: float
    height: float
    shapes: list[RawShape] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    log: list[str] = field(default_factory=list)
    text_count: int = 0

    def canvas_area(self) -> float:
        return self.width * self.height


def inkscape_binary() -> str | None:
    return shutil.which("inkscape")


def ensure_plain_svg(path: Path, workdir: Path, convert_text: bool = True) -> tuple[Path, list[str]]:
    """Convert AI/EPS/PDF to plain SVG with headless Inkscape; convert text to paths."""
    path = Path(path)
    warnings: list[str] = []
    suffix = path.suffix.lower()
    needs_inkscape = suffix in {".ai", ".eps", ".pdf"}
    has_text = False
    if suffix == ".svg":
        try:
            has_text = b"<text" in path.read_bytes()
        except OSError:
            pass
    if not needs_inkscape and not (has_text and convert_text):
        return path, warnings
    ink = inkscape_binary()
    if ink is None:
        if needs_inkscape:
            raise RuntimeError(f"{path.name} needs Inkscape to convert to SVG, but inkscape is not on PATH. "
                               "Install Inkscape (apt install inkscape) or export a plain SVG first.")
        warnings.append("The SVG contains <text> elements and Inkscape is not installed to convert them "
                        "to paths; text will be ignored. Convert text to paths in your editor first.")
        return path, warnings
    workdir.mkdir(parents=True, exist_ok=True)
    out = workdir / (path.stem + "_plain.svg")
    cmd = [ink, str(path), "--export-type=svg", "--export-plain-svg", "--export-text-to-path",
           f"--export-filename={out}"]
    if suffix == ".eps":
        cmd.insert(2, "--pdf-poppler")
    env = {"HOME": str(workdir), "PATH": "/usr/bin:/bin:/usr/local/bin"}
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=300, env=env)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"Inkscape failed to convert {path.name}: {exc.stderr.decode(errors='ignore')[-800:]}") from exc
    if not out.exists() or out.stat().st_size == 0:
        raise RuntimeError(f"Inkscape produced no output for {path.name}")
    warnings.append(f"Converted {path.name} to plain SVG with Inkscape ({out.name}); text converted to paths.")
    return out, warnings


def _color_hex(color) -> str | None:
    if color is None or getattr(color, "value", None) is None:
        return None
    try:
        return color.hex.lower()[:7]
    except Exception:
        return None


def _gradient_colors(svg_path: Path) -> dict[str, str]:
    """Average colour of each gradient (so a gradient fill can be flattened)."""
    out: dict[str, str] = {}
    try:
        tree = etree.parse(str(svg_path))
    except Exception:
        return out
    ns = {"svg": "http://www.w3.org/2000/svg"}
    grads = {}
    for g in tree.iter("{http://www.w3.org/2000/svg}linearGradient", "{http://www.w3.org/2000/svg}radialGradient"):
        grads[g.get("id")] = g
    for gid, g in grads.items():
        stops = list(g.iter("{http://www.w3.org/2000/svg}stop"))
        href = g.get("{http://www.w3.org/1999/xlink}href") or g.get("href")
        if not stops and href and href.startswith("#") and href[1:] in grads:
            stops = list(grads[href[1:]].iter("{http://www.w3.org/2000/svg}stop"))
        rgbs = []
        for s in stops:
            style = s.get("style", "")
            m = re.search(r"stop-color:\s*(#[0-9a-fA-F]{6})", style)
            c = m.group(1) if m else s.get("stop-color")
            if c and re.match(r"#[0-9a-fA-F]{6}$", c):
                rgbs.append(tuple(int(c[i:i + 2], 16) for i in (1, 3, 5)))
        if rgbs:
            avg = np.mean(np.asarray(rgbs), axis=0).round().astype(int)
            out[gid] = "#%02x%02x%02x" % tuple(avg)
    return out


def _sample_segment(seg, step: float) -> list[tuple[float, float]]:
    """Points along a segment (excluding its start), spaced at most `step` apart."""
    if isinstance(seg, (Line, Close)):
        return [(seg.end.x, seg.end.y)]
    if isinstance(seg, (CubicBezier, QuadraticBezier, Arc)):
        try:
            length = seg.length(error=1e-3)
        except Exception:
            length = step
        n = max(2, int(math.ceil(length / step)))
        pts = []
        for i in range(1, n + 1):
            p = seg.point(i / n)
            pts.append((p.x, p.y))
        return pts
    return []


def path_to_rings(path: SvgPath, step: float) -> list[tuple[np.ndarray, bool]]:
    """Flatten a path into a list of (points Nx2, closed) subpaths."""
    rings: list[tuple[np.ndarray, bool]] = []
    current: list[tuple[float, float]] = []
    closed = False

    def flush():
        nonlocal current, closed
        if len(current) >= 2:
            rings.append((np.asarray(current, dtype=float), closed))
        current = []
        closed = False

    for seg in path.segments():
        if isinstance(seg, Move):
            flush()
            if seg.end is not None:
                current = [(seg.end.x, seg.end.y)]
            continue
        if seg.start is None or seg.end is None:
            continue
        if not current:
            current = [(seg.start.x, seg.start.y)]
        current.extend(_sample_segment(seg, step))
        if isinstance(seg, Close):
            closed = True
            flush()
    flush()
    return rings


def _is_hidden(elem, kind: str) -> bool:
    v = elem.values
    if v.get("visibility") == "hidden" or v.get("display") == "none":
        return True
    try:
        if float(v.get("opacity", 1)) <= 0:
            return True
        if kind == "fill" and float(v.get("fill-opacity", 1)) <= 0:
            return True
        if kind == "stroke" and float(v.get("stroke-opacity", 1)) <= 0:
            return True
    except (TypeError, ValueError):
        pass
    return False


def _walk(group, clips: dict[str, Any], out: list, skipped: dict[str, int]):
    for child in group:
        name = type(child).__name__
        if name == "ClipPath" or name == "Mask":
            cid = child.id or child.values.get("id")
            shapes: list = []
            _walk(child, clips, shapes, skipped)
            if cid:
                clips[cid] = (name, shapes)
            continue
        if name in CONTAINER_SKIP:
            skipped[name] = skipped.get(name, 0) + 1
            continue
        if isinstance(child, Shape):
            out.append(child)
        elif name == "Text":
            out.append(child)
        elif name == "Image":
            skipped["Image"] = skipped.get("Image", 0) + 1
        elif isinstance(child, Group) or hasattr(child, "__iter__"):
            try:
                _walk(child, clips, out, skipped)
            except TypeError:
                pass


def load_document(svg_path: Path, flatten_step: float, log: list[str] | None = None) -> Document:
    """Parse an SVG into filled/stroked shapes (user units)."""
    svg_path = Path(svg_path)
    svg = SVG.parse(str(svg_path), reify=True)
    width = float(svg.width) if svg.width else None
    height = float(svg.height) if svg.height else None
    if svg.viewbox is not None:
        width = float(svg.viewbox.width)
        height = float(svg.viewbox.height)
    doc = Document(source=svg_path, width=width or 0.0, height=height or 0.0)
    gradients = _gradient_colors(svg_path)
    clips: dict[str, Any] = {}
    elems: list = []
    skipped: dict[str, int] = {}
    _walk(svg, clips, elems, skipped)
    for name, n in skipped.items():
        doc.warnings.append(f"Ignored {n} {name} element(s) (not embroiderable).")

    def clip_geom(elem) -> MultiPolygon | None:
        ref = elem.values.get("clip-path") or elem.values.get("mask")
        if not ref:
            return None
        m = re.match(r"url\(#([^)]+)\)", ref)
        if not m or m.group(1) not in clips:
            doc.warnings.append(f"Clip/mask {ref} not found; element stitched unclipped.")
            return None
        kind, shapes = clips[m.group(1)]
        polys = []
        for s in shapes:
            if isinstance(s, Shape):
                p = s if isinstance(s, SvgPath) else SvgPath(s)
                rings = [r for r, c in path_to_rings(p, flatten_step) if len(r) >= 3]
                polys.append(G.polygon_from_rings(rings, s.values.get("clip-rule", "nonzero")))
        if kind == "Mask":
            doc.warnings.append(f"Mask #{m.group(1)} approximated by its shapes' outline (soft masks are not supported).")
        if not polys:
            return None
        return G.to_multipolygon(unary_union(polys))

    index = 0
    for elem in elems:
        if type(elem).__name__ == "Text":
            doc.text_count += 1
            continue
        path = elem if isinstance(elem, SvgPath) else SvgPath(elem)
        try:
            path.reify()
        except Exception:
            pass
        rings = path_to_rings(path, flatten_step)
        if not rings:
            continue
        fill_hex = _color_hex(elem.fill)
        raw_fill = str(elem.values.get("fill", "") or "")
        if raw_fill.startswith("url(") and fill_hex is None:
            gid = re.match(r"url\(#([^)]+)\)", raw_fill)
            if gid and gid.group(1) in gradients:
                fill_hex = gradients[gid.group(1)]
                doc.warnings.append(f"Gradient fill {raw_fill} flattened to its average colour {fill_hex}.")
        stroke_hex = _color_hex(elem.stroke)
        elem_id = elem.id or elem.values.get("id") or f"elem{index}"
        cls = str(elem.values.get("class", "") or "")
        clip = clip_geom(elem)
        try:
            opacity = float(elem.values.get("opacity", 1))
        except (TypeError, ValueError):
            opacity = 1.0
        if 0 < opacity < 1:
            doc.warnings.append(f"Element {elem_id} has opacity {opacity:g}; it is stitched as a solid colour.")

        if fill_hex and not _is_hidden(elem, "fill"):
            closed_rings = [r for r, c in rings if len(r) >= 3]
            rule = elem.values.get("fill-rule", "nonzero") or "nonzero"
            geom = G.polygon_from_rings(closed_rings, rule)
            if clip is not None and not geom.is_empty:
                geom = G.to_multipolygon(geom.intersection(clip))
            if not geom.is_empty:
                doc.shapes.append(RawShape(index, elem_id, fill_hex, "fill", geom, source_class=cls))
                index += 1
        if stroke_hex and not _is_hidden(elem, "stroke"):
            sw = float(getattr(elem, "implicit_stroke_width", None) or elem.stroke_width or 1.0)
            if sw > 0:
                cap = {"butt": "flat", "round": "round", "square": "square"}.get(elem.values.get("stroke-linecap", "butt"), "flat")
                join = {"miter": "mitre", "round": "round", "bevel": "bevel"}.get(elem.values.get("stroke-linejoin", "miter"), "mitre")
                lines_ = []
                for r, closed in rings:
                    pts = r
                    if closed and not np.allclose(pts[0], pts[-1]):
                        pts = np.vstack([pts, pts[:1]])
                    if len(pts) >= 2:
                        lines_.append(LineString(pts))
                if lines_:
                    center = MultiLineString(lines_)
                    geom = G.to_multipolygon(center.buffer(sw / 2.0, cap_style=cap, join_style=join))
                    if clip is not None and not geom.is_empty:
                        geom = G.to_multipolygon(geom.intersection(clip))
                        center = center.intersection(clip)
                        if not isinstance(center, MultiLineString):
                            center = MultiLineString(G.lines(center))
                    if not geom.is_empty:
                        doc.shapes.append(RawShape(index, elem_id, stroke_hex, "stroke", geom, center, sw, cls))
                        index += 1
    if doc.text_count:
        doc.warnings.append(f"{doc.text_count} text element(s) were ignored; convert text to paths first.")
    if doc.width <= 0 or doc.height <= 0:
        b = unary_union([s.geom for s in doc.shapes]).bounds if doc.shapes else (0, 0, 1, 1)
        doc.width = b[2] - b[0]
        doc.height = b[3] - b[1]
    if log is not None:
        log.append(f"Parsed {svg_path.name}: {len(doc.shapes)} shapes, canvas {doc.width:.1f} x {doc.height:.1f} units")
    return doc
