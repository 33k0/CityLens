---
name: classify-batch
description: Label one batch file of voice comments with a category from data/categories.json, a stance, and exact-substring evidence, and write the labels JSON. Use for "/classify-batch <batch.jsonl> <labels.json>".
---

# classify-batch  (skill version: classify-batch-v1)

Arguments: an input batch file `data/raw/bob_batches/batch_NN.jsonl` and an output path
`data/raw/bob_batches/labels_NN.json`. `scripts/classify.py --engine bob` writes the batch files and runs this skill
once per batch.

The batch files hold PII-scrubbed comment text only. They are the one part of `data/raw/` you may read, and only
the batch file you were given. Follow `.bob/rules/civic-data.md`.

## Steps

1. Read `data/categories.json`: the category keys, include/exclude rules and `stance_definition`.
2. Read the whole batch file. Each line is a JSON object
   `{comment_id, language, item, item_title, subject, text}`. A retry batch also has `errors`, which lists
   what was wrong with your previous label for that row.
3. **Read and label every comment yourself.** Do not write or run code that assigns labels: no keyword scripts and
   no calls to other models. You may use a script only to check that your quotes occur in the text.
4. For each row, produce:
   - `comment_id`, copied unchanged;
   - `category`: exactly one key from `data/categories.json`, chosen by the comment's main ask;
   - `confidence`: a number from 0 to 1;
   - `evidence_quote`: 5–30 consecutive words copied **character for character** from `text`, including OCR
     errors such as `|` for `I`, curly quotes and odd spacing, that justify the category;
   - `stance`: one of `support`, `oppose`, `neutral`, `unclear`, as defined by `stance_definition` and relative
     to the item;
   - `stance_evidence`: words copied character for character from `text` that show the stance. Required for
     support and oppose; may be `""` for neutral or unclear;
   - `language`: the row's language. Label Spanish and Vietnamese comments from the original text and never
     translate quotes.
5. Write a JSON array with one object per input row, in input order, to the output path. Write nothing else
   to that file.
6. Reply with one line: the number of rows labeled and the category counts.

## Never

- Skip a row, invent a comment_id, or label from the subject alone when the text says more.
- Paraphrase, shorten with "...", or translate a quote. `scripts/classify.py` rejects anything that is not an
  exact substring and sends that row back to you once with the error listed.
- Read other files in `data/raw/`, or change `data/categories.json`.
