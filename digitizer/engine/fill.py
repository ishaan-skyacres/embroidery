"""Tatami fill: staggered rows, skip-last, pull compensation, sections and hidden travel."""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import shapely
from shapely import affinity
from shapely.geometry import LineString, MultiLineString, Point, Polygon
from shapely.prepared import prep

from .. import geometry as G
from ..stitchplan import JUMP, STITCH, Stitch
from .running import running_stitches


@dataclass
class Section:
    rows: list[tuple[int, float, float, float]]   # (row_index, y, x_start, x_end) in rotated frame


def _row_segments(poly: Polygon, spacing: float, pull: float) -> list[list[tuple[float, float, float, float]]]:
    """Horizontal row segments (row_index, y, x0, x1) across the polygon, grouped by row."""
    x0, y0, x1, y1 = poly.bounds
    rows = []
    n = int(math.floor((y1 - y0) / spacing))
    y_start = y0 + ((y1 - y0) - n * spacing) / 2.0
    if n == 0:
        y_start = (y0 + y1) / 2
    for i in range(n + 1):
        y = y_start + i * spacing
        line = LineString([(x0 - 1, y), (x1 + 1, y)])
        inter = poly.intersection(line)
        segs = []
        for ln in G.lines(inter):
            xs = [c[0] for c in ln.coords]
            a, b = min(xs), max(xs)
            if b - a < 0.05:
                continue
            segs.append((i, y, a - pull, b + pull))
        segs.sort(key=lambda s: s[2])
        rows.append(segs)
    return rows


def _build_sections(rows) -> list[Section]:
    """Group row segments into monotone sections (one segment per row, continuous)."""
    sections: list[Section] = []
    open_secs: list[Section] = []
    for segs in rows:
        new_open: list[Section] = []
        used = set()
        # map each open section to overlapping segments and vice versa
        for sec in open_secs:
            _, _, a0, a1 = sec.rows[-1]
            cands = [j for j, s in enumerate(segs) if s[3] > a0 and s[2] < a1]
            if len(cands) == 1:
                j = cands[0]
                s = segs[j]
                back = [sc for sc in open_secs if sc.rows[-1][3] > s[2] and sc.rows[-1][2] < s[3]]
                if len(back) == 1 and j not in used:
                    sec.rows.append(s)
                    used.add(j)
                    new_open.append(sec)
                    continue
            # section ends here
        for j, s in enumerate(segs):
            if j not in used:
                sec = Section(rows=[s])
                sections.append(sec)
                new_open.append(sec)
        open_secs = new_open
    # sections were appended at creation; keep that order (top to bottom)
    return sections


def _stitch_section(sec: Section, top_down: bool, start_left: bool, max_len: float, staggers: int,
                    skip_last: bool, min_end: float, x_origin: float) -> list[tuple[float, float]]:
    rows = sec.rows if top_down else sec.rows[::-1]
    pts: list[tuple[float, float]] = []
    left_to_right = start_left
    for k, (ri, y, a, b) in enumerate(rows):
        if staggers >= 3:
            # golden-ratio stagger: successive rows shift by 0.618 of the stitch length, so the
            # needle holes never line up into straight diagonal lines (an integer cycle does)
            offset = ((ri * 0.6180339887) % 1.0) * max_len
        else:
            offset = (ri % max(1, staggers)) * (max_len / max(1, staggers))
        # grid positions inside (a, b)
        first = math.ceil((a - x_origin - offset) / max_len)
        xs = []
        x = x_origin + offset + first * max_len
        while x < b:
            if x > a:
                xs.append(x)
            x += max_len
        # merge grid points that sit too close to a row end, but never let a stitch exceed max_len
        if xs and xs[0] - a < min_end and (xs[1] - a if len(xs) > 1 else b - a) <= max_len:
            xs = xs[1:]
        if xs and b - xs[-1] < min_end and (b - xs[-2] if len(xs) > 1 else b - a) <= max_len:
            xs = xs[:-1]
        seq = [a] + xs + [b]
        if not left_to_right:
            seq = seq[::-1]
        last_row = k == len(rows) - 1
        if skip_last and not last_row and len(seq) > 1:
            seq = seq[:-1]
        pts.extend((x, y) for x in seq)
        left_to_right = not left_to_right
    return pts


def tatami_fill(poly: Polygon, angle_deg: float, spacing: float, max_len: float, staggers: int, skip_last: bool,
                pull: float, min_end: float, start: tuple[float, float] | None, travel_len: float,
                trim_threshold: float, underlay: bool = False, underpath: bool = True,
                lock_len: float = 0.7) -> tuple[list[Stitch], list[str]]:
    """Fill one polygon. Returns stitches (travel runs flagged) and notes."""
    notes: list[str] = []
    c = poly.centroid
    origin = (c.x, c.y)
    rot = affinity.rotate(poly, -angle_deg, origin=origin)
    rows = _row_segments(rot, spacing, pull)
    sections = _build_sections(rows)
    if not sections:
        return [], notes
    prepared = prep(rot.buffer(0.01))
    inset_ring = rot.exterior
    stitches: list[Stitch] = []
    x_origin = rot.bounds[0]
    cur = None
    hint = None
    if start is not None:
        sp = affinity.rotate(Point(start), -angle_deg, origin=origin)
        hint = np.array([sp.x, sp.y])
    remaining = list(sections)
    travel_total = 0.0
    jumps = 0
    while remaining:
        # pick the section and orientation whose start is nearest
        best = None
        for sec in remaining:
            for top_down in (True, False):
                first = sec.rows[0] if top_down else sec.rows[-1]
                for start_left in (True, False):
                    sx = first[2] if start_left else first[3]
                    sy = first[1]
                    ref = cur if cur is not None else hint
                    d = 0.0 if ref is None else float(np.hypot(sx - ref[0], sy - ref[1]))
                    # prefer top-down/left-first when equal
                    key = (d, not top_down, not start_left)
                    if best is None or key < best[0]:
                        best = (key, sec, top_down, start_left, (sx, sy))
        _, sec, top_down, start_left, entry = best
        remaining.remove(sec)
        pts = _stitch_section(sec, top_down, start_left, max_len, staggers, skip_last, min_end, x_origin)
        if cur is not None:
            d = float(np.hypot(entry[0] - cur[0], entry[1] - cur[1]))
            if d > trim_threshold:
                if underpath:
                    path = _travel_path(prepared, rot, inset_ring, tuple(cur), entry)
                    travel_total += G.line_length(path)
                    stitches.extend(running_stitches(path, travel_len, travel_len, 0.1, 0.3, 0, include_start=False,
                                                     travel=True, underlay=underlay))
                else:
                    # no underpath: lock off, jump to the next section, lock in
                    from .locks import tie_in, tie_off
                    prev_pts = [st for st in stitches if st.cmd == STITCH][-2:]
                    if len(prev_pts) == 2:
                        stitches.extend(tie_off(prev_pts[0].xy(), prev_pts[1].xy(), lock_len))
                    stitches.append(Stitch(entry[0], entry[1], JUMP))
                    heading = pts[1] if len(pts) > 1 else pts[0]
                    stitches.extend(tie_in(entry, heading, lock_len))
                    jumps += 1
        for x, y in pts:
            stitches.append(Stitch(x, y, STITCH, underlay=underlay))
        cur = np.array(pts[-1])
    if travel_total > 0:
        notes.append(f"{travel_total:.0f} mm of travel runs inside the fill")
    if jumps:
        notes.append(f"{jumps} jump(s) between fill sections (underpath off)")
    # rotate back
    out = []
    ca, sa = math.cos(math.radians(angle_deg)), math.sin(math.radians(angle_deg))
    for s in stitches:
        dx, dy = s.x - origin[0], s.y - origin[1]
        s.x = origin[0] + dx * ca - dy * sa
        s.y = origin[1] + dx * sa + dy * ca
        out.append(s)
    return out, notes


def _travel_path(prepared, poly: Polygon, ring, a, b) -> np.ndarray:
    """A path from a to b that stays inside the polygon: straight if possible, else along the boundary."""
    straight = LineString([a, b])
    if prepared.covers(straight):
        return np.asarray([a, b], float)
    # walk along the (inset) exterior ring: shorter of the two arcs
    try:
        da = ring.project(Point(a))
        db = ring.project(Point(b))
        L = ring.length
        if da > db:
            da, db = db, da
            a, b = b, a
            flipped = True
        else:
            flipped = False
        arc1 = shapely.ops.substring(ring, da, db)
        arc2_parts = [shapely.ops.substring(ring, db, L), shapely.ops.substring(ring, 0, da)]
        arc2 = MultiLineString([p for p in arc2_parts if not p.is_empty and p.length > 0])
        if arc1.length <= (db - da) + (L - (db - da)) - arc1.length:
            coords = np.asarray(arc1.coords)
        else:
            coords = np.vstack([np.asarray(p.coords) for p in arc2.geoms]) if not arc2.is_empty else np.asarray(arc1.coords)
            coords = coords[::-1]
        pa = np.asarray(a, float)
        pb = np.asarray(b, float)
        path = np.vstack([pa, coords, pb])
        if flipped:
            path = path[::-1]
        return path
    except Exception:
        return np.asarray([a, b], float)


def edge_run(poly: Polygon, inset: float, stitch_len: float) -> list[np.ndarray]:
    """Running-stitch rings just inside the outline (exterior and holes)."""
    shrunk = poly.buffer(-inset)
    rings = []
    for p in G.polygons(shrunk):
        rings.append(np.asarray(p.exterior.coords))
        for r in p.interiors:
            rings.append(np.asarray(r.coords))
    return rings
