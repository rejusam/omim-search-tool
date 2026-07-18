"""Search the OMIM API by keyword and save the results.

Run this file directly to use it. See README.md for the operator guide.
"""

import configparser
import csv
import datetime
import json
import pathlib
import re
import time
import requests

from openpyxl import Workbook
from openpyxl.utils import get_column_letter


ENTRY_FIELDS = [
    "rank", "mim_number", "prefix", "preferred_title", "status",
    "gene_symbols", "approved_gene_symbol", "gene_name", "cyto_location",
    "chromosome", "phenotype_count", "phenotypes", "inheritance", "omim_url",
]
PHENOTYPE_FIELDS = [
    "mim_number", "preferred_title", "gene_symbols", "approved_gene_symbol",
    "cyto_location", "phenotype", "phenotype_mim_number",
    "phenotype_mapping_key", "phenotype_inheritance",
    "phenotypic_series_number", "entry_url", "phenotype_url",
]
# Columns whose values are gene symbols and must be stored as text so Excel
# does not convert names like SEPT9 or MARCH1 into dates.
TEXT_COLUMNS = {"gene_symbols", "approved_gene_symbol"}


class OmimError(Exception):
    """Something went wrong talking to the OMIM API."""


class AuthFailed(OmimError):
    """The API key was rejected (HTTP 401)."""


class QuotaExhausted(OmimError):
    """The API key's request quota is used up (HTTP 429)."""


class OmimClient:
    """A small, throttled, retrying client for the OMIM API."""

    def __init__(self, api_key, base_url="https://api.omim.org/api",
                 session=None, pause_seconds=0.3, sleep=time.sleep):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        if session is None:
            session = requests.Session()
        self.session = session
        self.pause_seconds = pause_seconds
        self.sleep = sleep

    def request(self, path, params):
        """Make one GET request and return the parsed 'omim' payload.

        Retries server/network errors up to 3 attempts total. Raises
        AuthFailed on 401 and QuotaExhausted on 429 (no retry on either).
        """
        url = self.base_url + "/" + path
        headers = {
            "ApiKey": self.api_key,
            "Accept-Encoding": "gzip",
            "Accept": "application/json",
        }

        max_attempts = 3
        attempt = 1
        while True:
            self.sleep(self.pause_seconds)
            response = self.session.get(
                url, params=params, headers=headers, timeout=60
            )
            status = response.status_code

            if status == 200:
                body = response.json()
                return body.get("omim", {})
            if status == 401:
                raise AuthFailed("The API key was rejected.")
            if status == 429:
                raise QuotaExhausted("The API key's request quota is exhausted.")

            # 400, 404, 500 and anything else: retry a few times, then give up.
            if attempt >= max_attempts:
                raise OmimError("OMIM returned HTTP " + str(status) + ".")
            self.sleep(2 ** attempt)  # 2s, then 4s
            attempt = attempt + 1

    def search(self, query, start, limit, include=None):
        """Run an entry search and return the 'omim' payload."""
        params = {
            "search": query,
            "start": start,
            "limit": limit,
            "format": "json",
        }
        if include is not None:
            params["include"] = include
        return self.request("entry/search", params)


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


def probe_count(client, query):
    """Ask OMIM how many results a query has, cheaply (no includes)."""
    payload = client.search(query, start=0, limit=1)
    search_response = payload.get("searchResponse", {})
    return search_response.get("totalResults", 0)


def fetch_entries(client, query, max_results):
    """Fetch entries for a query, paging with include=geneMap.

    Returns (entries, raw_responses, complete). If a quota stop or repeated
    error interrupts paging, returns whatever was gathered with complete=False.
    """
    # Make first request with include=geneMap to get both totalResults and first page
    try:
        payload = client.search(query, start=0, limit=20, include="geneMap")
    except (QuotaExhausted, OmimError):
        return [], [], False

    search_response = payload.get("searchResponse", {})
    total = search_response.get("totalResults", 0)

    # Get all page start offsets and determine which ones we still need
    starts = page_starts(total, max_results)

    entries = []
    raw_responses = [payload]
    complete = True

    # Extract entries from first page
    entry_list = search_response.get("entryList", [])
    for item in entry_list:
        entries.append(item.get("entry", {}))

    # Fetch remaining pages (skip start=0 since we already have it)
    for start in starts:
        if start == 0:
            continue
        try:
            payload = client.search(query, start=start, limit=20, include="geneMap")
        except (QuotaExhausted, OmimError):
            complete = False
            break
        raw_responses.append(payload)
        search_response = payload.get("searchResponse", {})
        entry_list = search_response.get("entryList", [])
        for item in entry_list:
            entries.append(item.get("entry", {}))

    return entries, raw_responses, complete


def gene_map_of(entry):
    """Return the entry's first gene map dict, or an empty dict if none."""
    gene_map_list = entry.get("geneMapList")
    if not gene_map_list:
        return {}
    return gene_map_list[0].get("geneMap", {})


def _phenotype_maps_of(entry):
    """Return the list of phenotypeMap dicts for an entry (possibly empty)."""
    gene_map = gene_map_of(entry)
    phenotype_map_list = gene_map.get("phenotypeMapList")
    if not phenotype_map_list:
        return []
    result = []
    for item in phenotype_map_list:
        phenotype_map = item.get("phenotypeMap", {})
        result.append(phenotype_map)
    return result


def entry_to_row(entry, rank):
    """Flatten one entry into a Sheet 1 (Entries) row."""
    mim_number = entry.get("mimNumber", "")
    titles = entry.get("titles", {})
    gene_map = gene_map_of(entry)
    phenotype_maps = _phenotype_maps_of(entry)

    phenotype_names = []
    inheritance_values = []
    for phenotype_map in phenotype_maps:
        name = phenotype_map.get("phenotype", "")
        if name != "":
            phenotype_names.append(name)
        inheritance = phenotype_map.get("phenotypeInheritance", "")
        if inheritance != "" and inheritance not in inheritance_values:
            inheritance_values.append(inheritance)

    row = {
        "rank": rank,
        "mim_number": mim_number,
        "prefix": entry.get("prefix", ""),
        "preferred_title": titles.get("preferredTitle", ""),
        "status": entry.get("status", ""),
        "gene_symbols": gene_map.get("geneSymbols", ""),
        "approved_gene_symbol": gene_map.get("approvedGeneSymbols", ""),
        "gene_name": gene_map.get("geneName", ""),
        "cyto_location": gene_map.get("cytoLocation", ""),
        "chromosome": gene_map.get("chromosomeSymbol", ""),
        "phenotype_count": len(phenotype_names),
        "phenotypes": " | ".join(phenotype_names),
        "inheritance": " | ".join(inheritance_values),
        "omim_url": "https://omim.org/entry/" + str(mim_number),
    }
    return row


def entry_to_phenotype_rows(entry):
    """Flatten one entry into zero or more Sheet 2 (Phenotypes) rows."""
    mim_number = entry.get("mimNumber", "")
    titles = entry.get("titles", {})
    gene_map = gene_map_of(entry)
    phenotype_maps = _phenotype_maps_of(entry)

    rows = []
    for phenotype_map in phenotype_maps:
        phenotype_mim = phenotype_map.get("phenotypeMimNumber", "")
        row = {
            "mim_number": mim_number,
            "preferred_title": titles.get("preferredTitle", ""),
            "gene_symbols": gene_map.get("geneSymbols", ""),
            "approved_gene_symbol": gene_map.get("approvedGeneSymbols", ""),
            "cyto_location": gene_map.get("cytoLocation", ""),
            "phenotype": phenotype_map.get("phenotype", ""),
            "phenotype_mim_number": phenotype_mim,
            "phenotype_mapping_key": phenotype_map.get("phenotypeMappingKey", ""),
            "phenotype_inheritance": phenotype_map.get("phenotypeInheritance", ""),
            "phenotypic_series_number": phenotype_map.get("phenotypicSeriesNumber", ""),
            "entry_url": "https://omim.org/entry/" + str(mim_number),
            "phenotype_url": "https://omim.org/entry/" + str(phenotype_mim),
        }
        rows.append(row)
    return rows


def slugify(text):
    """Turn a query into a short, filesystem-safe slug."""
    lowered = text.lower()
    replaced = re.sub(r"[^a-z0-9]+", "_", lowered)
    trimmed = replaced.strip("_")
    if len(trimmed) > 40:
        trimmed = trimmed[:40].strip("_")
    return trimmed


def make_run_folder(results_dir, query):
    """Create and return a unique folder for this run's output."""
    results_dir = pathlib.Path(results_dir)
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M")
    slug = slugify(query)
    base_name = "omim_" + slug + "_" + timestamp

    folder = results_dir / base_name
    suffix = 2
    while folder.exists():
        folder = results_dir / (base_name + "_" + str(suffix))
        suffix = suffix + 1

    folder.mkdir(parents=True)
    return folder


def write_csv(path, rows, fieldnames):
    """Write rows to a UTF-8-with-BOM csv so Excel reads it correctly."""
    with open(path, "w", encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_json(path, raw_responses, metadata):
    """Write the raw API responses plus a metadata block."""
    document = {"metadata": metadata, "responses": raw_responses}
    with open(path, "w", encoding="utf-8") as json_file:
        json.dump(document, json_file, indent=2)


def _write_sheet(sheet, fieldnames, rows):
    """Write a header row and data rows, protecting gene-symbol columns."""
    for column_index, name in enumerate(fieldnames, start=1):
        sheet.cell(row=1, column=column_index, value=name)

    row_index = 2
    for row in rows:
        for column_index, name in enumerate(fieldnames, start=1):
            value = row.get(name, "")
            cell = sheet.cell(row=row_index, column=column_index)
            if name in TEXT_COLUMNS:
                cell.value = str(value)
                cell.number_format = "@"
            else:
                cell.value = value
        row_index = row_index + 1

    sheet.freeze_panes = "A2"
    last_column = get_column_letter(len(fieldnames))
    last_row = max(row_index - 1, 1)
    sheet.auto_filter.ref = "A1:" + last_column + str(last_row)


def write_xlsx(path, entry_rows, phenotype_rows, search_info):
    """Write the three-sheet results workbook."""
    workbook = Workbook()

    entries_sheet = workbook.active
    entries_sheet.title = "Entries"
    _write_sheet(entries_sheet, ENTRY_FIELDS, entry_rows)

    phenotypes_sheet = workbook.create_sheet("Phenotypes")
    _write_sheet(phenotypes_sheet, PHENOTYPE_FIELDS, phenotype_rows)

    info_sheet = workbook.create_sheet("Search info")
    info_sheet.cell(row=1, column=1, value="Field")
    info_sheet.cell(row=1, column=2, value="Value")
    info_row = 2
    for label, value in search_info.items():
        info_sheet.cell(row=info_row, column=1, value=label)
        info_sheet.cell(row=info_row, column=2, value=str(value))
        info_row = info_row + 1

    workbook.save(path)


def write_run(folder, entry_rows, phenotype_rows, raw_responses, search_info):
    """Write all four output files into the run folder."""
    folder = pathlib.Path(folder)
    write_xlsx(folder / "results.xlsx", entry_rows, phenotype_rows, search_info)
    write_csv(folder / "entries.csv", entry_rows, ENTRY_FIELDS)
    write_csv(folder / "phenotypes.csv", phenotype_rows, PHENOTYPE_FIELDS)
    write_json(folder / "raw.json", raw_responses, search_info)
