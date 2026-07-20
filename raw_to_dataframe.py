"""Load a run's raw.json into pandas DataFrames.

A run folder's raw.json holds the untouched OMIM API responses. This module
turns them into the same two tables the spreadsheet has - one row per entry,
and one row per phenotype - so results can be filtered and analysed in pandas
without running the search again.

Usage from the command line:

    python raw_to_dataframe.py results/omim_neuropathy_20260719-1056/raw.json

Usage from Python or a notebook:

    from raw_to_dataframe import load_raw, entries_dataframe

    document = load_raw("results/omim_.../raw.json")
    entries = entries_dataframe(document)
"""

import json
import pathlib
import sys

import pandas

from omim_search import entry_to_row, entry_to_phenotype_rows


def load_raw(path):
    """Read a raw.json file and return the whole document."""
    with open(path, "r", encoding="utf-8") as json_file:
        return json.load(json_file)


def iter_entries(document):
    """Yield every entry dict across all pages of responses.

    Each response is one page of results. A page holds a searchResponse with
    an entryList, and each item in that list wraps the entry under an 'entry'
    key. Pages with no entryList are skipped rather than treated as an error -
    a run that stopped early can leave one.
    """
    responses = document.get("responses", [])
    for response in responses:
        search_response = response.get("searchResponse", {})
        entry_list = search_response.get("entryList", [])
        for item in entry_list:
            entry = item.get("entry")
            if entry is not None:
                yield entry


def entries_dataframe(document):
    """Build the one-row-per-entry table, matching Sheet 1 of the xlsx."""
    rows = []
    rank = 1
    for entry in iter_entries(document):
        rows.append(entry_to_row(entry, rank))
        rank = rank + 1
    return pandas.DataFrame(rows)


def phenotypes_dataframe(document):
    """Build the one-row-per-phenotype table, matching Sheet 2 of the xlsx.

    An entry with no phenotype maps contributes no rows, so this table is a
    different length from the entries table.
    """
    rows = []
    for entry in iter_entries(document):
        rows.extend(entry_to_phenotype_rows(entry))
    return pandas.DataFrame(rows)


def metadata_series(document):
    """Return the run's metadata block as a pandas Series."""
    return pandas.Series(document.get("metadata", {}))


def main(argv):
    """Print a summary of the two tables for the raw.json given on the command line."""
    if len(argv) != 2:
        print("Usage: python raw_to_dataframe.py <path to raw.json>")
        return 1

    path = pathlib.Path(argv[1])
    if not path.exists():
        print("No such file: " + str(path))
        return 1

    document = load_raw(path)
    entries = entries_dataframe(document)
    phenotypes = phenotypes_dataframe(document)

    print("Metadata")
    print(metadata_series(document).to_string())
    print()
    print("Entries: " + str(len(entries)) + " rows, " + str(len(entries.columns)) + " columns")
    print(entries.head().to_string())
    print()
    print("Phenotypes: " + str(len(phenotypes)) + " rows, " + str(len(phenotypes.columns)) + " columns")
    print(phenotypes.head().to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
