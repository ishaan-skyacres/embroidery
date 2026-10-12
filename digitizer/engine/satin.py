"""Satin columns along skeleton branches, with width-dependent underlay."""
from __future__ import annotations

import math

import numpy as np
from shapely.geometry import Point
from shapely.ops import nearest_points
from shapely.prepared import prep

from .. import geometry as G
from ..stitchplan import STITCH, Stitch
from .running import running_stitches


class Clipper:
    """Keeps rail points inside the region (needed near junctions and tips)."""

    def __init__(self, region):
        self.region = region
        self.prepared = prep(region) if region is not None else None
        self.boundary = region.boundary if region is not None else None

    def clip(self, p: np.ndarray) -> np.ndarray:
        if self.prepared is None:
            return p
        pt = Point(p[0], p[1])
        if self.prepared.covers(pt):
            return p
        q = nearest_points(self.boundary, pt)[0]
        return np.array([q.x, q.y])


def sample_branch(pts: np.ndarray, half_w: np.ndarray, step: float):
    """Resample the centreline at `step`, returning points, unit normals and half-widths."""
    pts = np.asarray(pts, float)
    half_w = np.asarray(half_w, float)
    seg = np.hypot(*np.diff(pts, axis=0).T)
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    total = cum[-1]
    if total < 1e-6:
        return pts[:1], np.array([[0.0, 1.0]]), half_w[:1]
    n = max(1, int(round(total / step)))
    t = np.linspace(0, total, n + 1)
    x = np.interp(t, cum, pts[:, 0])
    y = np.interp(t, cum, pts[:, 1])
    w = np.interp(t, cum, half_w)
    p = np.column_stack([x, y])
    # tangent by smoothed central differences
    tang = np.gradient(p, axis=0)
    k = max(1, int(round(1.0 / step)))   # ~1 mm smoothing window
    if len(p) > 2 * k + 1:
        kernel = np.ones(2 * k + 1) / (2 * k + 1)
        tang = np.column_stack([np.convolve(tang[:, 0], kernel, mode="same"), np.convolve(tang[:, 1], kernel, mode="same")])
    norms = np.linalg.norm(tang, axis=1)
    norms[norms < 1e-9] = 1.0
    tang = tang / norms[:, None]
    normal = np.column_stack([-tang[:, 1], tang[:, 0]])
    return p, normal, w


def rails(pts, half_w, step, comp: float, inset: float, clipper: Clipper | None):
    p, n, w = sample_branch(pts, half_w, step)
    r = np.maximum(w + comp - inset, 0.05)
    left = p + n * r[:, None]
    right = p - n * r[:, None]
    if clipper is not None:
        left = np.array([clipper.clip(q) for q in left])
        right = np.array([clipper.clip(q) for q in right])
    return p, left, right


def satin_stitches(pts, half_w, spacing: float, comp: float, split_len: float, clipper: Clipper | None,
                   short_inset: float = 0.15) -> list[Stitch]:
    """Zigzag satin from branch start to end; stitch i lands on alternate rails."""
    p, left, right = rails(pts, half_w, spacing / 2.0, comp, 0.0, clipper)
    out: list[Stitch] = []
    n = len(p)
    # short-stitch inset on the inside of tight curves
    def inset_if_crowded(rail, i):
        # stitches on the same rail are two samples apart; on the inside of a tight curve they
        # bunch up, so pull them toward the centre a little (Ink/Stitch's "short stitch inset")
        q = rail[i]
        if i > 1 and np.linalg.norm(rail[i] - rail[i - 2]) < 0.25:
            q = q + (p[i] - q) * short_inset
        return q
    prev = None
    counter = 0
    for i in range(n):
        q = inset_if_crowded(left, i) if i % 2 == 0 else inset_if_crowded(right, i)
        if prev is not None:
            d = float(np.linalg.norm(q - prev))
            if d > split_len:
                k = int(math.ceil(d / split_len))
                # stagger the split points so needle holes do not line up, without letting any
                # piece grow beyond split_len
                slack = max(0.0, split_len / d - 1.0 / k)
                phase = min(((counter % 4) / 4.0) * (0.5 / k), slack)
                for j in range(1, k):
                    t = j / k + (phase if j % 2 else -phase)
                    t = min(max(t, 0.05), 0.95)
                    m = prev + (q - prev) * t
                    out.append(Stitch(float(m[0]), float(m[1]), STITCH))
                counter += 1
        out.append(Stitch(float(q[0]), float(q[1]), STITCH))
        prev = q
    return out


def contour_underlay(pts, half_w, inset: float, stitch_len: float, comp: float, clipper) -> list[Stitch]:
    """Run along one rail to the far end and back along the other (ends where it started)."""
    _, left, right = rails(pts, half_w, 0.5, 0.0, inset, clipper)
    path = np.vstack([left, right[::-1]])
    return running_stitches(path, stitch_len, stitch_len * 0.7, 0.1, 0.4, 0, include_start=False, underlay=True)


def zigzag_underlay(pts, half_w, spacing: float, inset: float, clipper, reverse: bool = False) -> list[Stitch]:
    p, left, right = rails(pts, half_w, spacing / 2.0, 0.0, inset, clipper)
    if reverse:
        left, right = left[::-1], right[::-1]
    out = []
    for i in range(len(p)):
        q = left[i] if i % 2 == 0 else right[i]
        out.append(Stitch(float(q[0]), float(q[1]), STITCH, underlay=True))
    return out


def center_walk(pts, stitch_len: float, reverse: bool = False) -> list[Stitch]:
    path = np.asarray(pts, float)
    if reverse:
        path = path[::-1]
    return running_stitches(path, stitch_len, stitch_len * 0.75, 0.1, 0.4, 0, include_start=False, underlay=True)
