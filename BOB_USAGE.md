# BOB_USAGE.md — what IBM Bob did in this project

Every row below is a real `bob run` recorded in `data/bob_runs.json` (task ids are Bob's own). Nothing here is
simulated. Bob Shell 2.0.6, headless form `bob run --accept-license --mode agent --format json -w <repo> --trust
--max-turns N --max-cost C "<prompt>"`. The user supplied the API key and accepted the IBM license on 2026-10-23; the
key lives only in gitignored `.env.local`.

## What Bob produced

1. **The voice taxonomy, from scratch** (`categorize`): Bob read the letters and emails and wrote
   `data/categories.json` (8 categories) and `prompts/classify.txt` via the `.bob/skills/categorize-comments` skill.
   `authored_by: "ibm-bob"`.
2. **Subcategories** (`subcategories`): 3–5 per category, derived from a digest of every unique comment. Top-level
   keys were frozen and the script verifies they did not change.
3. **The 311 mapping** (`map_311_taxonomy`): Bob mapped the 97 distinct 311 request types (covering 455,545 rows) into
   its own categories or `none` (`data/taxonomy_311_bob.json`).
4. **Every voice label** (`label_batch_*`, `retry_batch_*`, `copies_batch_*`): category, subcategory, stance and exact
   evidence quotes for all 435 comments. Bob labeled the 235 distinct texts plus 8 campaign copies directly; the other
   192 copies inherit their representative's label only after the quotes are re-located verbatim in each copy.

## Runs

| step | status | Bob task id | seconds | cost |
|---|---|---|---|---|
| probe | success | fd928ba7328b79f2512185420cd09586 | 4 | $0.027 |
| categorize | success | cfd109171c6263ed58abb96510696fb8 | 282 | $2.437 |
| map_311_taxonomy | success | e88e0f6a081dcd03e85bd3fe4da06cfa | 46.7 | $0.193 |
| subcategories | success | ca875b5c452ffbdd257bd7df5055dad3 | 43.2 | $0.377 |
| label_batch_04 | success | dc0feaf265d95fc6686b73520b38e986 | 57.4 | $0.251 |
| label_batch_03 | success | d8da17b570e48c15b9be88d2b19209d5 | 80.5 | $0.225 |
| label_batch_01 | success | ef74cba6e728209cbf1ff858fb26c44c | 96.6 | $0.969 |
| label_batch_05 | success | cc7b71240160acebfb4a12c263feb622 | 63.2 | $0.198 |
| label_batch_02 | success | c147f8196b92098e7b35f97c2a523caa | 139.1 | $1.066 |
| label_batch_06 | success | fe423910fabbf79084b8852eaf725718 | 58.9 | $0.191 |
| retry_batch_92 | success | 5d6c820f4844f3393e16aa1c515ab681 | 13.8 | $0.199 |
| retry_batch_91 | success | 9177fcfb2910d8c0bdbd532f53bdcbbe | 93.1 | $0.908 |
| retry_batch_90 | success | eaede3cc304539634133dbf442aae7e8 | 106.8 | $0.997 |
| label_batch_01 | success | cc55f66e985834a866ba123a9ec45a50 | 13.0 | $0.154 |
| copies_batch_80 | success | e3b4daeab1b39baac06619020f1f1bf8 | 17.6 | $0.165 |
| **total** | | | | **$8.36** |

Budget guard: $10 for the milestone (`BOB_BUDGET_USD`), `--max-cost` 2–3 per run. Three label batches wrote JSON with
unescaped double quotes inside quotes (report titles in quotation marks); the labels were repaired locally at no cost
and the prompt now asks Bob to escape them.

## Result

- Engine per comment: {'bob': np.int64(427), 'fallback': np.int64(8)}. Every `evidence_quote` and `stance_evidence` is an exact
  substring of its own comment (checked in code and tests). `--offline` replays the cached labels with zero calls.
- Category × channel:

| category                           |   email |   letter |
|:-----------------------------------|--------:|---------:|
| Code Enforcement & Permitting      |      19 |        2 |
| Environment & Development Review   |      13 |        0 |
| Governance & Civic Rights          |       0 |      246 |
| Housing & Affordability Policy     |      51 |        2 |
| Other / General                    |       4 |       15 |
| Public Safety & Emergency Response |       7 |        5 |
| Sanitation & Environmental Quality |       9 |        0 |
| Streets & Infrastructure           |      61 |        1 |

- Stance × channel:

| stance   |   email |   letter |
|:---------|--------:|---------:|
| neutral  |      13 |        2 |
| oppose   |      58 |       17 |
| support  |      87 |      237 |
| unclear  |       6 |       15 |

Granite 4.1 8B via Ollama remains installed as the second-line fallback for labels Bob cannot produce validly; in the
final run it was not needed. The rule engine is the last fallback and is labeled `fallback` wherever used.

