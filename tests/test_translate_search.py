import pytest

import translate_search


def test_normalize_replaces_slash_with_space():
    assert translate_search.normalize("LAMIN A/C") == "LAMIN A C"


def test_normalize_replaces_parentheses_colon_and_plus():
    term = "ATPase, Cu(2+)-TRANSPORTING, ALPHA POLYPEPTIDE"
    assert translate_search.normalize(term) == "ATPase, Cu 2 -TRANSPORTING, ALPHA POLYPEPTIDE"


def test_normalize_keeps_commas_hyphens_and_the_word_or():
    term = "PERIPHERAL NEUROPATHY, AUTOSOMAL RECESSIVE, WITH OR WITHOUT IMPAIRED INTELLECTUAL DEVELOPMENT"
    assert translate_search.normalize(term) == term


def test_normalize_leaves_plain_term_unchanged():
    assert translate_search.normalize("Wilson disease") == "Wilson disease"


def test_normalization_rows_flag_only_changed_terms():
    rows = translate_search.normalization_rows(["LAMIN A/C", "Wilson disease"])
    assert rows[0] == {
        "original": "LAMIN A/C",
        "searched": "LAMIN A C",
        "changed": "yes",
    }
    assert rows[1]["changed"] == "no"


def test_load_terms_reads_first_column_and_dedupes(tmp_path):
    path = tmp_path / "terms.csv"
    path.write_text("Wilson disease\nLAMIN A/C\nWilson disease\n", encoding="utf-8")
    assert translate_search.load_terms(path) == ["Wilson disease", "LAMIN A/C"]


def test_load_terms_skips_header_when_asked(tmp_path):
    path = tmp_path / "terms.csv"
    path.write_text("final_term\nWilson disease\n", encoding="utf-8")
    assert translate_search.load_terms(path, skip_header=True) == ["Wilson disease"]


def test_build_blocks_splits_evenly():
    blocks = translate_search.build_blocks(["a", "b", "c", "d"], 2)
    assert blocks == [["a", "b"], ["c", "d"]]


def test_build_blocks_leaves_a_short_last_block():
    blocks = translate_search.build_blocks(["a", "b", "c"], 2)
    assert blocks == [["a", "b"], ["c"]]


def test_build_blocks_of_523_terms_at_60_gives_nine():
    terms = ["t" + str(number) for number in range(523)]
    blocks = translate_search.build_blocks(terms, translate_search.DEFAULT_BLOCK_SIZE)
    assert len(blocks) == 9
    assert len(blocks[-1]) == 43


def test_build_blocks_rejects_zero_size():
    with pytest.raises(ValueError):
        translate_search.build_blocks(["a"], 0)
