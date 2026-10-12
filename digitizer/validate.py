"""Hard checks: read the DST back and confirm it agrees with the plan, report, thread sheet and procedure."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pyembroidery as pe

from .layering import Layout
from .params import Params
from .stitchplan import STITCH, StitchPlan


class ValidationError(Exception):
    pass


@dataclass
class ValidationResult:
    ok: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checks: list[str] = field(default_factory=list)
    dst_stitches: int = 0
    dst_color_changes: int = 0
    dst_bounds_mm: tuple[float, float, float, float] = (0, 0, 0, 0)
    dst_block_counts: list[int] = field(default_factory=list)
    min_len: float = 0.0
    max_len: float = 0.0
    short_count: int = 0
    long_count: int = 0


def read_dst_blocks(path: Path) -> tuple[list[list[tuple[float, float, int]]], tuple[float, float, float, float]]:
    pattern = pe.read(str(path))
    if pattern is None:
        raise ValidationError(f"{path} could not be read back")
    blocks: list[list[tuple[float, float, int]]] = [[]]
    for x, y, cmd in pattern.stitches:
        c = cmd & pe.COMMAND_MASK
        if c in (pe.COLOR_CHANGE, pe.NEEDLE_SET, pe.COLOR_BREAK):
            blocks.append([])
        elif c == pe.END:
            break
        else:
            blocks[-1].append((x / 10.0, y / 10.0, c))
    blocks = [b for b in blocks if any(c == pe.STITCH for _, _, c in b)]
    pts = [(x, y) for b in blocks for x, y, c in b if c == pe.STITCH]
    if not pts:
        raise ValidationError(f"{path} contains no stitches")
    a = np.asarray(pts)
    return blocks, (float(a[:, 0].min()), float(a[:, 1].min()), float(a[:, 0].max()), float(a[:, 1].max()))


def validate(plan: StitchPlan, dst_path: Path, layout: Layout, params: Params,
             thread_sheet_counts: list[int], procedure_counts: list[int], report_total: int) -> ValidationResult:
    res = ValidationResult()
    max_stitch = float(params["machine.max_stitch_mm"])
    min_stitch = float(params["general.min_stitch_length_mm"])
    clearance = float(params["machine.hoop_clearance_mm"])

    if not dst_path.exists() or dst_path.stat().st_size == 0:
        res.errors.append(f"{dst_path.name} is missing or empty")
        res.ok = False
        return res
    blocks, bounds = read_dst_blocks(dst_path)
    res.dst_bounds_mm = bounds
    res.dst_block_counts = [sum(1 for _, _, c in b if c == pe.STITCH) for b in blocks]
    res.dst_stitches = sum(res.dst_block_counts)
    res.dst_color_changes = len(blocks) - 1

    # hoop fit (DST y axis is flipped relative to the plan, which does not change the extents)
    w = bounds[2] - bounds[0]
    h = bounds[3] - bounds[1]
    hw, hh = layout.hoop_w, layout.hoop_h
    if layout.orientation != "as labelled":
        hw, hh = hh, hw
    if w <= hw - 2 * clearance + 1e-6 and h <= hh - 2 * clearance + 1e-6:
        res.checks.append(f"DST extents {w:.1f} x {h:.1f} mm fit hoop {layout.hoop_name} ({layout.orientation}) with {clearance:.0f} mm clearance")
    else:
        res.errors.append(f"DST extents {w:.1f} x {h:.1f} mm do not fit hoop {layout.hoop_name} with {clearance:.0f} mm clearance")
    # centred on origin
    cx = (bounds[0] + bounds[2]) / 2
    cy = (bounds[1] + bounds[3]) / 2
    if abs(cx) <= 0.6 and abs(cy) <= 0.6:
        res.checks.append(f"DST is centred on the hoop origin (centre offset {cx:.2f}, {cy:.2f} mm)")
    else:
        res.errors.append(f"DST is not centred: centre is at ({cx:.1f}, {cy:.1f}) mm")

    # colour changes
    expected_changes = len(plan.blocks) - 1
    if res.dst_color_changes == expected_changes:
        res.checks.append(f"{res.dst_color_changes} colour changes = {len(plan.blocks)} thread groups - 1")
    else:
        res.errors.append(f"DST has {res.dst_color_changes} colour changes but the plan has {len(plan.blocks)} groups "
                          f"(expected {expected_changes})")

    # stitch lengths (between consecutive needle-down records within a block), with lock stitches
    # identified from the plan when it carries that information, otherwise by their position
    # (within a few stitches of a jump, trim or colour change)
    lengths = []
    is_lock = []
    plan_has_locks = any(s.lock for b in plan.blocks for s in b.stitches)
    for bi, b in enumerate(blocks):
        plan_flags = [s.lock for s in plan.blocks[bi].stitches if s.cmd == STITCH] if (plan_has_locks and bi < len(plan.blocks)) else None
        boundary = set()
        if plan_flags is None:
            k = 0
            idx_of_stitch = []
            for x, y, c in b:
                if c == pe.STITCH:
                    idx_of_stitch.append(k)
                    k += 1
                else:
                    boundary.add(k)       # a jump/trim happens before stitch number k
            boundary.add(0)
            boundary.add(k)
        prev = None
        k = 0
        for x, y, c in b:
            if c == pe.STITCH:
                if prev is not None:
                    lengths.append(math.hypot(x - prev[0], y - prev[1]))
                    if plan_flags is not None:
                        lock = (k < len(plan_flags) and plan_flags[k]) or (k - 1 < len(plan_flags) and plan_flags[k - 1])
                    else:
                        lock = any(abs(k - bnd) <= 6 for bnd in boundary)
                    is_lock.append(bool(lock))
                prev = (x, y)
                k += 1
            elif c == pe.JUMP:
                prev = (x, y)
    L = np.asarray(lengths)
    lockmask = np.asarray(is_lock, dtype=bool) if is_lock else np.zeros(0, dtype=bool)
    res.min_len = float(L[~lockmask].min()) if len(L) and (~lockmask).any() else 0.0
    res.max_len = float(L.max()) if len(L) else 0.0
    res.long_count = int((L > max_stitch + 1e-6).sum())
    # lock stitches are exempt. Both ends of a stitch are rounded to the 0.1 mm DST grid, so a
    # 0.30 mm stitch can measure as little as 0.30 - 0.1 * sqrt(2) = 0.16 mm after rounding.
    res.short_count = int(((L < min_stitch - 0.15) & ~lockmask).sum())
    if not plan_has_locks:
        res.warnings.append("lock stitches could not be identified exactly in this DST (engine without lock flags); "
                            "short stitches within 6 stitches of a jump or colour change were treated as locks")
    if res.long_count:
        res.errors.append(f"{res.long_count} stitch(es) longer than {max_stitch} mm (max {res.max_len:.2f} mm)")
    else:
        res.checks.append(f"longest stitch {res.max_len:.2f} mm <= {max_stitch} mm")
    if res.short_count:
        res.errors.append(f"{res.short_count} stitch(es) shorter than {min_stitch} mm that are not lock stitches (min {res.min_len:.2f} mm)")
    else:
        res.checks.append(f"shortest non-lock stitch {res.min_len:.2f} mm (>= {min_stitch} mm before rounding to the 0.1 mm DST grid)")

    # counts agree everywhere
    plan_counts = [b.stitch_count() for b in plan.blocks]
    if res.dst_block_counts == plan_counts:
        res.checks.append(f"per-stop stitch counts in the DST match the plan: {plan_counts}")
    else:
        res.errors.append(f"per-stop stitch counts differ: DST {res.dst_block_counts} vs plan {plan_counts}")
    if res.dst_stitches == plan.stitch_count() == report_total:
        res.checks.append(f"total stitch count {res.dst_stitches} agrees between DST, plan and report")
    else:
        res.errors.append(f"total stitch count differs: DST {res.dst_stitches}, plan {plan.stitch_count()}, report {report_total}")
    if thread_sheet_counts == plan_counts:
        res.checks.append("thread sheet stop counts match the plan")
    else:
        res.errors.append(f"thread sheet counts {thread_sheet_counts} differ from plan {plan_counts}")
    if procedure_counts == plan_counts:
        res.checks.append("procedure run sheet stop counts match the plan")
    else:
        res.errors.append(f"procedure counts {procedure_counts} differ from plan {plan_counts}")
    names = [b.group for b in plan.blocks]
    if len(set(names)) == len(names):
        res.checks.append("no colour group appears in two separate blocks")
    else:
        dup = sorted({n for n in names if names.count(n) > 1})
        res.errors.append(f"colour group(s) {', '.join(dup)} appear in more than one block")
    res.ok = not res.errors
    return res
