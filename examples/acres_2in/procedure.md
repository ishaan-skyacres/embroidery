# Stitching procedure: Acres 2in

## 1. Before you start

1. [ ] Design: Acres 2in. Final size 154.6 x 51.2 mm (6.08 x 2.01 in).

2. [ ] Hoop: use the 200x200 hoop (200 x 200 mm), mounted as labelled. The design leaves 22 mm to the nearest hoop edge (minimum 10 mm).

3. [ ] Totals: 6091 stitches, 1 thread colours, 0 thread changes. Estimated time about 10 min (10 min sewing at 600 spm plus about 2 min per thread change).

4. [ ] Shopping and prep list:
    - Thread 1: olive (#679943), suggested Isacord Polyester 5633 Lime.
    - Bobbin thread: 60 wt pre-wound, white (light fabric; the back of the embroidery shows the bobbin colour).
    - Needle: 75/11 embroidery needle (sharp point); 90/14 on heavy canvas or denim. Start every project with a fresh needle.
    - Stabilizer: One layer of medium-weight tear-away under the fabric (two layers on light cotton or linen). Heavy canvas or denim is stable enough on its own with one layer.
    - Temporary spray adhesive (505 or similar) if the garment cannot be hooped and must be floated.
    - Small curved embroidery scissors for jump threads, a seam ripper, and a lint brush.

5. [ ] File transfer: copy design.dst to a USB stick (FAT32) in a folder you will recognise, or send it with the Poolin Wi-Fi app (InStitch). Name it clearly, for example Acres_2in_155mm.dst, so it is easy to find on the touchscreen.

## 2. Hooping

1. [ ] Decide where the design goes on the garment and mark its centre with a water-soluble pen or a pin. The design is centred on the hoop origin, so this mark is where the needle starts.

2. [ ] Orientation: the design is 155 mm wide and 51 mm tall; the top of the design (negative y in the previews) is the top of the artwork. Mount the hoop as labelled and check on screen that the design is upright relative to the garment before stitching.

3. [ ] Stabilizer: One layer of medium-weight tear-away under the fabric (two layers on light cotton or linen). Heavy canvas or denim is stable enough on its own with one layer. Hoop the fabric with the stabilizer underneath. Drum-tight, grain straight.

4. [ ] Hoop the fabric with the stabilizer underneath: loosen the outer ring, lay the stabilizer then the fabric over the inner ring, press the outer ring down, then tighten. The fabric should be drum-tight but not stretched (pull gently on wovens only).

5. [ ] Line up the hoop's centre marks with your centre mark. Attach the hoop to the machine.

6. [ ] Load design.dst on the machine, check its position on screen, and run the trace/outline function so the foot travels around the design area: confirm it clears the hoop edge and lands where you want it. Adjust and trace again if needed.

7. [ ] Set the speed no higher than about 600 spm for the first run; slow down for small details.

## 3. Thread-by-thread run sheet

One block per colour stop, in sewing order. The machine stops and trims at the end of each colour.

1. [ ] Stop 1 of 1: load olive (#679943), Isacord Polyester 5633 Lime. <span style="display:inline-block;width:1.2em;height:1em;background:#679943;border:1px solid #444"></span>
    - Thread the needle with this colour before pressing start. Hold the thread tail for the first few stitches.
    - This colour stitches: 5 tatami fill area(s) totalling 3813 mm2 (largest: 959 mm2 centre left, 737 mm2 centre right, 720 mm2 centre).
    - 6091 stitches, about 10 min.
    - Watch: Large fill: watch for puckering at the edges; if the fabric ripples, stop and re-hoop with more stabilizer.
    - Watch: 5 jump(s) inside this colour: trim the floating threads by hand at the stop (lower 9 mm, lower 48 mm, centre right 6 mm, lower left 53 mm ...).
    - At the stop: the machine trims the colour automatically; this colour also has 5 jump(s) inside it that the machine does NOT trim. Cut the floating threads on top close to the fabric before continuing.

    ![stop](procedure_thumbs/stop_01.png)

## 4. Finishing

1. [ ] Remove the hoop from the machine and take the fabric out of the hoop. Do not pull the fabric; loosen the ring first.

2. [ ] Tear-away stabilizer: support the stitches with one hand and tear the stabilizer away gently, in small pieces, so the stitches are not distorted. Trim what remains close to the design.

3. [ ] Trim remaining jump threads close on both the front and the back.

4. [ ] Press from the back on a thick towel with a pressing cloth; never press the front directly (it flattens the thread).

## 5. Troubleshooting

| Symptom | Likely cause | Fix | params.yaml setting |
|---|---|---|---|
| Puckering around fills | Not enough stabilizer, fabric hooped loose, or stitching too dense | Add a stabilizer layer, re-hoop drum-tight, reduce density | fill.row_spacing_mm (raise to 0.45), fill.underlay.* |
| Gaps between colours | Pull compensation too low for this fabric | Increase overlap and pull compensation, test again | general.overlap_mm (0.5), fill.pull_compensation_mm, satin.pull_compensation_mm |
| Outline does not line up with the fill | Fabric shifted in the hoop, or fills pulled in | Re-hoop with cut-away, more underlay, more compensation | fill.pull_compensation_mm, fill.underlay.edge_run_always |
| Bird-nesting under the fabric | Top thread not seated in the tension discs or take-up lever; thread caught on the spool | Rethread the top from the start, check the spool unwinds freely | (not a digitizing problem) |
| Thread breaks or shredding | Dull or wrong needle, burr on the plate, too dense or too short stitches | New needle, slow the machine, open the density | satin.spacing_mm, fill.row_spacing_mm, general.min_stitch_length_mm |
| Bobbin thread showing on top | Top tension too tight or bobbin too loose | Lower top tension one step; check the bobbin case | satin.spacing_mm (if only on satins) |
| Satin text unreadable | Letters too small for the thread | Scale the design up or simplify the text | detail.min_text_height_mm, satin.min_width_mm, --size-mm |
| Underlay shows at the edges | Underlay inset too small for this fabric | Increase the underlay insets | fill.underlay.inset_mm, satin.underlay.contour_inset_mm |
| Design off-centre on the garment | Centre mark or hoop alignment off | Re-mark, re-hoop, use trace before stitching | (machine positioning) |
| Jump threads left on top | Single-needle machine does not trim inside a colour | Trim by hand at each stop | sequence.max_travel_mm, sequence.travel_under_cover |

## 6. Test-stitch checklist

Stitch the design first on a scrap of the same fabric with the same stabilizer, then tick off:

1. [ ] Edges are sharp and even

2. [ ] No gaps between colours

3. [ ] No underlay showing outside the top stitching

4. [ ] No puckering around the fills

5. [ ] Text and fine lines are readable

6. [ ] Colours look as expected next to the garment

7. [ ] Outline sits on the fill edges (registration)

8. [ ] If anything fails, change the setting named in the troubleshooting table in params.yaml and re-export.
