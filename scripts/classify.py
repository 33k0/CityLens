"""Milestone 5: category + stance for the VOICE family (letters + emails). Never 311.

Engine order per row: cache -> Granite via Ollama (/api/chat, strict JSON schema, temperature 0, fixed seed)
-> deterministic rule engine. Every evidence_quote and stance_evidence must be an exact substring of the
comment text after whitespace normalization; the LLM gets one correction retry, then the row falls back to rules.

Also: identity-hash duplicate detection, MinHash/LSH form-letter campaigns, the labeled-sample template, and
provenance records in public/data/provenance.json.

  python scripts/classify.py                 # all voice rows, Granite if available
  python scripts/classify.py --item 25-081   # only rows of one item (merged into classifications.csv)
  python scripts/classify.py --engine rules  # force the rule engine
  python scripts/classify.py --cache-only    # offline replay: no model calls, fail if a row is not cached
  python scripts/classify.py --fingerprint   # print the voice corpus fingerprint (used by run_bob.mjs)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from families import FAMILY_OF  # noqa: E402

DATA = ROOT / "data"
CATEGORIES_PATH = DATA / "categories.json"
PROMPT_PATH = ROOT / "prompts" / "classify.txt"
CACHE_PATH = DATA / "classify_cache.json"
OUT_CSV = DATA / "classifications.csv"
CAMPAIGNS_PATH = DATA / "campaigns.json"
SAMPLE_PATH = DATA / "labeled_sample_template.csv"
PROVENANCE_PATH = ROOT / "public" / "data" / "provenance.json"
INPUTS = [DATA / "comments_raw.csv", DATA / "emails_raw.csv"]

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "granite4.1:8b")
MODEL_FALLBACKS = ["granite4.1:8b", "ibm/granite4.1:8b"]
RULES_MODEL = "rules-v1"
SEED = 42
MAX_CHARS = 6000
STANCES = ["support", "oppose", "neutral", "unclear"]
OUT_COLS = ["comment_id", "channel", "item", "category", "confidence", "evidence_quote", "stance", "stance_source",
            "stance_evidence", "language", "engine", "model", "campaign_id", "duplicate_of"]

# MinHash campaign detection
SHINGLE = 5
NUM_PERM = 128
JACCARD_MIN = 0.7
LSH_THRESHOLD = 0.5         # candidate recall; every edge is then verified exactly
OVERLAP_MIN_SHINGLES = 20   # overlap coefficient only for texts with >= 20 shingles
CAMPAIGN_MIN_ROWS = 3
# identity-hash duplicates
DUP_RATIO_MIN = 90


def warn(msg: str) -> None:
    bar = "!" * 78
    print(f"\n{bar}\n!! WARNING: {msg}\n{bar}\n", file=sys.stderr, flush=True)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------- text helpers
_WS = re.compile(r"\s+")
_FOLD = str.maketrans({"‘": "'", "’": "'", "‛": "'", "′": "'", "“": '"', "”": '"',
                       "„": '"', "–": "-", "—": "-", "−": "-", " ": " "})


def norm_ws(s: str) -> str:
    return _WS.sub(" ", str(s or "")).strip()


def fold(s: str) -> str:
    """1:1 character fold (quotes, dashes) so indices in folded text map to the normalized text."""
    return s.translate(_FOLD)


def is_exact_substring(quote: str, text: str) -> bool:
    q = norm_ws(quote)
    return bool(q) and q in norm_ws(text)


def find_span(quote: str, text: str) -> str | None:
    """Return the exact substring of norm_ws(text) matching quote (tolerating curly-vs-straight quotes and
    dashes and stray wrapping quotes/ellipses), or None. The returned string is always a substring of
    norm_ws(text)."""
    t = norm_ws(text)
    q = norm_ws(quote).strip().strip('"\'“”‘’').strip()
    q = re.sub(r"^(\.\.\.|…)\s*|\s*(\.\.\.|…)$", "", q)
    if not q:
        return None
    if q in t:
        return q
    ft, fq = fold(t), fold(q)
    i = ft.find(fq)
    if i < 0:
        i = ft.lower().find(fq.lower())
    if i < 0:
        return None
    return t[i:i + len(q)]


# ---------------------------------------------------------------- taxonomy and prompt
def load_categories(path: Path | None = None) -> dict:
    path = path or CATEGORIES_PATH
    if not path.exists():
        raise SystemExit(f"{path} does not exist; run the categorize-comments skill (node scripts/run_bob.mjs)")
    cats = json.loads(path.read_text())
    problems = []
    if not isinstance(cats.get("stance_definition"), str) or not cats["stance_definition"].strip():
        problems.append("top-level 'stance_definition' (string) is required")
    items = cats.get("categories")
    if not isinstance(items, list) or not 5 <= len(items) <= 8:
        problems.append(f"'categories' must be a list of 5-8, got {len(items) if isinstance(items, list) else items!r}")
        items = items if isinstance(items, list) else []
    taxo_311 = set(pd.read_csv(DATA / "taxonomy_311.csv")["category"]) if (DATA / "taxonomy_311.csv").exists() else None
    keys = []
    for i, c in enumerate(items):
        k = c.get("key", f"#{i}")
        keys.append(k)
        if not re.fullmatch(r"[a-z][a-z0-9_]*", str(k)):
            problems.append(f"category {k!r}: key must be snake_case")
        for f in ("label", "description"):
            if not isinstance(c.get(f), str) or not c[f].strip():
                problems.append(f"category {k}: '{f}' (string) is required")
        for f in ("include", "exclude", "examples", "keywords", "maps_311"):
            if not isinstance(c.get(f), list):
                problems.append(f"category {k}: '{f}' (list) is required")
        if taxo_311 is not None and isinstance(c.get("maps_311"), list) and set(c["maps_311"]) - taxo_311:
            problems.append(f"category {k}: maps_311 has unknown 311 keys {sorted(set(c['maps_311']) - taxo_311)}")
    if len(set(keys)) != len(keys):
        problems.append("category keys must be unique")
    if problems:
        raise SystemExit(f"{path} is invalid:\n  - " + "\n  - ".join(problems))
    return cats


def categories_hash(cats: dict) -> str:
    return hashlib.sha256(json.dumps(cats, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]


def load_prompt(path: Path | None = None) -> dict:
    path = path or PROMPT_PATH
    raw = path.read_text()
    m = re.search(r"prompt_version:\s*(\S+)", raw)
    version = m.group(1) if m else "unversioned"
    parts = re.split(r"^=== SYSTEM ===[ \t]*$", raw, maxsplit=1, flags=re.M)
    if len(parts) != 2:
        raise SystemExit(f"{path}: missing a line '=== SYSTEM ==='")
    halves = re.split(r"^=== USER ===[ \t]*$", parts[1], maxsplit=1, flags=re.M)
    if len(halves) != 2:
        raise SystemExit(f"{path}: missing a line '=== USER ==='")
    system, user = halves[0].strip(), halves[1].strip()
    for part, allowed in ((system, {"categories_block", "stance_definition"}),
                          (user, {"language", "item", "item_title", "subject", "text"})):
        used = set(re.findall(r"(?<!\{)\{([A-Za-z_]*)\}(?!\})", part))
        if used - allowed:
            raise SystemExit(f"{path}: unknown placeholders {sorted(used - allowed)}; allowed {sorted(allowed)}")
    if "{text}" not in user:
        raise SystemExit(f"{path}: the user part must contain {{text}}")
    return {"version": version, "system": system, "user": user}


def categories_block(cats: dict) -> str:
    lines = []
    for c in cats["categories"]:
        lines.append(f"- {c['key']}: {c['label']}. {c['description']}")
        lines.append(f"  include: {'; '.join(c['include'])}")
        lines.append(f"  exclude: {'; '.join(c['exclude'])}")
    return "\n".join(lines)


def response_schema(cats: dict) -> dict:
    return {
        "type": "object",
        "properties": {
            "category": {"type": "string", "enum": [c["key"] for c in cats["categories"]]},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "evidence_quote": {"type": "string"},
            "stance": {"type": "string", "enum": STANCES},
            "stance_evidence": {"type": "string"},
        },
        "required": ["category", "confidence", "evidence_quote", "stance", "stance_evidence"],
        "additionalProperties": False,
    }


def validate_label(obj, cats: dict, text: str) -> tuple[dict | None, list[str]]:
    """Schema + evidence validation. Returns (cleaned label, errors). Quotes are replaced by the exact
    substring of the normalized text they matched."""
    errs: list[str] = []
    if not isinstance(obj, dict):
        return None, ["response is not a JSON object"]
    keys = {c["key"] for c in cats["categories"]}
    cat = obj.get("category")
    if cat not in keys:
        errs.append(f"category {cat!r} is not one of {sorted(keys)}")
    stance = obj.get("stance")
    if stance not in STANCES:
        errs.append(f"stance {stance!r} is not one of {STANCES}")
    conf = obj.get("confidence")
    if not isinstance(conf, (int, float)) or isinstance(conf, bool) or not (0 <= conf <= 1):
        errs.append(f"confidence {conf!r} is not a number in [0, 1]")
    eq = obj.get("evidence_quote")
    eq_span = find_span(eq, text) if isinstance(eq, str) else None
    if not eq_span:
        errs.append("evidence_quote is not an exact substring of the comment text")
    se = obj.get("stance_evidence", "")
    se = se if isinstance(se, str) else ""
    se_span = find_span(se, text) if se.strip() else ""
    if se.strip() and not se_span:
        errs.append("stance_evidence is not an exact substring of the comment text")
    if stance in ("support", "oppose") and not se.strip():
        errs.append("stance_evidence is required when stance is support or oppose")
    if errs:
        return None, errs
    return {"category": cat, "confidence": round(float(conf), 3), "evidence_quote": eq_span,
            "stance": stance, "stance_evidence": se_span or ""}, []


# ---------------------------------------------------------------- rule engine (deterministic fallback)
def _kw_regex(kw: str) -> re.Pattern:
    case_sensitive = kw.isupper() and len(kw) <= 4  # ICE, RV, EIR, D3
    pat = r"(?<!\w)" + re.escape(kw) + r"(?!\w)"
    return re.compile(pat, 0 if case_sensitive else re.IGNORECASE)


def _cue(p: str, stance: str, w: float, cs: bool = False):
    return (re.compile(p, 0 if cs else re.IGNORECASE), stance, w)


STANCE_CUES = [
    # support
    _cue(r"(?<!\w)SUPPORT(?:S|ING|ED)?(?!\w)", "support", 3, cs=True),
    _cue(r"\bin (?:strong )?support of\b", "support", 2),
    _cue(r"\b(?:strong(?:ly)?|full(?:y)?) support", "support", 2),
    _cue(r"\bletters? of (?:support|recommendation)\b", "support", 2),
    _cue(r"\b(?:I|we) (?:strongly |fully )?support\b", "support", 2),
    _cue(r"\bplease (?:support|approve|appoint|pass|adopt)\b", "support", 2),
    _cue(r"\bvote yes\b", "support", 2),
    _cue(r"\bin favor of\b", "support", 2),
    _cue(r"\b(?:strongly )?recommend\b", "support", 1),
    _cue(r"\burge you to (?:approve|adopt|support|pass|appoint|fund)\b", "support", 2),
    _cue(r"\bsupport(?:s|ing|ed)?\b", "support", 1),
    _cue(r"(?<!\w)apoy(?:o|amos)(?!\w)", "support", 2),
    _cue(r"(?<!\w)a favor de(?!\w)", "support", 2),
    _cue(r"(?<!\w)ỦNG HỘ(?!\w)", "support", 3, cs=True),
    _cue(r"(?<!\w)ủng hộ(?!\w)", "support", 2),
    # oppose
    _cue(r"(?<!\w)OPPOS(?:E|ED|ING|ITION)(?!\w)", "oppose", 3, cs=True),
    _cue(r"(?<!\w)AGAINST(?!\w)", "oppose", 3, cs=True),
    _cue(r"\boppos(?:e|ed|ing|ition)\b", "oppose", 2),
    _cue(r"\bvote no\b", "oppose", 2),
    _cue(r"\bdo not (?:approve|accept|support|pass|adopt)\b", "oppose", 2),
    _cue(r"\bnot in favor\b", "oppose", 2),
    _cue(r"\bagainst\b", "oppose", 1),
    _cue(r"(?<!\w)me opongo(?!\w)", "oppose", 2),
    _cue(r"(?<!\w)ME OPONGO(?!\w)", "oppose", 3, cs=True),
    _cue(r"(?<!\w)OPONGO(?!\w)", "oppose", 3, cs=True),
    _cue(r"(?<!\w)oposici[oó]n(?!\w)", "oppose", 2),
    _cue(r"(?<!\w)en contra(?!\w)", "oppose", 2),
    _cue(r"(?<!\w)PHẢN ĐỐI(?!\w)", "oppose", 3, cs=True),
    _cue(r"(?<!\w)phản đối(?!\w)", "oppose", 2),
    # neutral / undecided
    _cue(r"\b(?:undecided|neutral|torn|mixed feelings|on the fence|see both sides|not sure|don'?t know which way)\b",
         "neutral", 2),
    _cue(r"(?<!\w)no estoy segur[oa](?!\w)", "neutral", 2),
    _cue(r"(?<!\w)chưa chắc(?!\w)", "neutral", 2),
]
_NEGATION = re.compile(r"(?:\bnot|n't|\bnever|\bno)\s+(?:\w+\s+)?$", re.IGNORECASE)


def _sentence_around(t: str, start: int, end: int, max_len: int = 220) -> str:
    """Sentence of normalized text t containing [start, end), clipped to max_len on word boundaries.
    Always returns a substring of t."""
    left = max(t.rfind(". ", 0, start), t.rfind("! ", 0, start), t.rfind("? ", 0, start))
    s = 0 if left < 0 else left + 2
    rights = [i for i in (t.find(". ", end), t.find("! ", end), t.find("? ", end)) if i >= 0]
    e = (min(rights) + 1) if rights else len(t)
    if e - s > max_len:
        half = max_len // 2
        s2 = max(s, start - half)
        e2 = min(e, max(end, s2 + max_len))
        if s2 > s:
            sp = t.find(" ", s2)
            s2 = sp + 1 if 0 <= sp < start else s2
        if e2 < e:
            sp = t.rfind(" ", end, e2)
            e2 = sp if sp > end else e2
        s, e = s2, e2
    return t[s:e].strip()


def _first_sentence(t: str) -> str:
    if not t:
        return ""
    return _sentence_around(t, 0, min(len(t), 1), max_len=160)


class RuleEngine:
    def __init__(self, cats: dict):
        self.cats = cats
        self.kw = {c["key"]: [(kw, _kw_regex(kw), 1 + 0.5 * (len(kw.split()) - 1)) for kw in c["keywords"]]
                   for c in cats["categories"]}
        self.other = cats["categories"][-1]["key"]

    def _cat_scores(self, s: str) -> tuple[dict, dict]:
        scores, best = {}, {}
        for key, kws in self.kw.items():
            total, top = 0.0, None
            for _kw, rx, w in kws:
                for m in rx.finditer(s):
                    total += w
                    if top is None or w > top[2]:
                        top = (m.start(), m.end(), w)
            scores[key], best[key] = total, top
        return scores, best

    def classify(self, text: str, subject: str = "", item_title: str = "") -> dict:
        t = norm_ws(text)
        body, best = self._cat_scores(t)
        context, _ = self._cat_scores(norm_ws(subject) + " . " + norm_ws(item_title))
        order = [c["key"] for c in self.cats["categories"]]
        combined = {k: body[k] + 0.75 * context[k] for k in order}
        top = max(order, key=lambda k: (combined[k], -order.index(k)))
        total = sum(combined.values())
        if combined[top] == 0:
            cat, conf = self.other, 0.2
            quote = _first_sentence(t)
        else:
            cat = top
            conf = round(min(0.9, 0.3 + 0.6 * combined[top] / total), 3)
            if best[cat]:
                quote = _sentence_around(t, best[cat][0], best[cat][1])
            else:  # only the subject / item title matched
                quote, conf = _first_sentence(t), round(min(conf, 0.45), 3)
        stance, sev = self.stance(t)
        return {"category": cat, "confidence": conf, "evidence_quote": quote, "stance": stance,
                "stance_evidence": sev}

    @staticmethod
    def stance_hits(t: str) -> list[tuple[int, int, str, float]]:
        raw = []
        for rx, stance, w in STANCE_CUES:
            for m in rx.finditer(t):
                if _NEGATION.search(t[max(0, m.start() - 14):m.start()]):
                    continue
                raw.append((m.start(), m.end(), stance, w))
        raw.sort(key=lambda h: (-h[3], h[0]))
        kept: list[tuple[int, int, str, float]] = []
        for h in raw:  # overlapping cues count once, at the highest weight
            if all(h[1] <= k[0] or h[0] >= k[1] for k in kept):
                kept.append(h)
        return sorted(kept)

    def stance(self, t: str) -> tuple[str, str]:
        hits = self.stance_hits(t)
        tot = Counter()
        for h in hits:
            tot[h[2]] += h[3]
        s, o, n = tot["support"], tot["oppose"], tot["neutral"]
        if s == 0 and o == 0:
            stance = "neutral" if n > 0 else "unclear"
        elif n >= max(s, o):
            stance = "neutral"
        elif s > o:
            stance = "support"
        elif o > s:
            stance = "oppose"
        else:
            stance = "neutral"  # equal support and oppose cues: mixed
        if stance == "unclear":
            return stance, ""
        pool = [h for h in hits if h[2] == stance] or hits
        h = max(pool, key=lambda h: (h[3], -h[0]))
        return stance, _sentence_around(t, h[0], h[1])


# ---------------------------------------------------------------- Ollama / Granite
class OllamaUnavailable(Exception):
    pass


def ollama_model_available(host: str = OLLAMA_HOST, wanted: str = OLLAMA_MODEL) -> tuple[str | None, str]:
    try:
        r = httpx.get(f"{host}/api/tags", timeout=5)
        r.raise_for_status()
    except Exception as e:  # noqa: BLE001
        return None, f"Ollama not reachable at {host} ({type(e).__name__})"
    names = {m.get("name") for m in r.json().get("models", [])}
    for cand in [wanted] + [m for m in MODEL_FALLBACKS if m != wanted]:
        if cand in names or f"{cand}:latest" in names:
            return cand, ""
    return None, f"model {wanted} not pulled in Ollama (have: {sorted(n for n in names if n)})"


def ollama_chat(messages: list[dict], schema: dict, model: str, host: str = OLLAMA_HOST) -> dict:
    """One /api/chat call. Separate function so tests can mock it."""
    r = httpx.post(f"{host}/api/chat", json={
        "model": model, "messages": messages, "format": schema, "stream": False, "keep_alive": "30m",
        "options": {"temperature": 0, "seed": SEED, "num_ctx": 8192},
    }, timeout=300)
    r.raise_for_status()
    return r.json()


class GraniteEngine:
    def __init__(self, cats: dict, prompt: dict, model: str, chat=None):
        self.cats, self.prompt, self.model = cats, prompt, model
        self.schema = response_schema(cats)
        self.chat = chat or (lambda msgs: ollama_chat(msgs, self.schema, model))
        self.system = prompt["system"].format(categories_block=categories_block(cats),
                                              stance_definition=cats["stance_definition"])
        self.eval_tokens = 0
        self.eval_ns = 0

    def user_message(self, row: dict) -> str:
        text = str(row.get("text") or "")
        return self.prompt["user"].format(language=row.get("language") or "unknown", item=row.get("item") or "",
                                          item_title=row.get("item_title") or "", subject=row.get("subject") or "",
                                          text=text[:MAX_CHARS])

    def classify(self, row: dict) -> tuple[dict | None, str]:
        """Returns (label, failure_reason). label None means: fall back to rules for this row."""
        text = str(row.get("text") or "")
        msgs = [{"role": "system", "content": self.system}, {"role": "user", "content": self.user_message(row)}]
        errs: list[str] = []
        for attempt in range(2):
            try:
                resp = self.chat(msgs)
            except Exception as e:  # noqa: BLE001
                return None, f"ollama error: {type(e).__name__}: {e}"[:200]
            self.eval_tokens += int(resp.get("eval_count") or 0)
            self.eval_ns += int(resp.get("eval_duration") or 0)
            content = (resp.get("message") or {}).get("content", "")
            try:
                obj = json.loads(content)
            except json.JSONDecodeError:
                obj = None
            label, errs = validate_label(obj, self.cats, text) if obj is not None else (None, ["invalid JSON"])
            if label:
                label["retried"] = attempt == 1
                return label, ""
            if attempt == 0:
                msgs = msgs + [{"role": "assistant", "content": content}, {"role": "user", "content": (
                    "Your answer was rejected: " + "; ".join(errs) + ". evidence_quote and stance_evidence must be "
                    "copied character for character from the comment text between <<< and >>>, in its original "
                    "language, with no changes, no ellipses and no translation. Return the corrected JSON object.")}]
        return None, "validation failed after retry: " + "; ".join(errs)


# ---------------------------------------------------------------- cache
def cache_key(model: str, prompt_version: str, text: str) -> str:
    return hashlib.sha256(f"{model}\x1f{prompt_version}\x1f{text}".encode()).hexdigest()


def load_cache() -> dict:
    try:
        return json.loads(CACHE_PATH.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_cache(cache: dict) -> None:
    tmp = CACHE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(cache, ensure_ascii=False, sort_keys=True))
    tmp.replace(CACHE_PATH)


# ---------------------------------------------------------------- inputs
def load_voice() -> pd.DataFrame:
    frames = []
    for p in INPUTS:
        if not p.exists():
            warn(f"{p.relative_to(ROOT)} is missing; classifying without it")
            continue
        frames.append(pd.read_csv(p, dtype=str, keep_default_na=False))
    if not frames:
        raise SystemExit("no voice inputs found")
    df = pd.concat(frames, ignore_index=True)
    bad = df[~df["channel"].map(lambda c: FAMILY_OF.get(c) == "voice")]
    if len(bad):
        raise SystemExit(f"channel separation: refusing to classify non-voice rows: {sorted(set(bad['channel']))}")
    assert df["comment_id"].is_unique, "comment_id must be unique across voice inputs"
    return df


def row_language(row: dict) -> str:
    lang = (row.get("language") or "").strip()
    if lang:
        return lang
    try:
        from langdetect import DetectorFactory, detect
        DetectorFactory.seed = 0
        return detect(str(row.get("text") or "")[:2000])
    except Exception:  # noqa: BLE001
        return "unknown"


# ---------------------------------------------------------------- dedup
def identity_duplicates(df: pd.DataFrame) -> tuple[dict, dict]:
    """(a) same identity_hash + near-identical text, across channels or as a resubmission within one item.
    Existing duplicate_of values are kept. Returns ({comment_id: duplicate_of}, stats)."""
    from rapidfuzz import fuzz
    dup = {r["comment_id"]: r["duplicate_of"] for _, r in df.iterrows() if r.get("duplicate_of")}
    stats = {"kept_existing": len(dup), "added": 0, "same_sender_other_item_not_marked": 0}
    rows = df[df["identity_hash"] != ""].sort_values(["received_at", "comment_id"])
    for _h, g in rows.groupby("identity_hash"):
        if len(g) < 2:
            continue
        recs = g.to_dict("records")
        for j, later in enumerate(recs):
            if later["comment_id"] in dup:
                continue
            for earlier in recs[:j]:
                if earlier["comment_id"] in dup:  # compare against originals only
                    continue
                cross_channel = earlier["channel"] != later["channel"]
                same_item = earlier["item"] == later["item"]
                ratio = fuzz.ratio(norm_ws(earlier["text"]).lower(), norm_ws(later["text"]).lower())
                if ratio < DUP_RATIO_MIN:
                    continue
                if cross_channel or same_item:
                    dup[later["comment_id"]] = dup.get(earlier["comment_id"]) or earlier["comment_id"]
                    stats["added"] += 1
                    break
                stats["same_sender_other_item_not_marked"] += 1
    return dup, stats


_SALUTATION = re.compile(r"^\s*(?:dear|hello|hi|hey|greetings|good (?:morning|afternoon|evening)|to the|to whom|"
                         r"honorable|estimad[oa]s?|buen[oa]s|kính gửi|councilmembers?|council|mayor)\b.{0,70}$",
                         re.IGNORECASE)
_SIGNOFF = re.compile(r"^\s*(?:\[name removed\]|thanks?|thank you|best|regards|sincerely|cheers|gracias|"
                      r"xin cảm ơn|cảm ơn)[\s,.!\[\]a-z]*$", re.IGNORECASE)


def strip_envelope(text: str) -> str:
    """Drop the salutation line and sign-off/name lines so form letters with different greetings still match."""
    lines = [ln for ln in str(text or "").splitlines() if ln.strip()]
    if lines and len(lines[0]) <= 80 and _SALUTATION.match(lines[0]):
        lines = lines[1:]
    while lines and len(lines[-1]) <= 60 and _SIGNOFF.match(lines[-1]):
        lines = lines[:-1]
    return "\n".join(lines)


def _shingles(text: str) -> set[str]:
    toks = re.findall(r"\w+", norm_ws(strip_envelope(text)).lower())
    if len(toks) < SHINGLE:
        return {" ".join(toks)} if toks else set()
    return {" ".join(toks[i:i + SHINGLE]) for i in range(len(toks) - SHINGLE + 1)}


def find_campaigns(df: pd.DataFrame) -> tuple[dict, list[dict]]:
    """(b) MinHash/LSH form-letter detection within voice. Candidates from LSH are verified with exact Jaccard
    on the shingle sets, so the result is deterministic. Returns ({comment_id: campaign_id}, summaries)."""
    from datasketch import MinHash, MinHashLSH
    recs = df.to_dict("records")
    sh = {r["comment_id"]: _shingles(r["text"]) for r in recs}
    lsh = MinHashLSH(threshold=LSH_THRESHOLD, num_perm=NUM_PERM)
    mh = {}
    for cid, s in sh.items():
        if not s:
            continue
        m = MinHash(num_perm=NUM_PERM, seed=1)
        for x in sorted(s):
            m.update(x.encode())
        mh[cid] = m
        lsh.insert(cid, m)
    parent = {cid: cid for cid in mh}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def jac(a, b):
        A, B = sh[a], sh[b]
        return len(A & B) / len(A | B) if A | B else 0.0

    def similar(a, b):
        A, B = sh[a], sh[b]
        if jac(a, b) >= JACCARD_MIN:
            return True
        small = min(len(A), len(B))
        return small >= OVERLAP_MIN_SHINGLES and len(A & B) / small >= JACCARD_MIN

    for cid in sorted(mh):
        for other in sorted(lsh.query(mh[cid])):
            if other != cid and similar(cid, other):
                ra, rb = find(cid), find(other)
                if ra != rb:
                    parent[max(ra, rb)] = min(ra, rb)
    groups = defaultdict(list)
    for cid in mh:
        groups[find(cid)].append(cid)
    by_id = {r["comment_id"]: r for r in recs}
    comps = [sorted(g) for g in groups.values() if len(g) >= CAMPAIGN_MIN_ROWS]
    comps.sort(key=lambda g: (-len(g), g[0]))
    assign, summaries = {}, []
    for i, members in enumerate(comps, 1):
        camp = f"C{i:02d}"
        rep = max(members, key=lambda c: (sum(jac(c, o) for o in members if o != c), -members.index(c)))
        common = {x for x in sh[rep] if sum(x in sh[m] for m in members) >= 0.8 * len(members)}
        items = Counter(by_id[m]["item"] for m in members)
        for m in members:
            assign[m] = camp
        summaries.append({
            "campaign_id": camp, "size": len(members),
            "size_excluding_duplicates": sum(1 for m in members if not by_id[m].get("duplicate_of")),
            "distinct_senders": len({by_id[m]["identity_hash"] or m for m in members}),
            "item": items.most_common(1)[0][0], "items": dict(items),
            "channels": dict(Counter(by_id[m]["channel"] for m in members)),
            "representative_comment_id": rep,
            "template_snippet": _template_snippet(by_id[rep]["text"], common),
            "min_pairwise_jaccard_to_rep": round(min(jac(rep, o) for o in members if o != rep), 3),
            "comment_ids": members,
        })
    return assign, summaries


def _template_snippet(text: str, common: set[str], limit: int = 200) -> str:
    """Longest run of the representative's text whose 5-word shingles are shared by >= 80% of the campaign."""
    t = norm_ws(text)
    words = list(re.finditer(r"\w+", t))
    toks = [w.group().lower() for w in words]
    best, cur_start, best_rng = 0, None, None
    for i in range(len(toks) - SHINGLE + 1):
        if " ".join(toks[i:i + SHINGLE]) in common:
            cur_start = i if cur_start is None else cur_start
            n = i - cur_start + SHINGLE
            if n > best:
                best, best_rng = n, (cur_start, i + SHINGLE - 1)
        else:
            cur_start = None
    if not best_rng:
        return t[:limit]
    s, e = words[best_rng[0]].start(), words[best_rng[1]].end()
    snip = t[s:e]
    if len(snip) > limit:
        cut = snip.rfind(" ", 0, limit)
        snip = snip[:cut if cut > 0 else limit]
    return snip


# ---------------------------------------------------------------- provenance
def upsert_provenance(records: list[dict]) -> None:
    PROVENANCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        prov = json.loads(PROVENANCE_PATH.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        prov = {}
    existing = {r["step"]: r for r in prov.get("records", [])}
    for r in records:
        existing[r["step"]] = r
    prov = {"schema": 1, "note": "One record per pipeline step, latest run. Bob run history: data/bob_runs.json.",
            "updated_at": now(), "records": sorted(existing.values(), key=lambda r: r.get("started_at") or "")}
    PROVENANCE_PATH.write_text(json.dumps(prov, indent=2, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------- labeled sample
def write_sample(out: pd.DataFrame, raw: pd.DataFrame, n: int = 100, seed: int = 7) -> dict:
    m = out.merge(raw[["comment_id", "text"]], on="comment_id")
    m = m[m["duplicate_of"] == ""]
    non_en = m[m["language"] != "en"]
    en = m[m["language"] == "en"]
    take_non = non_en if len(non_en) < n // 2 else non_en.sample(n // 2, random_state=seed)
    need = n - len(take_non)
    # spread English picks across channel x item, one campaign member at most per campaign
    en = en.sample(frac=1, random_state=seed)
    en = pd.concat([en[en["campaign_id"] == ""], en[en["campaign_id"] != ""].drop_duplicates("campaign_id")])
    en = en.assign(_rk=en.groupby(["channel", "item"]).cumcount()).sort_values(["_rk", "channel", "item"])
    take_en = en.head(need)
    s = pd.concat([take_non, take_en]).sort_values(["channel", "language", "comment_id"])
    tpl = pd.DataFrame({
        "comment_id": s["comment_id"], "channel": s["channel"], "language": s["language"],
        "text_excerpt": s["text"].map(lambda t: norm_ws(t)[:400]),
        "predicted_category": s["category"], "predicted_stance": s["stance"],
        "true_category": "", "true_stance": "",
    })
    tpl.to_csv(SAMPLE_PATH, index=False)
    return {"rows": len(tpl), "non_english": int((tpl["language"] != "en").sum()),
            "english": int((tpl["language"] == "en").sum())}


# ---------------------------------------------------------------- main
def corpus_fingerprint(df: pd.DataFrame) -> dict:
    h = hashlib.sha256()
    for cid, text in sorted(zip(df["comment_id"], df["text"])):
        h.update(f"{cid}\x1f{text}\x1e".encode())
    return {"n_comments": int(len(df)), "by_channel": dict(Counter(df["channel"])), "sha256": h.hexdigest()[:16]}


def run(engine_pref: str = "auto", item: str | None = None, use_cache: bool = True, limit: int | None = None,
        chat=None, cache_only: bool = False) -> dict:
    started = now()
    t0 = time.time()
    cats = load_categories()
    prompt = load_prompt()
    pver = f"{prompt['version']}+cats-{categories_hash(cats)}"
    raw = load_voice()
    rules = RuleEngine(cats)

    granite, fallback_reason, model = None, "", None
    if cache_only:
        model = OLLAMA_MODEL
        def no_calls(_msgs):
            raise RuntimeError("cache-only mode: refusing to call Ollama")
        granite = GraniteEngine(cats, prompt, model, chat=no_calls)
    elif engine_pref == "rules":
        fallback_reason = "rule engine forced (--engine rules)"
    elif chat is not None:
        model = OLLAMA_MODEL
        granite = GraniteEngine(cats, prompt, model, chat=chat)
    else:
        model, why = ollama_model_available()
        if model:
            granite = GraniteEngine(cats, prompt, model)
        else:
            fallback_reason = why
            if engine_pref == "ollama":
                raise SystemExit(f"--engine ollama requested but {why}")
    if granite is None:
        warn(f"Granite/Ollama unavailable -> deterministic RULE ENGINE for every row. Reason: {fallback_reason}")

    dup, dup_stats = identity_duplicates(raw)
    camp, campaigns = find_campaigns(raw.assign(duplicate_of=raw["comment_id"].map(lambda c: dup.get(c, ""))))

    todo = raw if not item or item == "all" else raw[raw["item"] == item]
    if limit:
        todo = todo.head(limit)
    cache = load_cache() if use_cache else {}
    counts = Counter()
    fallback_rows: list[dict] = []
    results = []
    for i, row in enumerate(todo.to_dict("records"), 1):
        text = str(row["text"] or "")
        lang = row_language(row)
        row["language"] = lang
        label, eng, mdl = None, None, None
        if granite:
            key = cache_key(granite.model, pver, granite.user_message(row))
            hit = cache.get(key) if use_cache else None
            if cache_only and hit is None:
                for alt in MODEL_FALLBACKS:
                    hit = cache.get(cache_key(alt, pver, granite.user_message(row)))
                    if hit is not None:
                        break
            if hit is not None and "_failed" in hit:  # Granite was rejected for this text before: rules
                counts["cache_hits"] += 1
                fallback_rows.append({"comment_id": row["comment_id"], "reason": hit["_failed"] + " (cached)"})
            elif hit is not None:
                label, eng, mdl = dict(hit), "ollama", granite.model
                counts["cache_hits"] += 1
            elif cache_only:
                raise SystemExit(f"--cache-only: {row['comment_id']} is not in {CACHE_PATH.name} for prompt "
                                 f"{pver}; run a warm build (npm run data) to classify it")
            else:
                label, why = granite.classify(row)
                if label:
                    eng, mdl = "ollama", granite.model
                    counts["retried_ok"] += int(label.pop("retried", False))
                    cache[key] = label
                    if i % 10 == 0:
                        save_cache(cache)
                else:
                    fallback_rows.append({"comment_id": row["comment_id"], "reason": why})
                    if why.startswith("validation failed"):  # deterministic at temperature 0: remember it
                        cache[key] = {"_failed": why}
                    warn(f"{row['comment_id']}: Granite label rejected, using rules ({why})")
        if label is None:
            key = cache_key(RULES_MODEL, pver, f"{row.get('subject')}\x1f{row.get('item_title')}\x1f{text}")
            label = cache.get(key) if use_cache else None
            if label is None and cache_only:
                raise SystemExit(f"--cache-only: rule label for {row['comment_id']} is not cached")
            if label is None:
                label = rules.classify(text, row.get("subject", ""), row.get("item_title", ""))
                cache[key] = label
            eng, mdl = "fallback", RULES_MODEL
        counts[eng] += 1
        results.append({
            "comment_id": row["comment_id"], "channel": row["channel"], "item": row["item"],
            "category": label["category"], "confidence": label["confidence"],
            "evidence_quote": label["evidence_quote"], "stance": label["stance"],
            "stance_source": "llm" if eng == "ollama" else "rule", "stance_evidence": label["stance_evidence"],
            "language": lang, "engine": eng, "model": mdl,
        })
        if i % 25 == 0:
            print(f"  {i}/{len(todo)} classified ({dict(counts)}) {time.time() - t0:.0f}s", flush=True)
    save_cache(cache)

    new = pd.DataFrame(results)
    if OUT_CSV.exists() and item and item != "all":
        old = pd.read_csv(OUT_CSV, dtype=str, keep_default_na=False)
        new = pd.concat([old[~old["comment_id"].isin(new["comment_id"])], new.astype(str)])
    new["campaign_id"] = new["comment_id"].map(lambda c: camp.get(c, ""))
    new["duplicate_of"] = new["comment_id"].map(lambda c: dup.get(c, ""))
    order = {c: i for i, c in enumerate(raw["comment_id"])}
    new = new.sort_values("comment_id", key=lambda s: s.map(order))[OUT_COLS]
    new.to_csv(OUT_CSV, index=False)
    for c in campaigns:
        c["stance"] = dict(Counter(new.set_index("comment_id")["stance"].reindex(c["comment_ids"]).dropna()))
    CAMPAIGNS_PATH.write_text(json.dumps({
        "method": f"MinHash/LSH ({NUM_PERM} perms, candidate threshold {LSH_THRESHOLD}) over {SHINGLE}-word shingles "
                  f"of the text with salutation and sign-off lines removed; an edge needs Jaccard >= {JACCARD_MIN} or "
                  f"overlap coefficient >= {JACCARD_MIN} (both texts >= {OVERLAP_MIN_SHINGLES} shingles), verified "
                  f"on exact shingle sets; campaigns are connected components with >= {CAMPAIGN_MIN_ROWS} rows; "
                  "voice family only",
        "counting_rule": "Downstream counts a campaign once by default (one voice per campaign_id), with the "
                         "campaign size shown alongside.",
        "campaigns": campaigns}, indent=2, ensure_ascii=False) + "\n")
    sample = write_sample(new, raw)
    finished = now()
    wall = round(time.time() - t0, 1)
    tps = round(granite.eval_tokens / (granite.eval_ns / 1e9), 1) if granite and granite.eval_ns else None

    reasons = Counter(r["reason"].split(":")[0] for r in fallback_rows)
    classify_rec = {
        "step": "classify_cache_replay" if cache_only else "classify",
        "engine": "cache" if cache_only else ("ollama" if counts["ollama"] else "fallback"),
        "model": (granite.model if granite else RULES_MODEL),
        "reason": ("--cache-only: no model calls; labels replayed from data/classify_cache.json. " if cache_only
                   else "") + (fallback_reason or ("" if not fallback_rows else
                               f"{len(fallback_rows)} rows fell back to rules: {dict(reasons)}")),
        "started_at": started, "finished_at": finished, "wall_seconds": wall,
        "counts": {"rows": len(todo), "ollama": counts["ollama"], "fallback": counts["fallback"],
                   "cache_hits": counts["cache_hits"], "ollama_retried_ok": counts["retried_ok"],
                   "by_channel": dict(Counter(new["channel"])),
                   "by_engine_and_channel": {f"{e}/{c}": int(n) for (e, c), n in
                                             new.groupby(["engine", "channel"]).size().items()}},
        "fallback_rows": fallback_rows,
        "tokens_per_second": tps, "prompt_version": pver, "item": item or "all",
        "categories_source": cats.get("source"),
    }
    bob_reason = os.environ.get("BOB_FALLBACK_REASON", "")
    by_bob = cats.get("authored_by") == "ibm-bob"
    taxonomy_rec = {
        "step": "taxonomy", "engine": "bob" if by_bob else "fallback",
        "model": "IBM Bob Shell" if by_bob else None,
        "reason": "" if by_bob else ("IBM Bob did not author the taxonomy" + (f" ({bob_reason})" if bob_reason else "")
                                     + "; data/categories.json was written by the build agent"),
        "bob_task_ids": cats.get("bob_task_ids", []), "authored_on": cats.get("authored_on"),
        "taxonomy_version": cats.get("version"), "prompt_version": prompt["version"],
        "started_at": started, "finished_at": started,
        "counts": {"categories": len(cats["categories"])}, "categories_source": cats.get("source"),
    }
    dedup_rec = {
        "step": "dedup_campaigns", "engine": "fallback", "model": "rapidfuzz+datasketch",
        "reason": "deterministic, no model involved",
        "started_at": started, "finished_at": finished,
        "counts": {**dup_stats, "duplicates_total": sum(1 for v in dup.values() if v),
                   "campaigns": len(campaigns), "campaign_rows": len(camp),
                   "campaign_sizes": {c["campaign_id"]: c["size"] for c in campaigns}},
        "categories_source": cats.get("source"),
    }
    upsert_provenance([classify_rec] if cache_only else [taxonomy_rec, dedup_rec, classify_rec])
    summary = {"counts": dict(counts), "wall_seconds": wall, "tokens_per_second": tps,
               "fallback_rows": len(fallback_rows), "fallback_reasons": dict(reasons),
               "campaigns": {c["campaign_id"]: (c["size"], c["item"]) for c in campaigns},
               "duplicates": dedup_rec["counts"], "sample": sample}
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return summary


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--engine", choices=["auto", "ollama", "rules"], default="auto")
    ap.add_argument("--item", default="all", help="agenda item / matter to classify, or 'all'")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--cache-only", action="store_true", help="offline: no model calls; fail if a row is not cached")
    ap.add_argument("--fingerprint", action="store_true", help="print the voice corpus fingerprint and exit")
    a = ap.parse_args()
    if a.fingerprint:
        print(json.dumps(corpus_fingerprint(load_voice())))
        return
    run(a.engine, a.item, not a.no_cache, a.limit, cache_only=a.cache_only)


if __name__ == "__main__":
    main()
