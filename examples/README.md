# Example outputs

`rack_120mm/` holds the outputs of running the sample artwork (`input/rack.svg`,
a three-shelf tomato grow rack, 6 flat colours, 457 paths) at 120 mm on the
longest side for the 280 x 200 mm hoop on woven fabric with the pure-Python
engine:

```
digitize input/rack.svg --size-mm 120 --out examples/rack_120mm --engine python --name "tomato rack"
```

Open `preview_realistic.png`, `simulator.html` and `procedure.html` to see what
the tool produces. `report.md` lists every digitizing decision for this file.

`rack_5.1in_overshirt/` is the same artwork at 5.1 in (129.5 mm) tall for the
200 x 200 mm hoop on a woven 70% polyester overshirt:

```
digitize input/rack.svg --size-mm 129.54 --hoop 200x200 --fabric woven --engine python --name "tomato rack overshirt" --out examples/rack_5.1in_overshirt
```
