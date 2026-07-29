import json

import pytest

import translate_search


def test_normalize_replaces_slash_with_space():
    assert translate_search.normalize("LAMIN A/C") == "LAMIN A C"


def test_normalize_replaces_parentheses_colon_and_plus():
    term = "ATPase, Cu(2+)-TRANSPORTING, ALPHA POLYPEPTIDE"
    assert translate_search.normalize(term) == "ATPase, Cu 2 TRANSPORTING, ALPHA POLYPEPTIDE"


def test_normalize_keeps_commas_and_the_word_or():
    term = "PERIPHERAL NEUROPATHY, AUTOSOMAL RECESSIVE, WITH OR WITHOUT IMPAIRED INTELLECTUAL DEVELOPMENT"
    assert translate_search.normalize(term) == term


def test_normalize_replaces_hyphens_with_spaces_for_pubmed_parity():
    term = "CHARCOT-MARIE-TOOTH DISEASE"
    assert translate_search.normalize(term) == "CHARCOT MARIE TOOTH DISEASE"


def test_normalize_replaces_double_quotes_with_spaces():
    term = 'SO-CALLED "BRITTLE" BONE DISEASE'
    assert translate_search.normalize(term) == "SO CALLED BRITTLE BONE DISEASE"


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


def test_every_term_appears_in_exactly_one_rendered_block():
    terms = ["condition " + str(number) for number in range(137)]
    blocks = translate_search.build_blocks(terms, translate_search.DEFAULT_BLOCK_SIZE)
    rendered = [translate_search.render_block("scopus", block) for block in blocks]

    for term in terms:
        quoted = '"' + term + '"'
        hits = sum(block_text.count(quoted) for block_text in rendered)
        assert hits == 1, term + " appeared " + str(hits) + " times, expected 1"


def test_render_block_scopus_uses_all_field_and_uppercase_or():
    assert translate_search.render_block("scopus", ["a b", "c"]) == 'TITLE-ABS-KEY("a b" OR "c")'


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
    assert 'TITLE-ABS-KEY("vestibulopathy")' in text
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


def test_load_phenotype_terms_reads_one_per_line(tmp_path):
    path = tmp_path / "phenotype.txt"
    path.write_text("auditory neuropathy\n\nvestibulopathy\n", encoding="utf-8")
    assert translate_search.load_phenotype_terms(path) == [
        "auditory neuropathy",
        "vestibulopathy",
    ]


def test_make_pack_folder_is_dated_and_unique(tmp_path):
    first = translate_search.make_pack_folder(tmp_path, "2026-07-29")
    second = translate_search.make_pack_folder(tmp_path, "2026-07-29")
    assert first.name == "searchpack_20260729"
    assert second.name == "searchpack_20260729_2"
    assert first.is_dir() and second.is_dir()


def test_build_instructions_names_every_database_and_the_pubmed_total():
    text = translate_search.build_instructions(9, "kept_terms.csv", "2026-07-29")
    assert "scopus.txt" in text
    assert "cinahl.txt" in text
    assert "ovid_medline.txt" in text
    assert "ovid_embase.txt" in text
    assert "559" in text
    assert "RIS" in text


def test_build_instructions_requires_starting_from_an_empty_history():
    text = translate_search.build_instructions(9, "kept_terms.csv", "2026-07-29")
    assert "empty search history" in text
    assert "clear" in text.lower()
    assert "set numbers 1 to 10" in text


def test_build_instructions_requires_exactly_the_expected_set_count():
    text = translate_search.build_instructions(9, "kept_terms.csv", "2026-07-29")
    assert "exactly 10 numbered sets" in text
    assert "Fewer means a block failed to run" in text
    assert "More means the history was not empty" in text


def test_run_writes_every_expected_file(tmp_path):
    terms_file = tmp_path / "kept_terms.csv"
    terms_file.write_text("final_term\nWilson disease\nLAMIN A/C\n", encoding="utf-8")
    results = tmp_path / "results"

    folder = translate_search.run(
        terms_file, results_dir=results, block_size=1, skip_header=True,
        generated="2026-07-29",
    )

    names = sorted(item.name for item in folder.iterdir())
    assert names == [
        "INSTRUCTIONS.md",
        "cinahl.txt",
        "ovid_embase.txt",
        "ovid_medline.txt",
        "scopus.txt",
        "search_summary.json",
        "term_normalization.csv",
    ]


def test_run_writes_normalized_terms_into_the_queries(tmp_path):
    terms_file = tmp_path / "kept_terms.csv"
    terms_file.write_text("LAMIN A/C\n", encoding="utf-8")
    folder = translate_search.run(
        terms_file, results_dir=tmp_path / "results", generated="2026-07-29"
    )
    text = (folder / "scopus.txt").read_text(encoding="utf-8")
    assert 'TITLE-ABS-KEY("LAMIN A C")' in text
    assert "LAMIN A/C" not in text


def test_run_records_counts_in_the_summary(tmp_path):
    terms_file = tmp_path / "kept_terms.csv"
    terms_file.write_text("Wilson disease\nLAMIN A/C\nFABRY DISEASE\n", encoding="utf-8")
    folder = translate_search.run(
        terms_file, results_dir=tmp_path / "results", block_size=2,
        generated="2026-07-29",
    )
    summary = json.loads((folder / "search_summary.json").read_text(encoding="utf-8"))
    assert summary["terms"] == 3
    assert summary["blocks"] == 2
    assert summary["block_size"] == 2
    assert summary["terms_normalized"] == 1
    assert summary["source_file"] == "kept_terms.csv"
    assert len(summary["block_chars"]["scopus"]) == 2
    assert summary["phenotype_block_chars"]["scopus"] == len(
        translate_search.render_block("scopus", translate_search.PHENOTYPE_TERMS)
    )


def test_run_writes_the_normalization_audit(tmp_path):
    terms_file = tmp_path / "kept_terms.csv"
    terms_file.write_text("LAMIN A/C\nWilson disease\n", encoding="utf-8")
    folder = translate_search.run(
        terms_file, results_dir=tmp_path / "results", generated="2026-07-29"
    )
    text = (folder / "term_normalization.csv").read_text(encoding="utf-8-sig")
    assert "original,searched,changed" in text
    assert "LAMIN A/C,LAMIN A C,yes" in text
    assert "Wilson disease,Wilson disease,no" in text


def test_run_prints_the_term_count_and_first_and_last_term(tmp_path, capsys):
    terms_file = tmp_path / "kept_terms.csv"
    terms_file.write_text(
        "final_term\nWilson disease\nLAMIN A/C\nFABRY DISEASE\n", encoding="utf-8"
    )
    translate_search.run(
        terms_file, results_dir=tmp_path / "results", skip_header=True,
        generated="2026-07-29",
    )
    out = capsys.readouterr().out
    assert "3 terms" in out
    assert "Wilson disease" in out
    assert "FABRY DISEASE" in out


def test_run_raises_on_an_empty_term_file(tmp_path):
    terms_file = tmp_path / "kept_terms.csv"
    terms_file.write_text("\n", encoding="utf-8")
    with pytest.raises(ValueError):
        translate_search.run(
            terms_file, results_dir=tmp_path / "results", generated="2026-07-29"
        )


def test_run_uses_a_custom_phenotype_file(tmp_path):
    terms_file = tmp_path / "kept_terms.csv"
    terms_file.write_text("Wilson disease\n", encoding="utf-8")
    phenotype_file = tmp_path / "phenotype.txt"
    phenotype_file.write_text("custom filter term\n", encoding="utf-8")

    folder = translate_search.run(
        terms_file, results_dir=tmp_path / "results",
        phenotype_path=phenotype_file, generated="2026-07-29",
    )

    text = (folder / "scopus.txt").read_text(encoding="utf-8")
    assert 'TITLE-ABS-KEY("custom filter term")' in text
    assert "auditory neuropathy" not in text


def test_run_normalizes_phenotype_terms_like_condition_terms(tmp_path):
    terms_file = tmp_path / "kept_terms.csv"
    terms_file.write_text("Wilson disease\n", encoding="utf-8")
    phenotype_file = tmp_path / "phenotype.txt"
    phenotype_file.write_text("CHARCOT-MARIE-TOOTH filter\n", encoding="utf-8")

    folder = translate_search.run(
        terms_file, results_dir=tmp_path / "results",
        phenotype_path=phenotype_file, generated="2026-07-29",
    )

    text = (folder / "scopus.txt").read_text(encoding="utf-8")
    assert 'TITLE-ABS-KEY("CHARCOT MARIE TOOTH filter")' in text


def test_run_raises_on_an_empty_phenotype_file(tmp_path):
    terms_file = tmp_path / "kept_terms.csv"
    terms_file.write_text("Wilson disease\n", encoding="utf-8")
    phenotype_file = tmp_path / "phenotype.txt"
    phenotype_file.write_text("\n", encoding="utf-8")

    with pytest.raises(ValueError):
        translate_search.run(
            terms_file, results_dir=tmp_path / "results",
            phenotype_path=phenotype_file, generated="2026-07-29",
        )


def test_run_leaves_no_folder_behind_when_a_block_is_too_long(tmp_path):
    terms_file = tmp_path / "kept_terms.csv"
    terms_file.write_text("Wilson disease\nFABRY DISEASE\n", encoding="utf-8")
    results = tmp_path / "results"
    with pytest.raises(translate_search.BlockTooLongError):
        translate_search.run(
            terms_file, results_dir=results, max_chars=10, generated="2026-07-29"
        )
    assert not results.exists()


def test_main_reports_a_missing_file(tmp_path, capsys):
    code = translate_search.main(["translate_search.py", str(tmp_path / "nope.csv")])
    assert code == 1
    assert "No such file" in capsys.readouterr().out
