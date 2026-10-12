"""Thread sheet (md/pdf), report.md, params_used.yaml."""
from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

from .colors import hex_to_rgb
from .params import Params
from .stitchplan import StitchPlan


def thread_rows(plan: StitchPlan, params: Params) -> list[dict[str, Any]]:
    spm = float(params["machine.estimate_speed_spm"])
    rows = []
    for i, b in enumerate(plan.blocks, start=1):
        t = b.thread or {}
        rows.append({
            "stop": i, "color": b.color, "group": b.group,
            "brand": t.get("brand", ""), "code": t.get("code", ""), "name": t.get("name", ""),
            "delta_e": t.get("delta_e", ""), "stitches": b.stitch_count(),
            "minutes": b.stitch_count() / spm,
        })
    return rows


def write_thread_sheet_md(rows: list[dict], plan: StitchPlan, params: Params, path: Path, title: str) -> Path:
    spm = float(params["machine.estimate_speed_spm"])
    change = float(params["machine.thread_change_minutes"])
    lines = [f"# Thread sheet: {title}", "",
             "DST files do not store thread colours; the machine will show placeholder colours. "
             "Load the threads below in this order.", "",
             "| Stop | Swatch | Hex | Group | Suggested thread | Stitches | Minutes |",
             "|---|---|---|---|---|---|---|"]
    for r in rows:
        swatch = f'<span style="display:inline-block;width:1.6em;height:1em;background:{r["color"]};border:1px solid #444"></span>'
        thread = f'{r["brand"]} {r["code"]} {r["name"]}'.strip() + (f' (dE {r["delta_e"]})' if r["delta_e"] != "" else "")
        lines.append(f'| {r["stop"]} | {swatch} | {r["color"]} | {r["group"]} | {thread} | {r["stitches"]} | {r["minutes"]:.1f} |')
    total = plan.stitch_count()
    lines += ["", f"Total: {total} stitches, {len(rows)} thread colours, {len(rows) - 1} thread changes, "
              f"about {total / spm:.0f} min sewing at {spm:.0f} spm plus {(len(rows) - 1) * change:.0f} min for thread changes.", ""]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def write_thread_sheet_pdf(rows: list[dict], plan: StitchPlan, params: Params, path: Path, title: str) -> Path:
    from reportlab.lib import colors as rl
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=15 * mm, bottomMargin=15 * mm)
    story = [Paragraph(f"Thread sheet: {title}", styles["Title"]),
             Paragraph("DST files do not store thread colours; the machine shows placeholder colours. Load threads in this order.", styles["Normal"]),
             Spacer(1, 6 * mm)]
    data = [["Stop", "", "Hex", "Group", "Suggested thread", "Stitches", "Min"]]
    for r in rows:
        thread = f'{r["brand"]} {r["code"]}<br/>{r["name"]}' + (f' (dE {r["delta_e"]})' if r["delta_e"] != "" else "")
        data.append([str(r["stop"]), "", r["color"], r["group"], Paragraph(thread, styles["Normal"]), str(r["stitches"]), f'{r["minutes"]:.1f}'])
    t = Table(data, colWidths=[12 * mm, 14 * mm, 20 * mm, 30 * mm, 70 * mm, 20 * mm, 14 * mm])
    style = [("GRID", (0, 0), (-1, -1), 0.4, rl.grey), ("BACKGROUND", (0, 0), (-1, 0), rl.HexColor("#e8e8e8")),
             ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("FONTSIZE", (0, 0), (-1, -1), 9)]
    for i, r in enumerate(rows, start=1):
        rr, gg, bb = hex_to_rgb(r["color"])
        style.append(("BACKGROUND", (1, i), (1, i), rl.Color(rr / 255, gg / 255, bb / 255)))
    t.setStyle(TableStyle(style))
    story.append(t)
    spm = float(params["machine.estimate_speed_spm"])
    change = float(params["machine.thread_change_minutes"])
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(f"Total {plan.stitch_count()} stitches, {len(rows)} colours, {len(rows) - 1} changes, about "
                           f"{plan.stitch_count() / spm:.0f} min sewing at {spm:.0f} spm plus {(len(rows) - 1) * change:.0f} min for changes.",
                           styles["Normal"]))
    doc.build(story)
    return path


def write_params_used(params: Params, path: Path, extra: dict[str, Any]) -> Path:
    import yaml
    data = dict(params.data)
    data = {k: v for k, v in data.items() if k != "fabrics"}
    data["fabric_preset"] = params.fabric_info()
    data["run"] = extra
    data["applied_overrides"] = params.applied_overrides
    path.write_text("# Exact parameters used for this run (re-run with --params this_file to reproduce; edit to tweak)\n"
                    + yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path


def write_report(path: Path, ctx: dict[str, Any]) -> Path:
    """report.md from the run context dict."""
    plan: StitchPlan = ctx["plan"]
    layout = ctx["layout"]
    params: Params = ctx["params"]
    val = ctx.get("validation")
    L = plan.stitch_lengths(include_locks=False)
    spm = float(params["machine.estimate_speed_spm"])
    change = float(params["machine.thread_change_minutes"])
    w, h = plan.size()
    lines = [f"# Digitizing report: {ctx['title']}", "",
             f"Generated {dt.datetime.now():%Y-%m-%d %H:%M} from `{ctx['input']}` with engine **{plan.engine}** "
             f"({ctx.get('engine_note', '')}).", "",
             "## Size and hoop", "",
             f"- Final size: {w:.1f} x {h:.1f} mm ({w / 25.4:.2f} x {h / 25.4:.2f} in), requested {ctx['size_mm']:.0f} mm on the longest side",
             f"- Hoop: {layout.hoop_name} ({layout.hoop_w:.0f} x {layout.hoop_h:.0f} mm), mounted {layout.orientation}; "
             f"{layout.margin_mm:.1f} mm to the nearest hoop edge (required clearance {layout.clearance_mm:.0f} mm)",
             f"- Design centred on the hoop origin: stitch bounds {', '.join(f'{v:.1f}' for v in plan.bounds())} mm", "",
             "## Stitches", "",
             f"- Total stitches: {plan.stitch_count()}",
             f"- Colour stops: {len(plan.blocks)} ({len(plan.blocks) - 1} thread changes)",
             f"- Jumps inside colours: {plan.jump_count() - len(plan.blocks)} (plus one jump to the start of each colour); trims: {plan.trim_count()}",
             f"- Estimated time: {plan.stitch_count() / spm:.0f} min sewing at {spm:.0f} spm + {(len(plan.blocks) - 1) * change:.0f} min thread changes "
             f"= about {plan.sew_minutes(spm, change):.0f} min",
             f"- Stitch length (excluding lock stitches): min {L.min():.2f} mm, max {L.max():.2f} mm, mean {L.mean():.2f} mm" if len(L) else "- no stitches",
             f"- Stitches under {params['general.min_stitch_length_mm']} mm (non-lock): {int((L < float(params['general.min_stitch_length_mm'])).sum()) if len(L) else 0}; "
             f"over {params['machine.max_stitch_mm']} mm: {int((L > float(params['machine.max_stitch_mm'])).sum()) if len(L) else 0}", "",
             "| Stop | Group | Colour | Stitches | Jumps | Trims | What it stitches |", "|---|---|---|---|---|---|---|"]
    for i, b in enumerate(plan.blocks, start=1):
        lines.append(f"| {i} | {b.group} | {b.color} | {b.stitch_count()} | {b.jump_count()} | {b.trim_count()} | "
                     + "; ".join(b.descriptions)[:200] + " |")
    lines += ["", "## Colour grouping", ""]
    for g in ctx["groups"]:
        t = g.thread or {}
        lines.append(f"- **{g.name}** {g.color}: members {', '.join(g.members)}" + (" (skipped)" if g.skip else "")
                     + (f"; thread {t.get('brand', '')} {t.get('code', '')} {t.get('name', '')} (dE {t.get('delta_e', '?')})" if t and not g.skip else ""))
    if ctx.get("grouping_log"):
        lines += [""] + [f"- {m}" for m in ctx["grouping_log"]]
    lines += ["", "## Layering and sequencing", ""]
    lines += [f"- {m}" for m in layout.log]
    if layout.conflicts:
        lines.append(f"- {len(layout.conflicts)} layering conflict(s) resolved by per-shape knockout (details above).")
    lines += ["", "## Classification decisions", ""]
    for name, parts in ctx["parts"].items():
        kinds: dict[str, int] = {}
        for p in parts:
            kinds[p.kind] = kinds.get(p.kind, 0) + 1
        lines.append(f"- **{name}**: " + ", ".join(f"{v} {k}" for k, v in kinds.items()))
        for p in parts:
            if p.notes or p.warnings:
                lines.append(f"  - {p.kind} {p.index}: {p.description}; " + "; ".join(p.notes + p.warnings))
    conv = [l for l in ctx["log"] if "-> tatami fill" in l or "split" in l or "converted" in l]
    if conv:
        lines += ["", "Satin columns converted or split:", ""] + [f"- {l}" for l in conv]
    lines += ["", "## Dropped slivers", ""]
    sl = layout.dropped_slivers
    if sl:
        lines.append(f"{len(sl)} region(s) under {params['general.sliver_area_mm2']} mm2 were dropped, {sum(s['area_mm2'] for s in sl):.1f} mm2 in total:")
        lines += [f"- {s['group']}: {s['area_mm2']} mm2 at ({s['x']}, {s['y']}) mm" for s in sl[:40]]
        if len(sl) > 40:
            lines.append(f"- ... and {len(sl) - 40} more (see params_used.yaml / run log)")
    else:
        lines.append("None.")
    lines += ["", "## Warnings", ""]
    warns = ctx.get("warnings", []) + layout.warnings + [w for ps in ctx["parts"].values() for p in ps for w in p.warnings]
    lines += [f"- {w}" for w in warns] if warns else ["None."]
    lines += ["", "## Density", ""]
    dens = ctx.get("density", {})
    if dens:
        lines.append(f"- Mean {dens['mean_per_mm2']:.1f} and max {dens['max_per_mm2']:.1f} needle penetrations per mm2 (lock stitches excluded); "
                     f"{len(dens['hotspots'])} cell(s) over {dens['threshold']:g} per mm2 flagged in density_map.png")
        for hx, hy, v in dens["hotspots"][:8]:
            lines.append(f"  - hot spot {v:.0f}/mm2 at ({hx:.1f}, {hy:.1f}) mm")
    cov = ctx.get("coverage")
    if cov is not None:
        lines += ["", "## Coverage", "",
                  "Share of each colour's artwork that its stitches cover (thread width " + f"{params['preview.thread_width_mm']} mm):", ""]
        for name, area in cov.region_mm2.items():
            lines.append(f"- {name}: {100 - cov.fraction(name) * 100:.1f}% covered ({cov.uncovered_mm2[name]:.1f} of {area:.0f} mm2 uncovered)")
        if cov.gaps:
            lines += ["", f"Uncovered patches over {params.get('preview.coverage_gap_mm2', 1.0)} mm2 (largest first, see coverage_gaps.png):", ""]
            for g in cov.gaps[:25]:
                lines.append(f"- {g.group}: {g.area_mm2:.1f} mm2, up to {g.width_mm:.1f} mm wide, at ({g.x:.1f}, {g.y:.1f}) mm")
        else:
            lines.append("No uncovered patch over the reporting threshold.")
    fab = params.fabric_info()
    lines += ["", "## Fabric preset and stabilizer", "",
              f"- Preset: **{params.get('fabric')}** ({fab.get('label', '')})",
              f"- Stabilizer: {fab.get('stabilizer', '')}", f"- Needle: {fab.get('needle', '')}",
              f"- Topping: {fab.get('topping', '')}", f"- Hooping: {fab.get('hooping', '')}"]
    if params.applied_overrides:
        lines += ["", "Parameter overrides applied:", ""] + [f"- {o}" for o in params.applied_overrides]
    lines += ["", "## Validation", ""]
    if val is not None:
        lines += [f"- {'PASS' if val.ok else 'FAIL'}"]
        lines += [f"- ok: {c}" for c in val.checks]
        lines += [f"- **ERROR: {e}**" for e in val.errors]
        lines += [f"- warning: {w}" for w in val.warnings]
    lines += ["", "## Files", ""] + [f"- `{f}`" for f in ctx.get("files", [])]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
