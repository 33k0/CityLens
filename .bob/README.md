# .bob/ — IBM Bob configuration for Civic Voice Map

| file | purpose |
|---|---|
| `rules/civic-data.md` | Rules every Bob mode follows here: PII stays in `data/raw/`, nothing finer than a tract, exact-substring evidence for every label, voice and 311 never summed, no model/vendor names in UI text, no faked runs. |
| `skills/categorize-comments/SKILL.md` | `/categorize-comments <item\|all>`: maintains `data/categories.json` and `prompts/classify.txt` from the actual letters and emails, runs `scripts/classify.py`, checks the output. |
| `skills/categorize-comments/taxonomy-rules.md` | How voice categories are made: 5–8, derived from the text, `maps_311`, stable keys, multilingual keywords, stance definition. |
| `skills/council-query/SKILL.md` | `/council-query <question>`: grounded answers for staff with `comment_id` citations and separate `voice` / `requests_311` numbers. |

The four files were written to the addendum's description, because the original addendum was never supplied.

## How Bob is invoked

`node scripts/run_bob.mjs [item|all]` (pipeline step e in `scripts/data.sh`) runs
`bob run --mode agent --format json --max-turns 20 -w <repo> "/categorize-comments <item>"` when `bob` is installed,
`BOB_API_KEY` is set and the IBM license has been accepted by the user. It stops after `BOB_MAX_RUNS` runs (default 6,
counted in `data/bob_runs.json`). Otherwise it prints a loud warning and runs `scripts/classify.py` directly. Every
attempt is recorded in `public/data/provenance.json` (`step: "bob_categorize"`, `engine: "bob"` or `"fallback"`
with the reason).

The script never passes `--accept-license`. To enable Bob, run `bob` once yourself and accept the license, then put
`BOB_API_KEY=...` in `.env.local`.
