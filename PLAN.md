# Plan: open-source vector-to-embroidery digitizer for the Poolin EOC06

## What gets built

A Python 3 command-line tool, `digitize`, that turns a flat-colour vector file
into a machine-ready Tajima DST plus previews, a thread sheet, a stitching
procedure and a quality report. Everything is open source: Ink/Stitch (GPL),
pyembroidery, shapely, scikit-image, Pillow, reportlab, Inkscape (headless,
only for AI/EPS/PDF conversion).

```
digitize INPUT --size-mm 120 --hoop 280x200 --fabric woven --out out/
```

## Pipeline

1. **Input**: AI/EPS/PDF are converted to plain SVG with headless Inkscape.
   The SVG is parsed with svgelements: transforms flattened, hidden and
   zero-opacity elements dropped, clip paths resolved by intersection, strokes
   turned into outlines (their centreline is kept as a running-stitch
   candidate), fill rules (nonzero/evenodd) honoured by polygonising every
   subpath and keeping faces by winding number.
2. **Colour grouping**: every fill/stroke colour goes to CIELAB; CIEDE2000
   clustering merges shades under the threshold (default dE 8), `--colors N`
   merges the closest pairs down to N but refuses any merge over dE 25 and
   stops to ask. `groups.yaml` or `--group` entries override; colours can be
   `skip`. Background (full-canvas shape or `--fabric-color`) is skipped unless
   `--stitch-background`. Each group gets an area-weighted colour and the
   nearest thread from Madeira Polyneon, Isacord and Robison-Anton charts
   (Ink/Stitch GPL palettes). `groups_preview.png` and `groups_suggested.yaml`
   are written; `--review-groups` stops here.
3. **Scale and layering**: scale to `--size-mm` on the longest side, centre on
   the hoop origin, check the hoop in both orientations with 10 mm clearance.
   Same-group shapes are unioned; the drawing order decides which group is
   above which (pairwise overlap areas build a layering DAG). Lower layers are
   knocked out under upper layers minus a 0.4 mm overlap. A group that must be
   both under and over another is reported with its location and a proposed
   merge or knockout.
4. **Shape classification**: each group region is rasterised at 0.05 mm, a
   distance transform and skeleton give the local width everywhere. Parts
   narrower than 1.5 mm become running or bean stitch along the skeleton,
   parts 1.5 to 10 mm with a simple ribbon skeleton become satin branches
   (direction perpendicular to the skeleton), everything else becomes tatami
   fill with an angle at least 30 degrees away from any touching fill. Every
   decision is logged.
5. **Stitch engine**:
   - Path A (preferred): Ink/Stitch run headless from source in an isolated
     Python 3.11 venv; the tool writes a cleaned SVG with `inkstitch:`
     attributes and calls the `output` extension; the DST is checked to be
     non-empty and parseable, otherwise Path B runs.
   - Path B (fallback, pure Python): own tatami fill (stagger, skip-last,
     underlay with inset, edge run, pull compensation, travel through the
     shape), satin (zigzag with width-dependent underlay, split over 7 mm,
     convert over 10 mm), running and bean stitch, lock stitches, jump/trim
     rules, centre-out sequencing, DST/PES/EXP via pyembroidery.
   Both paths produce the same StitchPlan object so previews, procedure,
   report and validation are shared.
6. **Previews**: realistic render with a mm ruler, art overlay at 40%, one PNG
   per colour stop, a self-contained `simulator.html`, and a density heat map.
7. **Outputs**: `design.dst` (plus `.pes`, `.exp`), `thread_sheet.md/.pdf`,
   `procedure.md/.html/.pdf`, `report.md`, `params_used.yaml`.
8. **Validation**: the DST is read back and checked (hoop fit, colour changes =
   groups minus one, 0.3 to 12.1 mm stitch lengths except locks, counts match
   the report, procedure and thread sheet). Any failure aborts loudly.

## Parameters

All defaults, ranges and sources are in `PARAMS.md`; the live values are in
`params.yaml` and can be overridden per run.

## Verification

Unit tests for the generators, grouping, sequencing, procedure and validation;
fixture SVGs (5-colour logo, thin outline, small text, wide shape, messy
12-shade file) run end to end with golden outputs; the real file
(`input/rack.svg`) is run at 120 mm and every preview is inspected.
