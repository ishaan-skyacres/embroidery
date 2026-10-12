"""Running and bean stitch along polylines; Eulerian routing of line graphs."""
from __future__ import annotations

import math

import networkx as nx
import numpy as np

from .. import geometry as G
from ..classify import SkeletonGraph
from ..stitchplan import STITCH, Stitch


def running_points(coords: np.ndarray, stitch_len: float, curve_len: float, tol: float, min_len: float) -> np.ndarray:
    """Needle positions along a polyline: long stitches on straights, short on curves."""
    coords = np.asarray(coords, dtype=float)
    if len(coords) < 2:
        return coords
    # simplify within tolerance so stitches follow the line without extra vertices
    from shapely.geometry import LineString
    line = LineString(coords).simplify(tol, preserve_topology=False)
    verts = np.asarray(line.coords)
    if len(verts) < 2:
        return coords[:1]
    # turn angle at each vertex
    def turn(i):
        if i <= 0 or i >= len(verts) - 1:
            return 0.0
        a = verts[i] - verts[i - 1]
        b = verts[i + 1] - verts[i]
        na, nb = np.linalg.norm(a), np.linalg.norm(b)
        if na < 1e-9 or nb < 1e-9:
            return 0.0
        c = np.clip(np.dot(a, b) / (na * nb), -1, 1)
        return math.degrees(math.acos(c))
    pts = [verts[0]]
    for i in range(len(verts) - 1):
        a, b = verts[i], verts[i + 1]
        seg = float(np.linalg.norm(b - a))
        if seg < 1e-9:
            continue
        curvy = turn(i) > 20 or turn(i + 1) > 20
        L = curve_len if curvy else stitch_len
        n = max(1, int(math.ceil(seg / L)))
        for k in range(1, n + 1):
            pts.append(a + (b - a) * (k / n))
    pts = np.asarray(pts)
    # merge stitches shorter than min_len (keep the last point)
    out = [pts[0]]
    for p in pts[1:-1]:
        if np.linalg.norm(p - out[-1]) >= min_len:
            out.append(p)
    if len(pts) > 1:
        if np.linalg.norm(pts[-1] - out[-1]) < min_len and len(out) > 1:
            out[-1] = pts[-1]
        else:
            out.append(pts[-1])
    return np.asarray(out)


def running_stitches(coords: np.ndarray, stitch_len: float, curve_len: float, tol: float, min_len: float,
                     bean_repeats: int = 0, include_start: bool = True, **flags) -> list[Stitch]:
    pts = running_points(coords, stitch_len, curve_len, tol, min_len)
    out: list[Stitch] = []
    if include_start and len(pts):
        out.append(Stitch(float(pts[0][0]), float(pts[0][1]), STITCH, **flags))
    for i in range(1, len(pts)):
        a, b = pts[i - 1], pts[i]
        out.append(Stitch(float(b[0]), float(b[1]), STITCH, **flags))
        for _ in range(bean_repeats):
            out.append(Stitch(float(a[0]), float(a[1]), STITCH, **flags))
            out.append(Stitch(float(b[0]), float(b[1]), STITCH, **flags))
    return out


def route_graph(graph: SkeletonGraph, start_hint: tuple[float, float] | None = None):
    """Eulerian routes covering every branch once (extra traversals marked repeat).

    Returns a list of components; each is a list of (branch_pts, repeat: bool).
    """
    mg = nx.MultiGraph()
    for i, br in enumerate(graph.branches):
        mg.add_edge(br.a, br.b, key=i, weight=max(br.length, 1e-6), branch=i, repeat=False)
    for n, xy in graph.nodes.items():
        if n in mg:
            mg.nodes[n]["xy"] = xy
    routes = []
    comps = [mg.subgraph(c).copy() for c in nx.connected_components(mg)]
    # order components nearest-first
    def comp_center(c):
        pts = [graph.nodes[n] for n in c.nodes if n in graph.nodes]
        return np.mean(np.asarray(pts), axis=0) if pts else np.zeros(2)
    cur = np.asarray(start_hint, float) if start_hint is not None else None
    remaining = comps
    while remaining:
        if cur is None:
            nxt = max(remaining, key=lambda c: c.size(weight="weight"))
        else:
            nxt = min(remaining, key=lambda c: np.linalg.norm(comp_center(c) - cur))
        remaining = [c for c in remaining if c is not nxt]
        route = _euler_route(nxt, graph, cur)
        if route:
            last = route[-1][0][-1]
            cur = np.asarray(last, float)
        routes.append(route)
    return routes


def _euler_route(g: nx.MultiGraph, graph: SkeletonGraph, start_hint):
    """Open Eulerian path (Chinese postman): every branch once, the fewest repeats.

    Odd-degree nodes are paired by shortest paths whose branches are then stitched twice,
    except for a start and an end node: the start is the odd node nearest the current
    position and the end the odd node farthest from it, so the thread does not have to come
    back to where it began.
    """
    simple = nx.Graph()
    for u, v, k, d in g.edges(keys=True, data=True):
        w = d["weight"]
        if simple.has_edge(u, v):
            simple[u][v]["weight"] = min(simple[u][v]["weight"], w)
        else:
            simple.add_edge(u, v, weight=w)
    nodes = list(g.nodes)
    odd = [n for n, d in g.degree() if d % 2 == 1]

    def near(cands):
        if start_hint is None:
            return cands[0]
        return min(cands, key=lambda n: np.linalg.norm(np.asarray(graph.nodes.get(n, (0, 0)), float) - start_hint))

    if odd:
        dist = dict(nx.all_pairs_dijkstra_path_length(simple))
        # start and end at line ends (degree 1) when there are any: a junction used as an end
        # point forces extra repeats through it
        ends = [n for n in odd if g.degree(n) == 1] or odd
        start = near(ends)
        end = max([n for n in ends if n != start] or odd, key=lambda n: dist[start].get(n, 0.0))
        rest = [n for n in odd if n not in (start, end)]
        if rest:
            k = nx.Graph()
            for i, a in enumerate(rest):
                for b in rest[i + 1:]:
                    k.add_edge(a, b, weight=dist[a][b])
            matching = nx.min_weight_matching(k)
            dup = 0
            for a, b in matching:
                path = nx.dijkstra_path(simple, a, b)
                for u, v in zip(path[:-1], path[1:]):
                    cands = [(kk, dd) for _, nbr, kk, dd in g.edges(u, keys=True, data=True) if nbr == v]
                    if not cands:
                        continue
                    kk, dd = min(cands, key=lambda t: t[1]["weight"])
                    g.add_edge(u, v, key=f"dup{dup}", weight=dd["weight"], branch=dd["branch"], repeat=True)
                    dup += 1
        circuit = list(nx.eulerian_path(g, source=start, keys=True))
    else:
        start = near(nodes)
        circuit = list(nx.eulerian_circuit(g, source=start, keys=True))
    route = []
    for u, v, key in circuit:
        d = g.edges[u, v, key]
        br = graph.branches[d["branch"]]
        pts = br.pts if br.a == u else br.pts[::-1]
        if br.a == br.b:
            pts = br.pts
        route.append((pts, bool(d["repeat"])))
    return route
