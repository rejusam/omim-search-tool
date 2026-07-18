"""Search the OMIM API by keyword and save the results.

Run this file directly to use it. See README.md for the operator guide.
"""

import configparser


def load_api_key(config_path):
    """Return the saved API key, or None if there is no usable key."""
    parser = configparser.ConfigParser()
    read_files = parser.read(config_path)
    if not read_files:
        return None
    key = parser.get("omim", "api_key", fallback="")
    key = key.strip()
    if key == "":
        return None
    return key


def save_api_key(config_path, api_key):
    """Write the API key to the config file, creating it if needed."""
    parser = configparser.ConfigParser()
    parser["omim"] = {"api_key": api_key.strip()}
    with open(config_path, "w", encoding="utf-8") as config_file:
        parser.write(config_file)


def quote_term(term):
    """Wrap a term in quotes if it contains a space, so OMIM treats it as a phrase."""
    term = term.strip()
    if " " in term:
        return '"' + term + '"'
    return term


def build_query(any_of, must_include, exclude):
    """Build an OMIM query string from three lists of terms.

    any_of: entries may contain any of these (an OR group, but required as a group)
    must_include: entries must contain each of these
    exclude: entries must not contain any of these
    """
    parts = []

    clean_any_of = []
    for term in any_of:
        term = term.strip()
        if term != "":
            clean_any_of.append(quote_term(term))
    if clean_any_of:
        parts.append("+(" + " ".join(clean_any_of) + ")")

    for term in must_include:
        term = term.strip()
        if term != "":
            parts.append("+" + quote_term(term))

    for term in exclude:
        term = term.strip()
        if term != "":
            parts.append("-" + quote_term(term))

    if not parts:
        raise ValueError("Enter at least one search word.")

    return " ".join(parts)


def page_starts(total_results, max_results, page_size=20):
    """Return the list of 'start' offsets needed to fetch the results.

    total_results: how many results OMIM says there are
    max_results: cap on how many to fetch, or None for all
    """
    wanted = total_results
    if max_results is not None and max_results < wanted:
        wanted = max_results

    starts = []
    start = 0
    while start < wanted:
        starts.append(start)
        start = start + page_size
    return starts
