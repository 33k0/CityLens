"""Email channel ingest: topic assignment, PII scrubbing, portal duplicates. Synthetic inputs only."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import ingest_emails as ie  # noqa: E402


def test_strong_cue_beats_weak_cue():
    # "rent cap" (strong, rent) outweighs "more homes" (weak, fourplex)
    assert ie.assign_item("", "against", "I OPPOSE the rent cap. Approve more homes instead.")[0] == "MOCK-26-906"
    # weak-only tie resolves to the earlier item (fourplex before rent)
    assert ie.assign_item("", "renters need you", "As a renter I support this. More homes is how prices come down.")[0] == "MOCK-26-905"
    assert ie.assign_item("", "dark", "the lights went out near King and crime is up")[0] == "MOCK-26-902"
    assert ie.assign_item("", "x", "everything is too expensive")[0] == "MOCK-GEN"


def test_non_english_cues():
    assert ie.assign_item("", "Sin agua caliente", "")[0] == "MOCK-26-904"
    assert ie.assign_item("", "Đèn đường tắt", "")[0] == "MOCK-26-902"


def test_scrub_removes_sender_and_signers():
    body = "Dear Council,\nI SUPPORT this. Call 408-555-0100 or jane.q@example.com\n\nRespectfully,\nDenise Okafor\nCoordinator"
    out = ie.scrub(body, "Jane Quincy", "jane.q")
    assert "555-0100" not in out and "@" not in out
    assert "Denise Okafor" not in out and "Coordinator" in out
    sig = ie.scrub("I oppose it.\n\nJane Quincy", "Jane Quincy", "jane.q")
    assert "Jane" not in sig


def test_subject_scrub_keeps_org_subject():
    assert ie.scrub("Coalition letter — SUPPORT funding", "", "", signature=False) == "Coalition letter — SUPPORT funding"


def test_commenter_type():
    assert ie.commenter_type("Alviso Neighborhood Advocates (fictional)", "board@x.example.org", "") == "organization"
    assert ie.commenter_type("Property mgmt rep", "m@outlook.com", "") == "developer_or_counsel"
    assert ie.commenter_type("Rina", "rina@gmail.com", "") == "resident"


def test_attachment_parse():
    a = ie.parse_attachment("photo.jpg — https://upload.wikimedia.org/x.jpg")[0]
    assert a["kind"] == "image" and a["served"] is False and a["redacted"] is False
    assert ie.parse_attachment("Letter.pdf (5 pages, letterhead)")[0]["kind"] == "pdf"
    assert ie.parse_attachment("") == []
