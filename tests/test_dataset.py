"""Port R's test-dataset.R: the session default dataset, positional columns, and helpful column errors."""

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

import ezrsurvey as ez

podracing_survey = ez.podracing_survey
shopping_survey = ez.shopping_survey


def test_use_get_has_clear_round_trip():
    assert ez.has_dataset() is False
    out = ez.use_dataset(podracing_survey)
    assert out is podracing_survey
    assert ez.has_dataset() is True
    assert len(ez.get_dataset()) == 1000
    ez.clear_dataset()
    assert ez.has_dataset() is False
    with pytest.raises(ValueError):
        ez.get_dataset()


def test_helpers_use_the_default_when_data_is_omitted():
    ez.use_dataset(podracing_survey)
    assert_frame_equal(ez.calc_percentage(column="demo_gender"), ez.calc_percentage(podracing_survey, "demo_gender"))
    assert ez.calc_nps(value="nps_value")["nps"].tolist() == ez.calc_nps(podracing_survey, "nps_value")["nps"].tolist()
    assert ez.calc_summary(column="demo_age")["mean"].tolist() == ez.calc_summary(podracing_survey, "demo_age")["mean"].tolist()


def test_columns_can_be_passed_positionally_without_data():
    ez.use_dataset(podracing_survey)
    assert_frame_equal(ez.calc_percentage("demo_gender"), ez.calc_percentage(podracing_survey, "demo_gender"))
    assert_frame_equal(ez.calc_summary("demo_age"), ez.calc_summary(podracing_survey, "demo_age"))
    assert_frame_equal(ez.calc_nps("nps_value"), ez.calc_nps(podracing_survey, "nps_value"))
    assert_frame_equal(
        ez.calc_percentage_multi("motivations_", id="respondent_id"),
        ez.calc_percentage_multi(podracing_survey, "motivations_", id="respondent_id"),
    )
    assert_frame_equal(ez.crosstab("demo_gender", "region"), ez.crosstab(podracing_survey, "demo_gender", "region"))
    assert_frame_equal(ez.diagnose("demo_gender"), ez.diagnose(podracing_survey, "demo_gender"))
    assert_frame_equal(
        ez.calc_percentage_batch("demo_gender", "demo_job"),
        ez.calc_percentage_batch(podracing_survey, "demo_gender", "demo_job"),
    )
    assert_frame_equal(
        ez.calc_percentage(shopping_survey, "demo_gender"),
        shopping_survey.pipe(ez.calc_percentage, "demo_gender"),
    )


def test_helpers_error_helpfully_without_data():
    with pytest.raises(ValueError, match="no default dataset"):
        ez.calc_percentage(column="demo_gender")
    with pytest.raises(ValueError, match="no default dataset"):
        ez.calc_percentage("demo_gender")


def test_use_dataset_rejects_non_data_frames():
    with pytest.raises(ValueError):
        ez.use_dataset(list(range(10)))


def test_open_text_comments_are_unique():
    for data in (podracing_survey, shopping_survey):
        columns = [name for name in data.columns if name.endswith("_com") or name == "comment"]
        assert columns
        values = []
        for name in columns:
            values.extend(value for value in data[name] if isinstance(value, str) and value != "")
        assert len(values) == len(set(values))


def test_mistyped_column_is_named():
    d = pd.DataFrame({"gender": ["Male", "Female"], "nps_value": [9, 3]})
    with pytest.raises(ValueError, match="Column `gendr` not found"):
        ez.calc_percentage(d, "gendr")
    with pytest.raises(ValueError, match="Did you mean `gender`"):
        ez.calc_percentage(d, "gendr")
    with pytest.raises(ValueError, match="Column `nps_valu` not found"):
        ez.calc_summary(d, "nps_valu")
    with pytest.raises(ValueError, match="Column `gendr` not found"):
        ez.crosstab(d, "gendr", "nps_value")
    with pytest.raises(ValueError, match="Column `nps_valu` not found"):
        ez.calc_nps(d, "nps_valu")
    with pytest.raises(ValueError, match="Column `gendr` not found"):
        ez.split_multi(d, "gendr")
    with pytest.raises(ValueError, match="not found in the data"):
        ez.calc_percentage(d, "wholly_unrelated")
