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


def test_render_block_scopus_uses_all_field_and_uppercase_or():
    assert translate_search.render_block("scopus", ["a b", "c"]) == 'ALL("a b" OR "c")'


def test_render_block_cinahl_uses_tx_field():
    assert translate_search.render_block("cinahl", ["a b", "c"]) == 'TX ("a b" OR "c")'


def test_render_block_ovid_uses_mp_suffix_and_lowercase_or():
    assert translate_search.render_block("ovid_medline", ["a b", "c"]) == '("a b" or "c").mp.'
    assert translate_search.render_block("ovid_embase", ["a b", "c"]) == '("a b" or "c").mp.'


def test_combine_lines_scopus_numbering():
    lines = translate_search.combine_lines("scopus", 9)
    assert lines[0] == "#1 OR #2 OR #3 OR #4 OR #5 OR #6 OR #7 OR #8 OR #9"
    assert lines[1] == "#11 AND #10"


def test_combine_lines_cinahl_uses_s_prefix():
    lines = translate_search.combine_lines("cinahl", 2)
    assert lines[0] == "S1 OR S2"
    assert lines[1] == "S4 AND S3"


def test_combine_lines_ovid_uses_bare_numbers_and_lowercase():
    lines = translate_search.combine_lines("ovid_medline", 2)
    assert lines[0] == "1 or 2"
    assert lines[1] == "4 and 3"


def test_render_file_has_a_block_header_per_block_plus_phenotype():
    blocks = [["a"], ["b"]]
    text = translate_search.render_file(
        "scopus", blocks, ["vestibulopathy"], "kept_terms.csv", "2026-07-29"
    )
    assert "--- BLOCK 1 of 3 (condition terms) ---" in text
    assert "--- BLOCK 2 of 3 (condition terms) ---" in text
    assert "--- BLOCK 3 of 3 (phenotype filter) ---" in text
    assert 'ALL("vestibulopathy")' in text
    assert "#3 AND #2" not in text
    assert "#1 OR #2" in text
    assert "#4 AND #3" in text


def test_render_file_names_the_database_source_and_date():
    text = translate_search.render_file(
        "ovid_embase", [["a"]], ["vestibulopathy"], "kept_terms.csv", "2026-07-29"
    )
    assert "Ovid Embase" in text
    assert "kept_terms.csv" in text
    assert "2026-07-29" in text


def test_render_file_raises_when_a_block_exceeds_max_chars():
    long_terms = ["term number " + str(number) for number in range(100)]
    with pytest.raises(translate_search.BlockTooLongError):
        translate_search.render_file(
            "scopus", [long_terms], ["vestibulopathy"], "kept_terms.csv",
            "2026-07-29", max_chars=200,
        )


def test_or_word_is_a_single_source_of_truth_for_block_and_combine_line():
    original = translate_search.DIALECTS["ovid_medline"]["or_word"]
    translate_search.DIALECTS["ovid_medline"]["or_word"] = "OR"
    try:
        assert translate_search.render_block("ovid_medline", ["a", "b"]) == '("a" OR "b").mp.'
        assert translate_search.combine_lines("ovid_medline", 2)[0] == "1 OR 2"
    finally:
        translate_search.DIALECTS["ovid_medline"]["or_word"] = original
