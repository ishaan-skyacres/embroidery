# Example outputs

`rack3_5.1in_overshirt/` is the deliverable for the tomato grow rack
(`input/rack3.svg`, the cleaned-up artwork, 6 flat colours, 438 paths) at
5.1 in (129.5 mm) tall for the 200 x 200 mm hoop on a woven 70% polyester
overshirt, pure-Python engine:

```
digitize input/rack3.svg --size-mm 129.54 --hoop 200x200 --fabric woven --engine python --name "tomato rack overshirt" --out examples/rack3_5.1in_overshirt
```

`rack_120mm/` is the same artwork at 120 mm for the 280 x 200 mm hoop:

```
digitize input/rack3.svg --size-mm 120 --engine python --name "tomato rack" --out examples/rack_120mm
```

Open `preview_realistic.png`, `coverage_gaps.png`, `simulator.html` and
`procedure.html` to see what the tool produces. `report.md` lists every
digitizing decision. `input/rack.svg` is the earlier version of the artwork.

`skyacres_logo_3in/` is the SkyAcres logo (`input/skyacres_logo.svg`: the
emblem and wordmark, with the "AGROTECHNOLOGIES INC" line removed) at 3 in
(76.2 mm) tall for the 140 x 140 mm hoop on woven fabric, one colour:

```
digitize input/skyacres_logo.svg --height-mm 76.2 --hoop 140x140 --fabric woven --engine python --name "SkyAcres logo" --out examples/skyacres_logo_3in
```

`rack3_6in/` is the rack at 6 in (152.4 mm) tall for the 200 x 200 mm hoop,
woven preset:

```
digitize input/rack3.svg --height-mm 152.4 --hoop 200x200 --fabric woven --engine python --name "tomato rack 6in" --out examples/rack3_6in
```

`rack3_x2_5.2in_280/` and `rack3_x2_5.2in_200/` are two racks side by side at
5.2 in (132 mm) tall (`input/rack3_x2_gap15.svg` with a 15 mm gap for the
280 x 200 hoop, `input/rack3_x2_gap5.svg` with a 5 mm gap for the 200 x 200):

```
digitize input/rack3_x2_gap15.svg --height-mm 132.08 --hoop 280x200 --fabric woven --engine python --name "two racks 5.2in" --out examples/rack3_x2_5.2in_280
digitize input/rack3_x2_gap5.svg  --height-mm 132.08 --hoop 200x200 --fabric woven --engine python --name "two racks 5.2in" --out examples/rack3_x2_5.2in_200
```

`sky_2in/` and `acres_2in/` are the words "Sky" and "Acres" set in the
Tropical Taste Demo font (Glyphstyle), 2 in (50.8 mm) tall, one colour (the
SkyAcres olive). The SVGs (`input/sky.svg`, `input/acres.svg`) were made with
`scripts/text_to_svg.py`, which shapes the text with HarfBuzz (kerning and the
font's ligatures apply) and writes each glyph as a filled path. The font file
itself is not in the repository (demo licence); point the script at your copy:

```
pip install fonttools uharfbuzz
python scripts/text_to_svg.py "Tropical Taste Demo.otf" Sky   input/sky.svg   --fill "#679943"
python scripts/text_to_svg.py "Tropical Taste Demo.otf" Acres input/acres.svg --fill "#679943"
digitize input/sky.svg   --height-mm 50.8 --hoop 140x140 --fabric woven --engine python --name "Sky 2in"   --out examples/sky_2in
digitize input/acres.svg --height-mm 50.8 --hoop 200x200 --fabric woven --engine python --name "Acres 2in" --out examples/acres_2in
```

"Sky" comes out 75 x 51 mm (3152 stitches, about 5 min) and fits the 140 x 140
hoop; "Acres" is 155 x 51 mm (6091 stitches, about 10 min) and needs the
200 x 200 hoop (22 mm clearance). The stitch files are `design.dst` in each
folder.

`sky_derania_2in/` and `acres_derania_2in/` are the same two words in the
Derania Demo font (limitype, personal licence; also not in the repository),
2 in tall, same colour. Derania is a heavy block face, so both words are solid
tatami fills:

```
python scripts/text_to_svg.py "DeraniaDemo-PersonalLicense.otf" Sky   input/sky_derania.svg   --fill "#679943"
python scripts/text_to_svg.py "DeraniaDemo-PersonalLicense.otf" Acres input/acres_derania.svg --fill "#679943"
digitize input/sky_derania.svg   --height-mm 50.8 --hoop 140x140 --fabric woven --engine python --name "Sky 2in Derania"   --out examples/sky_derania_2in
digitize input/acres_derania.svg --height-mm 50.8 --hoop 280x200 --fabric woven --engine python --name "Acres 2in Derania" --out examples/acres_derania_2in
```

"Sky" is 115 x 51 mm (4725 stitches, about 8 min) and just fits the 140 x 140
hoop with 12.5 mm to the edge; "Acres" is 191 x 51 mm (8226 stitches, about
14 min), too wide for the 200 x 200 hoop's 10 mm clearance, so it is laid out
for the 280 x 200.
