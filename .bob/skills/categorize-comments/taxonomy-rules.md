# How to derive a voice taxonomy

1. **From the text, not from an org chart.** A category exists because residents raised it in their own words.
   Each category must be backed by at least 3 real comments. Its `examples` are exact substrings of those comments.
2. **Cover every item and channel.** Read across all agenda items in both letters and emails before naming
   anything. A large form-letter campaign is one voice, so do not let it dictate the structure. Every item must
   have a natural home.
3. **5–8 categories.** Fewer hides distinct asks. More spreads counts too thin for per-area comparison.
4. **Mutually exclusive.** Each comment gets one category, chosen by its main ask. For every pair of categories
   that could be confused, write an `include` / `exclude` rule that decides between them, and state it in terms
   of what the comment asks for.
5. **One catch-all, last.** It holds hardship stories, one-off topics and messages too vague to place. Keep it
   small: if more than about 10% of comments land there, a category is missing.
6. **Plain-language names.** Labels a resident would understand. Keys are snake_case and stable once published.
   Do not use model, vendor or product names, and do not name individuals.
7. **Map to 311 afterwards.** Once the categories are final, list in `maps_311` the keys from
   `data/taxonomy_311.csv` (column `category`) that report the same kind of problem, where that is natural. Do not
   rename or reshape a category to fit 311. An empty `maps_311` is fine. The mapping only lets a reader view
   the matching 311 layer side by side, by percentile. It never licenses adding 311 counts to voice counts.
8. **Multilingual keywords.** Give English, Spanish and Vietnamese cue words for the deterministic fallback.
   All-caps keywords of 4 letters or fewer match case-sensitively.
9. **Stance is about the item.** Define support / oppose / neutral / unclear relative to the action, proposal,
   candidate or item the comment addresses. Mixed or explicitly undecided comments are neutral. Content-free
   cover notes ("see attached") are unclear.
