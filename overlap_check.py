"""Report which records in a database export are new to a reference set.

Each database searched for the review returns records the PubMed search had
already found. This tool takes an export (RIS or csv, as downloaded from
Scopus, CINAHL or Ovid) and a reference set of records already held, and
reports how many are duplicates and how many are genuinely new.

Matching is tried in order of reliability: PubMed ID, then DOI, then the
title with punctuation and case removed. A record that matches none of the
three is counted as new.
"""

import argparse
import csv
import pathlib
import re
import sys
import unicodedata

FIELDS = ["pmid", "doi", "title", "year", "source"]


def normalize_title(title):
    """Strip case, accents and punctuation so two spellings of a title match."""
    text = unicodedata.normalize("NFKD", title or "").lower()
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    return " ".join(text.split())


def _record(pmid, doi, title, year, source):
    """Build one record with the identifiers trimmed and DOIs lowercased."""
    return {
        "pmid": (pmid or "").strip(),
        "doi": (doi or "").strip().lower(),
        "title": (title or "").strip(),
        "year": (year or "").strip(),
        "source": (source or "").strip(),
    }


def read_csv_export(path):
    """Read a csv export, taking whichever of the known column names are present."""
    records = []
    with open(path, "r", encoding="utf-8-sig", newline="") as csv_file:
        for row in csv.DictReader(csv_file):
            lower = {}
            for key, value in row.items():
                if key is not None:
                    lower[key.strip().lower()] = value
            records.append(_record(
                _first(lower, ["pubmed id", "pmid", "ui", "accession number"]),
                _first(lower, ["doi", "di"]),
                _first(lower, ["title", "document title", "ti"]),
                _first(lower, ["year", "publication year", "py"]),
                _first(lower, ["source title", "journal", "so"]),
            ))
    return records


def _first(row, names):
    """Return the first non-empty value among the candidate column names."""
    for name in names:
        value = row.get(name)
        if value is not None and str(value).strip() != "":
            return str(value)
    return ""


RIS_TAGS = {
    "TI": "title",
    "T1": "title",
    "DO": "doi",
    "PY": "year",
    "Y1": "year",
    "JO": "source",
    "T2": "source",
    "JF": "source",
    "AN": "pmid",
    "DB": "database",
    "ID": "accession",
}


def _pmid_from(record):
    """Return the accession as a PubMed ID, but only when it is one.

    Ovid puts the record's accession number in the ID tag. In a MEDLINE export
    that accession is the PubMed ID; in an Embase export it is an Embase
    number, which would match an unrelated PubMed ID by coincidence. So the
    accession is only trusted when the record says it came from MEDLINE.
    """
    if record.get("pmid"):
        return record["pmid"]
    database = record.get("database", "").lower()
    if "medline" in database or "pubmed" in database:
        return record.get("accession", "")
    return ""


def read_ris_export(path):
    """Read an RIS export, one record per ER tag."""
    records = []
    current = {}
    with open(path, "r", encoding="utf-8-sig") as ris_file:
        for line in ris_file:
            match = re.match(r"^([A-Z][A-Z0-9])  - ?(.*)$", line.rstrip("\n"))
            if match is None:
                continue
            tag, value = match.group(1), match.group(2).strip()
            if tag == "ER":
                if current:
                    records.append(_record(
                        _pmid_from(current), current.get("doi", ""),
                        current.get("title", ""), current.get("year", ""),
                        current.get("source", ""),
                    ))
                current = {}
                continue
            field = RIS_TAGS.get(tag)
            if field is not None and field not in current:
                current[field] = value
    if current:
        records.append(_record(
            _pmid_from(current), current.get("doi", ""),
            current.get("title", ""), current.get("year", ""),
            current.get("source", ""),
        ))
    return records


def read_export(path):
    """Read an export, choosing the reader by file extension."""
    path = pathlib.Path(path)
    if path.suffix.lower() == ".ris":
        return read_ris_export(path)
    return read_csv_export(path)


def build_index(records):
    """Collect the pmids, dois and normalized titles of a reference set."""
    pmids = set()
    dois = set()
    titles = set()
    for record in records:
        if record["pmid"]:
            pmids.add(record["pmid"])
        if record["doi"]:
            dois.add(record["doi"].strip().lower())
        title = normalize_title(record["title"])
        if title:
            titles.add(title)
    return {"pmid": pmids, "doi": dois, "title": titles}


def match_reason(record, index):
    """Return how this record matches the reference set, or None if it is new."""
    if record["pmid"] and record["pmid"] in index["pmid"]:
        return "pmid"
    doi = record["doi"].strip().lower()
    if doi and doi in index["doi"]:
        return "doi"
    title = normalize_title(record["title"])
    if title and title in index["title"]:
        return "title"
    return None


def compare(exported, reference):
    """Split an export into records already held and records that are new."""
    index = build_index(reference)
    matched = {"pmid": 0, "doi": 0, "title": 0}
    new_records = []
    for record in exported:
        reason = match_reason(record, index)
        if reason is None:
            new_records.append(record)
        else:
            matched[reason] = matched[reason] + 1
    return {
        "exported": len(exported),
        "reference": len(reference),
        "matched": matched,
        "already_held": sum(matched.values()),
        "new": len(new_records),
        "new_records": new_records,
    }


def format_report(result, export_name, reference_name):
    """Build the printed summary of a comparison."""
    matched = result["matched"]
    lines = [
        "Export:    " + export_name + " (" + str(result["exported"]) + " records)",
        "Reference: " + reference_name + " (" + str(result["reference"]) + " records)",
        "",
        "Already held: " + str(result["already_held"]),
        "  matched on PubMed ID: " + str(matched["pmid"]),
        "  matched on DOI:       " + str(matched["doi"]),
        "  matched on title:     " + str(matched["title"]),
        "New to screening: " + str(result["new"]),
    ]
    without_pmid = 0
    for record in result["new_records"]:
        if not record["pmid"]:
            without_pmid = without_pmid + 1
    lines.append("  of which not indexed in PubMed: " + str(without_pmid))
    return "\n".join(lines)


def write_new_records(path, records):
    """Write the new records to a csv so they can be checked by hand."""
    with open(path, "w", encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=FIELDS)
        writer.writeheader()
        for record in records:
            writer.writerow(record)


def run(export_path, reference_path, output_path=None):
    """Compare an export against a reference set and return the result."""
    exported = read_export(export_path)
    reference = read_export(reference_path)
    if not exported:
        raise ValueError("No records found in " + str(export_path))
    if not reference:
        raise ValueError("No records found in " + str(reference_path))
    result = compare(exported, reference)
    print(format_report(result, pathlib.Path(export_path).name,
                        pathlib.Path(reference_path).name))
    if output_path is not None:
        write_new_records(output_path, result["new_records"])
        print("\nWrote " + str(len(result["new_records"])) + " new records to " +
              str(output_path))
    return result


def main(argv):
    """Entry point: overlap_check.py <export> --against <reference>."""
    parser = argparse.ArgumentParser(
        description="Report which records in a database export are new."
    )
    parser.add_argument("export", help="the new export (.ris or .csv)")
    parser.add_argument("--against", required=True,
                        help="the records already held (.ris or .csv)")
    parser.add_argument("--out", help="write the new records to this csv")
    args = parser.parse_args(argv[1:])

    for path in [args.export, args.against]:
        if not pathlib.Path(path).exists():
            print("No such file: " + path)
            return 1
    run(args.export, args.against, output_path=args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
