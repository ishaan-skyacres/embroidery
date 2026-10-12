import numpy as np
from shapely.geometry import box

from digitizer.classify import Branch, SkeletonGraph
from digitizer.engine import fill as F
from digitizer.engine import satin as S
from digitizer.engine.locks import enforce_min_length, tie_in, tie_off
from digitizer.engine.running import route_graph, running_stitches
from digitizer.stitchplan import STITCH, Stitch


def _pts(stitches):
    return np.array([(s.x, s.y) for s in stitches if s.cmd == STITCH])


def test_tatami_rows_pitch_and_stitch_length():
    st, _ = F.tatami_fill(box(0, 0, 20, 10), 0, 0.4, 3.8, 4, True, 0.25, 1.0, None, 2.0, 3.0)
    p = _pts(st)
    rows = np.unique(np.round(p[:, 1], 3))
    assert len(rows) == 26 and np.allclose(np.diff(rows), 0.4)
    lengths = np.hypot(*np.diff(p, axis=0).T)
    assert lengths.max() <= 3.8 + 0.6 + 1e-6      # stitch length (plus a row change)
    assert p[:, 0].min() <= -0.25 + 1e-6 and p[:, 0].max() >= 20.25 - 1e-6   # pull compensation extends rows


def test_tatami_rotated_fill_stays_inside_shape_and_is_dense():
    poly = box(0, 0, 30, 12)
    st, _ = F.tatami_fill(poly, 45, 0.4, 3.8, 4, True, 0.0, 1.0, None, 2.0, 3.0)
    p = _pts(st)
    assert poly.buffer(0.05).contains(__import__("shapely").geometry.MultiPoint(p.tolist()))
    assert len(p) > poly.area / (0.4 * 3.8) * 0.9


def test_satin_spacing_and_width():
    pts = np.array([[0.0, 0.0], [20.0, 0.0]])
    hw = np.array([1.0, 1.0])
    st = S.satin_stitches(pts, hw, 0.4, 0.2, 7.0, None)
    p = _pts(st)
    assert abs(len(p) - 101) <= 2                      # 2 stitches per 0.4 mm
    assert np.allclose(np.abs(p[1:-1, 1]), 1.2, atol=0.05)   # half width + pull compensation
    same_rail = np.hypot(*(p[2:] - p[:-2]).T)
    assert np.allclose(same_rail, 0.4, atol=0.02)


def test_satin_splits_long_stitches():
    pts = np.array([[0.0, 0.0], [10.0, 0.0]])
    hw = np.array([4.5, 4.5])                           # 9 mm wide column
    st = S.satin_stitches(pts, hw, 0.4, 0.0, 7.0, None)
    p = _pts(st)
    lengths = np.hypot(*np.diff(p, axis=0).T)
    assert lengths.max() <= 7.0 + 1e-6


def test_running_lengths_and_bean():
    line = np.array([[0.0, 0.0], [30.0, 0.0]])
    st = running_stitches(line, 2.2, 1.5, 0.15, 0.5, 0)
    p = _pts(st)
    L = np.hypot(*np.diff(p, axis=0).T)
    assert L.max() <= 2.2 + 1e-6 and L.min() >= 0.5
    bean = running_stitches(line, 2.2, 1.5, 0.15, 0.5, 1)
    assert len(bean) == 1 + 3 * (len(p) - 1)


def test_euler_route_covers_every_branch_once():
    # a "T": three branches meeting at node 0
    g = SkeletonGraph(nodes={0: (0, 0), 1: (10, 0), 2: (0, 10), 3: (-10, 0)},
                      branches=[Branch(np.array([[0, 0], [10, 0]], float), np.array([0.3, 0.3]), 0, 1),
                                Branch(np.array([[0, 0], [0, 10]], float), np.array([0.3, 0.3]), 0, 2),
                                Branch(np.array([[0, 0], [-10, 0]], float), np.array([0.3, 0.3]), 0, 3)])
    routes = route_graph(g, (0, 0))
    edges = [r for route in routes for r in route]
    assert sum(1 for _, rep in edges if not rep) == 3
    assert sum(1 for _, rep in edges if rep) == 1       # open path: only one branch has to be walked twice


def test_locks_and_min_length():
    ti = tie_in((0, 0), (1, 0), 0.7)
    to = tie_off((0, 0), (1, 0), 0.7)
    assert len(ti) == 4 and all(s.lock for s in ti) and len(to) == 4
    seq = ti + [Stitch(0, 0), Stitch(0.1, 0), Stitch(2, 0)]
    out = enforce_min_length(seq, 0.3)
    assert [s.lock for s in out].count(True) == 4
    assert [(s.x, s.y) for s in out if not s.lock] == [(2, 0)]   # duplicates of the lock end are removed
