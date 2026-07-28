# Multi-database search strings — design

Date: 2026-07-29

## Purpose

The OMIM completeness search has been run in PubMed: 523 condition terms
combined with OR, intersected with a four-term phenotype filter, returning 559
records. The review team now wants the same search run in Scopus, CINAHL and
Ovid. Zay Melville will run those searches and will import the results into
Covidence, which finds duplicates automatically.

This tool therefore produces one thing: paste-ready search strings in each
platform's syntax, with instructions for running and exporting them. It does not
retrieve records, call any database API, or remove duplicates.

## Constraints

- The 523 terms combined with OR run to 23,033 characters. No search box on any
  of these platforms will accept that in one paste; the PubMed run itself had to
  bypass the web interface and use E-utilities.
- The searches must stay comparable with the PubMed run, because their purpose
  is to check the completeness of a search already reported in the methods.
- Zay must be able to run each database by hand, in a reasonable number of
  steps, without a script or an API key.

## Approach

### Inputs

- `kept_terms.csv` — the 523 final terms, first column, as produced by the
  PubMed run.
- The phenotype filter, fixed for this review:
  `"auditory neuropathy" OR "vestibular neuropathy" OR vestibulopathy OR "vestibular nerve"`.
  Baked in as a constant, overridable with `--phenotype-file`.

### Translation fidelity

Parity free text. Each term is a quoted phrase; no subject headings, no
adjacency operators, no field restriction beyond each platform's nearest
equivalent to an all-fields search. Subject-heading translation was considered
and rejected: the terms are OMIM catalogue titles, most of which have no
matching MeSH, Emtree or CINAHL heading, so the work is large and the gain
small. Parity also keeps all four result sets directly comparable with the
PubMed set.

### Normalization

Two kinds of substitution, both replacing the character with a space and
collapsing the whitespace that results.

**For parity with the PubMed run:** hyphens. The PubMed search that produced
the 559 records replaced them before searching, so keeping them here would mean
the four databases searched different strings from PubMed while the methods text
claimed one search. `CHARCOT-MARIE-TOOTH DISEASE` is searched as
`CHARCOT MARIE TOOTH DISEASE`, exactly as PubMed saw it.

**Because a platform's parser would otherwise break:** `(`, `)`, `/`, `:`, `+`
and the double quote. `LAMIN A/C` becomes `LAMIN A C`. This is the one place the
strings deliberately differ from the PubMed run, which never stripped these
characters — it affects 18 of the 523 terms, and every one is listed in the
audit file so the divergence can be stated in the methods text. The double quote
appears in no current term but would emit a malformed query if a regenerated
list ever contained one, since each term is wrapped in quotes unescaped.

Commas are left alone (197 terms contain one) and so is the word "or" (4 terms
contain it), because both are safe inside a quoted phrase on every platform.
Every substitution is recorded so the change can be described in the methods
text.

### Per-database syntax

| Database | Block form | Combine |
|---|---|---|
| Scopus | `ALL("term1" OR "term2" ...)` | `(#1 OR ... OR #9) AND #10` |
| CINAHL (EBSCOhost) | `TX ("term1" OR "term2" ...)` | `S1 OR ... OR S9`, then `AND S10` |
| Ovid MEDLINE | `("term1" or "term2" ...).mp.` | `1 or 2 or ... or 9`, then `10 and 11` |
| Ovid Embase | as Ovid MEDLINE | as Ovid MEDLINE |

`ALL`, `TX` and `.mp.` are each platform's closest equivalent to the all-fields
search PubMed ran. Scopus `ALL` also searches cited references, so the Scopus
set will be noisier than the other three; this is noted in the instructions and
should be noted in the methods text.

### Blocking

Terms are split into blocks of 60, giving 9 blocks of roughly 2,500 characters —
comfortably inside every platform's limit. Zay pastes 9 blocks per database as
separate searches, then combines the set numbers, then intersects with the
phenotype set. Block size is a CLI flag so it can be reduced if a platform
objects.

## Components

`translate_search.py`, alongside `omim_search.py` and `pubmed_counts.py`.

```
python translate_search.py kept_terms.csv --block-size 60
```

No interactive prompts: the audience for this tool is the operator, not the
clinical end user.

Four units, each independently testable:

- `load_terms(path)` — reads the first column of a csv or xlsx, strips the BOM
  and blank rows, removes duplicates, returns a list of strings.
- `normalize(term)` — applies the substitution above, returns
  `(original, searched)`.
- `build_blocks(terms, size)` — splits the term list into blocks.
- `render(db, blocks, phenotype)` — one renderer per dialect, selected from a
  dict keyed by database name; returns the block text and the combine lines.

Only the renderers know database syntax. Adding a fifth database is one dict
entry and one renderer.

## Outputs

```
results/searchpack_<date>/
  scopus.txt
  cinahl.txt
  ovid_medline.txt
  ovid_embase.txt
  INSTRUCTIONS.md
  term_normalization.csv
  search_summary.json
```

Each `.txt` file carries `--- BLOCK n of 9 ---` headers, the query for each
block, and at the end the combine line and the phenotype line.

`INSTRUCTIONS.md` is addressed to Zay: where the advanced search box is on each
platform, paste the blocks in order, combine the set numbers, intersect with the
phenotype set, then export RIS with abstracts for Covidence. It states that
PubMed returned 559 records, so a result set that is wildly smaller is a sign a
block was truncated on paste.

`term_normalization.csv` — `original,searched,changed` for all 523 terms; the 18
changed rows are the audit trail.

`search_summary.json` — term count, block count, block size, run date, and the
character length of each block.

## Error handling

The run stops with a clear message rather than emitting a query that would fail
silently:

- input file missing or unreadable;
- no terms found after loading;
- any rendered block longer than `--max-chars` (default 4000).

## Testing

`tests/test_translate_search.py`, following the style of the existing tests:

- normalization of each of the 18 awkward terms, and non-modification of terms
  containing commas or the word "or";
- block splitting at exact and ragged boundaries;
- output shape of each of the four renderers;
- combine-line numbering under all three conventions: `#n` (Scopus), `Sn`
  (CINAHL) and bare numbers (Ovid);
- the max-chars guard raising rather than writing output.

## Out of scope

No record retrieval, no database APIs, no deduplication, no overlap check
against the existing 559 PubMed records. Covidence handles duplicates.
