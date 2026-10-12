"""Regenerate the golden summaries: python tests/update_golden.py"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from digitizer.pipeline import RunOptions, run  # noqa: E402
from tests.make_fixtures import HERE, write_all  # noqa: E402
from tests.test_pipeline import GOLDEN, _summary  # noqa: E402

write_all()
GOLDEN.mkdir(exist_ok=True)
for name, size in [("logo5", 80), ("thin_outline", 60), ("wide_shape", 60), ("messy12", 80)]:
    with tempfile.TemporaryDirectory() as td:
        res = run(RunOptions(input=HERE / f"{name}.svg", size_mm=size, out=Path(td) / name, engine="python", quiet=True))
        (GOLDEN / f"{name}.json").write_text(json.dumps(_summary(res), indent=1))
        print(name, _summary(res)["order"], _summary(res)["counts"])
