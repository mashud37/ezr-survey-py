"""Port R's test-import.R: stacking a folder of exports, column blocks, file-name metadata and question rows."""

import warnings

import pandas as pd
import pytest

import ezrsurvey as ez


def test_read_folder_stacks_and_tags_the_source(tmp_path):
    pd.DataFrame({"id": [1, 2], "x": ["a", "b"]}).to_csv(tmp_path / "one.csv", index=False)
    pd.DataFrame({"id": [3, 4], "x": ["c", "d"]}).to_csv(tmp_path / "two.csv", index=False)
    out = ez.read_folder(str(tmp_path))
    assert len(out) == 4
    assert "file" in out.columns
    assert set(out["file"]) == {"one.csv", "two.csv"}
    assert all(isinstance(value, str) for value in out["id"])


def test_read_folder_errors_helpfully(tmp_path):
    with pytest.raises(ValueError):
        ez.read_folder(str(tmp_path / "does-not-exist"))


def test_select_prefix_keeps_id_and_prefixed_columns():
    out = ez.select_prefix(ez.podracing_survey, "demo_", keep="respondent_id")
    assert out.columns[0] == "respondent_id"
    assert all(name.startswith("demo_") for name in out.columns[1:])


def test_select_suffix_keeps_id_and_suffixed_columns():
    out = ez.select_suffix(ez.podracing_survey, "_com", keep="respondent_id")
    assert out.columns[0] == "respondent_id"
    assert set(out.columns[1:]) == {"nps_com", "show_com"}


def test_parse_filename_splits_metadata():
    out = ez.parse_filename(pd.DataFrame({"file": ["podracing_wave1_NA_2026.csv"]}), into=["survey", "wave", "locale", "year"])
    assert out["survey"].tolist() == ["podracing"]
    assert out["year"].tolist() == ["2026"]
    assert "file" in out.columns


def test_a_second_header_row_is_reported(tmp_path):
    (tmp_path / "export.csv").write_text(
        'id,gender,satisfaction\n"Response ID","What is your gender please?","How satisfied were you?"\n'
        "1,Male,Good\n2,Female,Ok\n",
        encoding="utf-8",
    )
    with pytest.warns(UserWarning, match="question wording"):
        ez.read_folder(str(tmp_path))
    assert len(ez.read_folder(str(tmp_path), question_row=False)) == 3
    dropped = ez.read_folder(str(tmp_path), question_row=True)
    assert len(dropped) == 2
    assert dropped["gender"].iloc[0] == "Male"


def test_an_ordinary_export_is_not_mistaken_for_one(tmp_path):
    ez.podracing_survey.head(3).to_csv(tmp_path / "a.csv", index=False)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        ez.read_folder(str(tmp_path))
