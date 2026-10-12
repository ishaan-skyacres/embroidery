"""Path A: run Ink/Stitch headless (from source, isolated Python 3.11 venv) on a prepared SVG."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import numpy as np
import pyembroidery as pe

from . import geometry as G
from .classify import Part
from .engine.running import route_graph
from .engine.satin import Clipper, rails
from .layering import Layout
from .params import Params
from .engine.locks import enforce_min_length
from .stitchplan import JUMP, STITCH, TRIM, StitchPlan

PX_PER_MM = 96.0 / 25.4
INKSTITCH_NS = "http://inkstitch.org/namespace"


def find_inkstitch() -> tuple[Path, Path] | None:
    """(python executable, inkstitch source dir) or None when Path A is not installed."""
    candidates_dir = [os.environ.get("INKSTITCH_DIR"), str(Path.home() / "inkstitch" / "inkstitch"),
                      str(Path(__file__).resolve().parent.parent / "third_party" / "inkstitch"),
                      "/home/user/inkstitch/inkstitch", "/opt/inkstitch"]
    candidates_py = [os.environ.get("INKSTITCH_PYTHON"),
                     str(Path(__file__).resolve().parent.parent / ".venv-inkstitch" / "bin" / "python"),
                     str(Path.home() / ".venv-inkstitch" / "bin" / "python")]
    d = next((Path(c) for c in candidates_dir if c and (Path(c) / "inkstitch.py").exists()), None)
    p = next((Path(c) for c in candidates_py if c and Path(c).exists()), None)
    if d is None or p is None:
        return None
    return p, d


def _fmt(v: float) -> str:
    return f"{v:.3f}".rstrip("0").rstrip(".")


def _path_d(coords_list, offset, closed=True) -> str:
    parts = []
    for coords in coords_list:
        pts = [((x + offset[0]) * PX_PER_MM, (y + offset[1]) * PX_PER_MM) for x, y in coords]
        if not pts:
            continue
        d = "M " + " ".join(f"{_fmt(x)},{_fmt(y)}" for x, y in pts)
        if closed:
            d += " Z"
        parts.append(d)
    return " ".join(parts)


def _attrs(d: dict) -> str:
    out = []
    for k, v in d.items():
        if v is None:
            continue
        if isinstance(v, bool):
            v = "True" if v else "False"
        out.append(f'inkstitch:{k}="{v}"')
    return " ".join(out)


def write_inkstitch_svg(layout: Layout, parts_by_group: dict[str, list[Part]], params: Params, path: Path,
                        order_fn) -> list[dict]:
    """Write the cleaned, parameterised SVG for Ink/Stitch. Returns the element manifest."""
    fp = params["fill"]
    sp = params["satin"]
    rp = params["running"]
    u = fp["underlay"]
    uc = sp["underlay"]
    W, H = layout.width_mm, layout.height_mm
    offset = (W / 2 + 10.0, H / 2 + 10.0)
    cw, ch = W + 20.0, H + 20.0
    lines = [f'<?xml version="1.0" encoding="UTF-8"?>',
             f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:inkstitch="{INKSTITCH_NS}" '
             f'xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" '
             f'width="{_fmt(cw)}mm" height="{_fmt(ch)}mm" viewBox="0 0 {_fmt(cw * PX_PER_MM)} {_fmt(ch * PX_PER_MM)}">',
             '<metadata><inkstitch:min_stitch_len_mm>%s</inkstitch:min_stitch_len_mm>'
             '<inkstitch:collapse_len_mm>%s</inkstitch:collapse_len_mm></metadata>'
             % (_fmt(float(params["general.min_stitch_length_mm"])), _fmt(float(params["machine.trim_jump_threshold_mm"])))]
    manifest = []
    eid = 0
    for region in layout.regions:
        parts = parts_by_group.get(region.name, [])
        if not parts:
            continue
        color = region.group.color
        lines.append(f'<g inkscape:groupmode="layer" inkscape:label="{region.name}" id="g_{region.name.replace(" ", "_")}">')
        for part in order_fn(parts, None):
            if part.kind in ("fill", "satin_fill"):
                for poly in G.polygons(part.geom):
                    eid += 1
                    size = max(poly.bounds[2] - poly.bounds[0], poly.bounds[3] - poly.bounds[1])
                    satin_like = part.kind == "satin_fill"
                    angle = part.angle_deg if part.angle_deg is not None else float(fp["angle_deg"])
                    attrs = {
                        "fill_method": "tatami_fill",
                        "angle": _fmt(-angle),      # Ink/Stitch angles are counter-clockwise on screen
                        "row_spacing_mm": _fmt(float(sp["spacing_mm"]) if satin_like else float(fp["row_spacing_mm"])),
                        "max_stitch_length_mm": _fmt(float(sp["split_stitch_length_mm"]) if satin_like else float(fp["max_stitch_length_mm"])),
                        "staggers": int(fp["staggers"]),
                        "skip_last": bool(fp["skip_last"]),
                        "pull_compensation_mm": _fmt(float(sp["pull_compensation_mm"]) if satin_like else float(fp["pull_compensation_mm"])),
                        "underpath": True,
                        "running_stitch_length_mm": _fmt(float(fp["travel_stitch_length_mm"])),
                        "fill_underlay": bool(u["enabled"]) and part.width_mm >= 2.0,
                        "fill_underlay_angle": _fmt(-(angle + float(u["angle_offset_deg"]))) if int(u.get("layers", 1)) < 2
                        else f"{_fmt(-(angle + float(u['angle_offset_deg'])))} {_fmt(-angle)}",
                        "fill_underlay_row_spacing_mm": _fmt(float(fp["row_spacing_mm"]) * float(u["row_spacing_factor"])),
                        "fill_underlay_max_stitch_length_mm": _fmt(float(u["max_stitch_length_mm"])),
                        "fill_underlay_inset_mm": _fmt(float(u["inset_mm"])),
                        "underlay_underpath": True,
                    }
                    d = _path_d([poly.exterior.coords] + [r.coords for r in poly.interiors], offset)
                    lines.append(f'<path id="e{eid}" d="{d}" style="fill:{color};stroke:none" {_attrs(attrs)}/>')
                    manifest.append({"id": f"e{eid}", "group": region.name, "kind": part.kind})
                    if (bool(u.get("edge_run_always")) or size >= float(u["edge_run_min_size_mm"])) and part.width_mm >= 2.0:
                        shrunk = poly.buffer(-float(u["edge_run_inset_mm"]))
                        for sp_ in G.polygons(shrunk):
                            eid += 1
                            d = _path_d([sp_.exterior.coords] + [r.coords for r in sp_.interiors], offset, closed=True)
                            lines.append(f'<path id="e{eid}" d="{d}" style="fill:none;stroke:{color};stroke-width:0.3" '
                                         f'{_attrs({"running_stitch_length_mm": _fmt(float(u["edge_run_stitch_length_mm"]))})}/>')
                            manifest.append({"id": f"e{eid}", "group": region.name, "kind": "edge_run"})
            elif part.kind == "satin":
                clipper = Clipper(part.geom) if part.geom is not None else None
                for br in part.graph.branches:
                    if len(br.pts) < 2 or br.length < 0.5:
                        continue
                    eid += 1
                    _, left, right = rails(br.pts, br.half_w, 0.5, 0.0, 0.0, clipper)
                    width = br.mean_width()
                    strength = uc.get("strength", "normal")
                    f = 0.75 if strength in ("strong", "double") else 1.0
                    attrs = {
                        "satin_column": True,
                        "zigzag_spacing_mm": _fmt(float(sp["spacing_mm"])),
                        "pull_compensation_mm": _fmt(float(sp["pull_compensation_mm"])),
                        "max_stitch_length_mm": _fmt(float(sp["split_stitch_length_mm"])),
                        "short_stitch_inset": int(sp["short_stitch_inset_percent"]),
                        "center_walk_underlay": width >= float(uc["none_below_mm"]) * f,
                        "center_walk_underlay_stitch_length_mm": _fmt(float(uc["center_walk_stitch_length_mm"])),
                        "contour_underlay": width >= float(uc["center_walk_below_mm"]) * f,
                        "contour_underlay_inset_mm": _fmt(float(uc["contour_inset_mm"])),
                        "contour_underlay_stitch_length_mm": _fmt(float(uc["contour_stitch_length_mm"])),
                        "zigzag_underlay": width >= float(uc["contour_below_mm"]) * f or (strength == "double" and width >= float(uc["center_walk_below_mm"]) * f),
                        "zigzag_underlay_spacing_mm": _fmt(float(uc["zigzag_spacing_mm"])),
                        "zigzag_underlay_inset_mm": _fmt(float(uc["zigzag_inset_mm"])),
                    }
                    d = _path_d([left, right], offset, closed=False)
                    lines.append(f'<path id="e{eid}" d="{d}" style="fill:none;stroke:{color};stroke-width:0.3" {_attrs(attrs)}/>')
                    manifest.append({"id": f"e{eid}", "group": region.name, "kind": "satin"})
            else:  # running
                repeats = int(rp["bean_repeats"]) if part.bean else 0
                for route in route_graph(part.graph, None):
                    coords = []
                    for pts, repeat in route:
                        coords.extend(pts if not coords else pts[1:])
                    if len(coords) < 2:
                        continue
                    eid += 1
                    attrs = {"running_stitch_length_mm": _fmt(float(rp["stitch_length_mm"])),
                             "running_stitch_tolerance_mm": _fmt(float(rp["tolerance_mm"])),
                             "bean_stitch_repeats": repeats}
                    d = _path_d([np.asarray(coords)], offset, closed=False)
                    lines.append(f'<path id="e{eid}" d="{d}" style="fill:none;stroke:{color};stroke-width:0.3" {_attrs(attrs)}/>')
                    manifest.append({"id": f"e{eid}", "group": region.name, "kind": "running"})
        lines.append("</g>")
    lines.append("</svg>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return manifest


def run_inkstitch(svg_path: Path, dst_path: Path, log: list[str], timeout: int = 1800) -> bool:
    found = find_inkstitch()
    if found is None:
        log.append("Ink/Stitch not found (set INKSTITCH_DIR and INKSTITCH_PYTHON, or run scripts/install_inkstitch.sh)")
        return False
    python, src = found
    env = dict(os.environ)
    env["INKSTITCH_OFFLINE_SCRIPT"] = "1"
    env.pop("PYTHONPATH", None)
    cmd = [str(python), "inkstitch.py", "--extension=output", "--format=dst", str(Path(svg_path).resolve())]
    try:
        dst_path = Path(dst_path).resolve()
        with open(dst_path, "wb") as out:
            proc = subprocess.run(cmd, cwd=str(src), stdout=out, stderr=subprocess.PIPE, env=env, timeout=timeout)
    except subprocess.TimeoutExpired:
        log.append(f"Ink/Stitch timed out after {timeout} s")
        return False
    err = proc.stderr.decode(errors="ignore").strip()
    if proc.returncode != 0:
        log.append(f"Ink/Stitch exited with code {proc.returncode}: {err[-600:]}")
        return False
    if not dst_path.exists() or dst_path.stat().st_size < 600:
        # Ink/Stitch can exit 0 with an empty payload on errors
        log.append(f"Ink/Stitch produced an empty DST: {err[-600:] or 'no error message'}")
        return False
    try:
        pattern = pe.read(str(dst_path))
        n = sum(1 for _, _, c in pattern.stitches if c & pe.COMMAND_MASK == pe.STITCH)
    except Exception as exc:
        log.append(f"Ink/Stitch DST could not be parsed: {exc}")
        return False
    if n == 0:
        log.append("Ink/Stitch DST parsed but has no stitches")
        return False
    if err:
        log.append(f"Ink/Stitch messages: {err[-400:]}")
    log.append(f"Ink/Stitch exported {n} stitches")
    return True


def plan_from_inkstitch_dst(dst_path: Path, layout: Layout, expected_blocks: list, min_stitch_len: float = 0.3) -> StitchPlan | None:
    pattern = pe.read(str(dst_path))
    plan = StitchPlan.from_pattern(pattern, engine="inkstitch")
    if len(plan.blocks) != len(expected_blocks):
        return None
    for b, region in zip(plan.blocks, expected_blocks):
        b.group = region.name
        b.color = region.group.color
        b.thread = region.group.thread or {}
        _flag_locks(b.stitches)
        b.stitches = enforce_min_length(b.stitches, min_stitch_len)
    plan.center()
    return plan


def _flag_locks(stitches, window: int = 6) -> None:
    """Ink/Stitch adds tack/lock stitches right after a jump and right before a jump, trim or colour
    change; mark the stitches within `window` of those points so the minimum-length rule spares them."""
    n = len(stitches)
    boundaries = [i for i, s in enumerate(stitches) if s.cmd in (JUMP, TRIM)] + [0, n - 1]
    for bnd in boundaries:
        for k in range(max(0, bnd - window), min(n, bnd + window + 1)):
            if stitches[k].cmd == STITCH:
                stitches[k].lock = True
