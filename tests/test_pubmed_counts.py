import pathlib

import openpyxl
import pytest
import requests

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
    assert no_key.pause_seconds == 0.34
    assert with_key.pause_seconds == 0.11


def test_client_retries_server_error_then_raises():
    session = _FakeSession([
        _FakeResponse(503, {}),
        _FakeResponse(503, {}),
        _FakeResponse(503, {}),
    ])
    client = pubmed_counts.PubMedClient(
        email="x@example.com", session=session, sleep=lambda seconds: None
    )
    with pytest.raises(pubmed_counts.PubMedError):
        client.count("anything")
    assert len(session.calls) == 3


def test_client_does_not_retry_client_error():
    session = _FakeSession([
        _FakeResponse(400, {}),
        _FakeResponse(200, {"esearchresult": {"count": "5"}}),
    ])
    client = pubmed_counts.PubMedClient(
        email="x@example.com", session=session, sleep=lambda seconds: None
    )
    with pytest.raises(pubmed_counts.PubMedError):
        client.count("anything")
    assert len(session.calls) == 1


def test_client_retries_rate_limit_then_succeeds():
    session = _FakeSession([
        _FakeResponse(429, {}),
        _FakeResponse(200, {"esearchresult": {"count": "7"}}),
    ])
    client = pubmed_counts.PubMedClient(
        email="x@example.com", session=session, sleep=lambda seconds: None
    )
    assert client.count("anything") == 7
    assert len(session.calls) == 2


def test_client_retries_network_error_then_raises():
    class _AlwaysFails:
        def __init__(self):
            self.calls = 0

        def get(self, url, params=None, headers=None, timeout=None):
            self.calls = self.calls + 1
            raise requests.exceptions.ConnectionError("boom")

    session = _AlwaysFails()
    client = pubmed_counts.PubMedClient(
        email="x@example.com", session=session, sleep=lambda seconds: None
    )
    with pytest.raises(pubmed_counts.PubMedError):
        client.count("anything")
    assert session.calls == 3


def test_load_ncbi_config_reads_email_and_key(tmp_path):
    config = tmp_path / "config.ini"
    config.write_text("[ncbi]\nemail = a@b.com\napi_key = k123\n", encoding="utf-8")
    email, api_key = pubmed_counts.load_ncbi_config(config)
    assert email == "a@b.com"
    assert api_key == "k123"


def test_load_ncbi_config_missing_returns_none(tmp_path):
    config = tmp_path / "config.ini"
    email, api_key = pubmed_counts.load_ncbi_config(config)
    assert email is None
    assert api_key is None


def test_save_ncbi_config_preserves_omim_section(tmp_path):
    config = tmp_path / "config.ini"
    config.write_text("[omim]\napi_key = omimkey\n", encoding="utf-8")
    pubmed_counts.save_ncbi_config(config, "a@b.com", "")
    email, api_key = pubmed_counts.load_ncbi_config(config)
    assert email == "a@b.com"
    assert api_key is None
    text = config.read_text(encoding="utf-8")
    assert "omimkey" in text


def test_make_row_computes_gap_and_urls():
    row = pubmed_counts.make_row("ACONITASE 2", 3, 50)
    assert row["term"] == "ACONITASE 2"
    assert row["exact_count"] == 3
    assert row["natural_count"] == 50
    assert row["gap"] == 47
    assert row["exact_url"] == pubmed_counts.pubmed_url('"ACONITASE 2"')
    assert row["natural_url"] == pubmed_counts.pubmed_url("ACONITASE 2")


def test_make_row_blank_gap_on_error():
    row = pubmed_counts.make_row("X", "error", "error")
    assert row["gap"] == ""


def test_write_run_creates_both_files(tmp_path):
    rows = [pubmed_counts.make_row("ACONITASE 2", 3, 50)]
    info = {"Input file": "terms.xlsx", "Run complete": "yes"}
    pubmed_counts.write_run(tmp_path, rows, info)
    assert (tmp_path / "counts.xlsx").exists()
    assert (tmp_path / "counts.csv").exists()
    text = (tmp_path / "counts.csv").read_text(encoding="utf-8-sig")
    assert "ACONITASE 2" in text
    assert "term,exact_count,natural_count,gap,exact_url,natural_url" in text


class _ScriptedClient:
    """Returns queued counts in call order; a PubMedError value raises."""

    def __init__(self, counts):
        self._counts = list(counts)
        self.pause_seconds = 0.0

    def count(self, query):
        value = self._counts.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


def test_count_terms_pairs_exact_then_natural():
    client = _ScriptedClient([3, 50, 0, 900000])
    rows = pubmed_counts.count_terms(client, ["ACONITASE 2", "ACHALASIA PROGEROID SYNDROME"])
    assert rows[0]["exact_count"] == 3
    assert rows[0]["natural_count"] == 50
    assert rows[1]["exact_count"] == 0
    assert rows[1]["natural_count"] == 900000


def test_count_terms_records_error_and_continues():
    client = _ScriptedClient([pubmed_counts.PubMedError("boom"), 7, 9])
    rows = pubmed_counts.count_terms(client, ["BAD", "GOOD"])
    assert rows[0]["exact_count"] == "error"
    assert rows[0]["natural_count"] == "error"
    assert rows[0]["gap"] == ""
    assert rows[1]["exact_count"] == 7
    assert rows[1]["natural_count"] == 9
