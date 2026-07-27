"""Count PubMed hits for each term in a list of condition names.

Reads a column of terms from an .xlsx or .csv file and, for each, asks PubMed
how many articles match - once as an exact quoted phrase and once as PubMed's
default search - so terms can be triaged before building a combined search.
"""

import configparser
import csv
import datetime
import pathlib
import sys
import time
import urllib.parse

import requests
from openpyxl import Workbook, load_workbook
from openpyxl.utils import get_column_letter

from omim_search import slugify, make_run_folder, write_csv


def read_terms(path):
    """Return the non-empty, trimmed first-column values from an xlsx or csv."""
    path = pathlib.Path(path)
    suffix = path.suffix.lower()
    if suffix == ".xlsx":
        rows = _first_column_xlsx(path)
    else:
        rows = _first_column_csv(path)
    terms = []
    for value in rows:
        if value is None:
            continue
        text = str(value).strip()
        if text != "":
            terms.append(text)
    return terms


def _first_column_xlsx(path):
    workbook = load_workbook(path, read_only=True, data_only=True)
    sheet = workbook.active
    values = []
    for row in sheet.iter_rows(min_col=1, max_col=1, values_only=True):
        values.append(row[0])
    return values


def _first_column_csv(path):
    values = []
    with open(path, "r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.reader(csv_file)
        for row in reader:
            if row:
                values.append(row[0])
            else:
                values.append(None)
    return values


PUBMED_WEB = "https://pubmed.ncbi.nlm.nih.gov/"


def exact_query(term):
    """Wrap the term in quotes so PubMed searches the exact phrase (no term mapping)."""
    return '"' + term.strip() + '"'


def natural_query(term):
    """Return the term unquoted, as a plain PubMed search would receive it."""
    return term.strip()


def pubmed_url(query):
    """Build the human-facing PubMed search URL for a query."""
    encoded = urllib.parse.urlencode({"term": query})
    return PUBMED_WEB + "?" + encoded
