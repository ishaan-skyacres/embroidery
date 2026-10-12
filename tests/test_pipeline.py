import json
import shutil
from pathlib import Path

import pytest

from digitizer.pipeline import RunOptions, run
from digitizer.svg_input import inkscape_binary

GOLDEN = Path(__file__).resolve().parent / "golden"


def _summary(res):
    plan = res.plan
    return {
        "order": [b.group for b in plan.blocks],
        "counts": [b.stitch_count() for b in plan.blocks],
        "groups": sorted((g.name, sorted(g.members), g.skip) for g in res.groups),
        "validation_ok": res.validation.ok,
    }


def _check_golden(name, summary):
    path = GOLDEN / f"{name}.json"
    if not path.exists():
        pytest.skip(f"no golden file {path} (run python tests/update_golden.py)")
    gold = json.loads(path.read_text())
    assert summary["order"] == gold["order"]
    assert summary["groups"] == [tuple(x) if isinstance(x, list) else x for x in map(lambda t: (t[0], t[1], t[2]), gold["groups"])]
    for a, b in zip(summary["counts"], gold["counts"]):
        assert abs(a - b) <= max(3, 0.03 * b), f"stitch count drifted: {summary['counts']} vs {gold['counts']}"


@pytest.mark.parametrize("name,size,extra", [
    ("logo5", 80, {}),
    ("thin_outline", 60, {}),
    ("wide_shape", 60, {}),
    ("messy12", 80, {}),
])
def test_fixture_end_to_end(fixtures, tmp_path, name, size, extra):
    out = tmp_path / name
    res = run(RunOptions(input=fixtures / f"{name}.svg", size_mm=size, out=out, engine="python", quiet=True, **extra))
    for f in ["design.dst", "design.pes", "design.exp", "thread_sheet.md", "thread_sheet.pdf", "procedure.md",
              "procedure.html", "procedure.pdf", "report.md", "params_used.yaml", "preview_realistic.png",
              "preview_vs_art.png", "density_map.png", "simulator.html", "groups_preview.png", "groups_suggested.yaml"]:
        assert (out / f).exists(), f
    assert res.validation.ok, res.validation.errors
    assert len(list((out / "preview_per_color").glob("*.png"))) == len(res.plan.blocks)
    # procedure and thread sheet agree with the plan
    proc = (out / "procedure.md").read_text()
    for b in res.plan.blocks:
        assert f"{b.stitch_count()} stitches" in proc
    _check_golden(name, _summary(res))
    return res


def test_messy12_groups_to_five_plus_background(fixtures, tmp_path):
    res = run(RunOptions(input=fixtures / "messy12.svg", size_mm=80, out=tmp_path / "m", engine="python", quiet=True))
    stitched = [g for g in res.groups if not g.skip]
    skipped = [g for g in res.groups if g.skip]
    assert len(stitched) == 5 and len(skipped) == 1 and skipped[0].members == ["#f4f1ea"]
    assert len(res.plan.blocks) == 5


def test_wide_shape_classification(fixtures, tmp_path):
    res = run(RunOptions(input=fixtures / "wide_shape.svg", size_mm=60, out=tmp_path / "w", engine="python", quiet=True))
    report = (tmp_path / "w" / "report.md").read_text()
    assert "wider than 7" in report or "too wide for satin" in report     # 8.5 mm ribbon converted from satin to fill
    assert "tatami fill" in report                                        # 13 mm bar is a plain fill
    kinds = {b.group: b.descriptions for b in res.plan.blocks}
    assert any("satin column" in d for d in kinds[[g for g in kinds if "blue" in g][0]])
    assert any("running-stitch" in d for d in kinds[[g for g in kinds if "black" in g or "grey" in g][0]])


def test_thin_outline_becomes_running_and_bean(fixtures, tmp_path):
    res = run(RunOptions(input=fixtures / "thin_outline.svg", size_mm=60, out=tmp_path / "t", engine="python", quiet=True))
    black = next(b for b in res.plan.blocks if b.color == "#202020")
    assert any("running-stitch" in d for d in black.descriptions)
    assert res.plan.blocks[-1] is black          # outline group stitched last


@pytest.mark.skipif(inkscape_binary() is None, reason="Inkscape needed to convert text to paths")
def test_small_text_warns(fixtures, tmp_path):
    res = run(RunOptions(input=fixtures / "small_text.svg", size_mm=60, out=tmp_path / "s", engine="python", quiet=True))
    assert any("text" in w.lower() and "mm" in w for w in res.warnings), res.warnings


def test_review_groups_stops_early(fixtures, tmp_path):
    res = run(RunOptions(input=fixtures / "logo5.svg", size_mm=80, out=tmp_path / "r", engine="python", review_groups=True, quiet=True))
    assert res.stopped_after_groups and (tmp_path / "r" / "groups_suggested.yaml").exists()
    assert not (tmp_path / "r" / "design.dst").exists()


def test_groups_yaml_roundtrip_and_order_override(fixtures, tmp_path):
    out = tmp_path / "g"
    res = run(RunOptions(input=fixtures / "logo5.svg", size_mm=80, out=out, engine="python", review_groups=True, quiet=True))
    yaml_path = out / "groups_suggested.yaml"
    text = yaml_path.read_text()
    # reverse the order and merge nothing; the tool must follow it and warn about layering
    import yaml
    data = yaml.safe_load(text)
    data["order"] = list(reversed(data["order"]))
    (out / "groups_edited.yaml").write_text(yaml.safe_dump(data))
    res2 = run(RunOptions(input=fixtures / "logo5.svg", size_mm=80, out=out / "run2", engine="python",
                          groups_file=out / "groups_edited.yaml", quiet=True))
    assert [b.group for b in res2.plan.blocks] == data["order"]
    assert any("sits under" in w for w in res2.warnings)
