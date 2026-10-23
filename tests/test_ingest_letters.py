"""ingest_letters tests on synthetic page text shaped like the Clerk's Outlook bundles."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import ingest_letters as il  # noqa: E402

FOOT = "This message is from outside the City email system. Do not open links or attachments from untrusted sources."
PAGE1 = """Outlook
FW: Item 10.4 - Data center appeal
From City Clerk <city.clerk@sanjoseca.gov>
Date Mon 10/19/2026 5:10 PM
To Agendadesk <Agendadesk@sanjoseca.gov>
1 attachment (631 KB)
Letter.pdf;
From: Jane Q Resident <jane.resident@gmail.com>
Sent: Monday, October 19, 2026 4:15 PM
To: Mahan, Matt <Matt.Mahan@sanjoseca.gov>; Kamei, Rosemary <Rosemary.Kamei@sanjoseca.gov>; Campos,
Pamela <Pamela.Campos@sanjoseca.gov>
Cc: City Clerk <city.clerk@sanjoseca.gov>
Subject: Item 10.4 - Data center appeal
[External Email. Do not open links or attachments from untrusted sources. Learn more]
Dear Council,
I live near the crosswalk at Story and King and I oppose this appeal. Call me at (408) 555-0100.
Jane Q Resident
1234 Tully Rd
San Jose, CA 95122
"""
PAGE2 = """Outlook
FW: Item 10.4 support
From City Clerk <city.clerk@sanjoseca.gov>
Date Tue 10/20/2026 7:41 AM
To Agendadesk <Agendadesk@sanjoseca.gov>
From: Ana Director <ana@coalition.org>
Sent: Monday, October 19, 2026 5:24 PM
To: City Clerk <city.clerk@sanjoseca.gov>
Subject: Item 10.4 support
On behalf of the Berryessa Neighborhood Coalition, we support staff's determination.
Ana Director
Executive Director, Berryessa Neighborhood Coalition
"""
PAGE3 = "EXHIBIT A\nscanned stuff"


def pages():
    return [{"n": 1, "text": PAGE1, "ocr": False}, {"n": 2, "text": PAGE2, "ocr": False}, {"n": 3, "text": PAGE3, "ocr": True}]


def test_split_on_outlook_wrapper():
    parts = il.split_emails(pages())
    assert [(a, b) for a, b, _ in parts] == [(1, 1), (2, 3)]


def test_ocr_logo_and_print_header_continuation():
    # OCR renders the logo as "Ga Outlook"; web-print continuation pages carry "... - Outlook" and are not new units
    p1 = "1/13/25, 9:10 AM Mail - Rules and Open Government Committee Agendas - Outlook\nGa Outlook\n" + PAGE1.split("\n", 1)[1]
    p2 = "1/13/25, 9:10 AM Mail - Rules and Open Government Committee Agendas - Outlook\nSincerely,\nJane\n" + FOOT
    assert il.is_wrapper_start(p1) and not il.is_wrapper_start(p2)
    units = il.split_units([{"n": 1, "text": p1, "ocr": True}, {"n": 2, "text": p2, "ocr": True}])
    assert len(units) == 1 and units[0].kind == "letter"
    assert il.letter_pages(units[0])[:2] == (2, 0)


def test_parse_and_scrub_resident():
    a, b, raw = il.split_emails(pages())[0]
    e = il.parse_email(raw, a, pages())
    assert e["subject"] == "Item 10.4 - Data center appeal"
    assert e["sent"].startswith("Monday, October 19, 2026")
    assert e["body"].startswith("Dear Council")
    assert "External Email" not in e["body"] and "Subject:" not in e["body"] and "Pamela" not in e["body"]
    name, email, h = il.identity(e["sender_line"])
    assert name == "Jane Q Resident" and email == "jane.resident@gmail.com" and h.startswith("sha256:")
    text = il.scrub(e["body"], name)
    assert "Jane" not in text and "555-0100" not in text and "[phone removed]" in text
    loc = il.location_hints(e["body"])
    assert loc["address"] == "1234 Tully Rd" and loc["zip"] == "95122" and loc["cross_street"] == "Story & King"
    assert il.commenter_type(e["sender_line"], email, e["body"]) == "resident"
    assert il.parse_sent(e["sent"]) == "2026-10-19T16:15:00-07:00"


def test_signoff_name_scrub_and_ocr_sender_junk():
    name, _, _ = il.identity("Rob")
    assert "LaNoce" not in il.scrub("Please vote no on item 3.4.\nThanks,\nRob LaNoce", name)
    name, _, _ = il.identity("Refugio Moreno a;")
    assert name == "Refugio Moreno"
    out = il.scrub("I support this.\nBest regards,\nGianella Ordonez | Policy + Advocacy Associate\nSacramento, California 95832", "")
    assert "Gianella" not in out and "Policy + Advocacy Associate" in out and "Sacramento" in out


def test_organization_and_exhibit_unit():
    units = il.split_units(pages())
    assert [u.kind for u in units] == ["letter", "letter"]
    assert units[1].attached == []  # page 3 has no new Clerk forward, so it stays in letter 2's range ...
    total, n_ex, body_pages, ex_pages = il.letter_pages(units[1])
    assert (total, n_ex, body_pages, ex_pages) == (2, 1, [2], [3])  # ... as an exhibit page
    e = il.parse_email(units[1].text)
    assert "EXHIBIT" not in e["body"] or len(e["body"]) < 200
    name, email, _ = il.identity(e["sender_line"])
    assert il.commenter_type(e["sender_line"], email, e["body"]) == "organization"


def test_exhibit_pages_after_footer_inside_letter():
    body = PAGE2 + "\n" + FOOT
    attached_letter = "January 3, 2026\nDear Council,\nSee our analysis.\nSincerely,\nAna"
    pg = [{"n": 1, "text": body, "ocr": False}, {"n": 2, "text": attached_letter, "ocr": True},
          {"n": 3, "text": "Table 1 ...", "ocr": True}]
    (u,) = il.split_units(pg)
    assert u.kind == "letter" and il.body_extent(u) == 1
    assert il.letter_pages(u)[:2] == (3, 2)


def test_unit_without_inner_header_is_exhibit():
    assert not il.is_letter_text("Outlook\nFW: map\nFrom City Clerk <city.clerk@sanjoseca.gov>\nDate Mon 1/13/2025 8:13 AM\n"
                                 "To Agendadesk <Agendadesk@sanjoseca.gov>\nSite plan sheet A-1")
    assert il.is_letter_text("From: A Person\nSubject: Item 3\nhello")
    assert il.is_letter_text("From: A Person\nSent: Monday, January 12, 2025 6:12 PM\nhello")
    # leading pages before the first wrapper are an exhibit with no preceding letter -> no row
    units = il.split_units([{"n": 1, "text": "Site plan sheet A-1", "ocr": False}] + [dict(p, n=p["n"] + 1) for p in pages()])
    assert [u.kind for u in units] == ["exhibit", "letter", "letter"]


def test_four_commenter_types():
    ct = il.commenter_type
    body = "Dear Council,\nPlease approve the project.\nSincerely,\nPat Smith\n"
    assert ct("Pat Smith", "pat@gmail.com", body) == "resident"
    assert ct("Pat Smith", "pat@gmail.com", body + "Partner\nSmith & Lee LLP\nAttorneys at Law") == "developer_or_counsel"
    assert ct("Pat Smith", "", "I write on behalf of the applicant, Acme.\n" + body) == "developer_or_counsel"
    assert ct("Pat Smith", "", body + "Acme Equities") == "developer_or_counsel"
    assert ct("Pat Smith", "pat@vta.org", body + "VTA Planning") == "government"
    assert ct("Pat Smith", "pat.smith@sccgov.gov", body) == "government"
    assert ct("Pat Smith", "", body + "Superintendent\nAlum Rock Union School District") == "government"
    assert ct("Pat Smith", "", body + "Executive Director\nWillow Glen Neighborhood Association") == "organization"
    assert ct("Pat Smith", "pat@acme-housing.org", body) == "organization"
    # City inboxes, bulk advocacy platforms, and disclaimers are not cues
    assert ct("Mayor", "mayor@sanjoseca.gov", body) == "resident"
    assert ct("Pat Smith", "noreply@adv.actionnetwork.org", body) == "resident"
    assert ct("Pat Smith", "", body + "PHP is not a law firm and this is not legal advice") == "resident"


def test_after_deadline():
    assert il.after_deadline("2026-10-19T16:15:00-07:00", "2026-10-19T17:00:00-07:00") is False
    assert il.after_deadline("2026-10-19T17:30:00-07:00", "2026-10-19T17:00") is True  # naive deadline = Pacific
    assert il.after_deadline("2026-10-19T17:30:00-07:00", "") is None
    assert il.after_deadline("", "2026-10-19T17:00:00-07:00") is None
    assert il.after_deadline("2026-10-19T23:00:00-07:00", "2026-10-19") is False  # date-only = end of day


def test_fuzzy_place_correction():
    assert il.fuzzy_fix_place("1234 Helger Way") == ("1234 Holger Way", True)
    assert il.fuzzy_fix_place("55 Pennit Ct") == ("55 Pennit Ct", False)
    assert il.fuzzy_fix_place("Story & King") == ("Story & King", False)
    assert il.fuzzy_fix_place("88 Tulley Rd") == ("88 Tully Rd", True)
    assert il.fuzzy_fix_place("Alum Rok & Capitol") == ("Alum Rock & Capitol", True)


def test_pages_summary():
    assert il.pages_summary({"organization": 47, "resident": 3}, {"organization": 2, "resident": 1}) == \
        "94% of pages from 2 organizations; 1 resident letter"
    assert il.pages_summary({}, {}) == "no letters"
    assert il.pages_summary({"resident": 10}, {"resident": 10}, {"resident": 8}) == "100% of pages from 8 residents"


def test_process_item_meta(monkeypatch):
    monkeypatch.setattr(il, "extract_pages", lambda pdf, log, use_ocr: pages())
    it = {"matter_file": "26-001", "title": "t", "meeting_date": "2026-10-20", "body": "City Council",
          "legistar_url": "https://sanjose.legistar.com/LegislationDetail.aspx?ID=1", "agenda_number": "10.4",
          "comment_deadline": "2026-10-19T17:00:00-07:00", "item_id": "1", "meeting_id": "", "priority": False,
          "attachment_urls": {}, "pdfs": [Path("letters_1.pdf")]}
    hints: dict = {}
    rows, meta = il.process_item(it, lambda s: None, False, hints)
    assert len(rows) == 2 and all(r.channel == "letter" and r.mock is False for r in rows)
    assert [r.after_deadline for r in rows] == [False, True]
    assert [(r.pages_total, r.pages_exhibit, r.pdf_file) for r in rows] == [(1, 0, "letters_1.pdf"), (2, 1, "letters_1.pdf")]
    assert meta["pages_by_type"] == {"resident": 1, "organization": 2}
    assert meta["letters_by_type"] == {"resident": 1, "organization": 1}
    assert meta["pages_summary"] == "67% of pages from 1 organization; 1 resident letter"
    assert all(r.comment_id.startswith("L") and len(r.comment_id) == 9 for r in rows)
    assert all("@" not in r.text and "555-0100" not in r.text for r in rows)
    assert hints[rows[0].comment_id]["address"] == "1234 Tully Rd"


def test_no_wrapper_fallback_split():
    body = PAGE1.split("Letter.pdf;\n", 1)[1] + "\n" + PAGE2.split("To Agendadesk <Agendadesk@sanjoseca.gov>\n", 1)[1]
    parts = il.split_emails([{"n": 1, "text": body, "ocr": False}])
    assert len(parts) == 2


def test_crawl_stub(capsys):
    assert il.main(["--crawl"]) == 2
    assert "crawl not implemented tonight" in capsys.readouterr().out


def test_duplicate_marking():
    mk = lambda cid: il.Letter(comment_id=cid, item="x", item_id="1", item_title="t", meeting_id="e", meeting_date="d",
                               channel="letter", mock=False, received_at="", posted_raw="", stance="unclear",
                               stance_source="pending_llm", neighborhood="", zip="", text="t", source_url="u", subject="s",
                               language="en", commenter_type="resident", identity_hash="", duplicate_of=None, ocr=False,
                               has_address_hint=False, pdf_page_start=1, pdf_page_end=1)
    rows = [mk("Labc"), mk("Labc"), mk("Lxyz")]
    il.mark_duplicates(rows)
    assert [r.comment_id for r in rows] == ["Labc", "Labc-2", "Lxyz"] and rows[1].duplicate_of == "Labc"
