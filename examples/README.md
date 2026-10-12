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
