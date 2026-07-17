import omim_search


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
