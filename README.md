# Vector-to-embroidery digitizer for the Poolin EOC06

`digitize` turns a flat-colour vector file (SVG, AI, EPS or PDF) into a
machine-ready **Tajima DST** for the Poolin EOC06 (plus PES and EXP spares),
with stitch previews, a sewing-order simulator, a thread sheet, a step-by-step
stitching procedure and a quality report. Everything is open source.

```
digitize INPUT.svg --size-mm 120 --hoop 280x200 --fabric woven --out out/
```

What you get in `out/`:

| File | What it is |
|---|---|
| `design.dst` (`.pes`, `.exp`) | the stitch file, centred on the hoop origin |
| `preview_realistic.png` | every stitch drawn as thread, true scale, mm ruler |
| `preview_vs_art.png` | the artwork at 40% under the stitches (coverage, gaps, edge creep) |
| `preview_per_color/` | one PNG per colour stop, in sewing order, jumps dashed |
| `simulator.html` | offline sewing-order animation: play/pause, speed, scrub, stop and stitch counter |
| `density_map.png` | needle penetrations per mm2, hot spots outlined |
| `coverage_gaps.png` | artwork of each colour that its stitches do not cover (magenta), with the biggest gaps circled |
| `thread_sheet.md` / `.pdf` | stop number, swatch, hex, group, suggested thread, stitches, minutes |
| `procedure.md` / `.html` / `.pdf` | the stitching procedure (setup, hooping, run sheet, finishing, troubleshooting, test checklist); the HTML has a checkbox per step |
| `report.md` | size, hoop fit, counts, times, stitch-length limits, conversions, dropped slivers, warnings, validation |
| `groups_preview.png`, `groups_suggested.yaml` | colour grouping to review and edit |
| `params_used.yaml` | the exact parameters of the run |

## Install

Tested on Ubuntu 24.04 (this repository was built on Linux). macOS and Windows
work the same way with Python 3.11+; Inkscape is only needed for AI/EPS/PDF
input and for text-to-path conversion.

```bash
# Linux (Debian/Ubuntu). Inkscape is optional but recommended.
sudo apt install python3 python3-venv inkscape fonts-dejavu-core
python3 -m venv .venv && . .venv/bin/activate
pip install -e .                 # installs the `digitize` command and dependencies
digitize --help
```

macOS: `brew install python inkscape` then the same `python3 -m venv` steps.
Windows: install Python 3.11+ from python.org and Inkscape from inkscape.org,
then in PowerShell: `py -m venv .venv; .venv\Scripts\activate; pip install -e .`

### Optional: Ink/Stitch engine (Path A)

The tool has two stitch engines that share the same pre-processing, colour
grouping, sequencing rules, previews and validation:

- **Path B (always available)**: pure-Python tatami, satin and running-stitch
  generators written to DST with pyembroidery.
- **Path A**: Ink/Stitch's engine run headless from source (no Inkscape GUI)
  in its own Python 3.11 venv. Install it with:

```bash
./scripts/install_inkstitch.sh          # clones Ink/Stitch, builds .venv-inkstitch, stubs wxPython
```

`digitize` finds it automatically (or set `INKSTITCH_DIR` and
`INKSTITCH_PYTHON`). `--engine auto` (default) uses Path A when installed and
falls back to Path B; `--engine python` or `--engine inkstitch` forces one.

Which engine is better? On the sample design (`input/rack.svg`, 120 mm) Path B
gave 22,652 stitches with 337 in-colour jumps; Path A gave 27,064 stitches with
803 jumps, because Ink/Stitch stitches each satin branch as a separate column
and jumps between them, while Path B walks satin trees out along the
centreline and satins back, hiding the travel. On a single-needle machine every
jump is a thread to trim by hand, so for designs with many small parts
`--engine python` is usually the better choice. Both outputs pass the same
validation; compare `report.md` of each.

## Run

```bash
digitize input/rack.svg --size-mm 120 --out out/            # defaults: hoop 280x200, woven
digitize logo.ai --size-mm 90 --hoop 140x140 --fabric knit --out out_logo/
digitize art.svg --size-mm 120 --review-groups --out out/    # stop after colour grouping
digitize art.svg --size-mm 120 --groups out/groups_suggested.yaml --out out/
digitize art.svg --size-mm 120 --colors 5 --merge-threshold 10 --out out/
digitize art.svg --size-mm 120 --group "#1a3c6e,#1b3d70=navy" --group "#fcfcfb=skip" --out out/
digitize towel.svg --size-mm 100 --fabric terry --knockdown --fabric-color "#ffffff" --out out/
```

Colour grouping: colours closer than delta E 8 (CIEDE2000) share a thread;
`--colors N` merges the closest pairs down to N but refuses to merge colours
further apart than delta E 25 and stops so you can decide. A shape that covers
the whole canvas, or any colour matching `--fabric-color`, is treated as
background and skipped unless `--stitch-background`. Edit
`out/groups_suggested.yaml` (members, names, `skip`, `thread`, `order`) and pass
it back with `--groups`.

Exit codes: 0 success, 1 input error, 2 validation failed (the files are still
written and `report.md` names the failure).

## Change parameters

All digitizing values live in `params.yaml` and are documented in `PARAMS.md`
(default, allowed range, reason, source). Three ways to change them:

1. Edit `params.yaml` (the defaults).
2. Pass a YAML with only the keys you want: `--params my.yaml`.
3. One-off: `--set fill.row_spacing_mm=0.45 --set satin.pull_compensation_mm=0.3`.

Every run writes `params_used.yaml`, which you can pass back with `--params` to
reproduce or tweak the run. Fabric presets (`--fabric woven|knit|pique|terry|fleece`)
are override sets in the same file; they also drive the stabilizer, needle and
topping advice in the report and procedure.

## Load the DST on the Poolin EOC06

1. **USB**: copy `out/design.dst` to a FAT32 USB stick (a short, clear name
   such as `rack_120mm.dst` is easiest to find on the touchscreen). Plug the
   stick into the machine, open the USB folder on screen and select the file.
2. **Wi-Fi**: send `design.dst` with the Poolin app (InStitch) to the machine.
3. DST has no thread colours: the screen shows placeholder colours. Load the
   threads in the order of `thread_sheet.pdf` (one stop per colour; the machine
   stops and trims at each change; you re-thread by hand).
4. Use the machine's trace function before the first stitch to check the design
   clears the hoop and lands where you want it.

## Test-stitch checklist

Stitch the design first on a scrap of the same fabric with the same stabilizer.
Then check:

- [ ] registration between colours: outlines sit on the fill edges, no gaps
- [ ] no puckering around the fills; edges sharp
- [ ] no underlay showing outside the top stitching
- [ ] no thread breaks on the narrow satins; text readable
- [ ] colours as expected next to the garment

If something is off, change the setting the troubleshooting table in
`procedure.md` names (typically `fill.pull_compensation_mm`,
`satin.pull_compensation_mm`, `general.overlap_mm` or `fill.row_spacing_mm` in
`params.yaml`), re-export and test again.

## How it works

1. **Input**: AI/EPS/PDF to plain SVG with headless Inkscape; text to paths.
   svgelements parses the SVG; transforms are flattened, hidden elements
   dropped, clip paths intersected, strokes outlined (keeping their centreline),
   fill rules honoured by polygonising every subpath.
2. **Colour grouping** (CIELAB, CIEDE2000), thread matching against the
   Madeira Polyneon, Isacord and Robison-Anton charts shipped with Ink/Stitch.
3. **Layout**: scale to `--size-mm`, centre on the hoop origin, check both hoop
   orientations with 10 mm clearance. Same-group shapes are unioned; the
   drawing order decides layering; lower colours are knocked out under upper
   ones minus a 0.4 mm overlap, per shape, so no colour is stitched twice and
   every colour is one block. Outline-like groups are stitched last.
4. **Classification** by local width (0.05 mm raster, distance transform,
   skeleton): under 1.5 mm becomes running or bean stitch along the skeleton,
   clean ribbons up to 7 mm become satin, compact blobs up to 10 mm become
   satin-style fills, everything else tatami fill with angles at least 30
   degrees apart between touching fills. Decisions are logged in `report.md`.
5. **Stitching** (either engine): underlay, pull compensation, lock stitches,
   travel hidden under later stitching, jumps only when needed, trims only for
   long jumps, 0.3 to 12.1 mm stitch lengths.
6. **Validation**: the DST is read back and checked against the plan, thread
   sheet and procedure; any mismatch fails the run loudly.

## Tests

```bash
pip install -e ".[test]"
pytest -q                      # unit tests + fixture SVGs end to end (golden summaries in tests/golden/)
python tests/update_golden.py  # after an intentional change in output
```

Fixtures: a 5-colour logo with overlapping shapes and a thin outline, a thin
outline file, small text, a 15 mm wide bar that must convert from satin to
fill, and a messy file with 12 near-duplicate shades plus a background.

## Layout of the repository

```
digitizer/            the package (cli, pipeline, svg_input, colors, layering, classify, engine/, engine_inkstitch, preview, simulator, outputs, procedure, validate)
digitizer/palettes/   thread charts (GPL files from Ink/Stitch, GPL-3.0)
params.yaml           all parameters (documented in PARAMS.md)
scripts/              install_inkstitch.sh, make_wx_stub.py
tests/                pytest suite, fixtures and golden summaries
input/rack.svg        the sample artwork; examples/ holds its outputs
```

License: GPL-3.0-or-later (the thread palettes and the optional Ink/Stitch engine are GPL).
