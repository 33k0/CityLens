"""Every file the browser loads must be strict JSON: Python's json writes NaN/Infinity by default, browsers reject them."""
import json
from pathlib import Path

import pytest

PUBLIC = Path(__file__).resolve().parents[1] / "public" / "data"
FILES = sorted(p for p in PUBLIC.rglob("*.json"))


def _reject(token):
    raise ValueError(f"non-standard JSON constant {token}")


@pytest.mark.parametrize("path", FILES, ids=lambda p: str(p.relative_to(PUBLIC)))
def test_strict_json(path):
    json.loads(path.read_text(), parse_constant=_reject)
