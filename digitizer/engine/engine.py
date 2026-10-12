"""Assemble colour blocks from classified parts: sequencing, travel, locks, underlay."""
from __future__ import annotations

import math
from typing import Any

import numpy as np
from shapely.geometry import LineString, MultiPolygon, Point
from shapely.ops import unary_union
from shapely.prepared import prep

from .. import geometry as G
from ..classify import Part, SkeletonGraph
from ..layering import Layout
from ..params import Params
from ..stitchplan import JUMP, STITCH, TRIM, ColorBlock, Stitch, StitchObject, StitchPlan
from . import fill as F
from . import satin as S
from .locks import enforce_min_length, split_long, tie_in, tie_off
from .running import route_graph, running_stitches


def location_words(x: float, y: float, w: float, h: float) -> str:
    """Rough position of a point in the design ('upper left', 'centre', ...)."""
    col = "left" if x < -w / 6 else ("right" if x > w / 6 else "")
    row = "upper" if y < -h / 6 else ("lower" if y > h / 6 else "")
    if not col and not row:
        return "centre"
    return (row + " " + col).strip() if row else ("centre " + col)


class BlockBuilder:
    """Builds one colour block's stitch list with travel and lock rules."""

    def __init__(self, params: Params, log: list[str]):
        self.params = params
        self.log = log
        self.trim_threshold = float(params["machine.trim_jump_threshold_mm"])
        self.max_travel = float(params["sequence.max_travel_mm"])
        self.travel_under_cover = bool(params["sequence.travel_under_cover"])
        self.travel_len = float(params["fill.travel_stitch_length_mm"])
        self.lock_len = float(params["general.lock_stitch.length_mm"])
        self.lock_style = params["general.lock_stitch.style"]
        self.min_len = float(params["general.min_stitch_length_mm"])
        self.max_len = float(params["machine.max_stitch_mm"])
        self.stitches: list[Stitch] = []
        self.cur: tuple[float, float] | None = None
        self.prev: tuple[float, float] | None = None
        self.jumps: list[tuple[tuple[float, float], tuple[float, float], float]] = []

    def _last_two(self):
        pts = [s for s in self.stitches if s.cmd == STITCH]
        if len(pts) >= 2:
            return pts[-2].xy(), pts[-1].xy()
        if pts:
            return pts[-1].xy(), pts[-1].xy()
        return None, None

    def connect(self, target: tuple[float, float], heading: tuple[float, float], cover) -> str:
        """Move the needle from the current position to `target`. Returns how."""
        if self.cur is None:
            self.stitches.append(Stitch(target[0], target[1], JUMP))
            self.stitches.extend(tie_in(target, heading, self.lock_len, self.lock_style))
            self.cur = target
            return "start"
        d = math.hypot(target[0] - self.cur[0], target[1] - self.cur[1])
        if d <= self.trim_threshold:
            return "stitch"
        if self.travel_under_cover and d <= self.max_travel and cover is not None:
            line = LineString([self.cur, target])
            if cover.covers(line):
                self.stitches.extend(running_stitches(np.asarray([self.cur, target]), self.travel_len, self.travel_len,
                                                      0.1, 0.3, 0, include_start=False, travel=True))
                self.cur = target
                return "travel"
        prev, last = self._last_two()
        if last is not None:
            self.stitches.extend(tie_off(prev, last, self.lock_len, self.lock_style))
        if d > self.max_travel:
            self.stitches.append(Stitch(last[0] if last else self.cur[0], last[1] if last else self.cur[1], TRIM))
        self.stitches.append(Stitch(target[0], target[1], JUMP))
        self.jumps.append((self.cur, target, d))
        self.stitches.extend(tie_in(target, heading, self.lock_len, self.lock_style))
        self.cur = target
        return "jump"

    def add(self, stitches: list[Stitch]) -> None:
        if not stitches:
            return
        self.stitches.extend(stitches)
        for s in reversed(stitches):
            if s.cmd == STITCH:
                self.cur = s.xy()
                break

    def finish(self) -> list[Stitch]:
        prev, last = self._last_two()
        if last is not None:
            self.stitches.extend(tie_off(prev, last, self.lock_len, self.lock_style))
        out = enforce_min_length(self.stitches, self.min_len)
        out = split_long(out, self.max_len)
        return out


# ---------------------------------------------------------------------------
def _fill_params(params: Params, kind: str) -> dict[str, Any]:
    if kind == "satin_fill":
        return dict(spacing=float(params["satin.spacing_mm"]), max_len=float(params["satin.split_stitch_length_mm"]),
                    staggers=int(params["fill.staggers"]), skip_last=bool(params["fill.skip_last"]),
                    pull=float(params["satin.pull_compensation_mm"]), min_end=0.4)
    return dict(spacing=float(params["fill.row_spacing_mm"]), max_len=float(params["fill.max_stitch_length_mm"]),
                staggers=int(params["fill.staggers"]), skip_last=bool(params["fill.skip_last"]),
                pull=float(params["fill.pull_compensation_mm"]), min_end=float(params["fill.min_row_end_stitch_mm"]))


def stitch_fill_part(part: Part, builder: BlockBuilder, params: Params, cover, notes: list[str]) -> list[StitchObject]:
    objs: list[StitchObject] = []
    fp = _fill_params(params, part.kind)
    u = params["fill.underlay"]
    angle = part.angle_deg if part.angle_deg is not None else float(params["fill.angle_deg"])
    polys = sorted(G.polygons(part.geom), key=lambda p: p.area, reverse=True)
    # nearest-first ordering of polygons from the current position
    ordered = []
    cur = builder.cur
    remaining = polys
    while remaining:
        if cur is None:
            nxt = remaining[0]
        else:
            nxt = min(remaining, key=lambda p: p.distance(Point(cur)))
        ordered.append(nxt)
        remaining = [p for p in remaining if p is not nxt]
        cur = (nxt.centroid.x, nxt.centroid.y)
    for poly in ordered:
        size = max(poly.bounds[2] - poly.bounds[0], poly.bounds[3] - poly.bounds[1])
        width = 2 * _inscribed(poly)
        first_target = None
        # ---- underlay
        if u["enabled"] and width >= 2.0:
            inset = float(u["inset_mm"]) if part.kind == "fill" else float(params["satin.underlay.contour_inset_mm"])
            shrunk = G.inset(poly, inset)
            layers = int(u.get("layers", 1))
            underlay_angles = [angle + float(u["angle_offset_deg"])]
            if layers >= 2:
                underlay_angles.append(angle)
            for ua in underlay_angles:
                for sp in G.polygons(shrunk):
                    if sp.area < 1.0:
                        continue
                    st, _ = F.tatami_fill(sp, ua, fp["spacing"] * float(u["row_spacing_factor"]), float(u["max_stitch_length_mm"]),
                                          2, False, 0.0, 0.5, builder.cur, builder.travel_len, builder.trim_threshold,
                                          underlay=True)
                    if not st:
                        continue
                    st = [s for s in st if s.cmd == STITCH]
                    how = builder.connect(st[0].xy(), st[1].xy() if len(st) > 1 else st[0].xy(), cover)
                    builder.add(st)
                    objs.append(StitchObject("underlay", f"tatami underlay at {ua % 180:.0f} deg", st, {"how": how}))
            edge = bool(u.get("edge_run_always", False)) or size >= float(u["edge_run_min_size_mm"]) or part.kind == "satin_fill"
            if edge:
                for ring in F.edge_run(poly, float(u["edge_run_inset_mm"]), float(u["edge_run_stitch_length_mm"])):
                    if len(ring) < 3:
                        continue
                    # start the ring at the point nearest the current position
                    if builder.cur is not None:
                        k = int(np.argmin(np.hypot(ring[:, 0] - builder.cur[0], ring[:, 1] - builder.cur[1])))
                        ring = np.vstack([ring[k:-1], ring[:k + 1]]) if k > 0 else ring
                    st = running_stitches(ring, float(u["edge_run_stitch_length_mm"]), 1.5, 0.15, 0.5, 0,
                                          include_start=True, underlay=True)
                    if len(st) < 2:
                        continue
                    how = builder.connect(st[0].xy(), st[1].xy(), cover)
                    builder.add(st)
                    objs.append(StitchObject("underlay", "edge-run underlay", st, {"how": how}))
        # ---- top fill
        st, fnotes = F.tatami_fill(poly, angle, fp["spacing"], fp["max_len"], fp["staggers"], fp["skip_last"], fp["pull"],
                                   fp["min_end"], builder.cur, builder.travel_len, builder.trim_threshold)
        notes.extend(fnotes)
        if not st:
            continue
        first = next(s for s in st if s.cmd == STITCH)
        second = next((s for s in st if s.cmd == STITCH and s is not first), first)
        how = builder.connect(first.xy(), second.xy(), cover)
        builder.add(st)
        label = "satin-style fill" if part.kind == "satin_fill" else "tatami fill"
        objs.append(StitchObject(part.kind, f"{label} {poly.area:.0f} mm2 at {angle % 180:.0f} deg", st,
                                 {"how": how, "area": poly.area, "angle": angle}))
    return objs


def _inscribed(poly) -> float:
    lo, hi = 0.0, max(poly.bounds[2] - poly.bounds[0], poly.bounds[3] - poly.bounds[1]) / 2
    for _ in range(12):
        mid = (lo + hi) / 2
        if poly.buffer(-mid).is_empty:
            hi = mid
        else:
            lo = mid
    return lo


def stitch_satin_part(part: Part, builder: BlockBuilder, params: Params, cover, notes: list[str]) -> list[StitchObject]:
    """Satin all branches of a skeleton graph with hidden travel (walk out, satin back)."""
    sp = params["satin"]
    uc = sp["underlay"]
    spacing = float(sp["spacing_mm"])
    comp = float(sp["pull_compensation_mm"])
    split_len = float(sp["split_stitch_length_mm"])
    strength = uc.get("strength", "normal")
    shift = 1 if strength in ("strong", "double") else 0
    thresholds = [float(uc["none_below_mm"]), float(uc["center_walk_below_mm"]), float(uc["contour_below_mm"])]
    if shift:
        thresholds = [t * 0.75 for t in thresholds]
    graph = part.graph
    clipper = S.Clipper(part.geom) if part.geom is not None else None
    objs: list[StitchObject] = []
    adjacency: dict[int, list[int]] = {}
    for i, br in enumerate(graph.branches):
        adjacency.setdefault(br.a, []).append(i)
        adjacency.setdefault(br.b, []).append(i)
    visited_branch = set()
    visited_node = set()
    walk_len = float(uc["center_walk_stitch_length_mm"])

    def branch_dir(i: int, from_node: int):
        br = graph.branches[i]
        if br.a == from_node:
            return br.pts, br.half_w, br.b
        return br.pts[::-1], br.half_w[::-1], br.a

    def satin_branch(i: int, pts, half_w, label: str):
        """Underlay then satin along pts (ends at pts[-1])."""
        width = float(2 * np.mean(half_w))
        st: list[Stitch] = []
        if width >= thresholds[2] or (width >= thresholds[1] and strength == "double"):
            st.extend(S.contour_underlay(pts, half_w, float(uc["contour_inset_mm"]), float(uc["contour_stitch_length_mm"]), comp, clipper))
            if strength == "double":
                st.extend(S.zigzag_underlay(pts, half_w, float(uc["zigzag_spacing_mm"]), float(uc["zigzag_inset_mm"]), clipper))
                st.extend(S.zigzag_underlay(pts, half_w, float(uc["zigzag_spacing_mm"]), float(uc["zigzag_inset_mm"]), clipper, reverse=True))
            elif width >= thresholds[2]:
                st.extend(S.zigzag_underlay(pts, half_w, float(uc["zigzag_spacing_mm"]), float(uc["zigzag_inset_mm"]), clipper))
                st.extend(S.center_walk(pts, walk_len, reverse=True))
        elif width >= thresholds[1]:
            st.extend(S.contour_underlay(pts, half_w, float(uc["contour_inset_mm"]), float(uc["contour_stitch_length_mm"]), comp, clipper))
        # the walk out (done by the caller) is the centre-walk underlay for 2 to 4 mm columns
        sat = S.satin_stitches(pts, half_w, spacing, comp, split_len, clipper, float(sp["short_stitch_inset_percent"]) / 100.0)
        st.extend(sat)
        return st, width

    def walk(pts) -> list[Stitch]:
        return S.center_walk(pts, walk_len)

    def dfs(node: int):
        visited_node.add(node)
        for i in list(adjacency.get(node, [])):
            if i in visited_branch:
                continue
            visited_branch.add(i)
            pts, hw, other = branch_dir(i, node)
            if len(pts) < 2:
                continue
            # travel out along the centreline (hidden under the satin stitched on the way back)
            out_walk = walk(pts)
            builder.add(out_walk)
            objs.append(StitchObject("underlay", "centre walk", out_walk))
            if other not in visited_node:
                dfs(other)
            # satin back toward `node`
            st, width = satin_branch(i, pts[::-1], hw[::-1], "satin")
            builder.add(st)
            objs.append(StitchObject("satin", f"satin {width:.1f} mm wide, {G.line_length(pts):.0f} mm", st, {"width": width}))

    # components: start each at the endpoint nearest the current position
    deg = graph.degree()
    all_nodes = set(graph.nodes)
    while all_nodes - visited_node:
        cand = all_nodes - visited_node
        ends = [n for n in cand if deg.get(n, 0) == 1] or list(cand)
        if builder.cur is not None:
            start = min(ends, key=lambda n: G.dist(graph.nodes[n], builder.cur))
        else:
            start = ends[0]
        if not any(i not in visited_branch for i in adjacency.get(start, [])):
            visited_node.add(start)
            continue
        first_branch = next(i for i in adjacency[start] if i not in visited_branch)
        pts, hw, _ = branch_dir(first_branch, start)
        heading = pts[min(1, len(pts) - 1)]
        how = builder.connect(tuple(pts[0]), tuple(heading), cover)
        if objs:
            objs[-1].meta.setdefault("how", how)
        dfs(start)
    return objs


def stitch_running_part(part: Part, builder: BlockBuilder, params: Params, cover, notes: list[str]) -> list[StitchObject]:
    rp = params["running"]
    repeats = int(rp["bean_repeats"]) if part.bean else 0
    objs: list[StitchObject] = []
    routes = route_graph(part.graph, builder.cur)
    for route in routes:
        first = True
        for pts, repeat in route:
            st = running_stitches(pts, float(rp["stitch_length_mm"]), float(rp["curve_stitch_length_mm"]),
                                  float(rp["tolerance_mm"]), float(rp["min_stitch_length_mm"]),
                                  0 if repeat else repeats, include_start=first)
            if not st:
                continue
            if first:
                heading = st[1].xy() if len(st) > 1 else st[0].xy()
                how = builder.connect(st[0].xy(), heading, cover)
                first = False
            builder.add(st)
            objs.append(StitchObject("bean" if (part.bean and not repeat) else "running",
                                     ("bean" if part.bean and not repeat else "running") + f" stitch {G.line_length(pts):.0f} mm", st))
    return objs


# ---------------------------------------------------------------------------
def order_parts(parts: list[Part], start: tuple[float, float] | None,
                next_start: tuple[float, float] | None = None) -> list[Part]:
    """Fills centre-out (large first), then satin, then outlines, each nearest-neighbour.

    When `next_start` is given, the last object of the last kind present is the one nearest to
    it, so the block ends close to where the next colour begins.
    """
    fills = [p for p in parts if p.kind in ("fill", "satin_fill")]
    satins = [p for p in parts if p.kind == "satin"]
    runs = [p for p in parts if p.kind == "running"]
    fills.sort(key=lambda p: (G.dist(p.center(), (0.0, 0.0)) - 0.02 * p.area))
    ordered = list(fills)
    cur = fills[-1].center() if fills else start
    groups = [g for g in (satins, runs) if g]
    for gi, group in enumerate(groups):
        remaining = list(group)
        last = None
        if next_start is not None and gi == len(groups) - 1 and len(remaining) > 1:
            last = min(remaining, key=lambda p: G.dist(p.center(), next_start))
            remaining.remove(last)
        while remaining:
            if cur is None:
                nxt = max(remaining, key=lambda p: p.area)
            else:
                nxt = min(remaining, key=lambda p: G.dist(p.center(), cur))
            ordered.append(nxt)
            remaining.remove(nxt)
            cur = nxt.center()
        if last is not None:
            ordered.append(last)
            cur = last.center()
    return ordered


def block_start_point(parts: list[Part]) -> tuple[float, float] | None:
    """Where a block will begin: the centre of its first object in sewing order."""
    ordered = order_parts(parts, None)
    return ordered[0].center() if ordered else None


def build_plan(layout: Layout, parts_by_group: dict[str, list[Part]], params: Params, log: list[str]) -> StitchPlan:
    plan = StitchPlan(engine="python")
    prev_end: tuple[float, float] | None = None
    W, H = layout.width_mm, layout.height_mm
    knockdown_done = False
    for region in layout.regions:
        parts = parts_by_group.get(region.name, [])
        if not parts and not (params["knockdown.enabled"] and not knockdown_done):
            continue
        builder = BlockBuilder(params, log)
        block = ColorBlock(group=region.name, color=region.group.color, thread=region.group.thread or {})
        notes: list[str] = []
        # optional knockdown layer under the whole design, in the first colour
        if params["knockdown.enabled"] and not knockdown_done:
            kd = params["knockdown"]
            whole = unary_union([r.region for r in layout.regions if not r.region.is_empty]).buffer(float(kd["expand_mm"]))
            for poly in G.polygons(whole):
                st, _ = F.tatami_fill(poly, float(params["fill.angle_deg"]) + 90, float(kd["row_spacing_mm"]),
                                      float(kd["max_stitch_length_mm"]), 2, True, 0.0, 0.5, builder.cur,
                                      builder.travel_len, builder.trim_threshold, underlay=True)
                st = [s for s in st if s.cmd == STITCH]
                if len(st) > 1:
                    builder.connect(st[0].xy(), st[1].xy(), None)
                    builder.add(st)
                    block.objects.append(StitchObject("knockdown", f"knockdown layer {poly.area:.0f} mm2", st))
            block.descriptions.append("a low-density knockdown layer under the whole design (keeps stitches from sinking into the pile)")
            knockdown_done = True
            log.append(f"{region.name}: knockdown layer added under the whole design")
        next_start = None
        if bool(params.get("sequence.end_near_next_start", True)):
            later = [r for r in layout.regions[layout.regions.index(region) + 1:] if parts_by_group.get(r.name)]
            if later:
                next_start = block_start_point(parts_by_group[later[0].name])
        ordered = order_parts(parts, prev_end, next_start)
        # geometry that later objects of this colour will cover (travel may cross it)
        remaining_geoms = [p.geom for p in ordered if p.geom is not None]
        for idx, part in enumerate(ordered):
            cover_geom = unary_union([g for g in remaining_geoms[idx:] if g is not None]) if remaining_geoms[idx:] else None
            cover = prep(cover_geom.buffer(0.3)) if cover_geom is not None and not cover_geom.is_empty else None
            if part.kind in ("fill", "satin_fill"):
                objs = stitch_fill_part(part, builder, params, cover, notes)
            elif part.kind == "satin":
                objs = stitch_satin_part(part, builder, params, cover, notes)
            else:
                objs = stitch_running_part(part, builder, params, cover, notes)
            block.objects.extend(objs)
            cx, cy = part.center()
            part.notes.append(f"at {location_words(cx, cy, W, H)}")
        block.stitches = builder.finish()
        block.descriptions.extend(describe_parts(ordered, W, H))
        block.watch.extend(watch_items(ordered, builder))
        if builder.jumps:
            block.watch.append(f"{len(builder.jumps)} jump(s) inside this colour: trim the floating threads by hand at the stop "
                               "(" + ", ".join(f"{location_words(b[0], b[1], W, H)} {d:.0f} mm" for _, b, d in builder.jumps[:4])
                               + (" ..." if len(builder.jumps) > 4 else "") + ").")
        if notes:
            log.append(f"{region.name}: " + "; ".join(sorted(set(notes))))
        plan.blocks.append(block)
        prev_end = block.last_xy() or prev_end
        log.append(f"{region.name}: {block.stitch_count()} stitches, {block.jump_count()} jumps, {block.trim_count()} trims")
    return plan


def describe_parts(parts: list[Part], W: float, H: float) -> list[str]:
    out = []
    fills = [p for p in parts if p.kind == "fill"]
    blobs = [p for p in parts if p.kind == "satin_fill"]
    satins = [p for p in parts if p.kind == "satin"]
    runs = [p for p in parts if p.kind == "running"]
    if fills:
        big = sorted(fills, key=lambda p: -p.area)[:3]
        where = ", ".join(f"{p.area:.0f} mm2 {location_words(*p.center(), W, H)}" for p in big)
        out.append(f"{len(fills)} tatami fill area(s) totalling {sum(p.area for p in fills):.0f} mm2 (largest: {where})")
    if blobs:
        out.append(f"{len(blobs)} small shape(s) stitched as satin-style fills ({min(p.width_mm for p in blobs):.0f} to "
                   f"{max(p.width_mm for p in blobs):.0f} mm across)")
    if satins:
        tot = sum(p.graph.total_length() for p in satins if p.graph)
        out.append(f"{len(satins)} satin column(s), {min(p.width_mm for p in satins):.1f} to "
                   f"{max(p.width_mm for p in satins):.1f} mm wide, {tot:.0f} mm in total")
    if runs:
        tot = sum(p.graph.total_length() for p in runs if p.graph)
        bean = any(p.bean for p in runs)
        out.append(f"{'bean (triple) ' if bean else ''}running-stitch lines, {tot:.0f} mm in total, for details thinner than 1.5 mm")
    return out


def watch_items(parts: list[Part], builder: BlockBuilder) -> list[str]:
    out = []
    if any(p.kind == "fill" and p.area > 400 for p in parts):
        out.append("Large fill: watch for puckering at the edges; if the fabric ripples, stop and re-hoop with more stabilizer.")
    if any(p.kind == "satin" and p.width_mm < 2.0 for p in parts):
        out.append("Narrow satin columns: watch for thread breaks or shredding; slow the machine if the thread frays.")
    if any(p.kind == "satin_fill" for p in parts):
        out.append("Small satin-style shapes: check the edges stay crisp and the shape is not pulling narrow.")
    if any(p.kind == "running" for p in parts):
        out.append("Outline lines: check they line up with the fills already stitched (registration). If they drift, the fabric slipped in the hoop.")
    return out
