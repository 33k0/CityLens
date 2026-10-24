# Civic data rules (apply to every Bob mode and skill in this repo)

1. **PII never leaves `data/raw/`.** Names, email addresses, phone numbers, street addresses and the raw email
   export stay in the gitignored `data/raw/`. Outside it, a sender is only an `identity_hash`. Do not read
   `data/raw/` into a prompt, a log, a commit or an answer. The one exception is `data/raw/bob_batches/`: it holds only
   PII-scrubbed comment text, and the `classify-batch` skill reads the single batch file it is given.
2. **Nothing finer than a census tract.** Locations are reported as tract, neighborhood, council district or
   citywide. Never as an address, cross-street, block group or coordinate.
3. **Every label has evidence.** Each category and stance label has an `evidence_quote` (and `stance_evidence`
   unless the stance is `unclear`) that is an exact substring of the comment text after whitespace normalization.
   A label without one is rejected and re-done by the deterministic fallback. Never paraphrase or translate a quote.
4. **Voice and 311 are never summed.** Voice = letters + email + site submissions. Problems = 311. No count,
   share, rank, chart, map layer or answer adds them together. Cross-family comparison uses citywide percentiles
   of per-1,000-resident rates via `scripts/families.py` / `src/data/families.ts`. JSON keeps them under separate
   `voice` and `requests_311` keys.
5. **No model or vendor names in UI text.** Strings shown to residents or staff say "automated label" or
   "rule-based label", never a model, company or product name. Provenance files may name models.
6. **Never fake a run.** If Bob, Ollama or any model cannot run, the fallback runs, and `public/data/provenance.json`
   records `engine: "fallback"` with the reason. Never pass `--accept-license` on the user's behalf.
7. **Simulated data is labeled.** Emails are simulated (`mock=true`). Every count that includes them says so.
   Never generate mock "Letters from the Public".
8. **Campaigns count once.** Form-letter campaigns (`campaign_id`) count as one voice by default, with their size shown.
