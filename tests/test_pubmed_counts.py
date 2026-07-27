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
