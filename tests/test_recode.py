"""Port R's test-recode.R: blanks, bands, worded scales, NPS groups, dropped answers and packed multi-selects."""

import math

import pandas as pd
import pytest

import ezrsurvey as ez
from ezrsurvey.recode import detect_delimiter


def texts(series):
    return [None if pd.isna(value) else value for value in series]


def test_na_blank_converts_blanks_and_non_answers():
    assert texts(ez.na_blank(["Yes", "", "Prefer not to answer", "No"])) == ["Yes", None, None, "No"]
    assert texts(ez.na_blank(["a", "n/a"], also="n/a")) == ["a", None]
    assert texts(ez.na_blank([" x "])) == ["x"]


def test_bin_numeric_assigns_left_closed_bands():
    out = ez.bin_numeric([15, 18, 24, 25, 41], breaks=[0, 18, 25, math.inf], labels=["<18", "18-24", "25+"])
    assert texts(out) == ["<18", "18-24", "18-24", "25+", "25+"]
    with pytest.raises(ValueError):
        ez.bin_numeric([1], breaks=[0, 1, 2], labels=["one"])


def test_recode_age_extracts_digits_and_bands():
    assert texts(ez.recode_age(["17", "22 years", "31", "47"])) == ["17 or younger", "22 to 25", "30 to 34", "35+"]


def test_recode_likert_maps_wordings_and_synonyms():
    assert ez.recode_likert(["Very bad", "Ok", "Good", "Very good"]).tolist() == [1, 3, 4, 5]
    assert ez.recode_likert("not on the scale").isna().all()
    out = ez.recode_likert(["Dissatisfied", "Satisfied"], synonyms={"Bad": "Dissatisfied", "Good": "Satisfied"})
    assert out.tolist() == [2, 4]
    assert ez.recode_likert("4 - Good").tolist() == [4]


def test_recode_likert_prefers_the_longest_matching_level():
    assert ez.recode_likert(["\U0001f642 Very good", "\U0001f610 Good"]).tolist() == [5, 4]
    likeability = ["Very unlikeable", "Unlikeable", "Likeable", "Very likeable"]
    assert ez.recode_likert(["* " + level for level in likeability], levels=likeability).tolist() == [1, 2, 3, 4]
    likelihood = ["Very unlikely", "Unlikely", "Likely", "Very likely"]
    assert ez.recode_likert(["* " + level for level in likelihood], levels=likelihood).tolist() == [1, 2, 3, 4]
    out = ez.recode_likert(["* Satisfied", "* Very satisfied"], synonyms={"Good": "Satisfied", "Very good": "Very satisfied"})
    assert out.tolist() == [4, 5]


def test_nps_group_classifies_ratings():
    assert ez.nps_group([0, 6, 7, 8, 9, 10]).tolist() == [-1, -1, 0, 0, 1, 1]
    assert ez.nps_group([3, 8, 10], labels=True).tolist() == ["Detractor", "Passive", "Promoter"]
    assert ez.nps_group([11]).isna().all()


def test_drop_items_is_case_insensitive():
    out = ez.drop_items(["Yes", "No", "Other", "Don't know"], ["other", "Don't know"])
    assert texts(out) == ["Yes", "No", None, None]
    assert texts(ez.drop_items([" a ", "b"], "a")) == [None, "b"]
    assert texts(ez.drop_items(["a", "b"], [])) == ["a", "b"]
    assert texts(ez.drop_items(["a", "b"], None)) == ["a", "b"]


PACKED = pd.DataFrame({"respondent": [1, 2, 3, 4], "motivations": ["Speed; Drivers", "Speed", "", "Betting; Speed"]})


def test_split_multi_widens_most_chosen_first():
    out = ez.split_multi(PACKED, "motivations")
    assert list(out.columns) == ["respondent", "motivations", "motivations_Speed", "motivations_Betting", "motivations_Drivers"]
    assert out["motivations_Speed"].tolist() == ["Speed", "Speed", "", "Speed"]
    assert out["motivations_Drivers"].tolist() == ["Drivers", "", "", ""]


def test_split_multi_honours_delimiter_and_prefix():
    out = ez.split_multi(pd.DataFrame({"x": ["a/b", "b"]}), "x", split="/", prefix="pick_")
    assert list(out.columns) == ["x", "pick_b", "pick_a"]


def test_split_multi_reproduces_the_packed_percentages():
    direct = ez.calc_percentage_multi(PACKED, "motivations", id="respondent", sort="desc")
    widened = PACKED.pipe(ez.split_multi, "motivations").pipe(ez.calc_percentage_multi, "motivations_", id="respondent", sort="desc")
    assert [str(option) for option in widened["option"]] == [str(option) for option in direct["option"]]
    assert widened["pct"].tolist() == direct["pct"].tolist()


def test_split_multi_treats_an_undelimited_column_as_one_answer():
    out = ez.split_multi(pd.DataFrame({"x": ["a", "b", "a"]}), "x")
    assert out["x_a"].tolist() == ["a", "", "a"]
    with pytest.raises(ValueError):
        ez.split_multi(pd.DataFrame({"x": ["", ""]}), "x")


def test_detect_delimiter_prefers_a_semicolon():
    assert detect_delimiter(["a, b; c", "d"]) == ";"
    assert detect_delimiter(["a, b", "c"]) == ","
    assert detect_delimiter(["a|b", "c"]) == "|"
    assert detect_delimiter(["a", "b", ""]) is None


def test_recode_age_reports_answers_without_a_number(capsys):
    ez.recode_age(["young", "old", "31"])
    assert "held no number" in capsys.readouterr().err
    out = ez.recode_age(["young", "31"], quiet=True)
    assert capsys.readouterr().err == ""
    assert pd.isna(out.iloc[0])


def test_bin_numeric_keeps_its_bands_in_order_not_alphabetical():
    out = ez.bin_numeric([45, 120, 60], breaks=[40, 70, 100, 150], labels=["40-70k", "70-100k", "100-150k"])
    assert isinstance(out.dtype, pd.CategoricalDtype)
    assert list(out.cat.categories) == ["40-70k", "70-100k", "100-150k"]
    table = ez.calc_percentage(pd.DataFrame({"band": out}), "band")
    assert table["band"].tolist() == ["40-70k", "100-150k"]
