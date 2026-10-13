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
