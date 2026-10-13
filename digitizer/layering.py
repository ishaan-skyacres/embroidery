"""Scale to size, centre on the hoop, union per group, knock out lower layers, order groups."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import shapely
from shapely import affinity
from shapely.geometry import LineString, MultiLineString, MultiPolygon, Point
from shapely.ops import unary_union

from . import geometry as G
from .colors import ColorGroup, hex_delta_e
from .params import Params, hoop_size
from .svg_input import Document, RawShape


@dataclass
class StrokeLine:
    line: np.ndarray          # Nx2 mm
    width_mm: float
    closed: bool


@dataclass
class GroupRegion:
    group: ColorGroup
    raw: MultiPolygon                          # union of member shapes (mm)
    region: MultiPolygon                       # after knockout and sliver removal
    strokes: list[StrokeLine] = field(default_factory=list)
    covered_by_upper: MultiPolygon | None = None   # parts of raw that sit under other colours
    layer_rank: int = 0

    @property
    def name(self) -> str:
        return self.group.name


@dataclass
class Layout:
    scale: float
    center_units: tuple[float, float]
    width_mm: float
    height_mm: float
    hoop_name: str
    hoop_w: float
    hoop_h: float
    orientation: str          # "as labelled" or "rotated 90 degrees"
    clearance_mm: float
    margin_mm: float
    regions: list[GroupRegion] = field(default_factory=list)
    conflicts: list[dict[str, Any]] = field(default_factory=list)
    dropped_slivers: list[dict[str, Any]] = field(default_factory=list)
    log: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_mm(self, x: float, y: float) -> tuple[float, float]:
        return ((x - self.center_units[0]) * self.scale, (y - self.center_units[1]) * self.scale)


def transform_geom(geom, layout: Layout):
    g = affinity.translate(geom, -layout.center_units[0], -layout.center_units[1])
    return affinity.scale(g, layout.scale, layout.scale, origin=(0, 0))


def compute_layout(doc: Document, shapes: list[RawShape], size_mm: float, params: Params,
                   hoop: str | None) -> Layout:
    """Scale so the longest side of the stitched artwork equals size_mm and centre on origin."""
    if not shapes:
        raise ValueError("No stitchable shapes found in the artwork.")
    bounds = unary_union([s.geom for s in shapes]).bounds
    w_units = bounds[2] - bounds[0]
    h_units = bounds[3] - bounds[1]
    scale = size_mm / max(w_units, h_units)
    width_mm = w_units * scale
    height_mm = h_units * scale
    name, hw, hh = hoop_size(params, hoop)
    clearance = float(params["machine.hoop_clearance_mm"])
    fits_as_is = width_mm <= hw - 2 * clearance and height_mm <= hh - 2 * clearance
    fits_rotated = width_mm <= hh - 2 * clearance and height_mm <= hw - 2 * clearance
    if fits_as_is:
        orientation = "as labelled"
        margin = min(hw - width_mm, hh - height_mm) / 2
    elif fits_rotated:
        orientation = "rotated 90 degrees"
        margin = min(hh - width_mm, hw - height_mm) / 2
    else:
        max_w = max(hw, hh) - 2 * clearance
        max_h = min(hw, hh) - 2 * clearance
        long_side = max(width_mm, height_mm)
        short_side = min(width_mm, height_mm)
        allowed = min(max_w / long_side, max_h / short_side) * long_side
        raise ValueError(
            f"Design {width_mm:.1f} x {height_mm:.1f} mm does not fit hoop {name} ({hw:.0f} x {hh:.0f} mm) "
            f"with {clearance:.0f} mm clearance in either orientation. Largest size that fits: --size-mm {allowed:.0f}.")
    layout = Layout(scale=scale, center_units=((bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2),
                    width_mm=width_mm, height_mm=height_mm, hoop_name=name, hoop_w=hw, hoop_h=hh,
                    orientation=orientation, clearance_mm=clearance, margin_mm=margin)
    layout.log.append(f"Scaled by {scale:.4f} mm/unit to {width_mm:.1f} x {height_mm:.1f} mm; hoop {name} "
                      f"{orientation}, {margin:.1f} mm to the nearest hoop edge (clearance {clearance:.0f} mm).")
    return layout


def build_regions(doc: Document, groups: list[ColorGroup], member_to_group: dict[str, str],
                  layout: Layout, params: Params, manual_order: list[str] | None) -> Layout:
    """Union shapes per group, knock out lower layers under upper ones, order groups."""
    overlap = float(params["general.overlap_mm"])
    sliver = float(params["general.sliver_area_mm2"])
    simplify_tol = float(params["general.simplify_tolerance_mm"])
    min_feature = float(params["general.min_feature_width_mm"])
    by_group: dict[str, list[RawShape]] = {g.name: [] for g in groups}
    for s in doc.shapes:
        gname = member_to_group.get(s.color)
        if gname is None:
            continue
        by_group[gname].append(s)
    active = [g for g in groups if not g.skip and by_group[g.name]]

    # geometry in mm, simplified
    shape_mm: dict[int, MultiPolygon] = {}
    for g in active:
        for s in by_group[g.name]:
            geom = transform_geom(s.geom, layout)
            geom = G.clean(geom.simplify(simplify_tol, preserve_topology=True))
            shape_mm[s.index] = geom
    all_shapes = [s for g in active for s in by_group[g.name] if s.index in shape_mm and not shape_mm[s.index].is_empty]

    # per-shape knockout by document order: parts under later shapes of other groups are removed,
    # except an overlap band so pull cannot open a gap.
    tree = shapely.STRtree([shape_mm[s.index] for s in all_shapes])
    regions: dict[str, list[MultiPolygon]] = {g.name: [] for g in active}
    covered: dict[str, list] = {g.name: [] for g in active}
    gname_of = {s.index: member_to_group[s.color] for s in all_shapes}
    over_area: dict[tuple[str, str], float] = {}
    over_where: dict[tuple[str, str], list] = {}
    for i, s in enumerate(all_shapes):
        geom = shape_mm[s.index]
        mine = gname_of[s.index]
        hits = tree.query(geom, predicate="intersects")
        uppers = []
        for j in hits:
            t = all_shapes[j]
            if t.index <= s.index or gname_of[t.index] == mine:
                continue
            tg = shape_mm[t.index]
            inter = geom.intersection(tg)
            if inter.is_empty or inter.area < 0.05:
                continue
            key = (gname_of[t.index], mine)       # (upper, lower)
            over_area[key] = over_area.get(key, 0.0) + inter.area
            over_where.setdefault(key, []).append((inter.area, inter.representative_point()))
            uppers.append(tg)
        if uppers:
            upper = unary_union(uppers)
            cover = G.to_multipolygon(geom.intersection(upper))
            covered[mine].append(cover)
            cut = G.inset(upper, overlap)
            if not cut.is_empty:
                geom = G.to_multipolygon(geom.difference(cut))
        regions[mine].append(geom)

    # strokes thinner than the minimum feature width keep their centreline
    strokes: dict[str, list[StrokeLine]] = {g.name: [] for g in active}
    for g in active:
        for s in by_group[g.name]:
            if s.kind == "stroke" and s.centerline is not None:
                w = s.stroke_width * layout.scale
                for ln in G.lines(transform_geom(s.centerline, layout)):
                    coords = np.asarray(ln.coords)
                    closed = bool(np.allclose(coords[0], coords[-1])) and len(coords) > 3
                    strokes[g.name].append(StrokeLine(coords, w, closed))

    # layering relation -> order
    conflicts = []
    rank_edges: dict[tuple[str, str], float] = {}
    names = [g.name for g in active]
    for a in names:
        for b in names:
            if a >= b:
                continue
            ab = over_area.get((a, b), 0.0)   # a over b
            ba = over_area.get((b, a), 0.0)
            if ab > 0 and ba > 0 and min(ab, ba) >= 1.0:
                minority = (b, a) if ab >= ba else (a, b)
                spots = sorted(over_where.get(minority, []), key=lambda t: -t[0])[:3]
                conflicts.append({
                    "upper": a if ab >= ba else b, "lower": b if ab >= ba else a,
                    "area_major": max(ab, ba), "area_minor": min(ab, ba),
                    "where": [(round(p.x, 1), round(p.y, 1), round(ar, 1)) for ar, p in spots],
                    "delta_e": round(hex_delta_e(next(g.color for g in active if g.name == a),
                                                 next(g.color for g in active if g.name == b)), 1),
                })
            if ab > 0 or ba > 0:
                if ab >= ba:
                    rank_edges[(b, a)] = ab      # b below a
                else:
                    rank_edges[(a, b)] = ba

    # outline-like groups (mostly thinner than the minimum feature width) are stitched last so
    # they cover the edges of the fills, whatever the drawing order says
    thin_fraction: dict[str, float] = {}
    line_ratio: dict[str, float] = {}
    for g in active:
        raw = unary_union(regions[g.name]) if regions[g.name] else MultiPolygon()
        if raw.is_empty:
            thin_fraction[g.name] = 0.0
            line_ratio[g.name] = 0.0
            continue
        wide = G.opening(raw, min_feature / 2.0)
        thin_fraction[g.name] = 1.0 - wide.area / raw.area
        # perimeter^2 / (4 pi area): 1 for a disc, hundreds for line work; independent of the design size
        line_ratio[g.name] = raw.length ** 2 / (4.0 * 3.141592653589793 * raw.area)
    outline_groups = {n for n in thin_fraction
                      if thin_fraction[n] >= 0.5 or (line_ratio[n] >= 500 and thin_fraction[n] >= 0.3)}
    for outline in list(outline_groups):
        reversed_from = []
        for other in names:
            if other in outline_groups or other == outline:
                continue
            if (outline, other) in rank_edges:
                reversed_from.append(other)
                del rank_edges[(outline, other)]
            rank_edges[(other, outline)] = rank_edges.get((other, outline), 0.0)
        layout.log.append(f"{outline} is line work ({thin_fraction[outline]*100:.0f}% thinner than {min_feature} mm, "
                          f"perimeter^2/4piA = {line_ratio[outline]:.0f}): stitched last as an outline group"
                          + (f" (drawn under {', '.join(reversed_from)})" if reversed_from else "") + ".")
    order = _topological_order(active, rank_edges, regions)
    if manual_order:
        known = [n for n in manual_order if n in names]
        missing = [n for n in names if n not in known]
        if missing:
            layout.warnings.append(f"groups.yaml order does not mention {', '.join(missing)}; appended at the end.")
        order = known + missing
        for (lower, upper), area in rank_edges.items():
            if order.index(lower) > order.index(upper):
                layout.warnings.append(
                    f"Your order stitches {lower} after {upper}, but {lower} sits under {upper} "
                    f"over {area:.0f} mm2 in the artwork; {lower} will cover {upper} there.")

    group_by_name = {g.name: g for g in active}
    layout.regions = []
    for rank, name in enumerate(order):
        raw = G.clean(unary_union(regions[name])) if regions[name] else MultiPolygon()
        kept = []
        for p in G.polygons(raw):
            extent = max(p.bounds[2] - p.bounds[0], p.bounds[3] - p.bounds[1])
            if p.area < sliver and extent < 2.5 * max(1.0, sliver):
                c = p.representative_point()
                layout.dropped_slivers.append({"group": name, "area_mm2": round(p.area, 2),
                                               "x": round(c.x, 1), "y": round(c.y, 1)})
            else:
                kept.append(p)
        region = G.to_multipolygon(unary_union(kept)) if kept else MultiPolygon()
        cov = G.clean(unary_union(covered[name])) if covered[name] else MultiPolygon()
        layout.regions.append(GroupRegion(group_by_name[name], raw, region, strokes[name], cov, rank))
    layout.conflicts = conflicts
    for c in conflicts:
        where = ", ".join(f"({x}, {y}) mm, {a} mm2" for x, y, a in c["where"])
        layout.log.append(
            f"Layering conflict: {c['upper']} is above {c['lower']} over {c['area_major']:.0f} mm2 but below it "
            f"over {c['area_minor']:.0f} mm2 at {where}. Resolved by knocking {c['upper']} out where {c['lower']} is "
            f"drawn on top, so each colour is still one block. Delta E between them is {c['delta_e']}"
            + (" (close enough to merge with --group if you prefer)." if c["delta_e"] < 15 else "."))
    layout.log.append("Sewing order: " + " -> ".join(order))
    return layout


def _topological_order(groups: list[ColorGroup], edges: dict[tuple[str, str], float],
                       regions: dict[str, list]) -> list[str]:
    """Order groups bottom to top; among free groups stitch the largest first, then the nearest."""
    names = [g.name for g in groups]
    preds: dict[str, set[str]] = {n: set() for n in names}
    for (lower, upper) in edges:
        preds[upper].add(lower)
    area = {n: sum(r.area for r in regions[n]) for n in names}
    cent = {n: (unary_union(regions[n]).centroid if regions[n] else Point(0, 0)) for n in names}
    order: list[str] = []
    remaining = set(names)
    while remaining:
        free = [n for n in remaining if not (preds[n] & remaining)]
        if not free:          # cycle: break it at the smallest area
            free = [min(remaining, key=lambda n: area[n])]
        if order:
            prev = cent[order[-1]]
            free.sort(key=lambda n: (-area[n] / max(1.0, max(area.values())) + 0.15 * prev.distance(cent[n]) / 100.0))
        else:
            free.sort(key=lambda n: -area[n])
        order.append(free[0])
        remaining.remove(free[0])
    return order
