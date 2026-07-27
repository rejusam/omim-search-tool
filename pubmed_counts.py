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


ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"


class PubMedError(Exception):
    """A PubMed request failed or returned an unusable response."""


def parse_count(payload):
    """Return the integer hit count from an ESearch JSON payload."""
    result = payload.get("esearchresult", {})
    if "ERROR" in result:
        raise PubMedError("PubMed returned an error: " + str(result["ERROR"]))
    count = result.get("count")
    if count is None:
        raise PubMedError("PubMed response had no count.")
    try:
        return int(count)
    except (TypeError, ValueError) as exc:
        raise PubMedError("PubMed count was not a number: " + str(count)) from exc


class PubMedClient:
    """A small, throttled, retrying client for PubMed ESearch count queries."""

    def __init__(self, email, api_key=None, tool="omim-pubmed-counter",
                 session=None, sleep=time.sleep):
        self.email = email
        self.api_key = api_key
        self.tool = tool
        if session is None:
            session = requests.Session()
        self.session = session
        self.sleep = sleep
        if api_key:
            self.pause_seconds = 0.11
        else:
            self.pause_seconds = 0.34

    def count(self, query):
        """Return how many PubMed records match the query string."""
        params = {
            "db": "pubmed",
            "term": query,
            "retmode": "json",
            "retmax": 0,
            "tool": self.tool,
            "email": self.email,
        }
        if self.api_key:
            params["api_key"] = self.api_key

        max_attempts = 3
        attempt = 1
        while True:
            self.sleep(self.pause_seconds)
            try:
                response = self.session.get(ESEARCH_URL, params=params, timeout=60)
            except requests.exceptions.RequestException as exc:
                if attempt >= max_attempts:
                    raise PubMedError("A network error occurred talking to PubMed.") from exc
                self.sleep(2 ** attempt)
                attempt = attempt + 1
                continue

            status = response.status_code
            if status == 200:
                return parse_count(response.json())
            # Retry transient failures - server errors and rate-limiting.
            # Other client errors (e.g. a bad query) are permanent, so raise now.
            transient = status >= 500 or status == 429
            if not transient or attempt >= max_attempts:
                raise PubMedError("PubMed returned HTTP " + str(status) + ".")
            self.sleep(2 ** attempt)
            attempt = attempt + 1


def load_ncbi_config(config_path):
    """Return (email, api_key) from the [ncbi] section, each None if blank/absent."""
    parser = configparser.ConfigParser()
    if not parser.read(config_path):
        return None, None
    email = parser.get("ncbi", "email", fallback="").strip()
    api_key = parser.get("ncbi", "api_key", fallback="").strip()
    return (email or None), (api_key or None)


def save_ncbi_config(config_path, email, api_key):
    """Write the [ncbi] section without disturbing other sections in the file."""
    parser = configparser.ConfigParser()
    parser.read(config_path)
    if not parser.has_section("ncbi"):
        parser.add_section("ncbi")
    parser.set("ncbi", "email", (email or "").strip())
    parser.set("ncbi", "api_key", (api_key or "").strip())
    with open(config_path, "w", encoding="utf-8") as config_file:
        parser.write(config_file)


FIELDS = ["term", "exact_count", "natural_count", "gap", "exact_url", "natural_url"]
_URL_FIELDS = {"exact_url", "natural_url"}


def make_row(term, exact_count, natural_count):
    """Build one output row; gap is blank unless both counts are numbers."""
    if isinstance(exact_count, int) and isinstance(natural_count, int):
        gap = natural_count - exact_count
    else:
        gap = ""
    return {
        "term": term,
        "exact_count": exact_count,
        "natural_count": natural_count,
        "gap": gap,
        "exact_url": pubmed_url(exact_query(term)),
        "natural_url": pubmed_url(natural_query(term)),
    }


def write_xlsx(path, rows, info):
    """Write a Counts sheet and a Run info sheet."""
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Counts"
    for column_index, name in enumerate(FIELDS, start=1):
        sheet.cell(row=1, column=column_index, value=name)
    row_index = 2
    for row in rows:
        for column_index, name in enumerate(FIELDS, start=1):
            value = row.get(name, "")
            cell = sheet.cell(row=row_index, column=column_index)
            if name in _URL_FIELDS and value != "":
                cell.value = value
                cell.hyperlink = value
                cell.style = "Hyperlink"
            else:
                cell.value = value
        row_index = row_index + 1
    sheet.freeze_panes = "A2"
    last_column = get_column_letter(len(FIELDS))
    last_row = max(row_index - 1, 1)
    sheet.auto_filter.ref = "A1:" + last_column + str(last_row)

    info_sheet = workbook.create_sheet("Run info")
    info_sheet.cell(row=1, column=1, value="Field")
    info_sheet.cell(row=1, column=2, value="Value")
    info_row = 2
    for label, value in info.items():
        info_sheet.cell(row=info_row, column=1, value=label)
        info_sheet.cell(row=info_row, column=2, value=str(value))
        info_row = info_row + 1

    workbook.save(path)


def write_run(folder, rows, info):
    """Write counts.xlsx and counts.csv into the run folder."""
    folder = pathlib.Path(folder)
    write_xlsx(folder / "counts.xlsx", rows, info)
    write_csv(folder / "counts.csv", rows, FIELDS)


CONFIG_PATH = pathlib.Path(__file__).parent / "config.ini"
RESULTS_DIR = pathlib.Path(__file__).parent / "results"


def count_terms(client, terms, sink=None, on_row=None):
    """Append one row per term to `sink` (created if None) and return it."""
    if sink is None:
        sink = []
    for index, term in enumerate(terms):
        if on_row is not None:
            on_row(index, term)
        try:
            exact = client.count(exact_query(term))
            natural = client.count(natural_query(term))
        except PubMedError:
            exact = "error"
            natural = "error"
        sink.append(make_row(term, exact, natural))
    return sink


def build_info(input_path, terms, rows, api_key, complete):
    """Assemble the Run info metadata block."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    if complete:
        complete_text = "yes"
    else:
        complete_text = "no - stopped early; results are partial"
    return {
        "Input file": str(input_path),
        "Terms in file": len(terms),
        "Rows written": len(rows),
        "Run at": timestamp,
        "API key used": "yes" if api_key else "no (3 requests/sec)",
        "Run complete": complete_text,
    }


def _get_config(config_path):
    """Return (email, api_key), prompting for and saving the email on first run."""
    email, api_key = load_ncbi_config(config_path)
    if email is None:
        print("NCBI asks for a contact email so they can reach you if a search")
        print("misbehaves. It is stored locally and never shared.")
        email = input("Enter a contact email address: ").strip()
        save_ncbi_config(config_path, email, api_key or "")
    return email, api_key


def run(input_path, config_path=None, results_dir=None):
    """Read terms, count them, and write a run folder. Returns the folder path."""
    if config_path is None:
        config_path = CONFIG_PATH
    if results_dir is None:
        results_dir = RESULTS_DIR

    email, api_key = _get_config(config_path)
    terms = read_terms(input_path)
    if not terms:
        print("No terms found in the first column of that file.")
        return None

    folder = make_run_folder(results_dir, pathlib.Path(input_path).stem)
    client = PubMedClient(email=email, api_key=api_key)

    def progress(index, term):
        print("  " + str(index + 1) + "/" + str(len(terms)) + "  " + term)

    complete = True
    rows = []
    try:
        count_terms(client, terms, sink=rows, on_row=progress)
    except KeyboardInterrupt:
        print("\nStopped early - writing what was counted so far.")
        complete = False

    info = build_info(input_path, terms, rows, api_key, complete)
    write_run(folder, rows, info)
    print("Wrote " + str(len(rows)) + " rows to " + str(folder))
    return folder


def main(argv):
    """Entry point: pubmed_counts.py <path to terms file>."""
    if len(argv) >= 2:
        input_path = argv[1]
    else:
        input_path = input("Path to the terms file (.xlsx or .csv): ").strip()
    if not pathlib.Path(input_path).exists():
        print("No such file: " + input_path)
        return 1
    run(input_path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
