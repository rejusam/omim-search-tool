import pytest

import overlap_check


def test_normalize_title_strips_case_and_punctuation():
    assert overlap_check.normalize_title("Charcot-Marie-Tooth: a review!") == \
        "charcot marie tooth a review"


def test_normalize_title_collapses_whitespace():
    assert overlap_check.normalize_title("  Two   words ") == "two words"


def test_read_csv_export_reads_scopus_column_names(tmp_path):
    path = tmp_path / "scopus.csv"
    path.write_text(
        "Authors,Title,Year,Source title,DOI,PubMed ID\n"
        "Smith J.,A study of vestibulopathy,2019,Ear and Hearing,10.1/ABC,12345\n",
        encoding="utf-8",
    )
    records = overlap_check.read_export(path)
    assert records == [{
        "pmid": "12345",
        "doi": "10.1/abc",
        "title": "A study of vestibulopathy",
        "year": "2019",
        "source": "Ear and Hearing",
    }]


def test_read_csv_export_leaves_missing_columns_empty(tmp_path):
    path = tmp_path / "ovid.csv"
    path.write_text("title,year\nA paper,2001\n", encoding="utf-8")
    records = overlap_check.read_export(path)
    assert records[0]["title"] == "A paper"
    assert records[0]["pmid"] == ""
    assert records[0]["doi"] == ""


def test_read_ris_export_splits_on_er(tmp_path):
    path = tmp_path / "export.ris"
    path.write_text(
        "TY  - JOUR\nTI  - First paper\nPY  - 2019\nDO  - 10.1/ONE\nER  - \n"
        "TY  - JOUR\nTI  - Second paper\nPY  - 2020\nER  - \n",
        encoding="utf-8",
    )
    records = overlap_check.read_export(path)
    assert len(records) == 2
    assert records[0]["title"] == "First paper"
    assert records[0]["doi"] == "10.1/one"
    assert records[1]["title"] == "Second paper"
    assert records[1]["doi"] == ""


def test_read_ris_export_keeps_a_final_record_without_trailing_er(tmp_path):
    path = tmp_path / "export.ris"
    path.write_text("TY  - JOUR\nTI  - Only paper\nPY  - 1999\n", encoding="utf-8")
    records = overlap_check.read_export(path)
    assert len(records) == 1
    assert records[0]["title"] == "Only paper"


def _rec(pmid="", doi="", title="", year="", source=""):
    return {"pmid": pmid, "doi": doi, "title": title, "year": year, "source": source}


def test_match_reason_prefers_pmid():
    index = overlap_check.build_index([_rec(pmid="1", title="A paper")])
    assert overlap_check.match_reason(_rec(pmid="1", title="Different"), index) == "pmid"


def test_match_reason_falls_back_to_doi_then_title():
    index = overlap_check.build_index([
        _rec(doi="10.1/x", title="Something else"),
        _rec(title="A paper"),
    ])
    assert overlap_check.match_reason(_rec(doi="10.1/X"), index) == "doi"
    assert overlap_check.match_reason(_rec(title="a  paper."), index) == "title"


def test_match_reason_returns_none_for_a_new_record():
    index = overlap_check.build_index([_rec(pmid="1", title="A paper")])
    assert overlap_check.match_reason(_rec(pmid="2", title="Another"), index) is None


def test_compare_counts_each_match_type_and_the_remainder():
    reference = [
        _rec(pmid="1", title="First"),
        _rec(doi="10.1/two", title="Second"),
        _rec(title="Third paper"),
    ]
    exported = [
        _rec(pmid="1", title="First"),
        _rec(doi="10.1/TWO", title="Second, renamed"),
        _rec(title="third paper"),
        _rec(pmid="9", title="Brand new"),
    ]
    result = overlap_check.compare(exported, reference)
    assert result["matched"] == {"pmid": 1, "doi": 1, "title": 1}
    assert result["already_held"] == 3
    assert result["new"] == 1
    assert result["new_records"][0]["title"] == "Brand new"


def test_format_report_counts_new_records_without_a_pmid():
    result = overlap_check.compare(
        [_rec(title="No pmid here"), _rec(pmid="7", title="Has pmid")],
        [_rec(pmid="1", title="Held")],
    )
    text = overlap_check.format_report(result, "export.csv", "held.csv")
    assert "New to screening: 2" in text
    assert "not indexed in PubMed: 1" in text


def test_run_writes_the_new_records_csv(tmp_path):
    export = tmp_path / "export.csv"
    export.write_text(
        "Title,Year,DOI,PubMed ID\nHeld already,2001,,111\nBrand new,2002,,222\n",
        encoding="utf-8",
    )
    reference = tmp_path / "held.csv"
    reference.write_text("pmid,title\n111,Held already\n", encoding="utf-8")
    out = tmp_path / "new_records.csv"

    result = overlap_check.run(export, reference, output_path=out)

    assert result["new"] == 1
    text = out.read_text(encoding="utf-8-sig")
    assert "Brand new" in text
    assert "Held already" not in text


def test_run_raises_on_an_empty_export(tmp_path):
    export = tmp_path / "export.csv"
    export.write_text("Title,Year\n", encoding="utf-8")
    reference = tmp_path / "held.csv"
    reference.write_text("pmid,title\n111,Held already\n", encoding="utf-8")
    with pytest.raises(ValueError):
        overlap_check.run(export, reference)


def test_main_reports_a_missing_file(tmp_path, capsys):
    reference = tmp_path / "held.csv"
    reference.write_text("pmid,title\n111,x\n", encoding="utf-8")
    code = overlap_check.main([
        "overlap_check.py", str(tmp_path / "nope.csv"), "--against", str(reference)
    ])
    assert code == 1
    assert "No such file" in capsys.readouterr().out


def test_read_ris_export_uses_the_ovid_id_tag_as_pmid_for_medline(tmp_path):
    path = tmp_path / "medline.ris"
    path.write_text(
        "TY  - JOUR\nDB  - Ovid MEDLINE(R) 1946-Present\nID  - 32672909\n"
        "T1  - SPTBN4 Disorder.\nY1  - 1993//\nER  - \n",
        encoding="utf-8",
    )
    records = overlap_check.read_export(path)
    assert records[0]["pmid"] == "32672909"


def test_read_ris_export_ignores_the_id_tag_for_embase(tmp_path):
    path = tmp_path / "embase.ris"
    path.write_text(
        "TY  - JOUR\nDB  - Embase\nID  - 32672909\nT1  - A paper.\nER  - \n",
        encoding="utf-8",
    )
    records = overlap_check.read_export(path)
    assert records[0]["pmid"] == ""
