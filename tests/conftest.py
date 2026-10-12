import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tests.make_fixtures import HERE as FIXTURES, write_all  # noqa: E402

write_all()


@pytest.fixture(scope="session")
def fixtures() -> Path:
    return FIXTURES


@pytest.fixture(scope="session")
def params():
    from digitizer.params import load_params
    return load_params()
