from pathlib import Path

import pyembroidery as pe
import pytest

from digitizer.pipeline import RunOptions, run
from digitizer.validate import validate


def test_validator_catches_tampered_dst(fixtures, tmp_path):
    out = tmp_path / "v"
    res = run(RunOptions(input=fixtures / "wide_shape.svg", size_mm=60, out=out, engine="python", quiet=True))
    plan, layout = res.plan, res.layout
    from digitizer.params import load_params
    params = load_params()
    counts = [b.stitch_count() for b in plan.blocks]
    ok = validate(plan, out / "design.dst", layout, params, counts, counts, plan.stitch_count())
    assert ok.ok
    # add an extra colour change and a 20 mm stitch
    pat = pe.read(str(out / "design.dst"))
    bad = pe.EmbPattern()
    for x, y, c in pat.stitches:
        bad.add_stitch_absolute(c, x, y)
    bad.add_stitch_absolute(pe.STITCH, 0, 0)
    bad.add_stitch_absolute(pe.STITCH, 200, 0)
    bad.color_change()
    bad.add_stitch_absolute(pe.STITCH, 210, 0)
    bad.add_stitch_absolute(pe.STITCH, 215, 0)
    bad.end()
    pe.write_dst(bad, str(out / "bad.dst"))
    res2 = validate(plan, out / "bad.dst", layout, params, counts, counts, plan.stitch_count())
    assert not res2.ok
    assert any("colour changes" in e for e in res2.errors)
    assert any("stitch count" in e for e in res2.errors)
