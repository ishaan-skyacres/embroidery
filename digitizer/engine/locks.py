"""Tie-in and tie-off (lock) stitches and stitch-list utilities."""
from __future__ import annotations

import math

import numpy as np

from ..stitchplan import JUMP, STITCH, TRIM, Stitch


def tie_in(p0, p1, length: float = 0.7, style: str = "half_stitch") -> list[Stitch]:
    """Lock stitches before an object that starts at p0 and heads toward p1."""
    d = np.asarray(p1, float) - np.asarray(p0, float)
    n = np.linalg.norm(d)
    d = d / n if n > 1e-9 else np.array([1.0, 0.0])
    p0 = np.asarray(p0, float)
    if style == "back_forth":
        pts = [p0 + d * length, p0, p0 + d * length, p0]
    else:  # half stitch: 0, 0.5, 1, 0.5, 0 of the lock length
        pts = [p0 + d * length * 0.5, p0 + d * length, p0 + d * length * 0.5, p0]
    return [Stitch(float(x), float(y), STITCH, lock=True) for x, y in pts]


def tie_off(p_prev, p_end, length: float = 0.7, style: str = "half_stitch") -> list[Stitch]:
    """Lock stitches after an object whose last stitch is at p_end coming from p_prev."""
    d = np.asarray(p_end, float) - np.asarray(p_prev, float)
    n = np.linalg.norm(d)
    d = d / n if n > 1e-9 else np.array([1.0, 0.0])
    p = np.asarray(p_end, float)
    if style == "back_forth":
        pts = [p - d * length, p, p - d * length, p]
    else:
        pts = [p - d * length * 0.5, p - d * length, p - d * length * 0.5, p]
    return [Stitch(float(x), float(y), STITCH, lock=True) for x, y in pts]


def enforce_min_length(stitches: list[Stitch], min_len: float) -> list[Stitch]:
    """Drop stitches shorter than min_len (lock stitches and commands exempt)."""
    out: list[Stitch] = []
    last = None            # last needle-down position (lock or not) or jump target
    for s in stitches:
        if s.cmd != STITCH or s.lock:
            out.append(s)
            if s.cmd in (STITCH, JUMP):
                last = s
            continue
        if last is not None and math.hypot(s.x - last.x, s.y - last.y) < min_len:
            # too close to the previous needle position: skip it (the next stitch absorbs it)
            continue
        out.append(s)
        last = s
    return out


def split_long(stitches: list[Stitch], max_len: float) -> list[Stitch]:
    """Split any needle stitch longer than max_len into equal pieces."""
    out: list[Stitch] = []
    last = None
    for s in stitches:
        if s.cmd == STITCH and last is not None and last.cmd == STITCH:
            d = math.hypot(s.x - last.x, s.y - last.y)
            if d > max_len:
                n = int(math.ceil(d / max_len))
                for i in range(1, n):
                    t = i / n
                    out.append(Stitch(last.x + (s.x - last.x) * t, last.y + (s.y - last.y) * t, STITCH,
                                      lock=s.lock, travel=s.travel, underlay=s.underlay))
        out.append(s)
        if s.cmd in (STITCH, JUMP):
            last = s
    return out
