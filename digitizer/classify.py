"""Shape classification by local width.

Each colour region is rasterised (0.05 mm pixels); a Euclidean distance
transform gives the local half-width and a thinning skeleton gives the
centreline graph. Parts narrower than the minimum feature width become
running/bean stitch along the skeleton, ribbon-like parts 1.5 to 10 mm wide
become satin branches, compact blobs up to 10 mm become satin-style fills, and
everything wider becomes tatami fill.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
from shapely.geometry import LineString, MultiPolygon, Polygon
from shapely.ops import unary_union
from skimage.morphology import skeletonize

from . import geometry as G
from .layering import GroupRegion
from .params import Params

PX_PER_MM = 20.0


# ---------------------------------------------------------------------------
# raster helpers
# ---------------------------------------------------------------------------
@dataclass
class Raster:
    mask: np.ndarray            # bool HxW
    x0: float                   # mm of pixel column 0 (left edge)
    y0: float
    ppm: float

    def to_mm(self, row: np.ndarray, col: np.ndarray) -> np.ndarray:
        return np.column_stack([self.x0 + (col + 0.5) / self.ppm, self.y0 + (row + 0.5) / self.ppm])

    def to_px(self, x: float, y: float) -> tuple[int, int]:
        return int((y - self.y0) * self.ppm), int((x - self.x0) * self.ppm)

    def inside(self, x: float, y: float) -> bool:
        r, c = self.to_px(x, y)
        return 0 <= r < self.mask.shape[0] and 0 <= c < self.mask.shape[1] and bool(self.mask[r, c])


def rasterize(geom, ppm: float = PX_PER_MM, pad_mm: float = 1.0) -> Raster:
    x0, y0, x1, y1 = geom.bounds
    x0 -= pad_mm
    y0 -= pad_mm
    w = int(math.ceil((x1 + pad_mm - x0) * ppm)) + 1
    h = int(math.ceil((y1 + pad_mm - y0) * ppm)) + 1
    img = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(img)
    for poly in G.polygons(geom):
        ext = [((x - x0) * ppm, (y - y0) * ppm) for x, y in poly.exterior.coords]
        draw.polygon(ext, fill=1)
    for poly in G.polygons(geom):
        for ring in poly.interiors:
            pts = [((x - x0) * ppm, (y - y0) * ppm) for x, y in ring.coords]
            draw.polygon(pts, fill=0)
    return Raster(np.asarray(img, dtype=bool), x0, y0, ppm)


# ---------------------------------------------------------------------------
# skeleton graph
# ---------------------------------------------------------------------------
@dataclass
class Branch:
    pts: np.ndarray                 # Nx2 mm
    half_w: np.ndarray              # N half-widths (mm)
    a: int                          # start node id
    b: int                          # end node id

    @property
    def length(self) -> float:
        return G.line_length(self.pts)

    def mean_width(self) -> float:
        return float(2 * np.mean(self.half_w)) if len(self.half_w) else 0.0

    def max_width(self) -> float:
        return float(2 * np.max(self.half_w)) if len(self.half_w) else 0.0

    def reversed(self) -> "Branch":
        return Branch(self.pts[::-1].copy(), self.half_w[::-1].copy(), self.b, self.a)


@dataclass
class SkeletonGraph:
    nodes: dict[int, tuple[float, float]] = field(default_factory=dict)
    branches: list[Branch] = field(default_factory=list)

    def degree(self) -> dict[int, int]:
        d = {n: 0 for n in self.nodes}
        for br in self.branches:
            d[br.a] = d.get(br.a, 0) + 1
            d[br.b] = d.get(br.b, 0) + 1
        return d

    def total_length(self) -> float:
        return sum(b.length for b in self.branches)

    def max_width(self) -> float:
        return max((b.max_width() for b in self.branches), default=0.0)

    def mean_width(self) -> float:
        tot = self.total_length()
        if tot <= 0:
            return 0.0
        return sum(b.mean_width() * b.length for b in self.branches) / tot


OFFSETS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


def skeleton_graph(geom, ppm: float = PX_PER_MM, prune: bool = True) -> SkeletonGraph:
    """Skeletonise a region and return its branch graph in mm with half-widths."""
    ras = rasterize(geom, ppm)
    mask = ras.mask
    if mask.sum() == 0:
        return SkeletonGraph()
    dt = ndimage.distance_transform_edt(mask)
    skel = skeletonize(mask)
    H, W = skel.shape
    if skel.sum() == 0:
        return SkeletonGraph()
    # degree of each skeleton pixel
    kernel = np.ones((3, 3), dtype=int)
    kernel[1, 1] = 0
    deg = ndimage.convolve(skel.astype(int), kernel, mode="constant") * skel
    junction = skel & (deg >= 3)
    endpoint = skel & (deg == 1)
    labels, n_j = ndimage.label(junction, structure=np.ones((3, 3)))
    node_id = np.full(skel.shape, -1, dtype=int)
    node_id[junction] = labels[junction] - 1
    next_id = n_j
    er, ec = np.nonzero(endpoint)
    for r, c in zip(er, ec):
        node_id[r, c] = next_id
        next_id += 1
    graph = SkeletonGraph()
    node_pixels: dict[int, list[tuple[int, int]]] = {}
    nr, nc = np.nonzero(node_id >= 0)
    for r, c in zip(nr, nc):
        node_pixels.setdefault(int(node_id[r, c]), []).append((r, c))
    visited = np.zeros(skel.shape, dtype=bool)

    def neighbours(r, c):
        for dr, dc in OFFSETS:
            rr, cc = r + dr, c + dc
            if 0 <= rr < H and 0 <= cc < W and skel[rr, cc]:
                yield rr, cc

    def trace(start_node: int, r0: int, c0: int, r1: int, c1: int):
        chain = [(r0, c0)]
        pr, pc = r0, c0
        r, c = r1, c1
        while True:
            if node_id[r, c] >= 0:
                chain.append((r, c))
                return node_id[r, c], chain
            if visited[r, c]:
                return None, chain
            visited[r, c] = True
            chain.append((r, c))
            nxt = None
            for rr, cc in neighbours(r, c):
                if (rr, cc) == (pr, pc):
                    continue
                if node_id[rr, cc] >= 0 and node_id[rr, cc] == start_node and len(chain) < 3:
                    continue
                if visited[rr, cc] and node_id[rr, cc] < 0:
                    continue
                nxt = (rr, cc)
                break
            if nxt is None:
                return None, chain
            pr, pc = r, c
            r, c = nxt

    def add_branch(a: int, b: int, chain: list[tuple[int, int]]):
        rows = np.array([p[0] for p in chain])
        cols = np.array([p[1] for p in chain])
        pts = ras.to_mm(rows, cols)
        hw = dt[rows, cols] / ppm
        graph.branches.append(Branch(pts, hw, a, b))

    for nid, pixels in list(node_pixels.items()):
        for r, c in pixels:
            for rr, cc in neighbours(r, c):
                if node_id[rr, cc] >= 0:
                    if node_id[rr, cc] != nid and nid < node_id[rr, cc] and not visited[rr, cc]:
                        # two node clusters touching directly: zero-length branch
                        add_branch(nid, int(node_id[rr, cc]), [(r, c), (rr, cc)])
                    continue
                if visited[rr, cc]:
                    continue
                end, chain = trace(nid, r, c, rr, cc)
                if end is None:
                    # dangling chain (should be rare): make its end a node
                    end = next_id
                    next_id += 1
                    node_id[chain[-1]] = end
                    node_pixels[end] = [chain[-1]]
                add_branch(nid, int(end), chain)
    # isolated loops without any node
    loops = skel & ~visited & (node_id < 0)
    lr, lc = np.nonzero(loops)
    if len(lr):
        lab, n = ndimage.label(loops, structure=np.ones((3, 3)))
        for k in range(1, n + 1):
            rr, cc = np.nonzero(lab == k)
            r, c = int(rr[0]), int(cc[0])
            nid = next_id
            next_id += 1
            node_id[r, c] = nid
            node_pixels[nid] = [(r, c)]
            for r2, c2 in neighbours(r, c):
                if not visited[r2, c2] and node_id[r2, c2] < 0:
                    end, chain = trace(nid, r, c, r2, c2)
                    add_branch(nid, nid if end is None else int(end), chain)
                    break
    for nid, pixels in node_pixels.items():
        rows = np.array([p[0] for p in pixels])
        cols = np.array([p[1] for p in pixels])
        xy = ras.to_mm(rows, cols).mean(axis=0)
        graph.nodes[nid] = (float(xy[0]), float(xy[1]))
    # dt at nodes, used for pruning and tip extension
    node_hw = {}
    for nid, pixels in node_pixels.items():
        node_hw[nid] = max(dt[r, c] for r, c in pixels) / ppm
    if prune:
        _prune_spurs(graph, node_hw)
    _merge_degree_two(graph)
    _extend_tips(graph, ras, dt)
    _smooth_branches(graph, ppm)
    return graph


def _prune_spurs(graph: SkeletonGraph, node_hw: dict[int, float]) -> None:
    for _ in range(3):
        deg = graph.degree()
        keep = []
        removed = False
        for br in graph.branches:
            a_end = deg.get(br.a, 0) == 1
            b_end = deg.get(br.b, 0) == 1
            if a_end != b_end:
                junction = br.b if a_end else br.a
                # a spur shorter than the inscribed radius at its junction lies inside the circle
                # the satin covers there anyway; longer spurs are real features (caps, lobes)
                limit = max(0.3, 0.5 * node_hw.get(junction, 0.0))
                if br.length < limit and deg.get(junction, 0) >= 3:
                    removed = True
                    continue
            keep.append(br)
        graph.branches = keep
        if not removed:
            break
    used = {br.a for br in graph.branches} | {br.b for br in graph.branches}
    graph.nodes = {n: p for n, p in graph.nodes.items() if n in used}


def _merge_degree_two(graph: SkeletonGraph) -> None:
    changed = True
    while changed:
        changed = False
        deg = graph.degree()
        for nid, d in deg.items():
            if d != 2:
                continue
            incident = [br for br in graph.branches if br.a == nid or br.b == nid]
            if len(incident) != 2 or incident[0] is incident[1]:
                continue
            b1, b2 = incident
            if b1.a == b1.b or b2.a == b2.b:
                continue
            if b1.b != nid:
                b1 = b1.reversed()
            if b2.a != nid:
                b2 = b2.reversed()
            merged = Branch(np.vstack([b1.pts, b2.pts[1:]]), np.concatenate([b1.half_w, b2.half_w[1:]]), b1.a, b2.b)
            graph.branches = [br for br in graph.branches if not any(br is x for x in incident)] + [merged]
            graph.nodes.pop(nid, None)
            changed = True
            break


def _extend_tips(graph: SkeletonGraph, ras: Raster, dt: np.ndarray) -> None:
    deg = graph.degree()
    for br in graph.branches:
        for end in ("a", "b"):
            nid = getattr(br, end)
            if deg.get(nid, 0) != 1 or len(br.pts) < 2:
                continue
            pts = br.pts if end == "b" else br.pts[::-1]
            k = min(len(pts) - 1, 6)
            d = G.unit(pts[-1] - pts[-1 - k])
            r = br.half_w[-1] if end == "b" else br.half_w[0]
            step = 0.5 / ras.ppm
            x, y = pts[-1]
            travelled = 0.0
            limit = max(r * 2.0, 0.5)
            while travelled < limit:
                nx, ny = x + d[0] * step, y + d[1] * step
                if not ras.inside(nx, ny):
                    break
                x, y, travelled = nx, ny, travelled + step
            if travelled > 0.05:
                new = np.array([[x, y]])
                if end == "b":
                    br.pts = np.vstack([br.pts, new])
                    br.half_w = np.append(br.half_w, br.half_w[-1])
                else:
                    br.pts = np.vstack([new, br.pts])
                    br.half_w = np.insert(br.half_w, 0, br.half_w[0])
                graph.nodes[nid] = (float(x), float(y))


def _smooth_branches(graph: SkeletonGraph, ppm: float) -> None:
    """Remove the raster staircase: Douglas-Peucker within 0.08 mm, then a light moving average.

    Half-widths are carried over by arc-length interpolation.
    """
    for br in graph.branches:
        n = len(br.pts)
        if n < 3:
            continue
        seg = np.hypot(*np.diff(br.pts, axis=0).T)
        cum = np.concatenate([[0.0], np.cumsum(seg)])
        line = LineString(br.pts)
        simp = np.asarray(line.simplify(0.08, preserve_topology=False).coords)
        if len(simp) < 2:
            continue
        # moving average on interior points (keeps ends)
        pts = simp.copy()
        if len(pts) > 4:
            for i in range(1, len(pts) - 1):
                pts[i] = (simp[i - 1] + 2 * simp[i] + simp[i + 1]) / 4.0
        # half-width at each new point from the nearest original arc-length position
        pos = np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(simp, axis=0).T))])
        pos = pos / max(pos[-1], 1e-9) * cum[-1]
        hw = np.interp(pos, cum, br.half_w)
        # smooth half-widths over ~0.5 mm so the rails are not jagged
        k = 2
        if len(hw) > 2 * k + 1:
            kern = np.ones(2 * k + 1) / (2 * k + 1)
            padded = np.concatenate([np.full(k, hw[0]), hw, np.full(k, hw[-1])])
            hw = np.convolve(padded, kern, mode="valid")
        br.pts = pts
        br.half_w = hw


# ---------------------------------------------------------------------------
# parts
# ---------------------------------------------------------------------------
@dataclass
class Part:
    group: str
    kind: str                           # fill | satin_fill | satin | running
    index: int
    geom: MultiPolygon | None = None
    graph: SkeletonGraph | None = None
    width_mm: float = 0.0
    max_width_mm: float = 0.0
    angle_deg: float | None = None
    bean: bool = False
    description: str = ""
    notes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    area: float = 0.0

    def center(self) -> tuple[float, float]:
        if self.geom is not None and not self.geom.is_empty:
            return G.centroid(self.geom)
        if self.graph and self.graph.branches:
            allpts = np.vstack([b.pts for b in self.graph.branches])
            return (float(allpts[:, 0].mean()), float(allpts[:, 1].mean()))
        return (0.0, 0.0)

    def bounds(self):
        if self.geom is not None and not self.geom.is_empty:
            return self.geom.bounds
        allpts = np.vstack([b.pts for b in self.graph.branches])
        return (allpts[:, 0].min(), allpts[:, 1].min(), allpts[:, 0].max(), allpts[:, 1].max())


def components(geom) -> list[Polygon]:
    return sorted(G.polygons(geom), key=lambda p: -p.area)


def principal_angle(poly) -> float:
    """Angle (deg, CCW from +x in y-down coords) of the longest axis of a polygon."""
    pts = np.asarray(poly.exterior.coords)
    pts = pts - pts.mean(axis=0)
    cov = np.cov(pts.T)
    vals, vecs = np.linalg.eigh(cov)
    v = vecs[:, np.argmax(vals)]
    return math.degrees(math.atan2(v[1], v[0])) % 180.0


def classify_region(region: GroupRegion, params: Params, log: list[str]) -> list[Part]:
    """Split one colour region into parts and decide how each is stitched."""
    name = region.name
    min_feature = float(params["general.min_feature_width_mm"])
    satin_min = float(params["satin.min_width_mm"])
    satin_max = float(params["satin.max_width_mm"])
    convert_w = float(params["satin.convert_to_fill_width_mm"])
    bean_min = float(params["running.bean_min_stroke_width_mm"])
    overlap = float(params["general.overlap_mm"])
    thin_action = params.get("detail.thin_feature_action", "running")
    parts: list[Part] = []
    counter = [0]

    def new_part(**kw) -> Part:
        counter[0] += 1
        p = Part(group=name, index=counter[0], **kw)
        parts.append(p)
        return p

    region_geom = region.region
    # thin strokes keep their original centreline
    stroke_polys = []
    for st in region.strokes:
        if st.width_mm < min_feature:
            line = LineString(st.line)
            stroke_polys.append(line.buffer(st.width_mm / 2 + 0.05))
            g = SkeletonGraph(nodes={0: tuple(st.line[0]), 1: tuple(st.line[-1])},
                              branches=[Branch(np.asarray(st.line, float), np.full(len(st.line), st.width_mm / 2), 0, 1)])
            bean = st.width_mm >= bean_min
            p = new_part(kind="running", graph=g, width_mm=st.width_mm, max_width_mm=st.width_mm, bean=bean,
                         description=f"{'bean' if bean else 'running'} stitch along a {st.width_mm:.2f} mm stroke")
            if thin_action == "warn":
                p.warnings.append(f"{name}: stroke {st.width_mm:.2f} mm wide is thinner than {min_feature} mm.")
    if stroke_polys:
        region_geom = G.to_multipolygon(region_geom.difference(unary_union(stroke_polys)))
    if region_geom.is_empty:
        return parts

    # 1. thin parts (narrower than the minimum feature width)
    wide = G.opening(region_geom, min_feature / 2.0)
    thin = G.to_multipolygon(region_geom.difference(wide.buffer(0.05)))
    thin = G.clean(thin, min_area=0.15)
    if not thin.is_empty and not wide.is_empty:
        # short slivers hugging the edge of a wide part are raster/vector fringe, not features
        keep = []
        wide_b = wide.buffer(0.1)
        for piece in G.polygons(thin):
            ext = max(piece.bounds[2] - piece.bounds[0], piece.bounds[3] - piece.bounds[1])
            if piece.area < 0.8 and ext < 2.5 and piece.intersects(wide_b):
                continue
            keep.append(piece)
        thin = G.to_multipolygon(unary_union(keep)) if keep else MultiPolygon()
    thicken_above = float(params.get("detail.thicken_above_mm", 1.0))
    if not thin.is_empty and thin_action != "thicken" and thicken_above < min_feature:
        # pieces nearly as wide as the satin minimum (the rim of a tray, a stem) read as unstitched
        # when reduced to a line: widen those to the minimum and stitch them as satin
        near = []
        rest = []
        for piece in G.polygons(thin):
            inner = G.opening(piece, thicken_above / 2.0)
            if not inner.is_empty and inner.area >= 0.5 * piece.area:
                near.append(piece)
            else:
                rest.append(piece)
        if near:
            thick = G.to_multipolygon(unary_union(near).buffer((min_feature - thicken_above) / 2.0 + 0.05))
            wide = G.to_multipolygon(unary_union([wide, thick]))
            thin = G.to_multipolygon(unary_union(rest)) if rest else MultiPolygon()
            log.append(f"{name}: {len(near)} feature(s) between {thicken_above} and {min_feature} mm wide "
                       f"({sum(q.area for q in near):.1f} mm2) thickened to {min_feature} mm and stitched as satin")
    if not thin.is_empty:
        if thin_action == "thicken":
            thick = G.to_multipolygon(thin.buffer(min_feature / 2.0))
            wide = G.to_multipolygon(unary_union([wide, thick]))
            log.append(f"{name}: thickened {thin.area:.1f} mm2 of thin features to {min_feature} mm.")
        else:
            graph = skeleton_graph(thin)
            if graph.branches:
                # drop dust: branches shorter than 1 mm not connected to anything
                deg = graph.degree()
                keep = [b for b in graph.branches if not (b.length < 1.0 and deg[b.a] == 1 and deg[b.b] == 1)]
                dropped = len(graph.branches) - len(keep)
                graph.branches = keep
                if keep:
                    mean_w = graph.mean_width()
                    bean = mean_w >= bean_min
                    p = new_part(kind="running", graph=graph, geom=thin, width_mm=mean_w, max_width_mm=graph.max_width(),
                                 bean=bean, area=thin.area,
                                 description=f"{'bean' if bean else 'running'} stitch along {len(keep)} thin line(s), "
                                             f"{mean_w:.2f} mm wide on average")
                    if thin_action == "warn":
                        p.warnings.append(f"{name}: {thin.area:.1f} mm2 of features thinner than {min_feature} mm "
                                          f"(stitched as {'bean' if bean else 'running'} stitch).")
                    else:
                        p.notes.append(f"{thin.area:.1f} mm2 thinner than {min_feature} mm rendered as "
                                       f"{'bean' if bean else 'running'} stitch")
                    if dropped:
                        p.notes.append(f"dropped {dropped} speck(s) under 1 mm")
                    log.append(f"{name}: {len(keep)} thin line(s) ({thin.area:.1f} mm2, mean width {mean_w:.2f} mm) -> "
                               f"{'bean' if bean else 'running'} stitch")
    if wide.is_empty:
        return parts

    # 2. wide parts: fill cores vs satin ribbons vs blobs
    for comp in components(wide):
        core = G.opening(comp, convert_w / 2.0)
        if core.is_empty:
            _classify_ribbon_or_blob(comp, name, new_part, satin_min, satin_max, convert_w, log, params)
            continue
        # The component has a region wider than the satin-to-fill limit: stitch the whole
        # component as tatami. Splitting narrow arms off as satin columns was tried and
        # produced fan-shaped artifacts where the arm meets the fill, so it is not done.
        fill_geom = comp
        for fc in components(fill_geom):
            if fc.area < 1.0:
                continue
            new_part(kind="fill", geom=G.to_multipolygon(fc), width_mm=2 * _max_inscribed(fc), area=fc.area,
                     description=f"tatami fill {fc.area:.0f} mm2")
            log.append(f"{name}: tatami fill {fc.area:.0f} mm2")
    return parts


def _max_inscribed(poly) -> float:
    """Largest inscribed radius (binary search on negative buffer)."""
    lo, hi = 0.0, max(poly.bounds[2] - poly.bounds[0], poly.bounds[3] - poly.bounds[1]) / 2
    for _ in range(14):
        mid = (lo + hi) / 2
        if poly.buffer(-mid).is_empty:
            hi = mid
        else:
            lo = mid
    return lo


def _classify_ribbon_or_blob(comp, name, new_part, satin_min, satin_max, convert_w, log, params):
    g = skeleton_graph(comp)
    r = _max_inscribed(comp)
    max_w = 2 * r
    if not g.branches or g.total_length() < 2.0 * max_w:
        # compact blob: satin-style fill across its short axis
        ang = (principal_angle(comp) + 90.0) % 180.0
        p = new_part(kind="satin_fill", geom=G.to_multipolygon(comp), width_mm=max_w, max_width_mm=max_w, area=comp.area,
                     angle_deg=ang, description=f"satin-style fill of a {max_w:.1f} mm blob")
        log.append(f"{name}: blob {comp.area:.0f} mm2, {max_w:.1f} mm wide -> satin-style fill at {ang:.0f} deg")
        return p
    w = g.mean_width()
    deg = g.degree()
    junctions = sum(1 for d in deg.values() if d >= 3)
    if junctions and w >= float(params["satin.branching_to_fill_width_mm"]):
        # a branchy shape wider than a lattice bar: satin fans out at the junctions, tatami is safer
        # (under 4 mm the fans are small and a tatami this narrow looks like a lattice)
        ang = (principal_angle(comp) + 45.0) % 180.0
        p = new_part(kind="fill", geom=G.to_multipolygon(comp), width_mm=w, max_width_mm=g.max_width(), area=comp.area,
                     description=f"tatami fill of a branching {w:.1f} mm wide shape")
        p.notes.append(f"satin not used: {junctions} junction(s) at {w:.1f} mm width")
        log.append(f"{name}: branching shape {w:.1f} mm wide ({junctions} junctions) -> tatami fill")
        return p
    if w > satin_max:
        ang = (principal_angle(comp) + 45.0) % 180.0
        p = new_part(kind="fill", geom=G.to_multipolygon(comp), width_mm=w, max_width_mm=g.max_width(), area=comp.area,
                     description=f"tatami fill of a {w:.1f} mm wide ribbon (too wide for satin)")
        p.notes.append(f"converted from satin: {w:.1f} mm wide > {satin_max} mm")
        log.append(f"{name}: ribbon {w:.1f} mm wide x {g.total_length():.0f} mm -> tatami fill (wider than {satin_max} mm)")
        return p
    p = new_part(kind="satin", graph=g, geom=G.to_multipolygon(comp), width_mm=w, max_width_mm=g.max_width(),
                 area=comp.area, description=f"satin {w:.1f} mm wide, {g.total_length():.0f} mm long, "
                                              f"{len(g.branches)} branch(es)")
    if g.max_width() > satin_max:
        p.notes.append(f"widest point {g.max_width():.1f} mm > {satin_max} mm: split stitches used there")
    log.append(f"{name}: satin {w:.1f} mm wide x {g.total_length():.0f} mm, {len(g.branches)} branch(es)")
    return p


def assign_fill_angles(parts: list[Part], params: Params, log: list[str]) -> None:
    """Give touching fills angles at least `adjacent_angle_offset_deg` apart."""
    base = float(params["fill.angle_deg"])
    offset = float(params["fill.adjacent_angle_offset_deg"])
    fills = [p for p in parts if p.kind == "fill" and p.geom is not None]
    fills.sort(key=lambda p: -p.area)
    candidates = [base] + [(base + d) % 180 for d in (90, 30, -30, 60, -60, 45, -45, 15, -15)]
    tree_geoms = [p.geom.buffer(0.6) for p in fills]
    import shapely
    tree = shapely.STRtree(tree_geoms) if tree_geoms else None
    assigned: dict[int, float] = {}
    for i, p in enumerate(fills):
        neigh = []
        if tree is not None:
            for j in tree.query(p.geom, predicate="intersects"):
                if j != i and j in assigned:
                    neigh.append(assigned[j])
        # blobs with their own angle count as neighbours too
        chosen = None
        for cand in candidates:
            if all(G.angle_diff_deg(cand, a) >= offset for a in neigh):
                chosen = cand
                break
        if chosen is None:
            chosen = max(candidates, key=lambda c: min(G.angle_diff_deg(c, a) for a in neigh))
        p.angle_deg = chosen
        assigned[i] = chosen
        if neigh and chosen != base:
            log.append(f"{p.group}: fill {p.index} angle {chosen:.0f} deg (touching fills use {sorted(set(round(a) for a in neigh))})")
