# Metrics formula sheet

Back-end reference for every analytic the app computes. Each row gives the metric, how to derive it from the files
in `public/data/` and `data/`, and what it means. The first column orders the sheet: **breadth tier** first, then
**output type**.

- **Tier 1 · Headline**: shown on every item, region and city view; the numbers a council office reads first.
- **Tier 2 · Analysis**: panel and drill-down metrics that explain the headline.
- **Tier 3 · Quality**: provenance and confidence checks; shown in footers and logs, used to decide whether a headline
  number can be trusted.

Output types, in sheet order: Count → Percentage → Rate → Percentile → Ratio / Index → Ranking → Time series → Flag.

## Notation and ground rules

| Symbol | Meaning | Source |
|---|---|---|
| `V` | Voice rows (family `voice`: channel `letter`, `email`, `site`) after the active filters | `public/data/comments.json` → `comments[]` |
| `F` | Active filters: `item`, `category`, `subcategory`, `channel`, date window on `received_at`, region `R` (set of `tract_id`) | UI state |
| `P` | 311 problem reports: `by_tract[t][category][YYYY-MM]`, category ≠ `none` (billing/account rows are already excluded) | `public/data/requests_311_by_tract.json` |
| `u(r)` | Unique-voice weight of a voice row: `0` if `duplicate_of` is set; `1 / n_c` if `campaign_id` = c, where `n_c` is the number of non-duplicate rows in campaign c; else `1` | `comments.json` |
| `U(S)` | Unique voices in a row set S = `Σ u(r)` over S | derived |
| `L` | Located rows: `tract_id` not null | `comments.json` |
| `Res` | Residence-basis rows: `location_basis ∈ {residence, both}`; falls back to all of `L` when fewer than 30 such rows exist (see `meta.json → voice_location_basis`) | `comments.json`, `fairness/meta.json` |
| `pop(t)` | ACS 2024 population of tract t | `data/tracts.csv`, also `requests_311_by_tract.json → population` |
| `M` | Months in the 311 window (`months_covered`; 16 for 2025-07 → 2026-10) | `requests_311_by_tract.json` |
| `N` | Tracts with a non-null rate (215 citywide) | derived |
| `pct(x_t)` | Citywide percentile = `100 × |{t' : x_t' < x_t}| / N` (share of tracts strictly below; ties sit at the bottom, so a tract with zero comments scores 0) | `scripts/families.py`, `src/data/families.ts`, `web/fairness.js` |
| `med_f` | Citywide median per-1k rate of family f over all 215 tracts, computed once and never recomputed for a region (voice 0.0, problems 150.6) | `fairness/meta.json → city_median_rate_per_1k` |
| groups | Protected attributes, unprivileged side: `low_income` (median_income < $141,289), `majority_nonwhite` (pct_nonwhite > 0.5), `renter_majority` (pct_renter > 0.5), `high_lep` (pct_lep > 0.176, the 75th percentile) | `fairness/meta.json → attributes` |

**Rules that apply to every row below**

1. **Never add a 311 number to a voice number.** Use `sumWithinFamily` / `sum_within_family`, which throw on mixed
   input. Cross-family comparison is allowed only through percentiles of per-1k rates or side-by-side within-family
   shares.
2. **Count voices with `u(r)` by default** (duplicates 0, each campaign once). Expose the raw row count next to it.
3. **Label provenance on every output.** 311 numbers are `real`. Any voice number that includes `mock: true` rows is
   `illustrative`; a letters-only variant is `real`.
4. **Zero denominators return `null`, not 0.** The UI shows "not enough data".
5. **Wording:** never "unfair", "biased" or "apathetic"; never describe what residents of a silent tract think.

## Formula sheet

| Output · Breadth | Metric | How to derive | Description |
|---|---|---|---|
| Count · Tier 1 Headline | **H1 Voice comments (rows)** | `|V_F|` | Every letter, email and site submission matching the filters, before any deduplication. Show it only next to H2 so a 180-copy campaign is never read as 180 independent opinions. |
| Count · Tier 1 Headline | **H2 Unique voices** | `U(V_F) = Σ u(r)` | The default "how many people weighed in" number: duplicates count 0 and each form-letter campaign counts once. Real data today: 435 rows → 239 unique voices. Fractional values are expected when a campaign is split across filters or tracts; round only for display. |
| Count · Tier 1 Headline | **H3 311 problem reports** | `Σ_t∈R Σ_c∈F Σ_m∈window by_tract[t][c][m]` | Located 311 requests that are problem reports (billing, payments, accounts and service setup are already excluded by Bob's `none` mapping). 217,415 citywide since 2025-07-01. Always labeled real and always a separate family from H1/H2. |
| Percentage · Tier 1 Headline | **H4 Category share, voice** | `100 × U(V_F ∩ category=c) / U(V_F)` | What residents wrote about, by Bob's 8 categories, as a share of unique voices. Shares sum to 100% within voice only. |
| Percentage · Tier 1 Headline | **H5 Category share, 311** | `100 × P_c / Σ_c P_c` within the same region and window | What residents reported to 311, by the same 8 category keys (Bob's mapping in `data/taxonomy_311_bob.json`). Shares sum to 100% within 311 only. Place next to H4, never in the same bar. |
| Percentage · Tier 1 Headline | **H6 Subcategory share** | `100 × U(category=c ∩ subcategory=s) / U(category=c)` | Breakdown inside one category, e.g. Streets & Infrastructure → Streetlight Outages 38, Pothole & Pavement Repair 21. Sums to 100% within the category. |
| Percentage · Tier 1 Headline | **H7 Stance distribution** | `100 × U(stance=k) / U(V_F)` for k ∈ support, oppose, neutral, unclear | Position on the agenda item or requested action, from Bob's label with an exact `stance_evidence` quote. Report `unclear` as its own slice, never folded into neutral. Encode with glyph and word, not color alone. |
| Percentage · Tier 1 Headline | **H8 Location coverage** | `100 × |L ∩ V_F| / |V_F|`, split by `location_precision` (address, neighborhood, zip, district, none) and by channel | How much of the voice set can be placed on the map. Real letters 16% located vs simulated emails 67%. Must accompany every map and every region number so silence from missing locations is not mistaken for silence from residents. |
| Rate · Tier 1 Headline | **H9 Voice participation rate per 1k (tract)** | `1000 × U(Res ∩ tract=t) / pop(t)`; campaign weight split evenly over the campaign's located tracts | Unique voices per 1,000 residents, counted where the writer is (residence basis). This is the input to every "who is heard" metric. Not annualized: the window is the comment corpus. |
| Rate · Tier 1 Headline | **H10 311 problem rate per 1k (tract, annualized)** | `1000 × P_t / pop(t) × 12 / M` | 311 problem reports per 1,000 residents per year. Stored as `rate_per_1k_annualized`. Citywide median 150.6; maximum ~697. |
| Percentile · Tier 1 Headline | **H11 Voice and 311 percentiles** | `voice_pct_t = pct(H9_t)`, `problem_pct_t = pct(H10_t)` | Where a tract ranks in its own family. This is the only bridge between the two families: it removes volume (217,415 vs ~60 located voices) and population, leaving a 0–100 position. |
| Ratio / Index · Tier 1 Headline | **H12 Disparate impact (DI), per family** | `fav_t = rate_t > med_f`; `DI = P(fav | unprivileged) / P(fav | privileged)` over tracts; computed by AIF360 `BinaryLabelDatasetMetric`, cross-checked by pandas to 1e-9 | Whether unprivileged tracts are above the citywide median as often as privileged ones. 1.0 = parity; < 0.8 = under-represented (flag); > 1.25 = over-represented. 311 today: 1.7–2.1 across the four attributes (unprivileged tracts report more). Two rows (voice, 311), never blended. `null` when the privileged rate is 0. |
| Ratio / Index · Tier 1 Headline | **H13 Statistical parity difference (SPD), per family** | `SPD = P(fav | unprivileged) − P(fav | privileged)` | The same comparison as a difference in percentage points; 0 = parity, negative = unprivileged tracts less often above the median. Show next to DI because DI explodes when the privileged rate is small. |
| Flag · Tier 1 Headline | **H14 Problems without voice** | `problem_pct_t ≥ 70 AND voice_pct_t ≤ 30` (`problems_without_voice()`); list sorted by `problem_pct − voice_pct` | Tracts in the top 30% for 311 problems per resident and the bottom 30% for comments per resident. 47 tracts today. Each row shows both percentiles, never raw counts side by side. |
| Count · Tier 2 Analysis | **A1 Campaigns** | from `comments.json → campaigns` or `data/campaigns.json`: number of campaigns, `size`, `distinct_senders`, `items` | Form-letter groups found by MinHash (Jaccard ≥ 0.7 on 5-word shingles). Report count, largest size and which item they target, so staff see organized mobilization rather than inflated totals. |
| Count · Tier 2 Analysis | **A2 Silent tracts and their residents** | `S0 = {t : U(L ∩ tract=t) = 0}`; report `|S0|` and `Σ_t∈S0 pop(t)` | How many tracts, and how many people, have no located comment at all. 184 of 215 tracts today. The resident count is the headline-friendly form ("X residents live where we heard nothing"). |
| Percentage · Tier 2 Analysis | **A3 Campaign share of an item** | `100 × |{r ∈ V_item : campaign_id set}| / |V_item|` | How much of an item's volume is form letters. 25-081 is mostly one campaign; high values mean H1 overstates breadth of input. |
| Percentage · Tier 2 Analysis | **A4 Commenter-type share and pages of record** | voices: `100 × U(commenter_type=k) / U(V_F)`; pages: `100 × Σ pages_total(type=k) / Σ pages_total` (letters only) | Who is speaking: resident, organization, developer_or_counsel, government. The pages version shows when a few organizations supply most of the written record ("94% of pages from 2 organizations; 1 resident letter"); `items[].pages_summary` has the sentence form. |
| Percentage · Tier 2 Analysis | **A5 Non-English share** | `100 × U(language ≠ en) / U(V_F)`, by language | Reach of multilingual outreach. Bob labels non-English comments in their own language, so these are first-class voices, not dropped rows. |
| Percentage · Tier 2 Analysis | **A6 Residents in silent or underheard tracts** | `100 × Σ_t∈S pop(t) / Σ_t pop(t)` for S = A2 or the H14 set | Share of the city's population living where the council heard nothing, or where problems are high and voice is low. Use the 215-tract population base. |
| Percentage · Tier 2 Analysis | **A7 After-deadline share** | `100 × |{after_deadline = true}| / |{after_deadline ≠ null}|` per item | Comments sent after the item's comment deadline. `null` until staff enter `comment_deadline` in `data/legistar_items.csv`; show "deadline not recorded" instead of 0%. |
| Rate · Tier 2 Analysis | **A8 Category-specific 311 rate per 1k** | `1000 × Σ_m by_tract[t][c][m] / pop(t) × 12 / M` | H10 restricted to one category, e.g. Sanitation & Environmental Quality per 1,000 residents. Drives the per-category problems map and the category version of H14. |
| Ratio / Index · Tier 2 Analysis | **A9 Net support index** | `100 × (U(support) − U(oppose)) / (U(support) + U(oppose))`; `null` if both are 0 | −100 (all oppose) to +100 (all support), ignoring neutral and unclear. Compare items or subcategories on one scale; always show the n behind it. |
| Ratio / Index · Tier 2 Analysis | **A10 Representation ratio and participation gap** | `expected_t = pop(t) / Σ pop × U(Res)`; `ratio_t = observed_t / expected_t`; `gap_t = (expected_t − observed_t) / expected_t` | How a tract's comment count compares with its population share. ratio 1 = proportional, 0 = silent (gap 1.0). Stored per tract in `fairness/voice_city.json → gaps`. |
| Ratio / Index · Tier 2 Analysis | **A11 Attention gap by category** | `H5_c − H4_c` in percentage points, for categories present in both families | Where residents' 311 reports and written comments point at different things: e.g. Sanitation is 58% of 311 problems but a small share of comments. Compares two within-family shares; never adds counts. |
| Ratio / Index · Tier 2 Analysis | **A12 Voice concentration** | share of `U(L)` from the top 10% of tracts by H9; optionally a Gini over tract voice counts | Whether a few neighborhoods supply most located comments. High concentration plus low H8 means the map reflects a handful of places. |
| Ratio / Index · Tier 2 Analysis | **A13 Corrected weights** | AIF360 Reweighing `W(g,l) = P(g)·P(l) / P(g,l)` per (group, favorable) cell; population weight `w_t = (pop(t)/Σpop) / (U_t/ΣU)` | Two corrections for who is over-represented: Reweighing balances groups of tracts, population weighting balances volume per resident. They can disagree (see `DECISIONS.md`); both feed A15. Stored in `fairness/*_city.json → correct`. |
| Ranking · Tier 2 Analysis | **A14 Underheard ranking** | `score_t = gap_t × relevance_t`, relevance 1.0 inside an item's `affected_tracts` (`public/data/affected.json`), 0.25 outside; ties by `expected_t` | Top-k tracts to reach for an item, each with a facts-only outreach brief (population, renter %, limited-English %, observed vs expected, 311 percentile). |
| Ranking · Tier 2 Analysis | **A15 Theme ranking, three ways (voice only)** | rank categories by (a) `U` raw, (b) `Σ u(r)·W(g,l)` (AIF360), (c) `Σ u(r)·w_t` (population); report rank change vs raw | Whether the priority order of issues changes once over-represented groups or high-volume tracts are down-weighted. Today only population weighting moves ranks 3–7. 311 never enters this ranking. |
| Ranking · Tier 2 Analysis | **A16 311 category by volume** | `P_c` sorted descending, with H5 share | The 311 counterpart to A15: a plain volume table, because 311 needs no participation correction. |
| Time series · Tier 2 Analysis | **A17 311 monthly trend** | `Σ_t,c by_tract[t][c][m]` per month m; change `= 100 × (x_m − x_{m−1}) / x_{m−1}` | Monthly problem volume overall or per category, driving the month slider. Partial current month (October 2026 runs to the 22nd) must be marked partial, not compared as a full month. |
| Time series · Tier 2 Analysis | **A18 Comment timing** | `days_before = meeting_date − date(received_at)` per row; report median and share arriving within 48 hours of the meeting | How late input arrives relative to the meeting. `null` for items without a meeting date (general correspondence). |
| Flag · Tier 2 Analysis | **A19 Region summary with not-enough-data** | for a drawn region R: voice block (H2, H4, H6, H7, top quotes) and 311 block (H3, H5, A8) as separate keys `voice` and `requests_311`; DI/SPD with the citywide `med_f`; `not_enough_data = |R| < 5 OR either group < 2 tracts OR U(V_R) < 10` | Everything about a drawn area in two stacked sections. When the flag is true, show the counts and the reason instead of DI/SPD. "Who we're not hearing from" uses voice only. Implemented in `fairness.region_summary` and `web/fairness.js → regionSummary`. |
| Percentage · Tier 3 Quality | **Q1 Labeling engine share** | `100 × |{engine = k}| / |V|` for k ∈ bob, ollama, fallback | Who produced the labels. Today 100% IBM Bob. Any non-Bob share must be shown wherever category or stance numbers appear. |
| Percentage · Tier 3 Quality | **Q2 Low-confidence share** | `100 × |{confidence < 0.6}| / |V|`, per category | Labels Bob was unsure of. A category with a high share should carry a caution note and be first in line for the human audit (Q9). |
| Percentage · Tier 3 Quality | **Q3 Inherited and aligned labels** | `100 × |{inherited_from set}| / |V|`; within that, `100 × |{quote_aligned}| / |{inherited}|` | Campaign copies that took their representative's label (200 rows), and how many needed their quote re-located because OCR differs between copies (103). Quotes are still exact substrings of each copy. |
| Percentage · Tier 3 Quality | **Q4 Location quality mix** | shares of `location_precision`, `location_source` (street_anchor counts as approximate), `location_basis`, and `multi_tract = true` among `L` | How trustworthy the map placement is. Street anchors placed by the item's cluster describe the issue, not the writer, and should render as approximate. |
| Percentage · Tier 3 Quality | **Q5 OCR share** | `100 × |{ocr = true}| / |{channel = letter}|` | Letters read from scans. High OCR share explains garbled quotes and missed locations; 93% of current letters. |
| Percentage · Tier 3 Quality | **Q6 Simulated share** | `100 × |{mock = true}| / |V_F|`; `label = illustrative` if > 0 | How much of a voice number comes from simulated emails or site submissions. Drives the real / illustrative label required on every voice output. |
| Percentage · Tier 3 Quality | **Q7 311 coverage** | located: `rows_located / rows_total`; non-problem: `rows_not_problems / rows_total` | Share of 311 rows on the map (49% have coordinates) and share excluded as billing/account requests (35,854). Report with any 311 total so the base is clear. |
| Count · Tier 3 Quality | **Q8 Bob cost per labeled comment** | `Σ session_costs (data/bob_runs.json) / |V|`; per step from `kind` | Running cost of the AI pipeline ($8.36 for 435 comments plus taxonomy and 311 mapping). Used to budget warm rebuilds; offline demo runs cost 0. |
| Percentage · Tier 3 Quality | **Q9 Classifier audit agreement** | after staff fill `true_category` / `true_stance` in `data/labeled_sample_template.csv`: `100 × |{predicted = true}| / |{true filled}|`, per category and per language | Accuracy of Bob's labels against human review. Not yet measured: until filled, publish "not yet audited", never an estimate. |
| Flag · Tier 3 Quality | **Q10 Metric validity flags** | `null` denominators; `not_enough_data` (A19); `illustrative` (Q6); partial month (A17); DI with privileged rate 0 | One place that decides whether a headline number is shown, shown with a caveat, or replaced by "not enough data". Every Tier 1 output passes through these checks. |

## Where each output lives today

| File | Metrics |
|---|---|
| `public/data/comments.json` | inputs for H1, H2, H4, H6, H7, H8, A3–A5, A7, A9, A18, Q1–Q6 |
| `public/data/requests_311_by_tract.json` | H3, H5, H10, A8, A16, A17, Q7 |
| `public/data/fairness/voice_city.json`, `311_city.json` | H9, H11, H12, H13, A10, A13, A14, A15 |
| `public/data/fairness/problems_without_voice.json` | H14 |
| `public/data/fairness/meta.json` | medians, thresholds, attribute definitions, counting rules |
| `public/data/coverage.json` | H8, Q4 |
| `data/campaigns.json`, `data/bob_runs.json`, `data/labeled_sample_template.csv` | A1, Q8, Q9 |
| `web/fairness.js` | client-side H12, H13, A10, A19 for drawn regions |
