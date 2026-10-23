"""Scraper parser test on a saved, name-scrubbed Granicus agenda-item page."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import ingest_ecomments as ing  # noqa: E402

FIX = Path(__file__).parent / "fixtures" / "granicus_item_page.html"


def test_parse_item_page():
    html = FIX.read_text()
    meta, comments, max_page = ing.parse_item_page(html, "2023-06-06_8.4", "https://example.test/item")
    assert meta["item_id"] == "646fdf1a44253859c000c2d3"
    assert meta["item_title"].startswith("8.4 23-842")
    assert meta["meeting_date"] == "2023-06-06"
    assert meta["declared_count"] == 273
    assert max_page == 14
    assert len(comments) == 20  # 20 per page
    c = comments[0]
    assert c.comment_id.startswith("G") and len(c.comment_id) == 9
    assert c.channel == "ecomment" and c.mock is False
    assert c.stance in {"support", "oppose", "neutral", "unclear"}
    assert c.stance_source == "self_reported"
    assert c.received_at.startswith("2023-")  # derived from the ObjectId
    assert c.text and len(c.text) <= 1300


def test_no_names_in_records():
    html = FIX.read_text()
    _, comments, _ = ing.parse_item_page(html, "x", "u")
    for c in comments:
        for v in vars(c).values():
            assert "Commenter " not in str(v)
            assert "/profile/" not in str(v)


def test_exact_duplicates_marked():
    html = FIX.read_text()
    _, comments, _ = ing.parse_item_page(html, "x", "u")
    base = comments[0].comment_id
    comments = comments + [ing.Comment(**{**vars(comments[0])})]
    out = ing.mark_exact_duplicates(comments, {})
    assert out[0].comment_id == base and out[0].duplicate_of is None
    assert out[-1].duplicate_of == base
    assert out[-1].comment_id.startswith(base + "-")
    assert len({c.comment_id for c in out}) == len(out)


def test_objectid_time():
    assert ing.objectid_time("647f5b9cf395e74c8f01b70b").startswith("2023-06-06")
    assert ing.objectid_time("zz") == ""
