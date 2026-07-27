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


class _FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class _FakeSession:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append(params)
        return self._responses.pop(0)


def test_parse_count_reads_the_number():
    payload = {"esearchresult": {"count": "1240", "idlist": []}}
    assert pubmed_counts.parse_count(payload) == 1240


def test_parse_count_raises_on_error_payload():
    payload = {"esearchresult": {"ERROR": "Invalid db name"}}
    with pytest.raises(pubmed_counts.PubMedError):
        pubmed_counts.parse_count(payload)


def test_client_count_sends_query_and_returns_number():
    session = _FakeSession([_FakeResponse(200, {"esearchresult": {"count": "5"}})])
    client = pubmed_counts.PubMedClient(
        email="x@example.com", session=session, sleep=lambda seconds: None
    )
    result = client.count('"ACONITASE 2"')
    assert result == 5
    assert session.calls[0]["term"] == '"ACONITASE 2"'
    assert session.calls[0]["retmax"] == 0
    assert session.calls[0]["email"] == "x@example.com"


def test_client_uses_faster_pause_with_api_key():
    no_key = pubmed_counts.PubMedClient(email="x@example.com")
    with_key = pubmed_counts.PubMedClient(email="x@example.com", api_key="abc")
    assert with_key.pause_seconds < no_key.pause_seconds
