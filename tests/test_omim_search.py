import json
import pathlib

import omim_search

FIXTURE_PATH = pathlib.Path(__file__).parent / "fixtures" / "search_response.json"


def _load_entries():
    with open(FIXTURE_PATH, encoding="utf-8") as fixture_file:
        payload = json.load(fixture_file)
    wrapped = payload["omim"]["searchResponse"]["entryList"]
    return [item["entry"] for item in wrapped]


def test_load_api_key_missing_file_returns_none(tmp_path):
    missing = tmp_path / "config.ini"
    assert omim_search.load_api_key(missing) is None


def test_save_then_load_round_trips_key(tmp_path):
    config_path = tmp_path / "config.ini"
    omim_search.save_api_key(config_path, "ABC123")
    assert omim_search.load_api_key(config_path) == "ABC123"


def test_load_api_key_ignores_blank(tmp_path):
    config_path = tmp_path / "config.ini"
    omim_search.save_api_key(config_path, "   ")
    assert omim_search.load_api_key(config_path) is None


def test_quote_term_single_word_unquoted():
    assert omim_search.quote_term("neuropathy") == "neuropathy"


def test_quote_term_multi_word_quoted():
    assert omim_search.quote_term("muscular dystrophy") == '"muscular dystrophy"'


def test_build_query_any_of_wraps_in_required_group():
    query = omim_search.build_query(["neuropathy", "neuronopathy"], [], [])
    assert query == "+(neuropathy neuronopathy)"


def test_build_query_reference_case_has_no_stray_operator():
    # The whole reason guided mode exists: "neuropathy or neuronopathy"
    # must never become a query containing the term "or".
    query = omim_search.build_query(["neuropathy", "neuronopathy"], [], [])
    assert " or " not in query.lower()


def test_build_query_combines_all_three_groups():
    query = omim_search.build_query(["neuropathy"], ["hereditary"], ["diabetic"])
    assert query == "+(neuropathy) +hereditary -diabetic"


def test_build_query_must_include_multiword_is_quoted():
    query = omim_search.build_query([], ["muscular dystrophy"], [])
    assert query == '+"muscular dystrophy"'


def test_build_query_all_empty_raises():
    import pytest
    with pytest.raises(ValueError):
        omim_search.build_query([], [], [])


def test_page_starts_single_page():
    assert omim_search.page_starts(5, None) == [0]


def test_page_starts_exact_multiple():
    assert omim_search.page_starts(40, None) == [0, 20]


def test_page_starts_partial_last_page():
    assert omim_search.page_starts(45, None) == [0, 20, 40]


def test_page_starts_zero_results():
    assert omim_search.page_starts(0, None) == []


def test_page_starts_capped_by_max_results():
    assert omim_search.page_starts(1000, 30) == [0, 20]


def test_page_starts_max_larger_than_total():
    assert omim_search.page_starts(10, 500) == [0]


class FakeResponse:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, responses):
        # responses: a list of FakeResponse, returned in order
        self._responses = list(responses)
        self.calls = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append({"url": url, "params": params, "headers": headers})
        return self._responses.pop(0)


def _client(responses):
    session = FakeSession(responses)
    client = omim_search.OmimClient(
        "TESTKEY", session=session, pause_seconds=0, sleep=lambda seconds: None
    )
    return client, session


def test_request_sends_api_key_header():
    client, session = _client([FakeResponse(200, {"omim": {"ok": True}})])
    client.request("status", {})
    assert session.calls[0]["headers"]["ApiKey"] == "TESTKEY"


def test_request_returns_omim_payload():
    client, _ = _client([FakeResponse(200, {"omim": {"value": 42}})])
    result = client.request("status", {})
    assert result == {"value": 42}


def test_request_401_raises_authfailed():
    import pytest
    client, _ = _client([FakeResponse(401)])
    with pytest.raises(omim_search.AuthFailed):
        client.request("status", {})


def test_request_429_raises_quotaexhausted_without_retry():
    import pytest
    client, session = _client([FakeResponse(429)])
    with pytest.raises(omim_search.QuotaExhausted):
        client.request("status", {})
    assert len(session.calls) == 1  # not retried


def test_request_500_retries_then_raises():
    import pytest
    client, session = _client([FakeResponse(500), FakeResponse(500), FakeResponse(500)])
    with pytest.raises(omim_search.OmimError):
        client.request("status", {})
    assert len(session.calls) == 3  # 3 attempts


def test_request_500_then_200_succeeds():
    client, session = _client([FakeResponse(500), FakeResponse(200, {"omim": {"ok": 1}})])
    result = client.request("status", {})
    assert result == {"ok": 1}
    assert len(session.calls) == 2


def test_search_builds_expected_path_and_params():
    client, session = _client([FakeResponse(200, {"omim": {"searchResponse": {}}})])
    client.search("+(neuropathy)", start=0, limit=20, include="geneMap")
    call = session.calls[0]
    assert call["url"].endswith("/entry/search")
    assert call["params"]["search"] == "+(neuropathy)"
    assert call["params"]["start"] == 0
    assert call["params"]["limit"] == 20
    assert call["params"]["include"] == "geneMap"
    assert call["params"]["format"] == "json"


def test_entry_to_row_core_fields():
    entries = _load_entries()
    row = omim_search.entry_to_row(entries[0], rank=1)
    assert row["rank"] == 1
    assert row["mim_number"] == 118220
    assert row["prefix"] == "#"
    assert row["status"] == "live"
    assert "CHARCOT-MARIE-TOOTH" in row["preferred_title"]
    assert row["approved_gene_symbol"] == "PMP22"
    assert row["cyto_location"] == "17p12"
    assert row["omim_url"] == "https://omim.org/entry/118220"


def test_entry_to_row_phenotype_summary():
    entries = _load_entries()
    row = omim_search.entry_to_row(entries[0], rank=1)
    assert row["phenotype_count"] == 2
    assert "Charcot-Marie-Tooth disease, type 1A" in row["phenotypes"]
    assert " | " in row["phenotypes"]


def test_entry_to_row_gene_only_entry_has_blank_gene_fields():
    entries = _load_entries()
    row = omim_search.entry_to_row(entries[1], rank=2)
    assert row["mim_number"] == 162400
    assert row["approved_gene_symbol"] == ""
    assert row["phenotype_count"] == 0
    assert row["phenotypes"] == ""


def test_entry_to_phenotype_rows_one_per_phenotype():
    entries = _load_entries()
    rows = omim_search.entry_to_phenotype_rows(entries[0])
    assert len(rows) == 2
    assert rows[0]["phenotype"] == "Charcot-Marie-Tooth disease, type 1A"
    assert rows[0]["phenotype_inheritance"] == "Autosomal dominant"
    assert rows[0]["phenotype_url"] == "https://omim.org/entry/118220"


def test_entry_to_phenotype_rows_gene_only_entry_empty():
    entries = _load_entries()
    rows = omim_search.entry_to_phenotype_rows(entries[1])
    assert rows == []
