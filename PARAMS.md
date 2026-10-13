# PARAMS.md: digitizing parameters, defaults, ranges and sources

Every number the tool uses lives in `params.yaml` (overridable per run with
`--params my.yaml` or `--set section.key=value`) and is explained here. Values
marked **verified** were confirmed against a primary source during research.
Values marked **conservative choice** are the starting values you supplied,
cross-checked against trade guidance that agreed in direction but gave no exact
figure; where sources disagreed, the more conservative (safer to sew) value was
chosen and the disagreement is noted.

Units are millimetres unless stated. "Ink/Stitch default" refers to the value in
the Ink/Stitch source at commit `a6a3d48` (main, October 2026).

Sources (referenced by tag below):

- [IS-FILL] Ink/Stitch `lib/elements/fill_stitch.py`
  <https://github.com/inkstitch/inkstitch/blob/main/lib/elements/fill_stitch.py>
- [IS-SATIN] Ink/Stitch `lib/elements/satin_column/satin_column.py`
  <https://github.com/inkstitch/inkstitch/blob/main/lib/elements/satin_column/satin_column.py>
- [IS-STROKE] Ink/Stitch `lib/elements/stroke.py`
  <https://github.com/inkstitch/inkstitch/blob/main/lib/elements/stroke.py>
- [IS-SET] Ink/Stitch `lib/utils/settings.py` (global defaults: min stitch 0.1 mm,
  minimum jump 3 mm, minimum satin stroke width 1 mm)
  <https://github.com/inkstitch/inkstitch/blob/main/lib/utils/settings.py>
- [IS-LOCK] Ink/Stitch `lib/stitch_plan/lock_stitch.py` and docs
  <https://inkstitch.org/docs/stitches/lock-stitches/>
- [IS-PARAMS] Ink/Stitch parameter docs <https://inkstitch.org/docs/params/>
- [IS-PREF] Ink/Stitch preferences docs <https://inkstitch.org/docs/preferences/>
- [IS-CLI] Ink/Stitch command line docs <https://inkstitch.org/docs/command-line/>
- [W-DENS] Wilcom EmbroideryStudio help, Tatami density
  <https://docs.wilcom.com/embroiderystudio/28/en/OnlineHelp/Digitizing/stitches/stitches-14.htm>
- [W-TUND] Wilcom help, Tatami underlay settings
  <https://docs.wilcom.com/embroiderystudio/28/en/OnlineHelp/Quality/stabilizing/stabilizing-11.htm>
- [W-RUND] Wilcom help, Run stitch underlay settings (edge run)
  <https://docs.wilcom.com/embroiderystudio/27/en/OnlineHelp/Quality/stabilizing/stabilizing-10.htm>
- [W-PULL] Wilcom help, Pull compensation
  <https://docs.wilcom.com/embroiderystudio/27/en/OnlineHelp/Quality/stabilizing/stabilizing-16.htm>
- [W-FAB] Wilcom help, About auto fabrics (per-fabric presets)
  <https://docs.wilcom.com/embroiderystudio/28/en/OnlineHelp/Digitizing/properties/properties-9.htm>
- [W-BLOG-PP] Wilcom blog, Push and pull compensation
  <https://wilcom.com/resources/blog/push-and-pull-compensation>
- [W-BLOG-SP] Wilcom blog, Stitch spacing or density
  <https://wilcom.com/resources/blog/stitch-spacing-or-density>
- [W-BLOG-LOW] Wilcom blog, High-impact low stitch-count designs (sequencing, trims)
  <https://wilcom.com/resources/blog/high-impact-low-stitch-count-designs>
- [W-ANGLE] Wilcom help, Set nominal angles
  <https://docs.wilcom.com/embroiderystudio/28/en/OnlineHelp/Digitizing/input/input-26.htm>
- [B-PULL] Bernina software help, Compensating for fabric stretch
  <https://softwarehelp.bernina.com/en/MainHelp/PART_Digitizing/quality/quality-8.htm>
- [B-SPLIT] Bernina software help, Split long stitches in satin fills
  <https://softwarehelp.bernina.com/en/MainHelp/PART_Digitizing/stitches/Split_long_stitches_in_satin_fills.htm>
- [MSN-SATIN] mySewnet help, Satin Column
  <https://softwarehelp.mysewnet.com/MSW/140/Digitizing/Topics/Satin_Column.htm>
- [MSN-UND] mySewnet help, Underlay stitches
  <https://softwarehelp.mysewnet.com/MSW/120/FontDigitizing/Topics/Underlay_Stitches.htm>
- [MSN-COMP] mySewnet help, Compensation
  <https://softwarehelp.mysewnet.com/MSW/140/Digitizing/Topics/Compensation.htm>
- [EMB-OUT] Embird Studio manual, outline parameters
  <https://www.embird.net/studio/manual/3175par_out.htm>
- [EMB-OBJ] Embird Studio manual, objects and stitch angles
  <https://embird.net/studio/manual/0075objects.htm>
- [COLDESI] ColDesi, Underlay 101
  <https://support.coldesi.com/Portals/8/Documents/Liberty%20Docs/Underlay%2101.pdf>
- [IMPR] Impressions Magazine, Digitizing and embroidering difficult fabrics (pique)
  <https://impressionsmagazine.com/process-technique/tips-for-digitizing-and-embroidering-difficult-fabrics/27324/>
- [IGN] Ignition Drawing, Small lettering guide
  <https://blog.ignitiondrawing.com/small-lettering-guide-part-1/>
- [GPRO] Graphics Pro, Stitching guidelines for digitizing
  <https://graphics-pro.com/feature/stitching-guidelines-for-digitizing/>
- [DRAW] DrawStitch, How to digitize satin stitches
  <https://www.drawstitch.com/blog/knowledge-base/how-to-digitize-satin-stitches/>
- [LINDEE] Lindee G Embroidery, About those dreaded jump stitches
  <https://lindeegembroidery.com/blog/item/about-those-dreaded-jump-stitches-2>
- [STERA] EduTechWiki, Stitch Era adjusting stitch sections (adjacent fill angles)
  <https://EduTechWiki.unige.ch/en/Stitch_Era_-_adjusting_stitch_sections>
- [DST] EduTechWiki, Embroidery format DST
  <https://edutechwiki.unige.ch/en/Embroidery_format_DST>
- [DST-KDE] KDE Liberty, Tajima ternary format
  <https://community.kde.org/Projects/Liberty/File_Formats/Tajima_Ternary>
- [PYEMB] pyembroidery README (DST 12.1 mm limit, write settings)
  <https://github.com/EmbroidePy/pyembroidery/blob/main/README.md>
- [POOLIN] Swing Design, Poolin EOC06 listing (860 spm, hoops, DST/DSB, USB and Wi-Fi)
  <https://www.swingdesign.com/products/poolin-eoc06-7-9in-x-11in-embroidery-machine-with-deluxe-accessory-bundle>
- [SCHMETZ] Schmetz needle guide <https://www.schmetzneedles.com/needle-guide/>
- [ALLST] Allstitch, Machine embroidery stabilizer guide
  <https://allstitch.com/pages/machine-embroidery-stabilizer-guide-what-stabilizer-to-use>

## 1. Machine (`machine:`)

| Key | Default | Range | Reason | Source |
|---|---|---|---|---|
| `hoops_mm` | `280x200`, `200x200`, `140x140` | fixed | The hoops shipped with the EOC06 (7.87 x 11 in, 7.87 x 7.87 in, 5.5 x 5.5 in). The largest is 200 wide x 280 tall as mounted; the tool checks both orientations and reports which one to use. **verified** | [POOLIN] |
| `default_hoop` | `280x200` | one of the above | Your instruction; largest field, least risk of a clearance failure. | you |
| `hoop_clearance_mm` | 10 | 5 to 20 | Keeps the presser foot and needle clear of the hoop frame; your requirement. | you |
| `max_stitch_mm` | 12.1 | fixed | Tajima DST stores each move as a signed 121-unit (0.1 mm) delta; longer moves must be split. Hard-fail above. **verified** | [DST], [DST-KDE], [PYEMB] |
| `max_speed_spm` | 860 | fixed | Rated maximum of the EOC06. **verified** | [POOLIN] |
| `estimate_speed_spm` | 600 | 400 to 860 | Realistic average including slow-downs on small objects and acceleration. Your instruction. | you |
| `thread_change_minutes` | 2.0 | 1 to 5 | Manual rethread on a single-needle machine, your estimate; used for total-time estimates. | you |
| `trims_at_color_change` | true | fixed | The EOC06 trims automatically at colour stops. | you |
| `trims_on_jump` | false | fixed | Do not rely on in-colour jump trims; the tool hides travel under later stitching and only emits an explicit TRIM when a jump is long. | you |
| `trim_jump_threshold_mm` | 3.0 | 2 to 5 | Moves up to this length are sewn as a normal stitch (no lock, no trim). Ink/Stitch calls this the minimum jump stitch length and defaults to 3 mm. **verified** | [IS-SET], [IS-PREF] |

## 2. General stitch rules (`general:`)

| Key | Default | Range | Reason | Source |
|---|---|---|---|---|
| `min_stitch_length_mm` | 0.3 | 0.1 to 0.5 | Stitches shorter than this are merged with their neighbour (lock stitches exempt). Ink/Stitch drops below 0.1 mm; 0.3 mm is the common trade minimum to avoid skipped stitches and thread breaks. **conservative choice** (sources range 0.1 to 0.5) | [IS-SET], [IS-PREF], [GPRO] |
| `lock_stitch.style` | `half_stitch` | `half_stitch`, `back_forth` | Tie-in/tie-off pattern. Ink/Stitch default is a half stitch: short back-and-forth along the path (0, 0.5, 1, 0.5, 0 of the lock length). **verified** | [IS-LOCK] |
| `lock_stitch.length_mm` | 0.7 | 0.5 to 1.0 | Ink/Stitch default scale for lock stitches is 0.7 mm. **verified** | [IS-LOCK] |
| `lock_stitch.where` | start and end of every object, before every trim and colour change | fixed | Ink/Stitch adds lock stitches wherever a jump, trim or colour change occurs; your requirement. **verified** | [IS-LOCK] |
| `overlap_mm` | 0.4 | 0.3 to 0.5 | Adjacent colours overlap so pull does not open a gap. Trade guidance: overlapping blocks of different stitch direction is built-in compensation; too much overlap makes lumps. **conservative choice** (your range) | [W-BLOG-PP], [MSN-COMP] |
| `simplify_tolerance_mm` | 0.1 | 0.05 to 0.2 | Curve flattening tolerance; same order as the running-stitch path tolerance so stitched edges follow the art. | [IS-STROKE] |
| `sliver_area_mm2` | 1.0 | 0.5 to 2 | Regions smaller than this after cleanup are dropped and listed. | you |
| `min_feature_width_mm` | 1.5 | 1.0 to 2.0 | Anything thinner cannot carry a satin at 40 wt thread; warn and offer thickening or running stitch. Graphics Pro gives 0.8 mm as the absolute minimum column width; 1.5 mm is the safe default. | [GPRO], [IGN] |

## 3. Tatami fill (`fill:`)

| Key | Default | Range | Reason | Source |
|---|---|---|---|---|
| `row_spacing_mm` | 0.40 | 0.35 to 0.45 | Common default density, a little wider than one 40 wt thread (about 0.4 mm). Ink/Stitch defaults to 0.25 mm, which is dense and intended for stable sampling; Wilcom and Bernina presets sit around 0.4 mm for standard tatami. Where sources disagree, 0.40 is the safer (less thread, less pucker). **conservative choice** | [IS-FILL], [W-DENS], [W-BLOG-SP] |
| `under_layer_row_spacing_mm` | 0.50 | 0.45 to 0.60 | A fill that sits under another layer, or on lofty or stretchy fabric, is opened up to reduce bulk and distortion. | you, [W-DENS] |
| `max_stitch_length_mm` | 3.8 | 3.0 to 4.0 | Ink/Stitch default 4.0 mm; Wilcom's common tatami length is 4 mm; 3.8 keeps a margin below 4 and well below the 12.1 mm DST cap. **verified range** | [IS-FILL], [W-DENS] |
| `min_row_end_stitch_mm` | 1.0 | 0.5 to 1.5 | Row-end stitches shorter than this are merged so edges don't pile up. | [IS-FILL] |
| `staggers` | 4 | 2 to 6 | Rows are offset so needle penetrations do not line up into visible lines. Ink/Stitch default 4. With 3 or more staggers the tool uses a golden-ratio offset sequence (each row shifts by 0.618 of the stitch length) instead of an integer cycle, because an integer cycle lines the holes up into straight diagonals (Ink/Stitch notes that fractional staggers show fewer diagonals). **verified** | [IS-FILL] |
| `angle_deg` | 45 | 0 to 179 | Diagonal fills cut across both warp and weft on a woven, which spreads pull in both directions. | you, [EMB-OBJ] |
| `adjacent_angle_offset_deg` | 30 | 20 to 90 | Adjacent fills with the same angle interleave and give a jagged shared edge; the tool assigns neighbouring regions angles at least this far apart. **verified direction** | [STERA], [W-ANGLE] |
| `skip_last` | true | bool | Skip the last stitch of each row: the first stitch of the next row lands there anyway. Cuts stitch count and edge build-up. **verified** | [IS-FILL] |
| `pull_compensation_mm` | 0.25 | 0.2 to 0.4 | Thread pull shortens each stitch along its own length, so a fill shrinks along the stitch direction and a satin column narrows across the column (which is also the stitch direction). Compensation therefore extends every row at both ends, along the stitch direction (Ink/Stitch: "expands rows outward from row center"). Bernina's automatic default is 0.2 mm; knits need more. **verified** | [IS-FILL], [B-PULL], [W-PULL], [W-BLOG-PP] |
| `underlay.enabled` | true | bool | Fills need underlay to stabilise the fabric and lift the top stitches. **verified** | [W-TUND], [COLDESI] |
| `underlay.angle_offset_deg` | 90 | 45 to 90 | Underlay runs against the top stitching (Ink/Stitch default fill angle + 90). **verified** | [IS-FILL], [W-TUND] |
| `underlay.row_spacing_factor` | 3 | 2.5 to 4 | Underlay row spacing = 3 x top row spacing (1.2 mm at 0.4). Ink/Stitch default. **verified** | [IS-FILL] |
| `underlay.max_stitch_length_mm` | 3.8 | 3 to 4 | Same as the top layer (Ink/Stitch default). | [IS-FILL] |
| `underlay.inset_mm` | 0.5 | 0.3 to 1.0 | Underlay is shrunk inward so it never peeks out past the top layer. Ink/Stitch default is 0 (not inset); 0.5 mm is the safe choice. **conservative choice** | [IS-FILL], [W-TUND] |
| `underlay.edge_run_min_size_mm` | 15 | 10 to 25 | Shapes larger than this also get an edge-run underlay just inside the outline, which firms the edge against push. Wilcom pairs edge run with tatami underlay on large shapes. **verified direction** | [W-RUND], [W-TUND] |
| `underlay.edge_run_inset_mm` | 0.5 | 0.3 to 1.0 | Same reasoning as the tatami underlay inset. | [W-RUND] |
| `underlay.edge_run_stitch_length_mm` | 2.5 | 2 to 3 | Standard running-stitch length. | [IS-STROKE] |
| `underlay.edge_run_always` | false | bool | Fabric presets for knits, terry and fleece set this so every fill gets an edge run regardless of size (stretch and pile need the edge firmed up). | [W-FAB], [IMPR] |
| `underlay.layers` | 1 | 1 to 2 | 2 adds a second tatami underlay layer at the fill angle (double tatami underlay) as recommended for pique. | [IMPR], [W-FAB] |
| `underpath` | true | bool | Travel between the sections of a fill as a running stitch inside the shape (Ink/Stitch's "underpath"), covered by rows stitched afterwards. With `false` the machine locks off and jumps between sections instead (more jumps, no hidden travel). Ink/Stitch default true. **verified** | [IS-FILL] |
| `travel_stitch_length_mm` | 2.0 | 1.5 to 2.5 | Travel runs inside a fill are short so tension pulls them into the fabric and the top layer hides them. | [LINDEE] |
| `underlay.skip_last` | false | bool | Skip the last stitch of each underlay row (Ink/Stitch `fill_underlay_skip_last`). Off by default: the underlay is sparse already. **verified** | [IS-FILL] |

## 4. Satin column (`satin:`)

| Key | Default | Range | Reason | Source |
|---|---|---|---|---|
| `spacing_mm` | 0.40 | 0.35 to 0.45 | Ink/Stitch default zigzag spacing is 0.4 mm peak to peak. **verified** | [IS-SATIN] |
| `min_width_mm` | 1.5 | 1.0 to 2.0 | Below this a satin cannot form cleanly (thread width 0.4 mm plus pull). Ink/Stitch refuses satin under 1 mm stroke width; trade minimum 0.8 mm; 1.5 is safe. On pile fabrics 2.0. **conservative choice** | [IS-SET], [GPRO] |
| `max_width_mm` | 7.0 | 6 to 8 | Satins wider than this snag and lie loose on clothing; Bernina recommends splitting at 7 mm. **verified** | [B-SPLIT], [DRAW] |
| `split_stitch_length_mm` | 7.0 | 5 to 7 | Satins between 7 and 10 mm are kept as satin with split stitches no longer than this (needle penetrations staggered). | [B-SPLIT] |
| `convert_to_fill_width_mm` | 10.0 | 8 to 12 | Over this width the column is converted to tatami fill; mySewnet suggests fills beyond 8 to 10 mm. **verified** | [MSN-SATIN], [DRAW] |
| `branching_to_fill_width_mm` | 4.0 | 3 to 6 | A shape whose skeleton has junctions (a lattice, a tray with a lip, a lobed leaf) is satin-stitched branch by branch only when narrower than this; wider branching shapes become tatami because satin fans out where branches meet. Narrow branching shapes stay satin because a tatami under 4 mm wide reads as a lattice. **conservative choice** (from test renders) | you |
| `pull_compensation_mm` | 0.2 | 0.17 to 0.4 | Per side. Bernina default 0.2 mm; satin columns thin by 0.17 to 0.25 mm on stable wovens. **verified** | [B-PULL], [W-BLOG-PP] |
| `underlay.none_below_mm` | 2.0 | 1.5 to 2.5 | Under 2 mm there is no room for underlay (mySewnet: satin wider than 2 mm generally warrants underlay). **verified** | [MSN-SATIN] |
| `underlay.center_walk_below_mm` | 4.0 | 3 to 5 | 2 to 4 mm: a single centre run. | you, [MSN-UND] |
| `underlay.contour_below_mm` | 7.0 | 6 to 8 | 4 to 7 mm: contour (edge-walk) underlay. mySewnet recommends edge walk for mixed-width columns. **verified direction** | [MSN-UND], [COLDESI] |
| `underlay.wide` | contour plus zigzag | fixed | Over 7 mm: both. mySewnet: for very wide satin columns select both underlay types. **verified** | [MSN-SATIN] |
| `underlay.center_walk_stitch_length_mm` | 2.0 | 1.5 to 3 | Ink/Stitch default 3 mm; 2 mm follows curves more closely. | [IS-SATIN] |
| `underlay.contour_inset_mm` | 0.4 | 0.3 to 0.6 | Ink/Stitch default inset per side so the underlay stays hidden. **verified** | [IS-SATIN] |
| `underlay.contour_stitch_length_mm` | 2.5 | 2 to 3 | Ink/Stitch default 3 mm. | [IS-SATIN] |
| `underlay.zigzag_spacing_mm` | 3.0 | 2 to 4 | Ink/Stitch default. **verified** | [IS-SATIN] |
| `underlay.zigzag_inset_mm` | 0.2 | 0.1 to 0.4 | Ink/Stitch default: half the contour inset. **verified** | [IS-SATIN] |
| `short_stitch_inset_percent` | 15 | 0 to 30 | On tight inside curves, stitches closer than 0.25 mm are inset by this much to avoid a thread pile-up. Ink/Stitch default. **verified** | [IS-SATIN] |
| `underlay.strength` | normal | normal, strong, double | `strong` (knits) lowers every width threshold by 25% so narrower columns get the next underlay step; `double` (pique) adds a second zigzag pass and contour underlay from 3 mm. | [IMPR], [W-FAB] |

## 5. Running stitch (`running:`)

| Key | Default | Range | Reason | Source |
|---|---|---|---|---|
| `stitch_length_mm` | 2.2 | 2.0 to 2.5 | Ink/Stitch default 2.5 mm; 2.0 to 2.5 is the normal outline length. | [IS-STROKE], [EMB-OUT] |
| `curve_stitch_length_mm` | 1.5 | 1.2 to 2.0 | Shorter stitches on tight curves so the line follows the art; Embird shortens on the inside of bends. **verified direction** | [EMB-OUT] |
| `tolerance_mm` | 0.15 | 0.1 to 0.2 | Maximum deviation from the path (Ink/Stitch default 0.2). | [IS-STROKE] |
| `min_stitch_length_mm` | 0.5 | 0.3 to 0.8 | Absolute minimum for running stitches (tighter than the global minimum). | you |
| `bean_repeats` | 1 | 0 to 2 | Bean (triple) run: each stitch goes forward, back, forward. Used for bold single-line outlines. Ink/Stitch `bean_stitch_repeats=1` means triple. **verified** | [IS-STROKE] |
| `bean_min_stroke_width_mm` | 0.6 | 0.4 to 1.2 | Lines drawn at least this wide (but under the satin minimum) are rendered as bean stitch so they read as bold as the art; thinner lines (hairlines, leaf veins) as a single run. | you |

## 6. Text and fine detail (`detail:`)

| Key | Default | Range | Reason | Source |
|---|---|---|---|---|
| `min_text_height_mm` | 5.0 | 4 to 6 | Satin lettering fills in below about 5 mm (caps) or 6.2 mm (mixed case). **verified** | [IGN], [GPRO] |
| `thin_feature_mm` | 1.5 | 1 to 2 | Same as `general.min_feature_width_mm`; features thinner than this are flagged. | [GPRO] |
| `thicken_above_mm` | 1.0 | 0.6 to 1.4 | Thin features at least this wide (but under `thin_feature_mm`) are widened to the minimum satin width and stitched as satin instead of being reduced to a line: a 1.2 mm rim or stem reads as unstitched when it becomes a single running stitch. Narrower features keep the `thin_feature_action`. **conservative choice** (from the sample design) | you |
| `thin_feature_action` | `running` | `warn`, `thicken`, `running` | What to do with a thin feature: warn only, thicken to the minimum, or stitch it as a running/bean line down its centre. Default renders it as a line so nothing is silently lost. | you |

## 7. Sequencing and pathing (`sequence:`)

| Key | Default | Range | Reason | Source |
|---|---|---|---|---|
| `order` | layers back to front, then large fills before details, outlines last | fixed | Lower layers first so upper layers cover their edges; outlines last to cover fill edges. | you, [W-BLOG-LOW] |
| outline group rule | thin fraction >= 50%, or line ratio >= 500 with thin fraction >= 30% | fixed | A colour group is treated as line work and stitched last when at least half its area is thinner than the minimum feature width, or when the area-weighted mean over its connected pieces of perimeter squared over 4 pi area (a measure of line-likeness independent of size and of repeats: 1 for a disc, about 800 for the sample's black line work, under 100 for groups of leaves) is at least 500 and at least 30% of it is thin. The second test keeps the rule stable when a design is scaled up and its lines grow past 1.5 mm. | test runs |
| `within_color` | centre out | fixed | Large fills are pushed outward from the centre of the design; everything else follows the tour. | you |
| `end_near_next_start` | false | bool | When true, the last object of a colour is the one nearest the next colour's start. Off by default: the move between colours is a jump the machine trims at the colour change anyway, while forcing the end costs a long in-colour jump that must be trimmed by hand (on the sample design it added a 70 mm jump). | you, test runs |
| `big_fill_mm2` | 400 | 100 to 1000 | Fills at least this big are stitched first, from the centre outward. Smaller fills join the tour below. | you |
| `optimize_tour` | true | bool | Objects other than large fills follow a nearest-neighbour route from where the previous colour ended, improved with 2-opt (fewer and shorter jumps; on the sample design olive went from 1510 mm to about 600 mm of jump travel). | you, test runs |
| `travel_under_cover` | true | bool | Travel inside a colour is a short running stitch routed through regions of the same colour that are not yet stitched, so later stitching covers it. | [LINDEE], [COLDESI] |
| `max_travel_mm` | 25 | 10 to 50 | Longer in-colour moves lock off and trim instead of travelling. | you |
| `trim_after_object` | false | bool | Lock off and trim after every object, like Ink/Stitch's per-object "trim after". Off: the tool only trims when a jump is longer than `max_travel_mm`, because the EOC06 does not trim inside a colour and every trim command is still a thread end to deal with. | [IS-PARAMS] |
| `trim_before_color_change` | true | bool | Emit an explicit trim before each colour change (the EOC06 trims there on its own; the command keeps the file correct on machines that need it). | [IS-PARAMS] |
| `within_color` fills | centre out | fixed | Fill objects of a colour are stitched from the design centre outward (largest first on ties); satins and lines follow nearest-neighbour from there. | you |

## 8. Fabric presets (`fabrics:`)

Values override the sections above when `--fabric` is given. Stabilizer and
needle advice is printed in the report and procedure.

| Preset | Fill spacing | Pull comp (fill / satin) | Underlay | Satin min width | Other | Stabilizer and needle | Source |
|---|---|---|---|---|---|---|---|
| `woven` (default: twill, canvas, denim) | 0.40 | 0.25 / 0.20 | standard | 1.5 | as above | 1 layer medium tear-away (2 layers on light wovens); 75/11 sharp or embroidery needle, 90/14 on heavy canvas or denim | [ALLST], [SCHMETZ], [B-PULL] |
| `knit` (T-shirts) | 0.45 | 0.35 / 0.30 | tatami underlay plus edge run on every fill over 10 mm; satin underlay one step up | 1.5 | lower total density | medium cut-away (never tear-away); 75/11 ballpoint | [W-FAB], [ALLST], [SCHMETZ] |
| `pique` (polos) | 0.36 (density up about 10%) | 0.24 / 0.24 | double: two tatami underlay layers (0 and 90 degrees), double zigzag under satins over 4 mm | 1.5 | | medium or heavy cut-away; 75/11 ballpoint | [IMPR], [W-FAB] |
| `terry` (towels) | 0.40 | 0.30 / 0.25 | edge-run underlay on all fills, knockdown layer optional (`--knockdown`) | 2.0 | knockdown tatami at 1.0 mm spacing under the whole design | tear-away or cut-away plus water-soluble topping on top; 75/11 or 90/14 | [W-FAB], [ALLST] |
| `fleece` | 0.40 | 0.30 / 0.25 | as terry | 2.0 | knockdown optional | cut-away plus water-soluble topping; 75/11 ballpoint | [ALLST] |

Pull compensation on knits: Wilcom notes knits stretch more than wovens so
compensation must increase; Impressions recommends increasing underlay and
compensation rather than density. Pique: increase density only slightly and use
double zigzag underlay where column width allows. **verified direction**
[W-FAB], [IMPR].

## 9. Colour grouping (`colors:`)

| Key | Default | Range | Reason | Source |
|---|---|---|---|---|
| `merge_threshold_de` | 8 | 3 to 15 | Colours closer than this CIEDE2000 distance share one thread (near-identical shades, anti-aliasing leftovers). Your instruction. | you |
| `refuse_merge_de` | 25 | 15 to 40 | The tool never merges two colours further apart than this just to hit `--colors N`; it stops and asks. | you |
| `palettes` | Madeira Polyneon, Isacord Polyester, Robison-Anton Polyester | any GPL palette in `digitizer/palettes/` | Open thread charts shipped with Ink/Stitch (GPL v3) used for nearest-thread suggestions. | Ink/Stitch `palettes/` |
| `background_coverage` | 0.9 | 0.5 to 1.0 | A shape covering at least this fraction of the canvas is treated as background and skipped unless `--stitch-background`. | you |

## 9b. Knockdown layer (`knockdown:`, enabled with `--knockdown`)

| Key | Default | Range | Reason | Source |
|---|---|---|---|---|
| `enabled` | false | bool | A low-density tatami under the whole design on terry or fleece so the top stitches do not sink into the pile; stitched first in the first colour. | you, [W-FAB] |
| `row_spacing_mm` | 1.0 | 0.8 to 1.5 | Open enough to flatten the pile without adding bulk. | you |
| `max_stitch_length_mm` | 3.0 | 2.5 to 4 | Standard tatami length. | [IS-FILL] |
| `expand_mm` | 1.0 | 0.5 to 2 | The knockdown extends this far past the design so edges are supported. | you |

## 10. Preview and estimates (`preview:`)

| Key | Default | Range | Reason | Source |
|---|---|---|---|---|
| `thread_width_mm` | 0.4 | 0.3 to 0.5 | Visual width of a 40 wt polyester thread. | [W-BLOG-SP] |
| `render_dpi` | 300 | 150 to 600 | Realistic preview resolution. | you |
| `fabric_color` | #d9d4c7 | any hex | Background colour of the previews (a neutral natural cotton); `--fabric-color` is a separate option that marks artwork colours as background to skip. | you |
| `density_cell_mm` | 1.0 | 0.5 to 2 | Cell size for the penetrations-per-mm2 heat map. | you |
| `coverage_warn_percent` | 2.0 | 0.5 to 5 | After stitching, each colour's artwork is rasterised and compared with its stitches drawn at thread width; a colour with more than this share uncovered raises a warning (`coverage_gaps.png` shows where). | you |
| `coverage_gap_mm2` | 1.0 | 0.5 to 5 | Uncovered patches at least this big are listed in the report with position and width. | you |
| `density_hotspot_per_mm2` | 8 | 5 to 12 | Cells with more needle penetrations per mm2 than this are flagged (thread-break and bird-nest risk). One tatami layer with underlay is about 0.9 penetrations per mm2; a satin edge cell is about 2.5 to 3; three stacked satin layers reach about 8. | you |

## 11. Disagreements noted

- **Fill row spacing.** Ink/Stitch's default is 0.25 mm (dense); your value and
  Wilcom/Bernina presets are about 0.4 mm. 0.40 mm was chosen (less thread,
  less pucker, standard trade value).
- **Fill underlay inset.** Ink/Stitch defaults to 0 mm; 0.5 mm was chosen so
  underlay never shows at the edge after pull.
- **Satin minimum width.** Ink/Stitch refuses satin under 1.0 mm; Graphics Pro
  cites 0.8 mm columns for tiny lettering; 1.5 mm was chosen as the safe
  default for a home machine with 40 wt thread.
- **Pull compensation on knits.** Sources agree only on direction (more on
  knits); 0.35 mm fill and 0.30 mm satin were chosen inside your 0.3 to 0.4
  range.
- **Minimum stitch length.** Ink/Stitch drops only below 0.1 mm; 0.3 mm is the
  common machine-safe minimum and was chosen.
