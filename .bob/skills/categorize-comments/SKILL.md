---
name: categorize-comments
description: Derive the voice-family taxonomy from the letters and emails themselves, write data/categories.json and prompts/classify.txt, then run scripts/classify.py to label every voice comment with category, stance and exact-substring evidence. Use for "/categorize-comments <item|all>".
---

# categorize-comments

Argument: an agenda item / matter id or `all` (the default).

Scope: the **voice** family only. That is `data/comments_raw.csv` (real letters) and `data/emails_raw.csv` (simulated
emails, `mock=true`), using columns `comment_id, channel, item, item_title, subject, language, text`. Never read, label or count
311 rows. Follow `.bob/rules/civic-data.md` at every step.

**Do not read** `data/raw/` (PII and earlier drafts), `tests/`, `public/`, `src/`, `data/classify_cache.json`,
`data/classifications.csv`, `data/categories.pre_bob.json` or `data/labeled_sample_template.csv` before you have
written the taxonomy. The taxonomy must come from the comment text, not from earlier labels or the UI.

## Steps

1. **Read a broad sample.** For every `item` in both files, read at least 8 comments, or all of them when the item has
   fewer. Read every non-English comment as well. Use a short script to print `comment_id`, `item`, `item_title`, `subject` and the first
   ~600 characters of `text`. Note what residents actually ask for.
2. **Derive the taxonomy** following `taxonomy-rules.md` in this folder, then write `data/categories.json`:

   ```json
   {
     "version": "<short id, bump on every change>",
     "family": "voice",
     "authored_by": "ibm-bob",
     "source": "<one sentence: what you read to derive it>",
     "stance_definition": "<what support / oppose / neutral / unclear mean for these comments>",
     "categories": [
       {"key": "snake_case", "label": "Plain language", "description": "...",
        "include": ["..."], "exclude": ["..."],
        "examples": ["2-3 exact phrases copied from real comments"],
        "keywords": ["English, Spanish and Vietnamese cue words for the rule fallback"],
        "maps_311": ["keys from data/taxonomy_311.csv column `category`, possibly empty"]}
     ]
   }
   ```

   The catch-all category must be the **last** element: the rule fallback assigns it when nothing matches.
3. **Write `prompts/classify.txt`.** `scripts/classify.py` depends on the following:
   - first line `# prompt_version: <id>`; bump the id whenever the prompt or the taxonomy changes, because the
     cache key includes it;
   - a line `=== SYSTEM ===`, then the system prompt; a line `=== USER ===`, then the user message;
   - placeholders, which are filled with `str.format`, so use no other curly braces: system part `{categories_block}`,
     `{stance_definition}`; user part `{language}`, `{item}`, `{item_title}`, `{subject}`, `{text}`;
   - the model returns JSON `{category, confidence, evidence_quote, stance, stance_evidence}`. The prompt must say
     that both quotes are copied character for character from the comment, in its original language, with no
     translation or ellipses. The script rejects anything that is not an exact substring.
4. **Smoke test** with `.venv/bin/python scripts/classify.py --engine rules --item <arg>`. This takes seconds and makes
   no model calls. Fix any error it reports in your files.
5. **Run** `.venv/bin/python scripts/classify.py --item <arg>`. Granite via Ollama labels each row with one
   correction retry and a per-row rule fallback. For `all` this takes about 30 minutes. If your shell step times out,
   say so and stop; `scripts/run_bob.mjs` finishes the run. Never hand-edit the output.
6. **Check** `data/classifications.csv`:
   - per-channel category and stance distributions, letters and emails reported separately;
   - `engine=fallback` rows and their reasons in `public/data/provenance.json` (`step: classify`);
   - 10 random rows where you confirm that `evidence_quote` supports the label.
7. **Report** in under 250 words: the categories, with key, label and one-line rationale; counts per engine; per-channel
   distributions; and any category you would split or merge next time.

## Never

- Invent comments, labels, quotes or a ground truth. Do not fill `true_*` columns.
- Put model or vendor names in labels, descriptions or any UI text.
- Use `--accept-license`, or run Bob recursively.
