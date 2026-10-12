"""Step-by-step stitching procedure (md, html with checkboxes, pdf) generated from the stitch plan."""
from __future__ import annotations

import html
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .params import Params
from .stitchplan import StitchPlan


@dataclass
class Step:
    text: str
    sub: list[str] = field(default_factory=list)
    image: str | None = None       # relative path to a thumbnail
    swatch: str | None = None      # hex colour to show


@dataclass
class Section:
    title: str
    intro: str = ""
    steps: list[Step] = field(default_factory=list)
    table: list[list[str]] | None = None


def _fmt_min(m: float) -> str:
    if m < 1:
        return f"{m * 60:.0f} s"
    return f"{m:.0f} min" if m >= 10 else f"{m:.1f} min"


def build_procedure(plan: StitchPlan, layout, params: Params, rows: list[dict], title: str, thumbs: list[str],
                    density: dict | None, fabric_color: str | None) -> list[Section]:
    spm = float(params["machine.estimate_speed_spm"])
    change = float(params["machine.thread_change_minutes"])
    fab = params.fabric_info()
    w, h = plan.size()
    n = len(plan.blocks)
    total_min = plan.sew_minutes(spm, change)
    sections: list[Section] = []

    # 1. before you start
    s1 = Section("1. Before you start")
    s1.steps.append(Step(f"Design: {title}. Final size {w:.1f} x {h:.1f} mm ({w / 25.4:.2f} x {h / 25.4:.2f} in)."))
    s1.steps.append(Step(f"Hoop: use the {layout.hoop_name} hoop ({layout.hoop_w:.0f} x {layout.hoop_h:.0f} mm), mounted {layout.orientation}. "
                         f"The design leaves {layout.margin_mm:.0f} mm to the nearest hoop edge (minimum {layout.clearance_mm:.0f} mm)."))
    s1.steps.append(Step(f"Totals: {plan.stitch_count()} stitches, {n} thread colours, {n - 1} thread changes. "
                         f"Estimated time about {total_min:.0f} min ({plan.stitch_count() / spm:.0f} min sewing at {spm:.0f} spm "
                         f"plus about {change:.0f} min per thread change)."))
    shop = Step("Shopping and prep list:")
    for r in rows:
        thread = f'{r["brand"]} {r["code"]} {r["name"]}'.strip() or "no chart match"
        shop.sub.append(f'Thread {r["stop"]}: {r["group"]} ({r["color"]}), suggested {thread}.')
    dark = False
    if fabric_color:
        try:
            from .colors import hex_to_lab
            dark = hex_to_lab(fabric_color)[0] < 45
        except Exception:
            dark = False
    shop.sub.append(f"Bobbin thread: 60 wt pre-wound, {'black' if dark else 'white'} ({'dark' if dark else 'light'} fabric; the back of the embroidery shows the bobbin colour).")
    shop.sub.append(f"Needle: {fab.get('needle', '75/11 embroidery needle')} Start every project with a fresh needle.")
    shop.sub.append(f"Stabilizer: {fab.get('stabilizer', '')}")
    if fab.get("topping") and not fab["topping"].lower().startswith("none"):
        shop.sub.append(f"Topping: {fab['topping']}")
    shop.sub.append("Temporary spray adhesive (505 or similar) if the garment cannot be hooped and must be floated.")
    shop.sub.append("Small curved embroidery scissors for jump threads, a seam ripper, and a lint brush.")
    s1.steps.append(shop)
    s1.steps.append(Step("File transfer: copy design.dst to a USB stick (FAT32) in a folder you will recognise, or send it with the Poolin Wi-Fi app (InStitch). "
                         f"Name it clearly, for example {title.replace(' ', '_')}_{w:.0f}mm.dst, so it is easy to find on the touchscreen."))
    sections.append(s1)

    # 2. hooping
    s2 = Section("2. Hooping")
    s2.steps.append(Step("Decide where the design goes on the garment and mark its centre with a water-soluble pen or a pin. "
                         "The design is centred on the hoop origin, so this mark is where the needle starts."))
    s2.steps.append(Step(f"Orientation: the design is {w:.0f} mm wide and {h:.0f} mm tall; the top of the design (negative y in the previews) "
                         f"is the top of the artwork. Mount the hoop {layout.orientation} and check on screen that the design is upright "
                         "relative to the garment before stitching."))
    s2.steps.append(Step(f"Stabilizer: {fab.get('stabilizer', '')} {fab.get('hooping', '')}"))
    if fab.get("topping") and not fab["topping"].lower().startswith("none"):
        s2.steps.append(Step(f"Topping: {fab['topping']}"))
    s2.steps.append(Step("Hoop the fabric with the stabilizer underneath: loosen the outer ring, lay the stabilizer then the fabric over the inner ring, "
                         "press the outer ring down, then tighten. The fabric should be drum-tight but not stretched "
                         + ("(do not pull a knit: it springs back and puckers)." if params.get("fabric") in ("knit", "pique", "fleece") else "(pull gently on wovens only).")))
    s2.steps.append(Step("Line up the hoop's centre marks with your centre mark. Attach the hoop to the machine."))
    s2.steps.append(Step("Load design.dst on the machine, check its position on screen, and run the trace/outline function so the foot "
                         "travels around the design area: confirm it clears the hoop edge and lands where you want it. Adjust and trace again if needed."))
    s2.steps.append(Step(f"Set the speed no higher than about {spm:.0f} spm for the first run; slow down for small details."))
    sections.append(s2)

    # 3. run sheet
    s3 = Section("3. Thread-by-thread run sheet", "One block per colour stop, in sewing order. The machine stops and trims at the end of each colour.")
    seen: dict[str, int] = {}
    for i, (b, r) in enumerate(zip(plan.blocks, rows), start=1):
        thread = f'{r["brand"]} {r["code"]} {r["name"]}'.strip() or "nearest thread you have"
        st = Step(f"Stop {i} of {n}: load {b.group} ({b.color}), {thread}.", swatch=b.color,
                  image=thumbs[i - 1] if i - 1 < len(thumbs) else None)
        if b.group in seen:
            st.sub.append(f"ATTENTION: this colour was already used at stop {seen[b.group]} and comes back here by design. "
                          "Load the same thread again.")
        seen[b.group] = i
        if i == 1:
            st.sub.append("Thread the needle with this colour before pressing start. Hold the thread tail for the first few stitches.")
        st.sub.append("This colour stitches: " + ("; ".join(b.descriptions) if b.descriptions else "see thumbnail") + ".")
        st.sub.append(f"{b.stitch_count()} stitches, about {_fmt_min(b.stitch_count() / spm)}.")
        for wtxt in b.watch:
            st.sub.append("Watch: " + wtxt)
        jumps = [j for j in b.jumps() if j[2] > float(params["machine.trim_jump_threshold_mm"])]
        if jumps:
            st.sub.append(f"At the stop: the machine trims the colour automatically; this colour also has {len(jumps)} jump(s) inside it "
                          "that the machine does NOT trim. Cut the floating threads on top close to the fabric before continuing.")
        else:
            st.sub.append("At the stop: the machine trims automatically. No jump threads to trim in this colour.")
        if i > 1:
            st.sub.append("Check registration: the new colour should meet the previous ones without gaps; if it is shifted, re-tension the hoop before going on.")
        if i < n:
            st.sub.append(f"Thread change to stop {i + 1} ({plan.blocks[i].group}): cut the thread near the spool, pull the old thread out "
                          "forward through the needle (never back up through the tension discs), put on the new spool, thread the path, "
                          "use the automatic needle threader, and hold the tail for the first stitches.")
        s3.steps.append(st)
    sections.append(s3)

    # 4. finishing
    s4 = Section("4. Finishing")
    s4.steps.append(Step("Remove the hoop from the machine and take the fabric out of the hoop. Do not pull the fabric; loosen the ring first."))
    kind = (fab.get("stabilizer", "") or "").lower()
    if "cut-away" in kind:
        s4.steps.append(Step("Cut-away stabilizer: trim it with curved scissors leaving 3 to 5 mm around the design. Do not cut the fabric."))
    else:
        s4.steps.append(Step("Tear-away stabilizer: support the stitches with one hand and tear the stabilizer away gently, in small pieces, "
                             "so the stitches are not distorted. Trim what remains close to the design."))
    if fab.get("topping") and not fab["topping"].lower().startswith("none"):
        s4.steps.append(Step("Water-soluble topping: tear off the excess, then dab the rest away with a damp cloth or rinse in cool water."))
    s4.steps.append(Step("Trim remaining jump threads close on both the front and the back."))
    s4.steps.append(Step("Press from the back on a thick towel with a pressing cloth; never press the front directly (it flattens the thread)."))
    sections.append(s4)

    # 5. troubleshooting
    s5 = Section("5. Troubleshooting")
    s5.table = [["Symptom", "Likely cause", "Fix", "params.yaml setting"],
                ["Puckering around fills", "Not enough stabilizer, fabric hooped loose, or stitching too dense",
                 "Add a stabilizer layer, re-hoop drum-tight, reduce density", "fill.row_spacing_mm (raise to 0.45), fill.underlay.*"],
                ["Gaps between colours", "Pull compensation too low for this fabric",
                 "Increase overlap and pull compensation, test again", "general.overlap_mm (0.5), fill.pull_compensation_mm, satin.pull_compensation_mm"],
                ["Outline does not line up with the fill", "Fabric shifted in the hoop, or fills pulled in",
                 "Re-hoop with cut-away, more underlay, more compensation", "fill.pull_compensation_mm, fill.underlay.edge_run_always"],
                ["Bird-nesting under the fabric", "Top thread not seated in the tension discs or take-up lever; thread caught on the spool",
                 "Rethread the top from the start, check the spool unwinds freely", "(not a digitizing problem)"],
                ["Thread breaks or shredding", "Dull or wrong needle, burr on the plate, too dense or too short stitches",
                 "New needle, slow the machine, open the density", "satin.spacing_mm, fill.row_spacing_mm, general.min_stitch_length_mm"],
                ["Bobbin thread showing on top", "Top tension too tight or bobbin too loose", "Lower top tension one step; check the bobbin case", "satin.spacing_mm (if only on satins)"],
                ["Satin text unreadable", "Letters too small for the thread", "Scale the design up or simplify the text",
                 "detail.min_text_height_mm, satin.min_width_mm, --size-mm"],
                ["Underlay shows at the edges", "Underlay inset too small for this fabric", "Increase the underlay insets",
                 "fill.underlay.inset_mm, satin.underlay.contour_inset_mm"],
                ["Design off-centre on the garment", "Centre mark or hoop alignment off", "Re-mark, re-hoop, use trace before stitching", "(machine positioning)"],
                ["Jump threads left on top", "Single-needle machine does not trim inside a colour", "Trim by hand at each stop",
                 "sequence.max_travel_mm, sequence.travel_under_cover"]]
    sections.append(s5)

    # 6. test stitch checklist
    s6 = Section("6. Test-stitch checklist", "Stitch the design first on a scrap of the same fabric with the same stabilizer, then tick off:")
    for t in ["Edges are sharp and even", "No gaps between colours", "No underlay showing outside the top stitching", "No puckering around the fills",
              "Text and fine lines are readable", "Colours look as expected next to the garment",
              "Outline sits on the fill edges (registration)"]:
        s6.steps.append(Step(t))
    s6.steps.append(Step("If anything fails, change the setting named in the troubleshooting table in params.yaml and re-export."))
    sections.append(s6)
    return sections


def write_procedure_md(sections: list[Section], path: Path, title: str) -> Path:
    lines = [f"# Stitching procedure: {title}", ""]
    for sec in sections:
        lines += [f"## {sec.title}", ""]
        if sec.intro:
            lines += [sec.intro, ""]
        if sec.table:
            lines.append("| " + " | ".join(sec.table[0]) + " |")
            lines.append("|" + "---|" * len(sec.table[0]))
            for row in sec.table[1:]:
                lines.append("| " + " | ".join(row) + " |")
            lines.append("")
        for i, st in enumerate(sec.steps, start=1):
            sw = f" <span style=\"display:inline-block;width:1.2em;height:1em;background:{st.swatch};border:1px solid #444\"></span>" if st.swatch else ""
            lines.append(f"{i}. [ ] {st.text}{sw}")
            for sub in st.sub:
                lines.append(f"    - {sub}")
            if st.image:
                lines.append(f"")
                lines.append(f"    ![stop]({st.image})")
            lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def write_procedure_html(sections: list[Section], path: Path, title: str) -> Path:
    css = """
    body{font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;max-width:760px;margin:0 auto;padding:16px;font-size:17px;line-height:1.45;color:#222}
    h1{font-size:24px} h2{font-size:20px;margin-top:28px;border-bottom:2px solid #ddd;padding-bottom:4px}
    ol{padding-left:0;list-style:none} li.step{margin:10px 0;padding:10px;border:1px solid #ddd;border-radius:8px;background:#fafafa}
    li.step label{display:flex;gap:10px;align-items:flex-start;font-weight:600}
    input[type=checkbox]{width:24px;height:24px;flex:none;margin-top:2px}
    li.step:has(input:checked){background:#e8f5e9;opacity:.75}
    ul.sub{margin:6px 0 0 34px;padding:0;font-weight:400} ul.sub li{margin:4px 0}
    .sw{display:inline-block;width:22px;height:22px;border:1px solid #444;border-radius:4px;vertical-align:middle}
    img.thumb{max-width:100%;border:1px solid #ccc;border-radius:6px;margin:8px 0 0 34px}
    table{border-collapse:collapse;font-size:14px} td,th{border:1px solid #ccc;padding:6px;vertical-align:top} th{background:#eee}
    @media print{li.step{break-inside:avoid} input[type=checkbox]{-webkit-appearance:checkbox}}
    """
    out = [f"<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'>",
           f"<title>Stitching procedure: {html.escape(title)}</title><style>{css}</style></head><body>",
           f"<h1>Stitching procedure: {html.escape(title)}</h1>",
           "<p>Tick each step as you go. Works offline; print it or prop a phone next to the machine.</p>"]
    k = 0
    for sec in sections:
        out.append(f"<h2>{html.escape(sec.title)}</h2>")
        if sec.intro:
            out.append(f"<p>{html.escape(sec.intro)}</p>")
        if sec.table:
            out.append("<table><tr>" + "".join(f"<th>{html.escape(c)}</th>" for c in sec.table[0]) + "</tr>")
            for row in sec.table[1:]:
                out.append("<tr>" + "".join(f"<td>{html.escape(c)}</td>" for c in row) + "</tr>")
            out.append("</table>")
        if sec.steps:
            out.append("<ol>")
            for st in sec.steps:
                k += 1
                sw = f" <span class='sw' style='background:{st.swatch}'></span>" if st.swatch else ""
                out.append(f"<li class='step'><label><input type='checkbox' id='s{k}'><span>{html.escape(st.text)}{sw}</span></label>")
                if st.sub:
                    out.append("<ul class='sub'>" + "".join(f"<li>{html.escape(s)}</li>" for s in st.sub) + "</ul>")
                if st.image:
                    out.append(f"<img class='thumb' src='{html.escape(st.image)}' alt='stitches of this stop highlighted'>")
                out.append("</li>")
            out.append("</ol>")
    out.append("</body></html>")
    path.write_text("\n".join(out), encoding="utf-8")
    return path


def write_procedure_pdf(sections: list[Section], path: Path, title: str, base_dir: Path) -> Path:
    from reportlab.lib import colors as rl
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    styles = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=styles["Normal"], fontSize=10.5, leading=14)
    sub = ParagraphStyle("sub", parent=body, leftIndent=18, fontSize=9.5, leading=12.5)
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=14 * mm, rightMargin=14 * mm, topMargin=14 * mm, bottomMargin=14 * mm)
    story = [Paragraph(f"Stitching procedure: {html.escape(title)}", styles["Title"])]
    for sec in sections:
        story.append(Paragraph(html.escape(sec.title), styles["Heading2"]))
        if sec.intro:
            story.append(Paragraph(html.escape(sec.intro), body))
        if sec.table:
            data = [[Paragraph(html.escape(c), sub) for c in row] for row in sec.table]
            t = Table(data, colWidths=[36 * mm, 48 * mm, 50 * mm, 48 * mm], repeatRows=1)
            t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, rl.grey), ("BACKGROUND", (0, 0), (-1, 0), rl.HexColor("#eeeeee")),
                                   ("VALIGN", (0, 0), (-1, -1), "TOP")]))
            story.append(t)
        for i, st in enumerate(sec.steps, start=1):
            block = []
            sw = ""
            if st.swatch:
                sw = f' <font color="{st.swatch}">&#9632;</font>'
            block.append(Paragraph(f"&#9744; {i}. {html.escape(st.text)}{sw}", body))
            for s in st.sub:
                block.append(Paragraph("&bull; " + html.escape(s), sub))
            if st.image and (base_dir / st.image).exists():
                img = Image(str(base_dir / st.image))
                ratio = img.imageHeight / float(img.imageWidth)
                img.drawWidth = 70 * mm
                img.drawHeight = 70 * mm * ratio
                img.hAlign = "LEFT"
                block.append(img)
            block.append(Spacer(1, 3 * mm))
            story.append(KeepTogether(block))
    doc.build(story)
    return path
