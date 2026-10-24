---
name: council-query
description: Answer a City staff question about what residents said, grounded only in the voice comments (letters, emails, site submissions) with comment_id citations, and keeping voice and 311 numbers in separate keys. Use for "/council-query <question>".
---

# council-query

Inputs you may read: `data/classifications.csv`, `data/comments_raw.csv`, `data/emails_raw.csv`,
`data/campaigns.json`, `data/categories.json`, `public/data/requests_311_by_tract.json` (311 aggregates only),
`public/data/provenance.json`. Never read `data/raw/`. Follow `.bob/rules/civic-data.md`.

## Steps

1. Restate the question as filters: item(s), category, stance, channel, area (tract or coarser only), period.
2. Select the matching voice comments. Count each campaign (`campaign_id`) **once by default**, and give the
   campaign size next to it. Rows with `duplicate_of` are never counted again.
3. Read the selected comments. Every claim in the answer must cite at least one `comment_id`, and every quote must be an
   exact substring of that comment's `text`.
4. If the question touches reported problems, take 311 numbers from the 311 aggregates and keep them apart.
   Compare across families only by citywide percentile of per-1k rates (`scripts/families.py`), never raw counts.
5. Return JSON, then a short plain-language answer:

```json
{
  "question": "...",
  "answer": "plain language, each claim followed by [comment_id]",
  "citations": [{"comment_id": "L…", "quote": "exact substring"}],
  "numbers": {
    "voice":        {"comments": 0, "campaigns_counted_once": 0, "by_stance": {}, "by_channel": {}},
    "requests_311": {"requests": 0, "months_covered": 0, "note": "separate family, never added to voice"}
  },
  "caveats": ["emails are simulated (mock=true)", "letters are OCR'd", "..."]
}
```

## Never

- Answer from general knowledge, or cite a comment you did not read.
- Add, average or rank a 311 count together with a voice count, or put them in one key.
- Name individuals, give addresses, or report anything finer than a census tract.
- Mention model or vendor names in text meant for the UI.
