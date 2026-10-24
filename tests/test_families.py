import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import families as f  # noqa: E402

FX = json.loads((Path(__file__).parent / "fixtures" / "families_parity.json").read_text())


def test_refuses_cross_family_sum():
    assert f.sum_within_family("voice", [{"channel": "letter", "n": 3}, {"channel": "site", "n": 1}]) == 4
    with pytest.raises(ValueError):
        f.sum_within_family("voice", [{"channel": "letter", "n": 3}, {"channel": "311", "n": 2300}])


def test_percentiles_ties_at_bottom():
    assert f.percentile_ranks({"a": 0, "b": 0, "c": 10, "d": 20, "e": None}) == {"a": 0, "b": 0, "c": 50, "d": 75, "e": None}


def test_fixture_parity():
    got = f.percentile_ranks(FX["rates"])
    for k, v in FX["expected_pct"].items():
        assert (got[k] is None and v is None) or abs(got[k] - v) < 1e-9
    assert [r["tract_id"] for r in f.problems_without_voice(FX["problem_pct"], FX["voice_pct"])] == FX["expected_gaps"]
