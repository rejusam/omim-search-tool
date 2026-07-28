"""Turn a list of condition terms into paste-ready search strings.

The OMIM completeness search combines 523 condition terms with OR and
intersects them with a phenotype filter. That string is far too long for the
search box of Scopus, CINAHL or Ovid, so this tool splits it into numbered
blocks in each platform's own syntax and writes instructions for combining the
blocks by set number. It only writes text: nothing here searches anything.
"""

from pubmed_counts import read_terms

# Characters that break a query parser even inside a quoted phrase. Commas and
# hyphens are safe on every platform and are deliberately left alone, as is the
# word "or" inside a quoted phrase.
PARSER_CHARS = "()/:+"

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
        "format": "ALL({terms})",
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


def _check_length(query, name, number, max_chars):
    """Refuse to write a block long enough to be truncated on paste."""
    if len(query) > max_chars:
        raise BlockTooLongError(
            "Block " + str(number) + " for " + name + " is " + str(len(query)) +
            " characters, over the " + str(max_chars) + " limit. Re-run with a "
            "smaller --block-size."
        )
