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
