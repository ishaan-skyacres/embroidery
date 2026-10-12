"""Shared stitch plan model used by both engines, previews, outputs and validation.

Coordinates are millimetres, y down (SVG convention), relative to the hoop
centre. pyembroidery handles the DST y flip when writing.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Iterator

import numpy as np
import pyembroidery as pe

STITCH = "STITCH"
JUMP = "JUMP"
TRIM = "TRIM"


@dataclass
class Stitch:
    x: float
    y: float
    cmd: str = STITCH
    lock: bool = False       # lock stitches are exempt from the minimum length rule
    travel: bool = False     # travel (underpath) running stitches inside a colour
    underlay: bool = False   # underlay stitches (rendered lighter in previews)

    def xy(self) -> tuple[float, float]:
        return (self.x, self.y)


@dataclass
class StitchObject:
    """One stitched object (a fill, a satin branch, an outline) with its stitches."""
    kind: str                       # fill | satin | running | bean | underlay | travel | knockdown
    description: str
    stitches: list[Stitch] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    def count(self) -> int:
        return sum(1 for s in self.stitches if s.cmd == STITCH)


@dataclass
class ColorBlock:
    group: str                      # colour group name
    color: str                      # display hex
    thread: dict[str, Any] = field(default_factory=dict)
    objects: list[StitchObject] = field(default_factory=list)
    stitches: list[Stitch] = field(default_factory=list)   # flattened, in sewing order
    descriptions: list[str] = field(default_factory=list)  # plain-language list of what it stitches
    watch: list[str] = field(default_factory=list)         # what to watch for while it runs

    def stitch_count(self) -> int:
        return sum(1 for s in self.stitches if s.cmd == STITCH)

    def jump_count(self) -> int:
        return sum(1 for s in self.stitches if s.cmd == JUMP)

    def trim_count(self) -> int:
        return sum(1 for s in self.stitches if s.cmd == TRIM)

    def first_xy(self) -> tuple[float, float] | None:
        for s in self.stitches:
            if s.cmd == STITCH:
                return s.xy()
        return None

    def last_xy(self) -> tuple[float, float] | None:
        for s in reversed(self.stitches):
            if s.cmd == STITCH:
                return s.xy()
        return None

    def bounds(self) -> tuple[float, float, float, float] | None:
        pts = [(s.x, s.y) for s in self.stitches if s.cmd == STITCH]
        if not pts:
            return None
        a = np.asarray(pts)
        return (a[:, 0].min(), a[:, 1].min(), a[:, 0].max(), a[:, 1].max())

    def jumps(self) -> list[tuple[tuple[float, float], tuple[float, float], float]]:
        """Visible jumps inside the block: (from, to, length_mm) for moves flagged JUMP."""
        out = []
        prev = None
        for s in self.stitches:
            if s.cmd == STITCH:
                prev = s.xy()
            elif s.cmd == JUMP and prev is not None:
                out.append((prev, s.xy(), math.hypot(s.x - prev[0], s.y - prev[1])))
                prev = s.xy()
        return out


@dataclass
class StitchPlan:
    blocks: list[ColorBlock] = field(default_factory=list)
    engine: str = "python"
    meta: dict[str, Any] = field(default_factory=dict)

    # ---- counts -----------------------------------------------------------
    def stitch_count(self) -> int:
        return sum(b.stitch_count() for b in self.blocks)

    def jump_count(self) -> int:
        return sum(b.jump_count() for b in self.blocks)

    def trim_count(self) -> int:
        return sum(b.trim_count() for b in self.blocks)

    def color_changes(self) -> int:
        return max(0, len(self.blocks) - 1)

    def bounds(self) -> tuple[float, float, float, float]:
        pts = [(s.x, s.y) for b in self.blocks for s in b.stitches if s.cmd == STITCH]
        if not pts:
            return (0.0, 0.0, 0.0, 0.0)
        a = np.asarray(pts)
        return (float(a[:, 0].min()), float(a[:, 1].min()), float(a[:, 0].max()), float(a[:, 1].max()))

    def size(self) -> tuple[float, float]:
        x0, y0, x1, y1 = self.bounds()
        return (x1 - x0, y1 - y0)

    def iter_segments(self) -> Iterator[tuple[int, Stitch, Stitch]]:
        """Yield (block_index, from, to) for every needle move that is a STITCH."""
        for bi, b in enumerate(self.blocks):
            prev = None
            for s in b.stitches:
                if s.cmd == TRIM:
                    continue
                if prev is not None and s.cmd == STITCH:
                    yield bi, prev, s
                prev = s

    def stitch_lengths(self, include_locks: bool = True) -> np.ndarray:
        out = []
        for _, a, b in self.iter_segments():
            if not include_locks and (a.lock or b.lock):
                continue
            out.append(math.hypot(b.x - a.x, b.y - a.y))
        return np.asarray(out) if out else np.zeros(0)

    def sew_minutes(self, spm: float, change_minutes: float) -> float:
        return self.stitch_count() / spm + self.color_changes() * change_minutes

    # ---- transforms -------------------------------------------------------
    def translate(self, dx: float, dy: float) -> None:
        for b in self.blocks:
            for s in b.stitches:
                s.x += dx
                s.y += dy
            for o in b.objects:
                for s in o.stitches:
                    if s not in b.stitches:
                        s.x += dx
                        s.y += dy

    def center(self) -> None:
        x0, y0, x1, y1 = self.bounds()
        self.translate(-(x0 + x1) / 2, -(y0 + y1) / 2)

    # ---- pyembroidery ---------------------------------------------------
    def to_pattern(self) -> pe.EmbPattern:
        """Build a pyembroidery pattern (units 0.1 mm, y down; pyembroidery flips for DST)."""
        pattern = pe.EmbPattern()
        for bi, block in enumerate(self.blocks):
            thread = pe.EmbThread()
            thread.set_hex_color(block.color)
            thread.description = block.group
            if block.thread:
                thread.brand = block.thread.get("brand")
                thread.catalog_number = block.thread.get("code")
                thread.description = f"{block.group} ({block.thread.get('brand')} {block.thread.get('code')})"
            pattern.add_thread(thread)
            if bi > 0:
                pattern.color_change()
            for s in block.stitches:
                x = round(s.x * 10)
                y = round(s.y * 10)
                if s.cmd == STITCH:
                    pattern.add_stitch_absolute(pe.STITCH, x, y)
                elif s.cmd == JUMP:
                    pattern.add_stitch_absolute(pe.JUMP, x, y)
                elif s.cmd == TRIM:
                    pattern.trim()
        pattern.end()
        return pattern

    @staticmethod
    def from_pattern(pattern: pe.EmbPattern, engine: str = "dst") -> "StitchPlan":
        """Read a pattern back into a plan: blocks split at colour changes, units mm."""
        plan = StitchPlan(engine=engine)
        block = ColorBlock(group="stop 1", color="#808080")
        plan.blocks.append(block)
        for x, y, cmd in pattern.stitches:
            c = cmd & pe.COMMAND_MASK
            if c == pe.STITCH:
                block.stitches.append(Stitch(x / 10.0, y / 10.0, STITCH))
            elif c == pe.JUMP:
                block.stitches.append(Stitch(x / 10.0, y / 10.0, JUMP))
            elif c == pe.TRIM:
                block.stitches.append(Stitch(x / 10.0, y / 10.0, TRIM))
            elif c in (pe.COLOR_CHANGE, pe.NEEDLE_SET, pe.COLOR_BREAK):
                block = ColorBlock(group=f"stop {len(plan.blocks) + 1}", color="#808080")
                plan.blocks.append(block)
            elif c == pe.END:
                break
        # drop a trailing empty block created by a colour change with nothing after it
        plan.blocks = [b for b in plan.blocks if b.stitches]
        for i, (b, t) in enumerate(zip(plan.blocks, pattern.threadlist)):
            b.color = t.hex_color() if hasattr(t, "hex_color") else "#808080"
        return plan

    def merge_consecutive_jumps(self) -> None:
        """Collapse runs of JUMP commands into a single jump to the last position."""
        for b in self.blocks:
            out: list[Stitch] = []
            for s in b.stitches:
                if s.cmd == JUMP and out and out[-1].cmd == JUMP:
                    out[-1] = s
                else:
                    out.append(s)
            b.stitches = out
