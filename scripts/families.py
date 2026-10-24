"""Channel separation rule, build-time mirror of src/data/families.ts.

Voice = letters + email + site. Problems = 311. Never summed, pooled or ranked together; cross-family
comparison uses citywide percentiles of per-1k-resident rates (share of tracts strictly below). tests/fixtures/families_parity.json is checked
by both pytest and vitest so the two implementations cannot drift.
"""
from __future__ import annotations

from bisect import bisect_left

FAMILY_OF = {"letter": "voice", "email": "voice", "site": "voice", "311": "problems"}
PROBLEM_PCT_MIN = 70
VOICE_PCT_MAX = 30


def sum_within_family(family: str, items: list[dict]) -> int:
    total = 0
    for it in items:
        if FAMILY_OF[it["channel"]] != family:
            raise ValueError(f"channel separation: refusing to add a {it['channel']} count into {family}")
        total += it["n"]
    return total


def rate_per_1k(count: float, population: float | None, months_covered: int = 12) -> float | None:
    if not population or population <= 0:
        return None
    return count / population * 1000 * (12 / max(1, months_covered))


def percentile_ranks(rates: dict[str, float | None]) -> dict[str, float | None]:
    vals = sorted(v for v in rates.values() if v is not None)
    n = len(vals)
    out: dict[str, float | None] = {}
    for k, v in rates.items():
        if v is None or n == 0:
            out[k] = None
            continue
        # share of tracts strictly below: tied tracts (e.g. every tract with zero comments) sit at the bottom of their
        # tie, so silent tracts score 0 instead of the middle of a large tie
        out[k] = 100 * bisect_left(vals, v) / n
    return out


def problems_without_voice(problem_pct: dict, voice_pct: dict) -> list[dict]:
    rows = [{"tract_id": t, "problem_pct": p, "voice_pct": voice_pct[t]} for t, p in problem_pct.items()
            if p is not None and voice_pct.get(t) is not None and p >= PROBLEM_PCT_MIN and voice_pct[t] <= VOICE_PCT_MAX]
    return sorted(rows, key=lambda r: (-(r["problem_pct"] - r["voice_pct"]), r["tract_id"]))
