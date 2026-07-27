import pathlib

import openpyxl
import pytest

import pubmed_counts


def _make_xlsx(tmp_path, values):
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    for row_index, value in enumerate(values, start=1):
        sheet.cell(row=row_index, column=1, value=value)
    path = tmp_path / "terms.xlsx"
    workbook.save(path)
    return path


def test_read_terms_from_xlsx_first_column(tmp_path):
    path = _make_xlsx(tmp_path, ["ABETALIPOPROTEINEMIA", "", "  ACONITASE 2  "])
    terms = pubmed_counts.read_terms(path)
    assert terms == ["ABETALIPOPROTEINEMIA", "ACONITASE 2"]


def test_read_terms_from_csv_first_column(tmp_path):
    path = tmp_path / "terms.csv"
    path.write_text("ABETALIPOPROTEINEMIA\nACONITASE 2\n", encoding="utf-8")
    terms = pubmed_counts.read_terms(path)
    assert terms == ["ABETALIPOPROTEINEMIA", "ACONITASE 2"]


def test_exact_query_quotes_the_phrase():
    assert pubmed_counts.exact_query("ACHALASIA-PROGEROID SYNDROME") == '"ACHALASIA-PROGEROID SYNDROME"'


def test_natural_query_is_unquoted_trimmed():
    assert pubmed_counts.natural_query("  ACONITASE 2 ") == "ACONITASE 2"


def test_pubmed_url_encodes_the_query():
    url = pubmed_counts.pubmed_url('"ACONITASE 2"')
    assert url == "https://pubmed.ncbi.nlm.nih.gov/?term=%22ACONITASE+2%22"
