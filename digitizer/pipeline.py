"""End-to-end pipeline: input -> groups -> layout -> classify -> stitch -> outputs -> validate."""
from __future__ import annotations

import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pyembroidery as pe

from . import colors as C
from . import preview as P
from .classify import assign_fill_angles, classify_region
from .engine.engine import build_plan, describe_parts, order_parts, watch_items
from .engine_inkstitch import find_inkstitch, plan_from_inkstitch_dst, run_inkstitch, write_inkstitch_svg
from .layering import build_regions, compute_layout
from .outputs import thread_rows, write_params_used, write_report, write_thread_sheet_md, write_thread_sheet_pdf
from .params import Params, load_params
from .procedure import build_procedure, write_procedure_html, write_procedure_md, write_procedure_pdf
from .simulator import write_simulator
from .svg_input import ensure_plain_svg, load_document
from .validate import ValidationError, validate


@dataclass
class RunOptions:
    input: Path
    size_mm: float = 120.0
    hoop: str | None = None
    fabric: str = "woven"
    out: Path = Path("out")
    engine: str = "auto"              # auto | inkstitch | python
    colors: int | None = None
    merge_threshold: float | None = None
    groups_file: Path | None = None
    group_args: list[str] = field(default_factory=list)
    review_groups: bool = False
    fabric_color: str | None = None
    stitch_background: bool = False
    params_file: Path | None = None
    sets: list[str] = field(default_factory=list)
    knockdown: bool = False
    name: str | None = None
    formats: tuple[str, ...] = ("dst", "pes", "exp")
    quiet: bool = False


@dataclass
class RunResult:
    out: Path
    plan: Any = None
    layout: Any = None
    groups: list = field(default_factory=list)
    validation: Any = None
    warnings: list[str] = field(default_factory=list)
    log: list[str] = field(default_factory=list)
    stopped_after_groups: bool = False
    files: list[str] = field(default_factory=list)


def _text_font_sizes(path: Path) -> list[tuple[str, float]]:
    """(text, font-size in user units) for every <text> element of an SVG (before text-to-path)."""
    if path.suffix.lower() != ".svg":
        return []
    import re
    try:
        from lxml import etree
        tree = etree.parse(str(path))
    except Exception:
        return []
    out = []
    for t in tree.iter("{http://www.w3.org/2000/svg}text"):
        size = t.get("font-size")
        style = t.get("style", "") or ""
        m = re.search(r"font-size\s*:\s*([0-9.]+)", style)
        if m:
            size = m.group(1)
        if size is None:
            parent = t.getparent()
            while parent is not None and size is None:
                size = parent.get("font-size")
                parent = parent.getparent()
        try:
            fs = float(re.match(r"[0-9.]+", str(size or "16")).group(0))
        except Exception:
            fs = 16.0
        text = "".join(t.itertext()).strip()
        if text:
            out.append((text, fs))
    return out


def _say(opts: RunOptions, msg: str, log: list[str] | None = None) -> None:
    if log is not None:
        log.append(msg)
    if not opts.quiet:
        print(msg, flush=True)


def run(opts: RunOptions) -> RunResult:
    t0 = time.time()
    out = Path(opts.out)
    out.mkdir(parents=True, exist_ok=True)
    work = out / "work"
    work.mkdir(exist_ok=True)
    params = load_params(opts.params_file, opts.fabric, opts.sets, opts.hoop, opts.knockdown)
    if opts.merge_threshold is not None:
        params.set("colors.merge_threshold_de", float(opts.merge_threshold))
    res = RunResult(out=out)
    log = res.log
    title = opts.name or Path(opts.input).stem

    # ---- 1. input --------------------------------------------------------
    text_sizes = _text_font_sizes(Path(opts.input))
    svg_path, warns = ensure_plain_svg(Path(opts.input), work)
    res.warnings += warns
    for w in warns:
        _say(opts, w, log)
    # curve flattening step in SVG units: about 0.2 mm at the final size
    try:
        from svgelements import SVG
        s = SVG.parse(str(svg_path))
        vb = s.viewbox
        longest = max(vb.width, vb.height) if vb is not None else max(float(s.width or 100), float(s.height or 100))
    except Exception:
        longest = 1000.0
    step = max(1e-3, 0.2 * longest / opts.size_mm)
    doc = load_document(svg_path, step, log)
    res.warnings += doc.warnings
    if not doc.shapes:
        raise ValueError("No shapes with a fill or stroke were found in the artwork.")

    # ---- 2. colour grouping ---------------------------------------------
    areas: dict[str, float] = {}
    for sh in doc.shapes:
        areas[sh.color] = areas.get(sh.color, 0.0) + sh.area
    manual: list[C.ColorGroup] = []
    manual_order = None
    if opts.groups_file:
        manual, manual_order = C.load_groups_yaml(Path(opts.groups_file))
        log.append(f"Loaded {len(manual)} manual group(s) from {opts.groups_file}")
    manual += C.parse_group_args(opts.group_args)
    assigned = {m for g in manual for m in g.members}
    # background detection
    canvas_area = doc.canvas_area()
    biggest = max(doc.shapes, key=lambda s: s.area)
    bg_colors: list[str] = []
    if canvas_area > 0 and biggest.area / canvas_area >= float(params["colors.background_coverage"]):
        bg_colors.append(biggest.color)
        log.append(f"Background detected: shape {biggest.id} ({biggest.color}) covers {biggest.area / canvas_area * 100:.0f}% of the canvas")
    if opts.fabric_color:
        fc = C.normalize_hex(opts.fabric_color)
        for c in areas:
            if C.hex_delta_e(c, fc) < 5 and c not in bg_colors:
                bg_colors.append(c)
                log.append(f"Colour {c} matches the fabric colour {fc} (delta E {C.hex_delta_e(c, fc):.1f}): treated as background")
    bg_colors = [c for c in bg_colors if c not in assigned]
    if bg_colors:
        if opts.stitch_background:
            log.append("--stitch-background given: background colours will be stitched")
        else:
            manual.append(C.ColorGroup(name="background", color=bg_colors[0], members=bg_colors, skip=True, manual=True, is_background=True))
            _say(opts, f"Skipping background colour(s) {', '.join(bg_colors)} (use --stitch-background to stitch them)", log)
    unknown = [m for g in manual for m in g.members if m not in areas]
    if unknown:
        res.warnings.append(f"groups mention colours not in the artwork: {', '.join(unknown)}")
    grouping_log: list[str] = []
    try:
        groups = C.auto_group(areas, float(params["colors.merge_threshold_de"]), opts.colors,
                              float(params["colors.refuse_merge_de"]), manual, grouping_log)
    except C.GroupingDecisionNeeded as exc:
        # write what we have so the user can decide
        m2g = {m: g.name for g in exc.groups for m in g.members}
        P.render_groups_preview(doc, exc.groups, m2g, areas, out / "groups_preview.png")
        (out / "groups_suggested.yaml").write_text(C.groups_to_yaml(exc.groups, [g.name for g in exc.groups], areas), encoding="utf-8")
        raise SystemExit(f"STOP: {exc}\nSee {out / 'groups_preview.png'} and edit {out / 'groups_suggested.yaml'}, "
                         f"then re-run with --groups {out / 'groups_suggested.yaml'}") from exc
    log += grouping_log
    for g in groups:
        g.area = sum(areas.get(m, 0.0) for m in g.members)
    # thread matching (area in mm2 is filled in after layout)
    palettes = C.load_palettes(params["colors.palettes"])
    for g in groups:
        if g.skip:
            continue
        opts_ = C.nearest_threads(g.color, palettes)
        g.thread_options = opts_
        if g.thread and (g.thread.get("code") or g.thread.get("name")):
            g.thread = {"brand": g.thread.get("brand", "your thread"), "code": g.thread.get("code", ""),
                        "name": g.thread.get("name", ""), "delta_e": "", "hex": g.color}
        elif opts_:
            g.thread = dict(opts_[0])
    member_to_group = {m: g.name for g in groups for m in g.members}
    res.groups = groups
    _say(opts, "Colour groups: " + "; ".join(f"{g.name} {g.color} <- {','.join(g.members)}" + (" (skip)" if g.skip else "") for g in groups), log)

    # ---- 3. layout ---------------------------------------------------------
    stitched_shapes = [s for s in doc.shapes if not next(g for g in groups if g.name == member_to_group[s.color]).skip]
    if not stitched_shapes:
        raise ValueError("Every colour is skipped; nothing to stitch.")
    layout = compute_layout(doc, stitched_shapes, opts.size_mm, params, opts.hoop)
    min_text = float(params["detail.min_text_height_mm"])
    for text, size in text_sizes:
        cap_mm = size * 0.72 * layout.scale       # cap height is about 0.72 em
        if cap_mm < min_text:
            res.warnings.append(f"Text '{text[:30]}' is about {cap_mm:.1f} mm high at this size, below the {min_text:g} mm minimum "
                                f"for satin lettering: scale the design up (at least --size-mm {opts.size_mm * min_text / max(cap_mm, 0.01):.0f}) "
                                "or make the text bigger in the artwork.")
    layout = build_regions(doc, groups, member_to_group, layout, params, manual_order)
    for g in groups:
        g.area = sum(areas.get(m, 0.0) for m in g.members) * layout.scale ** 2
    log += layout.log
    res.warnings += layout.warnings
    for m in layout.log:
        _say(opts, m)
    res.layout = layout
    order = [r.name for r in layout.regions]
    P.render_groups_preview(doc, groups, member_to_group, areas, out / "groups_preview.png", order)
    (out / "groups_suggested.yaml").write_text(C.groups_to_yaml(groups, order, {m: areas.get(m, 0) * layout.scale ** 2 for m in areas}), encoding="utf-8")
    res.files += ["groups_preview.png", "groups_suggested.yaml"]
    if opts.review_groups:
        res.stopped_after_groups = True
        _say(opts, f"Stopped after grouping (--review-groups). Review {out / 'groups_preview.png'}, edit {out / 'groups_suggested.yaml'} "
                   f"and re-run with --groups {out / 'groups_suggested.yaml'}")
        return res

    # ---- 4. classification --------------------------------------------------
    parts_by_group: dict[str, list] = {}
    for region in layout.regions:
        parts_by_group[region.name] = classify_region(region, params, log)
    all_parts = [p for ps in parts_by_group.values() for p in ps]
    assign_fill_angles(all_parts, params, log)
    for region in layout.regions:
        ps = parts_by_group[region.name]
        kinds: dict[str, int] = {}
        for p in ps:
            kinds[p.kind] = kinds.get(p.kind, 0) + 1
        _say(opts, f"{region.name}: " + ", ".join(f"{v} {k}" for k, v in kinds.items()))
    for p in all_parts:
        res.warnings += p.warnings

    # ---- 5. stitch engine -------------------------------------------------
    plan = None
    engine_note = ""
    if opts.engine in ("auto", "inkstitch"):
        if find_inkstitch() is None:
            msg = "Ink/Stitch (Path A) is not installed; using the pure-Python engine (Path B)."
            if opts.engine == "inkstitch":
                raise SystemExit("--engine inkstitch requested but Ink/Stitch was not found (set INKSTITCH_DIR/INKSTITCH_PYTHON "
                                 "or run scripts/install_inkstitch.sh)")
            _say(opts, msg, log)
        else:
            svg_in = work / "inkstitch_input.svg"
            write_inkstitch_svg(layout, parts_by_group, params, svg_in, order_parts)
            dst_a = work / "inkstitch_output.dst"
            _say(opts, "Running Ink/Stitch headless (Path A)...")
            ok = run_inkstitch(svg_in, dst_a, log)
            if ok:
                plan = plan_from_inkstitch_dst(dst_a, layout, layout.regions, float(params["general.min_stitch_length_mm"]))
                if plan is None:
                    log.append("Ink/Stitch output has a different number of colour blocks than expected; falling back to Path B")
                    ok = False
            if ok and plan is not None:
                engine_note = "Ink/Stitch run headless from source"
                for region, block in zip(layout.regions, plan.blocks):
                    ps = order_parts(parts_by_group[region.name], None)
                    block.descriptions = describe_parts(ps, layout.width_mm, layout.height_mm)
                    block.watch = watch_items(ps, None)
            elif opts.engine == "inkstitch":
                raise SystemExit("Ink/Stitch failed: " + " | ".join(log[-3:]))
            else:
                _say(opts, "Ink/Stitch failed; using the pure-Python engine (Path B). Reason: " + log[-1], log)
                plan = None
    if plan is None:
        _say(opts, "Stitching with the pure-Python engine (Path B)...")
        plan = build_plan(layout, parts_by_group, params, log)
        engine_note = "pure-Python generators (tatami, satin, running), pyembroidery writer"
    plan.meta.update({"title": title, "size_mm": opts.size_mm})
    res.plan = plan

    # ---- 6. embroidery files --------------------------------------------
    pattern = plan.to_pattern()
    files = []
    for fmt in opts.formats:
        p = out / f"design.{fmt}"
        pe.write(pattern, str(p))
        files.append(p.name)
    res.files += files
    _say(opts, f"Wrote {', '.join(files)}: {plan.stitch_count()} stitches, {len(plan.blocks)} colours, "
               f"{plan.jump_count()} jumps, {plan.trim_count()} trims")

    # ---- 7. previews --------------------------------------------------------
    _say(opts, "Rendering previews...")
    P.render_realistic(plan, params, out / "preview_realistic.png")
    art = P.render_art(svg_path, layout, plan, params)
    if art is not None:
        P.render_realistic(plan, params, out / "preview_vs_art.png", art=art)
    else:
        res.warnings.append("preview_vs_art.png not written (cairosvg could not render the SVG)")
    per = out / "preview_per_color"
    if per.exists():
        shutil.rmtree(per)
    for i, b in enumerate(plan.blocks):
        P.render_realistic(plan, params, per / f"{i + 1:02d}_{b.group.replace(' ', '_')}.png", only_block=i, dim_others=True,
                           ppm=float(params["preview.render_dpi"]) / 25.4 * 0.6, jumps=True)
    density = P.render_density(plan, params, out / "density_map.png")
    write_simulator(plan, out / "simulator.html", title)
    thumbs = []
    for i, b in enumerate(plan.blocks):
        rel = f"procedure_thumbs/stop_{i + 1:02d}.png"
        P.thumbnail_for_block(plan, params, i, out / rel)
        thumbs.append(rel)
    res.files += ["preview_realistic.png", "preview_vs_art.png", "preview_per_color/", "density_map.png", "simulator.html"]

    # ---- 8. documents -----------------------------------------------------
    rows = thread_rows(plan, params)
    write_thread_sheet_md(rows, plan, params, out / "thread_sheet.md", title)
    write_thread_sheet_pdf(rows, plan, params, out / "thread_sheet.pdf", title)
    sections = build_procedure(plan, layout, params, rows, title, thumbs, density, opts.fabric_color)
    write_procedure_md(sections, out / "procedure.md", title)
    write_procedure_html(sections, out / "procedure.html", title)
    write_procedure_pdf(sections, out / "procedure.pdf", title, out)
    write_params_used(params, out / "params_used.yaml",
                      {"input": str(opts.input), "size_mm": opts.size_mm, "hoop": layout.hoop_name, "fabric": opts.fabric,
                       "engine": plan.engine, "colors": opts.colors, "groups_file": str(opts.groups_file) if opts.groups_file else None,
                       "group_args": opts.group_args, "fabric_color": opts.fabric_color, "stitch_background": opts.stitch_background})
    res.files += ["thread_sheet.md", "thread_sheet.pdf", "procedure.md", "procedure.html", "procedure.pdf", "params_used.yaml", "report.md"]

    # ---- 9. validation ---------------------------------------------------
    run_sheet_counts = [b.stitch_count() for b in plan.blocks]   # the procedure prints block.stitch_count() directly
    val = validate(plan, out / "design.dst", layout, params, [r["stitches"] for r in rows], run_sheet_counts, plan.stitch_count())
    res.validation = val
    ctx = {"plan": plan, "layout": layout, "params": params, "groups": groups, "parts": parts_by_group, "log": log,
           "warnings": res.warnings, "density": density, "title": title, "input": str(opts.input), "size_mm": opts.size_mm,
           "engine_note": engine_note, "validation": val, "files": res.files, "grouping_log": grouping_log}
    write_report(out / "report.md", ctx)
    (out / "run.log").write_text("\n".join(log), encoding="utf-8")
    _say(opts, f"Done in {time.time() - t0:.0f} s. Outputs in {out}/ (report.md, procedure.html, preview_realistic.png, design.dst)")
    if not val.ok:
        raise ValidationError("VALIDATION FAILED:\n- " + "\n- ".join(val.errors) + f"\nSee {out / 'report.md'}")
    for c in val.checks:
        _say(opts, "  ok: " + c)
    return res
