"""Turn a list of condition terms into paste-ready search strings.

The OMIM completeness search combines 523 condition terms with OR and
intersects them with a phenotype filter. That string is far too long for the
search box of Scopus, CINAHL or Ovid, so this tool splits it into numbered
blocks in each platform's own syntax and writes instructions for combining the
blocks by set number. It only writes text: nothing here searches anything.
"""

import argparse
import datetime
import json
import pathlib
import sys

from pubmed_counts import read_terms
from omim_search import write_csv

# Characters replaced with a space before searching. ()/:+ break a query parser
# even inside a quoted phrase. Hyphens are replaced too, not because they break
# a parser, but for exact string parity with the PubMed run that produced the
# 559-record baseline (see normalize_term in pubmed_counts.py): PubMed searched
# these terms with hyphens already turned to spaces, so a term surviving here
# with a hyphen intact would be a different string than what PubMed searched.
# Double quotes are replaced because _quoted_or wraps every term in double
# quotes with no escaping; an unescaped quote inside a term would break the
# quoting. Commas and the word "or" inside a quoted phrase are safe on every
# platform and are deliberately left alone.
PARSER_CHARS = "()/:+-\""

NORMALIZATION_FIELDS = ["original", "searched", "changed"]


def normalize(term):
    """Replace parser-breaking characters with spaces and collapse whitespace."""
    cleaned = term
    for char in PARSER_CHARS:
        cleaned = cleaned.replace(char, " ")
    return " ".join(cleaned.split())


def normalization_rows(terms):
    """Build the audit rows showing which terms were altered and how."""
    rows = []
    for term in terms:
        searched = normalize(term)
        if searched == term:
            changed = "no"
        else:
            changed = "yes"
        rows.append({"original": term, "searched": searched, "changed": changed})
    return rows


def load_terms(path, skip_header=False):
    """Return the first-column terms of a csv or xlsx, deduplicated in order."""
    values = read_terms(path)
    if skip_header and values:
        values = values[1:]
    terms = []
    seen = set()
    for value in values:
        if value not in seen:
            seen.add(value)
            terms.append(value)
    return terms


DEFAULT_BLOCK_SIZE = 60


def build_blocks(terms, size):
    """Split the term list into blocks of at most `size` terms."""
    if size < 1:
        raise ValueError("Block size must be at least 1.")
    blocks = []
    start = 0
    while start < len(terms):
        blocks.append(terms[start:start + size])
        start = start + size
    return blocks


PHENOTYPE_TERMS = [
    "auditory neuropathy",
    "vestibular neuropathy",
    "vestibulopathy",
    "vestibular nerve",
]

DEFAULT_MAX_CHARS = 4000


class BlockTooLongError(Exception):
    """A rendered block is longer than the search box is expected to accept."""


def _quoted_or(terms, or_word):
    """Join terms as quoted phrases separated by the dialect's OR word."""
    quoted = []
    for term in terms:
        quoted.append('"' + term + '"')
    return (" " + or_word + " ").join(quoted)


# Each dialect entry declares everything a rendering needs: the display title
# and output filename, the block format string (with a {terms} placeholder
# for the quoted-OR phrase), the set-reference prefix, the OR/AND operator
# words in the case this platform expects, and where in the platform's UI to
# paste each block.
DIALECTS = {
    "scopus": {
        "title": "Scopus",
        "filename": "scopus.txt",
        "format": "TITLE-ABS-KEY({terms})",
        "set_prefix": "#",
        "or_word": "OR",
        "and_word": "AND",
        "where": "Scopus > Advanced search",
    },
    "cinahl": {
        "title": "CINAHL (EBSCOhost)",
        "filename": "cinahl.txt",
        "format": "TX ({terms})",
        "set_prefix": "S",
        "or_word": "OR",
        "and_word": "AND",
        "where": "CINAHL > Advanced Search, with Search modes set to Boolean/Phrase",
    },
    "ovid_medline": {
        "title": "Ovid MEDLINE",
        "filename": "ovid_medline.txt",
        "format": "({terms}).mp.",
        "set_prefix": "",
        "or_word": "or",
        "and_word": "and",
        "where": "Ovid > MEDLINE > Advanced Search, Keyword mode, 'Map Term to Subject Heading' unticked",
    },
    "ovid_embase": {
        "title": "Ovid Embase",
        "filename": "ovid_embase.txt",
        "format": "({terms}).mp.",
        "set_prefix": "",
        "or_word": "or",
        "and_word": "and",
        "where": "Ovid > Embase > Advanced Search, Keyword mode, 'Map Term to Subject Heading' unticked",
    },
}


def render_block(name, terms):
    """Render one block of terms in the named database's syntax."""
    dialect = DIALECTS[name]
    quoted_or = _quoted_or(terms, dialect["or_word"])
    return dialect["format"].format(terms=quoted_or)


def combine_lines(name, block_count):
    """Return the two set-combining lines: OR the term sets, then AND the filter."""
    dialect = DIALECTS[name]
    prefix = dialect["set_prefix"]
    references = []
    for number in range(1, block_count + 1):
        references.append(prefix + str(number))
    or_line = (" " + dialect["or_word"] + " ").join(references)
    phenotype_set = prefix + str(block_count + 1)
    combined_set = prefix + str(block_count + 2)
    and_line = combined_set + " " + dialect["and_word"] + " " + phenotype_set
    return [or_line, and_line]


def render_file(name, blocks, phenotype_terms, source_name, generated,
                max_chars=DEFAULT_MAX_CHARS):
    """Render the whole paste-ready file for one database."""
    dialect = DIALECTS[name]
    total = len(blocks) + 1
    lines = [
        dialect["title"] + " - OMIM completeness search",
        "Generated " + generated + " from " + source_name,
        "Paste each block below as its own search, in order, then run the two",
        "lines under COMBINE.",
        "",
    ]
    number = 1
    for block in blocks:
        query = render_block(name, block)
        _check_length(query, name, number, max_chars)
        lines.append("--- BLOCK " + str(number) + " of " + str(total) +
                     " (condition terms) ---")
        lines.append(query)
        lines.append("")
        number = number + 1

    query = render_block(name, phenotype_terms)
    _check_length(query, name, number, max_chars)
    lines.append("--- BLOCK " + str(number) + " of " + str(total) +
                 " (phenotype filter) ---")
    lines.append(query)
    lines.append("")

    lines.append("--- COMBINE ---")
    lines.append("Run these two lines after all " + str(total) + " blocks above:")
    for line in combine_lines(name, len(blocks)):
        lines.append(line)
    lines.append("")
    lines.append("The result of the last line is the final set to export.")
    return "\n".join(lines) + "\n"


def render_selfcontained_query(name, block, phenotype_terms):
    """Render one block already intersected with the phenotype filter."""
    dialect = DIALECTS[name]
    joiner = " " + dialect["and_word"] + " "
    return (render_block(name, block) + joiner +
            render_block(name, phenotype_terms))


def render_selfcontained_file(name, blocks, phenotype_terms, source_name,
                              generated, max_chars=DEFAULT_MAX_CHARS):
    """Render queries that need no search history: each carries the filter.

    The set-reference form in render_file depends on the platform resolving
    "#1 OR #2 ..." against its search history. Scopus read those references as
    ordinary text and returned its whole database, and its Combine queries
    screen offers no parentheses, so mixed AND/OR there cannot be checked.
    These queries are each a single parenthesised expression instead: nothing
    depends on set numbers, and their union is the same set.
    """
    dialect = DIALECTS[name]
    total = len(blocks)
    lines = [
        dialect["title"] + " - OMIM completeness search (self-contained queries)",
        "Generated " + generated + " from " + source_name,
        "Each query below already includes the phenotype filter. Run all " +
        str(total) + ", export each, and let Covidence remove the duplicates.",
        "No search history or set numbers are used, so the order does not matter.",
        "",
    ]
    number = 1
    for block in blocks:
        query = render_selfcontained_query(name, block, phenotype_terms)
        _check_length(query, name, number, max_chars)
        lines.append("--- QUERY " + str(number) + " of " + str(total) + " ---")
        lines.append(query)
        lines.append("")
        number = number + 1
    lines.append("Every query returns its own set. Export each one before")
    lines.append("moving to the next; the same paper matching two blocks is")
    lines.append("expected and is removed on import.")
    return "\n".join(lines) + "\n"


def _check_length(query, name, number, max_chars):
    """Refuse to write a block long enough to be truncated on paste."""
    if len(query) > max_chars:
        raise BlockTooLongError(
            "Block " + str(number) + " for " + name + " is " + str(len(query)) +
            " characters, over the " + str(max_chars) + " limit. Re-run with a "
            "smaller --block-size."
        )


INSTRUCTIONS_TEMPLATE = """# Running the OMIM completeness search

Generated {generated} from {source} — {blocks} condition-term blocks plus one
phenotype-filter block, {total} pastes per database.

These files hold the same search that was run in PubMed, written in each
platform's own syntax. The full term list is far too long for any search box,
so it is split into blocks that are combined afterwards by set number.

## Files

| File | Database | Where to paste it |
|---|---|---|
{table}

Each database also has a `<database>_selfcontained.txt`. Use those instead if
your platform does not resolve set references — see "If the set numbers do not
work" at the end.

## How to run each database

1. Start from an empty search history. If the history already holds sets from
   an earlier search, clear it first — the COMBINE lines below refer to set
   numbers 1 to {total} by absolute position, and any earlier set shifts every
   one of those references off by one.
2. Open the advanced search screen named in the table above.
3. Paste BLOCK 1, run it, and leave the result in the search history.
4. Repeat for every remaining block, in order. Do not clear the history.
5. Run the two lines under COMBINE at the end of the file. The first ORs the
   condition blocks together; the second intersects that with the phenotype
   block.
6. Export the final set as **RIS, with abstracts**, and import it into
   Covidence.

## Checks before exporting

- The search history should show exactly {total} numbered sets before you run
  the COMBINE lines — set numbers 1 to {total} and nothing else.
  Fewer means a block failed to run.
  More means the history was not empty when you started, so every COMBINE
  reference below is pointing at the wrong set.
- Each block should return results. A block returning zero usually means the
  paste was truncated — re-paste that block on its own.
- The same search in PubMed returned 559 records. A final set of a wildly
  different order of magnitude is worth checking before exporting.

## If the set numbers do not work

Some platforms do not resolve typed set references. In Scopus, pasting
"#1 OR #2 OR ..." returned the entire database — over 100 million records —
because the references were read as ordinary text rather than as earlier
searches. Intersecting that with the phenotype set would have produced a
believable-looking number containing none of the condition terms.

Two signs it has happened: the OR line returns a number far larger than any
single block, or the final set exactly equals the phenotype block's count.

Use `<database>_selfcontained.txt` instead. Each query there already contains
the phenotype filter, so nothing depends on set numbers. Run all {blocks},
export each one as RIS with abstracts, and import them all into the same
Covidence review — a paper matching two blocks appears twice and is removed on
import. The union is the same set the COMBINE lines were meant to produce.

Avoid a "combine queries" screen that offers no parentheses: a strip such as
"9 OR 8 OR ... OR 1 AND 10" depends on the platform's operator precedence, and
if AND binds tighter the filter applies to only one block.

## Notes

- Terms are quoted phrases, searched as free text with no subject headings, so
  that all databases stay comparable with the PubMed run.
- Scopus is searched with TITLE-ABS-KEY rather than ALL. Scopus's ALL field also
  matches a paper's cited references, so it retrieves papers that merely cite a
  matching title - PubMed's all-fields search does not do this, and a trial run
  returned 500,000 records for a single block. TITLE-ABS-KEY is the closer match
  to what PubMed searched.
- A few catalogue titles contained characters that break a search parser, such
  as the slash in "LAMIN A/C", or hyphens, which were replaced with spaces so
  that every term here is the exact string that was searched in PubMed. Every
  change is listed in term_normalization.csv.
"""


def load_phenotype_terms(path):
    """Read the phenotype filter terms, one per line."""
    terms = []
    with open(path, "r", encoding="utf-8-sig") as term_file:
        for line in term_file:
            text = line.strip()
            if text != "":
                terms.append(text)
    return terms


def make_pack_folder(results_dir, generated):
    """Create and return a dated, unique folder for this run's output."""
    results_dir = pathlib.Path(results_dir)
    base_name = "searchpack_" + generated.replace("-", "")
    folder = results_dir / base_name
    suffix = 2
    while folder.exists():
        folder = results_dir / (base_name + "_" + str(suffix))
        suffix = suffix + 1
    folder.mkdir(parents=True)
    return folder


def build_instructions(block_count, source_name, generated):
    """Write the run-and-export instructions for whoever searches the databases."""
    rows = []
    for name in DIALECTS:
        dialect = DIALECTS[name]
        rows.append("| `" + dialect["filename"] + "` | " + dialect["title"] +
                    " | " + dialect["where"] + " |")
    return INSTRUCTIONS_TEMPLATE.format(
        generated=generated,
        source=source_name,
        blocks=block_count,
        total=block_count + 1,
        table="\n".join(rows),
    )


def write_pack(folder, blocks, phenotype_terms, rows, source_name, generated,
               block_size, max_chars):
    """Write every output file into the folder and return the summary written."""
    folder = pathlib.Path(folder)
    block_chars = {}
    phenotype_block_chars = {}
    for name in DIALECTS:
        text = render_file(name, blocks, phenotype_terms, source_name, generated,
                           max_chars=max_chars)
        (folder / DIALECTS[name]["filename"]).write_text(text, encoding="utf-8")
        selfcontained = render_selfcontained_file(
            name, blocks, phenotype_terms, source_name, generated,
            max_chars=max_chars
        )
        (folder / (name + "_selfcontained.txt")).write_text(
            selfcontained, encoding="utf-8"
        )
        lengths = []
        for block in blocks:
            lengths.append(len(render_block(name, block)))
        block_chars[name] = lengths
        phenotype_block_chars[name] = len(render_block(name, phenotype_terms))

    (folder / "INSTRUCTIONS.md").write_text(
        build_instructions(len(blocks), source_name, generated), encoding="utf-8"
    )
    write_csv(folder / "term_normalization.csv", rows, NORMALIZATION_FIELDS)

    changed = 0
    for row in rows:
        if row["changed"] == "yes":
            changed = changed + 1
    summary = {
        "generated": generated,
        "source_file": source_name,
        "terms": len(rows),
        "blocks": len(blocks),
        "block_size": block_size,
        "max_chars": max_chars,
        "terms_normalized": changed,
        "phenotype_terms": phenotype_terms,
        "block_chars": block_chars,
        "phenotype_block_chars": phenotype_block_chars,
    }
    with open(folder / "search_summary.json", "w", encoding="utf-8") as summary_file:
        json.dump(summary, summary_file, indent=2)
    return summary


RESULTS_DIR = pathlib.Path(__file__).parent / "results"


def run(input_path, results_dir=None, block_size=DEFAULT_BLOCK_SIZE,
        max_chars=DEFAULT_MAX_CHARS, phenotype_path=None, skip_header=False,
        generated=None):
    """Build the search pack from a term file. Returns the output folder."""
    if results_dir is None:
        results_dir = RESULTS_DIR
    if generated is None:
        generated = datetime.date.today().isoformat()
    if phenotype_path is None:
        phenotype_terms = list(PHENOTYPE_TERMS)
    else:
        phenotype_terms = load_phenotype_terms(phenotype_path)
        if not phenotype_terms:
            raise ValueError("No phenotype terms found in " + str(phenotype_path))
    phenotype_terms = [normalize(term) for term in phenotype_terms]

    terms = load_terms(input_path, skip_header=skip_header)
    if not terms:
        raise ValueError("No terms found in the first column of " + str(input_path))
    print("Loaded " + str(len(terms)) + " terms. First: " + terms[0] +
          " | Last: " + terms[-1])

    rows = normalization_rows(terms)
    searched = []
    for row in rows:
        searched.append(row["searched"])
    blocks = build_blocks(searched, block_size)

    # Render everything before creating the folder, so a block that is too long
    # fails without leaving a half-written pack behind.
    for name in DIALECTS:
        render_file(name, blocks, phenotype_terms, pathlib.Path(input_path).name,
                    generated, max_chars=max_chars)

    folder = make_pack_folder(results_dir, generated)
    summary = write_pack(folder, blocks, phenotype_terms, rows,
                         pathlib.Path(input_path).name, generated, block_size,
                         max_chars)
    print("Wrote " + str(summary["blocks"]) + " blocks for " +
          str(len(DIALECTS)) + " databases to " + str(folder))
    return folder


def main(argv):
    """Entry point: translate_search.py <terms file> [options]."""
    parser = argparse.ArgumentParser(
        description="Turn a term list into paste-ready database search blocks."
    )
    parser.add_argument("terms_file", help="csv or xlsx with terms in the first column")
    parser.add_argument("--block-size", type=int, default=DEFAULT_BLOCK_SIZE,
                        help="terms per block (default %(default)s)")
    parser.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHARS,
                        help="refuse to write a block longer than this (default %(default)s)")
    parser.add_argument("--phenotype-file",
                        help="text file of phenotype filter terms, one per line")
    parser.add_argument("--skip-header", action="store_true",
                        help="ignore the first row of the terms file")
    args = parser.parse_args(argv[1:])

    if not pathlib.Path(args.terms_file).exists():
        print("No such file: " + args.terms_file)
        return 1
    run(args.terms_file, block_size=args.block_size, max_chars=args.max_chars,
        phenotype_path=args.phenotype_file, skip_header=args.skip_header)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
