"""Tests for scripts/classify.py. No network: Ollama is always mocked."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import classify as C  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures"
CATS = C.load_categories(FIXTURES / "categories_fixture.json")  # synthetic taxonomy, independent of the live one
KEYS = [c["key"] for c in CATS["categories"]]
PROMPT = C.load_prompt(FIXTURES / "classify_prompt_fixture.txt")
LIVE = C.CATEGORIES_PATH.exists()


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("network call attempted in tests")
    monkeypatch.setattr(C.httpx, "get", boom)
    monkeypatch.setattr(C.httpx, "post", boom)


def _corpus() -> pd.DataFrame:
    frames = [pd.read_csv(p, dtype=str, keep_default_na=False) for p in C.INPUTS if p.exists()]
    return pd.concat(frames, ignore_index=True)


# ------------------------------------------------------------------ taxonomy
@pytest.mark.skipif(not LIVE, reason="data/categories.json not built yet")
def test_live_taxonomy_shape_and_examples_are_real():
    live = C.load_categories()  # raises SystemExit on any schema problem
    text = " ".join(C.norm_ws(t) for t in _corpus()["text"])
    for c in live["categories"]:
        assert 2 <= len(c["examples"]) <= 3, c["key"]
        hits = sum(C.find_span(e, text) is not None for e in c["examples"])
        assert hits >= 1, f"{c['key']}: no example phrase occurs in the corpus"
    assert live.get("authored_by") in {"ibm-bob", "build-agent"}


def test_schema_validation_of_taxonomy_file(tmp_path):
    bad = json.loads((FIXTURES / "categories_fixture.json").read_text())
    bad["categories"][0]["maps_311"] = ["not_a_311_key"]
    del bad["categories"][1]["keywords"]
    p = tmp_path / "c.json"
    p.write_text(json.dumps(bad))
    with pytest.raises(SystemExit, match="maps_311 has unknown 311 keys"):
        C.load_categories(p)


def test_prompt_contract_is_enforced(tmp_path):
    p = tmp_path / "p.txt"
    p.write_text("# prompt_version: x\n=== SYSTEM ===\nUse {categories_block} {oops}\n=== USER ===\n{text}\n")
    with pytest.raises(SystemExit, match="unknown placeholders"):
        C.load_prompt(p)


# ------------------------------------------------------------------ rule engine
def test_fallback_is_deterministic():
    eng1, eng2 = C.RuleEngine(CATS), C.RuleEngine(CATS)
    rows = _corpus().head(60).to_dict("records")
    a = [eng1.classify(r["text"], r["subject"], r["item_title"]) for r in rows]
    b = [eng2.classify(r["text"], r["subject"], r["item_title"]) for r in rows]
    c = [eng1.classify(r["text"], r["subject"], r["item_title"]) for r in rows]
    assert a == b == c


def test_rule_evidence_is_exact_substring_on_whole_corpus():
    eng = C.RuleEngine(CATS)
    for r in _corpus().to_dict("records"):
        lab = eng.classify(r["text"], r["subject"], r["item_title"])
        assert lab["category"] in KEYS
        assert C.is_exact_substring(lab["evidence_quote"], r["text"]), r["comment_id"]
        if lab["stance_evidence"]:
            assert C.is_exact_substring(lab["stance_evidence"], r["text"]), r["comment_id"]


def test_written_classifications_have_exact_substrings():
    out = ROOT / "data" / "classifications.csv"
    if not out.exists() or not LIVE:
        pytest.skip("classifications.csv not built yet")
    live_keys = {c["key"] for c in C.load_categories()["categories"]}
    cls = pd.read_csv(out, dtype=str, keep_default_na=False)
    text = _corpus().set_index("comment_id")["text"]
    for r in cls.to_dict("records"):
        assert r["category"] in live_keys
        assert r["stance"] in C.STANCES
        assert C.is_exact_substring(r["evidence_quote"], text[r["comment_id"]]), r["comment_id"]
        if r["stance_evidence"]:
            assert C.is_exact_substring(r["stance_evidence"], text[r["comment_id"]]), r["comment_id"]


@pytest.mark.parametrize("text,stance", [
    ("Estimados concejales, apoyo bajar el límite de aumento de renta.", "support"),
    ("Vivo en Alviso y me opongo al centro de datos Terra Verde.", "oppose"),
    ("Kính gửi Hội đồng, Tôi ủng hộ việc giảm mức trần tăng tiền thuê nhà hàng năm.", "support"),
    ("Kính gửi quý vị, Tôi PHẢN ĐỐI việc cắt giảm giờ của trung tâm người cao tuổi.", "oppose"),
    ("I strongly SUPPORT legalizing fourplexes citywide.", "support"),
    ("I OPPOSE lowering the rent cap.", "oppose"),
    ("Please vote no to lowering voter thresholds for taxes.", "oppose"),
    ("I'm genuinely torn. I see both sides.", "neutral"),
    ("Please see the attached letter.", "unclear"),
    ("I'm not against a cap in principle.", "unclear"),
])
def test_stance_cues_multilingual(text, stance):
    got, ev = C.RuleEngine(CATS).stance(text)
    assert got == stance
    assert ev == "" or C.is_exact_substring(ev, text)


def test_spanish_and_vietnamese_categories():
    eng = C.RuleEngine(CATS)
    assert eng.classify("El bache enorme en Alma Avenue sigue sin arreglarse.")["category"] == "roads"
    assert eng.classify("Khu căn hộ của chúng tôi đã mất nước nóng hơn một tuần.")["category"] == "rent"
    assert eng.classify("Hello there.")["category"] == "misc"  # catch-all is the last category


# ------------------------------------------------------------------ schema validation
GOOD_TEXT = "I live in Alviso and I am strongly OPPOSED to the proposed Terra Verde data center off Gold Street."


def _label(**kw):
    base = {"category": "development", "confidence": 0.9,
            "evidence_quote": "proposed Terra Verde data center", "stance": "oppose",
            "stance_evidence": "I am strongly OPPOSED"}
    base.update(kw)
    return base


def test_schema_accepts_good_label():
    lab, errs = C.validate_label(_label(), CATS, GOOD_TEXT)
    assert errs == [] and lab["category"] == "development"


def test_schema_rejects_bad_category():
    lab, errs = C.validate_label(_label(category="data_centers"), CATS, GOOD_TEXT)
    assert lab is None and any("category" in e for e in errs)
    assert "data_centers" not in C.response_schema(CATS)["properties"]["category"]["enum"]


@pytest.mark.parametrize("bad", [
    {"stance": "maybe"}, {"confidence": 1.7}, {"confidence": "high"},
    {"evidence_quote": "a data center that is not in the text"},
    {"stance_evidence": "I SUPPORT it"}, {"stance_evidence": ""},
])
def test_schema_rejects_other_violations(bad):
    lab, errs = C.validate_label(_label(**bad), CATS, GOOD_TEXT)
    assert lab is None and errs


def test_whitespace_and_quote_folding():
    text = "The City’s   commitment\nto all residents"
    assert C.find_span("The City's commitment to all", text) == "The City’s commitment to all"
    assert C.is_exact_substring(C.find_span("The City's commitment to all", text), text)
    assert C.find_span("The City's commitment to everyone", text) is None


# ------------------------------------------------------------------ Granite engine (mocked)
def _resp(obj, n=20):
    return {"message": {"content": json.dumps(obj)}, "eval_count": n, "eval_duration": 10**9}


def test_granite_retry_then_success():
    calls = []

    def chat(msgs):
        calls.append(msgs)
        return _resp(_label(evidence_quote="invented words") if len(calls) == 1 else _label())

    eng = C.GraniteEngine(CATS, PROMPT, "granite4.1:8b", chat=chat)
    lab, why = eng.classify({"text": GOOD_TEXT, "language": "en", "item": "X", "item_title": "", "subject": ""})
    assert lab and lab["retried"] and why == ""
    assert len(calls) == 2 and "rejected" in calls[1][-1]["content"]


def test_granite_two_failures_fall_back():
    eng = C.GraniteEngine(CATS, PROMPT, "granite4.1:8b",
                          chat=lambda m: _resp(_label(category="nope")))
    lab, why = eng.classify({"text": GOOD_TEXT, "language": "en"})
    assert lab is None and "validation failed" in why


def test_prompt_renders_and_sends_original_language():
    eng = C.GraniteEngine(CATS, PROMPT, "granite4.1:8b", chat=lambda m: _resp(_label()))
    msg = eng.user_message({"text": "Vivo en Alviso y me OPONGO.", "language": "es", "item": "MOCK-26-901",
                            "item_title": "Terra Verde", "subject": "Oposición"})
    assert "Vivo en Alviso y me OPONGO." in msg and "Comment language: es" in msg
    assert all(k in eng.system for k in KEYS)
    long = eng.user_message({"text": "z" * 9000, "language": "en"})
    assert long.count("z") == C.MAX_CHARS


def test_run_end_to_end_with_mocked_ollama(tmp_path, monkeypatch):
    raw = pd.DataFrame([
        {"comment_id": "E1", "item": "I1", "item_title": "Terra Verde", "channel": "email", "text": GOOD_TEXT,
         "subject": "no", "language": "en", "identity_hash": "h1", "duplicate_of": "", "received_at": "1"},
        {"comment_id": "E2", "item": "I1", "item_title": "Terra Verde", "channel": "email",
         "text": "Vivo en Alviso y me opongo al centro de datos.", "subject": "", "language": "es",
         "identity_hash": "h2", "duplicate_of": "", "received_at": "2"},
    ])
    p = tmp_path / "emails_raw.csv"
    raw.to_csv(p, index=False)
    for name, val in [("INPUTS", [p]), ("CACHE_PATH", tmp_path / "cache.json"), ("OUT_CSV", tmp_path / "c.csv"),
                      ("CATEGORIES_PATH", FIXTURES / "categories_fixture.json"),
                      ("PROMPT_PATH", FIXTURES / "classify_prompt_fixture.txt"),
                      ("CAMPAIGNS_PATH", tmp_path / "camp.json"), ("SAMPLE_PATH", tmp_path / "s.csv"),
                      ("PROVENANCE_PATH", tmp_path / "prov.json")]:
        monkeypatch.setattr(C, name, val)

    def chat(msgs):
        user = msgs[1]["content"]
        if "Vivo en Alviso" in user:  # Spanish row: model answers in Spanish, validated as substring
            return _resp(_label(evidence_quote="me opongo al centro de datos", stance_evidence="me opongo"))
        return _resp(_label())

    s = C.run(chat=chat)
    assert s["counts"]["ollama"] == 2
    out = pd.read_csv(tmp_path / "c.csv", dtype=str, keep_default_na=False)
    assert list(out["stance_source"]) == ["llm", "llm"] and set(out["engine"]) == {"ollama"}
    prov = json.loads((tmp_path / "prov.json").read_text())
    steps = {r["step"]: r for r in prov["records"]}
    assert steps["classify"]["engine"] == "ollama" and steps["taxonomy"]["engine"] == "fallback"
    s2 = C.run(chat=lambda m: (_ for _ in ()).throw(AssertionError("cache miss")))
    assert s2["counts"]["cache_hits"] == 2
    sample = pd.read_csv(tmp_path / "s.csv", dtype=str, keep_default_na=False)
    assert (sample["true_category"] == "").all() and (sample["true_stance"] == "").all()

    # offline replay: no chat function at all, labels come from the cache, own provenance step
    s3 = C.run(cache_only=True)
    assert s3["counts"]["cache_hits"] == 2
    steps = {r["step"]: r for r in json.loads((tmp_path / "prov.json").read_text())["records"]}
    assert steps["classify_cache_replay"]["engine"] == "cache"
    assert steps["classify"]["engine"] == "ollama"  # the real run's record is not overwritten

    # a new comment that is not cached makes the offline replay fail loudly
    pd.concat([raw, raw.head(1).assign(comment_id="E3", text="Brand new comment about potholes.")]).to_csv(p, index=False)
    with pytest.raises(SystemExit, match="cache-only"):
        C.run(cache_only=True)


def test_bob_label_offline_never_calls_bob(monkeypatch, tmp_path):
    """npm run demo passes --offline: Bob labeling must replay the cache and never start a Bob run."""
    if not LIVE:
        pytest.skip("data/categories.json not built yet")
    import sys as _sys
    _sys.path.insert(0, str(ROOT / "scripts"))
    import bob_label as B

    def boom(*a, **k):
        raise AssertionError("Bob was called in --offline mode")

    monkeypatch.setattr(B, "bob", boom)
    monkeypatch.setattr(B.C, "load_cache", lambda: {})  # empty cache and no saved batch files:
    monkeypatch.setattr(B, "WORK", tmp_path / "empty")    # offline must refuse, not call Bob
    monkeypatch.setattr(_sys, "argv", ["bob_label.py", "--offline"])
    with pytest.raises(SystemExit, match="--offline"):
        B.main()


def test_refuses_311_rows(tmp_path, monkeypatch):
    p = tmp_path / "x.csv"
    pd.DataFrame([{"comment_id": "R1", "channel": "311", "text": "pothole"}]).to_csv(p, index=False)
    monkeypatch.setattr(C, "INPUTS", [p])
    with pytest.raises(SystemExit, match="channel separation"):
        C.load_voice()


# ------------------------------------------------------------------ dedup / campaigns
TEMPLATE = ("I'm writing to SUPPORT emergency funding to restore and protect the streetlights along the Story Road "
            "and King Road corridor. These lights have been dark for weeks and residents, seniors and students "
            "walking home are at risk. Please fund theft-resistant wiring and faster outage response now.")


def _df(rows):
    base = {"item": "I", "item_title": "", "channel": "email", "subject": "", "language": "en",
            "identity_hash": "", "duplicate_of": "", "received_at": ""}
    return pd.DataFrame([{**base, **r} for r in rows])


def test_minhash_groups_obvious_form_letter():
    rows = [{"comment_id": f"F{i}", "identity_hash": f"h{i}",
             "text": f"{greet}\n\n{TEMPLATE}\n\n{extra}\n\n[name removed]"}
            for i, (greet, extra) in enumerate([("Dear Council,", "I live near Tully."),
                                                ("Hello,", "My kids walk this route."),
                                                ("To the Mayor and Council,", ""),
                                                ("Hi Council,", "Thank you.")])]
    rows.append({"comment_id": "X1", "identity_hash": "hx",
                 "text": "There is a huge pothole on Alma Avenue near Washington that blew my tire this morning."})
    assign, summ = C.find_campaigns(_df(rows))
    assert {assign.get(f"F{i}") for i in range(4)} == {"C01"}
    assert "X1" not in assign
    assert summ[0]["size"] == 4 and len(summ[0]["template_snippet"]) <= 200
    assert "SUPPORT emergency funding" in summ[0]["template_snippet"]
    assert C.find_campaigns(_df(rows)) == (assign, summ)  # deterministic


def test_identity_duplicates_cross_channel_and_existing_kept():
    rows = [
        {"comment_id": "L1", "channel": "letter", "item": "A", "identity_hash": "same", "text": TEMPLATE,
         "received_at": "2025-01-01"},
        {"comment_id": "E1", "channel": "email", "item": "B", "identity_hash": "same", "text": TEMPLATE + " ",
         "received_at": "2025-01-02"},
        {"comment_id": "E2", "channel": "email", "item": "B", "identity_hash": "other", "text": "x",
         "duplicate_of": "E9"},
        {"comment_id": "L2", "channel": "letter", "item": "C", "identity_hash": "same", "text": TEMPLATE,
         "received_at": "2025-01-03"},
    ]
    dup, stats = C.identity_duplicates(_df(rows))
    assert dup["E1"] == "L1"      # same sender, near-identical, other channel
    assert dup["E2"] == "E9"      # existing duplicate_of kept
    assert "L2" not in dup        # same sender + channel, different item: counted on both items
    assert stats["same_sender_other_item_not_marked"] >= 1
