"""Geometry helpers built on shapely (all coordinates in mm unless noted, y down)."""
from __future__ import annotations

import math
from typing import Iterable, Sequence

import numpy as np
import shapely
from shapely import affinity
from shapely.geometry import (GeometryCollection, LineString, LinearRing, MultiLineString, MultiPoint,
                              MultiPolygon, Point, Polygon)
from shapely.ops import polygonize, unary_union

EMPTY = MultiPolygon()


def to_multipolygon(geom) -> MultiPolygon:
    """Coerce any geometry to a MultiPolygon of its polygonal parts."""
    if geom is None or geom.is_empty:
        return MultiPolygon()
    if isinstance(geom, Polygon):
        return MultiPolygon([geom])
    if isinstance(geom, MultiPolygon):
        return geom
    if isinstance(geom, GeometryCollection):
        polys = []
        for g in geom.geoms:
            polys.extend(to_multipolygon(g).geoms)
        return MultiPolygon(polys)
    return MultiPolygon()


def polygons(geom) -> list[Polygon]:
    return [p for p in to_multipolygon(geom).geoms if not p.is_empty and p.area > 0]


def lines(geom) -> list[LineString]:
    """All LineString parts of a geometry."""
    if geom is None or geom.is_empty:
        return []
    if isinstance(geom, LineString):
        return [geom]
    if isinstance(geom, (MultiLineString, GeometryCollection)):
        out = []
        for g in geom.geoms:
            out.extend(lines(g))
        return out
    return []


def clean(geom, min_area: float = 0.0):
    """Make valid, drop empty and tiny parts, return a MultiPolygon."""
    if geom is None or geom.is_empty:
        return MultiPolygon()
    geom = shapely.make_valid(geom)
    parts = [p for p in polygons(geom) if p.area >= min_area]
    if not parts:
        return MultiPolygon()
    merged = unary_union(parts)
    return to_multipolygon(merged)


def winding_number(ring: np.ndarray, px: float, py: float) -> int:
    """Winding number of point (px, py) with respect to a closed ring (N x 2 array)."""
    x = ring[:, 0]
    y = ring[:, 1]
    x2 = np.roll(x, -1)
    y2 = np.roll(y, -1)
    # upward crossings
    up = (y <= py) & (y2 > py)
    down = (y > py) & (y2 <= py)
    # is_left > 0 means point is left of edge
    is_left = (x2 - x) * (py - y) - (px - x) * (y2 - y)
    wn = int(np.sum(up & (is_left > 0))) - int(np.sum(down & (is_left < 0)))
    return wn


def polygon_from_rings(rings: Sequence[Sequence[tuple[float, float]]], fill_rule: str = "nonzero") -> MultiPolygon:
    """Build the filled region described by closed rings and an SVG fill rule.

    All rings are noded together and polygonised into faces; each face is kept
    if its winding number (nonzero) or crossing parity (evenodd) says it is
    inside. This handles holes, self-intersections and overlapping subpaths.
    """
    arrays = []
    for ring in rings:
        pts = np.asarray(ring, dtype=float)
        if len(pts) < 3:
            continue
        if np.allclose(pts[0], pts[-1]):
            pts = pts[:-1]
        if len(pts) < 3:
            continue
        # drop consecutive duplicates
        keep = np.ones(len(pts), dtype=bool)
        keep[1:] = np.any(np.abs(np.diff(pts, axis=0)) > 1e-9, axis=1)
        pts = pts[keep]
        if len(pts) >= 3:
            arrays.append(pts)
    if not arrays:
        return MultiPolygon()
    boundaries = [LineString(np.vstack([a, a[:1]])) for a in arrays]
    noded = unary_union(boundaries)
    faces = list(polygonize(noded))
    kept = []
    for face in faces:
        if face.area <= 0:
            continue
        pt = face.representative_point()
        wn = 0
        crossings = 0
        for a in arrays:
            w = winding_number(a, pt.x, pt.y)
            wn += w
            crossings += abs(w) % 2
        inside = (wn != 0) if fill_rule == "nonzero" else (crossings % 2 == 1)
        if inside:
            kept.append(face)
    if not kept:
        return MultiPolygon()
    return to_multipolygon(unary_union(kept))


def densify(coords: np.ndarray, step: float) -> np.ndarray:
    """Insert points so that no segment is longer than `step` (N x 2 array in, out)."""
    out = [coords[0]]
    for a, b in zip(coords[:-1], coords[1:]):
        d = float(np.hypot(*(b - a)))
        n = max(1, int(math.ceil(d / step)))
        for i in range(1, n + 1):
            out.append(a + (b - a) * (i / n))
    return np.asarray(out)


def resample_line(coords: np.ndarray, step: float, closed: bool = False) -> np.ndarray:
    """Resample a polyline at (approximately) even spacing `step`, keeping both ends."""
    coords = np.asarray(coords, dtype=float)
    if closed and not np.allclose(coords[0], coords[-1]):
        coords = np.vstack([coords, coords[:1]])
    seg = np.hypot(*np.diff(coords, axis=0).T)
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    total = cum[-1]
    if total <= 0:
        return coords[:1]
    n = max(1, int(round(total / step)))
    targets = np.linspace(0, total, n + 1)
    xs = np.interp(targets, cum, coords[:, 0])
    ys = np.interp(targets, cum, coords[:, 1])
    return np.column_stack([xs, ys])


def line_length(coords: np.ndarray) -> float:
    coords = np.asarray(coords, dtype=float)
    if len(coords) < 2:
        return 0.0
    return float(np.sum(np.hypot(*np.diff(coords, axis=0).T)))


def rotate(geom, angle_deg: float, origin=(0, 0)):
    return affinity.rotate(geom, angle_deg, origin=origin, use_radians=False)


def bbox(geom) -> tuple[float, float, float, float]:
    return tuple(geom.bounds)


def nearest_point_on(geom, pt: tuple[float, float]) -> tuple[float, float]:
    p = shapely.ops.nearest_points(geom, Point(pt))[0]
    return (p.x, p.y)


def inset(geom, d: float) -> MultiPolygon:
    """Negative buffer that keeps a MultiPolygon result."""
    return to_multipolygon(geom.buffer(-d, join_style="mitre", mitre_limit=2.0))


def outset(geom, d: float) -> MultiPolygon:
    return to_multipolygon(geom.buffer(d, join_style="round"))


def opening(geom, r: float) -> MultiPolygon:
    """Morphological opening: parts narrower than 2r disappear."""
    if r <= 0:
        return to_multipolygon(geom)
    return to_multipolygon(geom.buffer(-r, join_style="round").buffer(r, join_style="round"))


def centroid(geom) -> tuple[float, float]:
    c = geom.centroid
    return (c.x, c.y)


def dist(a: Sequence[float], b: Sequence[float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def unit(v: Sequence[float]) -> np.ndarray:
    v = np.asarray(v, dtype=float)
    n = np.linalg.norm(v)
    return v / n if n > 0 else np.array([1.0, 0.0])


def angle_diff_deg(a: float, b: float) -> float:
    """Smallest difference between two line angles (mod 180)."""
    d = abs((a - b) % 180.0)
    return min(d, 180.0 - d)


def multipoint(coords: Iterable[tuple[float, float]]) -> MultiPoint:
    return MultiPoint(list(coords))


def ring_coords(ring: LinearRing | LineString) -> np.ndarray:
    return np.asarray(ring.coords, dtype=float)
