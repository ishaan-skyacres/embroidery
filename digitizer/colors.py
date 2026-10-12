"""Colour science (CIELAB, CIEDE2000), colour grouping and thread matching."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import yaml

PALETTE_DIR = Path(__file__).resolve().parent / "palettes"


# ---------------------------------------------------------------------------
# colour conversions
# ---------------------------------------------------------------------------
def normalize_hex(h: str) -> str:
    h = h.strip().lower()
    if not h.startswith("#"):
        h = "#" + h
    if len(h) == 4:
        h = "#" + "".join(c * 2 for c in h[1:])
    if not re.match(r"^#[0-9a-f]{6}$", h):
        raise ValueError(f"Not a hex colour: {h!r}")
    return h


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = normalize_hex(h)
    return int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)


def rgb_to_hex(rgb: Iterable[float]) -> str:
    r, g, b = [int(round(max(0, min(255, v)))) for v in rgb]
    return "#%02x%02x%02x" % (r, g, b)


def rgb_to_lab(rgb: Iterable[float]) -> np.ndarray:
    """sRGB (0..255) to CIELAB (D65)."""
    c = np.asarray(rgb, dtype=float) / 255.0
    lin = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    m = np.array([[0.4124564, 0.3575761, 0.1804375],
                  [0.2126729, 0.7151522, 0.0721750],
                  [0.0193339, 0.1191920, 0.9503041]])
    xyz = m @ lin
    xyz = xyz / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16.0 / 116.0)
    L = 116.0 * f[1] - 16.0
    a = 500.0 * (f[0] - f[1])
    b = 200.0 * (f[1] - f[2])
    return np.array([L, a, b])


def lab_to_rgb(lab: Iterable[float]) -> tuple[int, int, int]:
    L, a, b = lab
    fy = (L + 16.0) / 116.0
    fx = fy + a / 500.0
    fz = fy - b / 200.0

    def finv(t):
        return t ** 3 if t ** 3 > 0.008856 else (t - 16.0 / 116.0) / 7.787
    xyz = np.array([finv(fx), finv(fy), finv(fz)]) * np.array([0.95047, 1.0, 1.08883])
    m = np.array([[3.2404542, -1.5371385, -0.4985314],
                  [-0.9692660, 1.8760108, 0.0415560],
                  [0.0556434, -0.2040259, 1.0572252]])
    lin = m @ xyz
    lin = np.clip(lin, 0, 1)
    c = np.where(lin <= 0.0031308, 12.92 * lin, 1.055 * np.power(lin, 1 / 2.4) - 0.055)
    return tuple(int(round(v * 255)) for v in c)


def hex_to_lab(h: str) -> np.ndarray:
    return rgb_to_lab(hex_to_rgb(h))


def ciede2000(lab1, lab2) -> float:
    """CIEDE2000 colour difference (Sharma, Wu, Dalal 2005)."""
    L1, a1, b1 = [float(v) for v in lab1]
    L2, a2, b2 = [float(v) for v in lab2]
    kL = kC = kH = 1.0
    C1 = math.hypot(a1, b1)
    C2 = math.hypot(a2, b2)
    Cbar = (C1 + C2) / 2.0
    G = 0.5 * (1 - math.sqrt(Cbar ** 7 / (Cbar ** 7 + 25.0 ** 7)))
    a1p = (1 + G) * a1
    a2p = (1 + G) * a2
    C1p = math.hypot(a1p, b1)
    C2p = math.hypot(a2p, b2)

    def hp(a, b):
        if a == 0 and b == 0:
            return 0.0
        h = math.degrees(math.atan2(b, a))
        return h + 360.0 if h < 0 else h
    h1p = hp(a1p, b1)
    h2p = hp(a2p, b2)
    dLp = L2 - L1
    dCp = C2p - C1p
    if C1p * C2p == 0:
        dhp = 0.0
    else:
        dh = h2p - h1p
        if dh > 180:
            dh -= 360
        elif dh < -180:
            dh += 360
        dhp = dh
    dHp = 2 * math.sqrt(C1p * C2p) * math.sin(math.radians(dhp / 2.0))
    Lbp = (L1 + L2) / 2.0
    Cbp = (C1p + C2p) / 2.0
    if C1p * C2p == 0:
        hbp = h1p + h2p
    else:
        s = h1p + h2p
        if abs(h1p - h2p) > 180:
            hbp = (s + 360) / 2.0 if s < 360 else (s - 360) / 2.0
        else:
            hbp = s / 2.0
    T = (1 - 0.17 * math.cos(math.radians(hbp - 30)) + 0.24 * math.cos(math.radians(2 * hbp))
         + 0.32 * math.cos(math.radians(3 * hbp + 6)) - 0.20 * math.cos(math.radians(4 * hbp - 63)))
    dtheta = 30 * math.exp(-(((hbp - 275) / 25.0) ** 2))
    RC = 2 * math.sqrt(Cbp ** 7 / (Cbp ** 7 + 25.0 ** 7))
    SL = 1 + (0.015 * (Lbp - 50) ** 2) / math.sqrt(20 + (Lbp - 50) ** 2)
    SC = 1 + 0.045 * Cbp
    SH = 1 + 0.015 * Cbp * T
    RT = -math.sin(math.radians(2 * dtheta)) * RC
    return math.sqrt((dLp / (kL * SL)) ** 2 + (dCp / (kC * SC)) ** 2 + (dHp / (kH * SH)) ** 2
                     + RT * (dCp / (kC * SC)) * (dHp / (kH * SH)))


def hex_delta_e(h1: str, h2: str) -> float:
    return ciede2000(hex_to_lab(h1), hex_to_lab(h2))


# ---------------------------------------------------------------------------
# friendly names
# ---------------------------------------------------------------------------
NAMED_COLORS = {
    "black": "#000000", "white": "#ffffff", "grey": "#808080", "light grey": "#c0c0c0", "dark grey": "#404040",
    "red": "#e02020", "dark red": "#8b0000", "orange": "#ff8c00", "yellow": "#ffd700", "gold": "#d4af37",
    "green": "#2e8b2e", "dark green": "#1f4d1f", "light green": "#8fbc5a", "olive": "#6b8e23", "teal": "#008080",
    "blue": "#2060d0", "navy": "#1a2f5e", "sky blue": "#87ceeb", "light blue": "#9ec5e8", "royal blue": "#3953a4",
    "purple": "#7030a0", "violet": "#8a2be2", "pink": "#ff8fb0", "magenta": "#d0208f", "brown": "#7b4a1e",
    "tan": "#d2b48c", "beige": "#e8dcc0", "cream": "#f5f0dc", "maroon": "#800020", "coral": "#ff7f50",
}


def friendly_name(h: str) -> str:
    lab = hex_to_lab(h)
    best = min(NAMED_COLORS.items(), key=lambda kv: ciede2000(lab, hex_to_lab(kv[1])))
    return best[0]


# ---------------------------------------------------------------------------
# thread palettes (GIMP .gpl files shipped with Ink/Stitch, GPL-3.0)
# ---------------------------------------------------------------------------
@dataclass
class Thread:
    brand: str
    name: str
    code: str
    hex: str
    lab: np.ndarray = field(repr=False, default=None)


def load_palette(path: Path) -> tuple[str, list[Thread]]:
    brand = path.stem.replace("InkStitch ", "")
    threads: list[Thread] = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or ":" in line[:12] and not line[0].isdigit():
                if line.lower().startswith("name:"):
                    brand = line.split(":", 1)[1].strip().replace("Ink/Stitch: ", "")
                continue
            parts = line.split()
            if len(parts) < 4:
                continue
            try:
                r, g, b = int(parts[0]), int(parts[1]), int(parts[2])
            except ValueError:
                continue
            code = parts[-1]
            name = " ".join(parts[3:-1]) or code
            hx = rgb_to_hex((r, g, b))
            threads.append(Thread(brand, name, code, hx, rgb_to_lab((r, g, b))))
    return brand, threads


_PALETTE_CACHE: dict[str, list[Thread]] = {}


def load_palettes(names: Iterable[str]) -> dict[str, list[Thread]]:
    out: dict[str, list[Thread]] = {}
    for name in names:
        if name in _PALETTE_CACHE:
            out[name] = _PALETTE_CACHE[name]
            continue
        path = PALETTE_DIR / f"{name}.gpl"
        if not path.exists():
            path = Path(name)
        if not path.exists():
            continue
        brand, threads = load_palette(path)
        _PALETTE_CACHE[name] = threads
        out[name] = threads
    return out


def nearest_threads(h: str, palettes: dict[str, list[Thread]]) -> list[dict[str, Any]]:
    """Best match per palette, sorted by delta E."""
    lab = hex_to_lab(h)
    results = []
    for _, threads in palettes.items():
        if not threads:
            continue
        best = min(threads, key=lambda t: ciede2000(lab, t.lab))
        results.append({"brand": best.brand, "name": best.name, "code": best.code, "hex": best.hex,
                        "delta_e": round(ciede2000(lab, best.lab), 1)})
    results.sort(key=lambda r: r["delta_e"])
    return results


# ---------------------------------------------------------------------------
# grouping
# ---------------------------------------------------------------------------
@dataclass
class ColorGroup:
    name: str
    color: str
    members: list[str]
    skip: bool = False
    manual: bool = False
    area: float = 0.0
    thread: dict[str, Any] | None = None
    thread_options: list[dict[str, Any]] = field(default_factory=list)
    order_hint: int | None = None
    is_background: bool = False

    def lab(self) -> np.ndarray:
        return hex_to_lab(self.color)


class GroupingDecisionNeeded(Exception):
    """Raised when --colors N would require merging two clearly different colours."""

    def __init__(self, a: ColorGroup, b: ColorGroup, delta_e: float, groups: list[ColorGroup]):
        self.a, self.b, self.delta_e, self.groups = a, b, delta_e, groups
        super().__init__(
            f"Reaching the requested number of colours would merge {a.name} ({a.color}) with {b.name} ({b.color}), "
            f"which differ by delta E {delta_e:.1f} (limit {0:.0f}). Choose which colours to combine with --group "
            f"or groups.yaml, or raise --colors.")


def weighted_color(members: list[str], areas: dict[str, float]) -> str:
    labs = np.array([hex_to_lab(m) for m in members])
    w = np.array([max(areas.get(m, 0.0), 1e-9) for m in members])
    lab = (labs * w[:, None]).sum(axis=0) / w.sum()
    return rgb_to_hex(lab_to_rgb(lab))


def unique_name(base: str, taken: set[str]) -> str:
    name = base
    i = 2
    while name in taken:
        name = f"{base}-{i}"
        i += 1
    taken.add(name)
    return name


def auto_group(areas: dict[str, float], threshold: float, n_colors: int | None, refuse_de: float,
               manual: list[ColorGroup], log: list[str]) -> list[ColorGroup]:
    """Cluster raw colours (hex -> area) into thread groups.

    `manual` groups are fixed; their members are removed from the automatic
    pool. Remaining colours are merged agglomeratively (closest centroid pair
    first) while the distance is under `threshold`, then further down to
    `n_colors` groups unless that would cross `refuse_de`.
    """
    assigned = {m for g in manual for m in g.members}
    pool = [ColorGroup(name=h, color=h, members=[h], area=areas[h]) for h in areas if h not in assigned]
    groups = list(manual)

    def centroid_dist(a: ColorGroup, b: ColorGroup) -> float:
        return ciede2000(a.lab(), b.lab())

    def merge(a: ColorGroup, b: ColorGroup) -> ColorGroup:
        members = a.members + b.members
        return ColorGroup(name=a.name, color=weighted_color(members, areas), members=members,
                          area=a.area + b.area)

    # 1. threshold merging among automatic colours
    while len(pool) > 1:
        best = None
        for i in range(len(pool)):
            for j in range(i + 1, len(pool)):
                d = centroid_dist(pool[i], pool[j])
                if best is None or d < best[0]:
                    best = (d, i, j)
        if best is None or best[0] >= threshold:
            break
        d, i, j = best
        log.append(f"Merged {pool[j].color} into {pool[i].color} (delta E {d:.1f} < {threshold})")
        merged = merge(pool[i], pool[j])
        pool = [g for k, g in enumerate(pool) if k not in (i, j)] + [merged]

    # 2. reduce to N groups (manual groups count, but are never merged)
    if n_colors is not None:
        skip_count = sum(1 for g in groups if g.skip)
        while len(groups) - skip_count + len(pool) > n_colors and len(pool) > 1:
            best = None
            for i in range(len(pool)):
                for j in range(i + 1, len(pool)):
                    d = centroid_dist(pool[i], pool[j])
                    if best is None or d < best[0]:
                        best = (d, i, j)
            d, i, j = best
            if d > refuse_de:
                exc = GroupingDecisionNeeded(pool[i], pool[j], d, groups + pool)
                exc.args = (exc.args[0].replace("limit 0", f"limit {refuse_de:g}"),)
                raise exc
            log.append(f"Merged {pool[j].color} into {pool[i].color} to reach {n_colors} colours (delta E {d:.1f})")
            merged = merge(pool[i], pool[j])
            pool = [g for k, g in enumerate(pool) if k not in (i, j)] + [merged]
        if len(groups) - skip_count + len(pool) > n_colors:
            log.append(f"Could not reach {n_colors} colours: manual groups already exceed it.")

    # 3. name automatic groups
    taken = {g.name for g in groups}
    pool.sort(key=lambda g: -g.area)
    for g in pool:
        g.name = unique_name(friendly_name(g.color), taken)
        g.members.sort(key=lambda m: -areas.get(m, 0))
    return groups + pool


def parse_group_args(items: Iterable[str]) -> list[ColorGroup]:
    """Parse --group '#1a3c6e,#1b3d70=navy' (or '=skip') entries."""
    out = []
    for item in items:
        if "=" not in item:
            raise ValueError(f"--group expects '#hex,#hex=name', got {item!r}")
        members, name = item.rsplit("=", 1)
        hexes = [normalize_hex(h) for h in members.split(",") if h.strip()]
        name = name.strip()
        skip = name.lower() == "skip"
        out.append(ColorGroup(name=("skip" if skip else name), color=hexes[0], members=hexes, skip=skip, manual=True))
    return out


def load_groups_yaml(path: Path) -> tuple[list[ColorGroup], list[str] | None]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    groups = []
    for name, spec in (data.get("groups") or {}).items():
        if isinstance(spec, list):
            spec = {"members": spec}
        members = [normalize_hex(m) for m in spec.get("members", [])]
        if not members:
            continue
        color = normalize_hex(spec["color"]) if spec.get("color") else None
        thread = spec.get("thread")
        if isinstance(thread, str):
            thread = {"name": thread}
        groups.append(ColorGroup(name=str(name), color=color or members[0], members=members,
                                 skip=bool(spec.get("skip", False)), manual=True, thread=thread))
    order = data.get("order")
    return groups, (list(order) if order else None)


def groups_to_yaml(groups: list[ColorGroup], order: list[str], areas: dict[str, float]) -> str:
    doc: dict[str, Any] = {"groups": {}, "order": [g.name for g in order_groups(groups, order) if not g.skip]}
    for g in groups:
        entry: dict[str, Any] = {"members": g.members, "color": g.color}
        if g.skip:
            entry["skip"] = True
        if g.thread:
            entry["thread"] = {k: v for k, v in g.thread.items() if k in ("brand", "code", "name")}
        if g.thread_options:
            entry["thread_options"] = [f"{t['brand']} {t['code']} {t['name']} (dE {t['delta_e']})" for t in g.thread_options[:3]]
        entry["area_mm2"] = round(g.area, 1)
        doc["groups"][g.name] = entry
    header = ("# Colour groups. Edit members/names/skip/thread, then re-run with --groups this_file.\n"
              "# 'order' is the sewing order (first = stitched first). The tool warns if it stitches a lower layer over an upper one.\n")
    return header + yaml.safe_dump(doc, sort_keys=False, allow_unicode=True)


def order_groups(groups: list[ColorGroup], order: list[str]) -> list[ColorGroup]:
    by_name = {g.name: g for g in groups}
    return [by_name[n] for n in order if n in by_name]
