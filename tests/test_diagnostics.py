"""Port R's test-diagnostics.R: standard errors, relative errors, margins, per-column diagnostics and the summary."""

import math
import statistics

import pandas as pd
import pytest

import ezrsurvey as ez

BANDS = {"high precision", "precise", "satisfactory", "use with caution", "likely reliability issues"}


def test_se_mean_matches_sd_over_root_n():
    x = [4, 5, 3, 4, 5, 2, 4]
    assert ez.se_mean(x) == pytest.approx(statistics.stdev(x) / math.sqrt(len(x)))
    assert math.isnan(ez.se_mean([1]))
    assert ez.se_mean([None, 4, 4]) == 0


def test_se_prop_matches_the_closed_form():
    assert ez.se_prop(0.33, 1184) == pytest.approx(math.sqrt(0.33 * 0.67 / 1184))
    assert ez.se_prop(33, 1184) == pytest.approx(ez.se_prop(0.33, 1184))
    with pytest.raises(ValueError):
        ez.se_prop(150, 100)


def test_se_prop_returns_percentage_points_on_request():
    assert ez.se_prop(0.33, 1184, pctp=True) == pytest.approx(ez.se_prop(0.33, 1184) * 100)
    assert ez.se_prop(0.33, 1184, pctp=False) == ez.se_prop(0.33, 1184)


def test_rse_and_margin_of_error_compose():
    se = ez.se_prop(0.33, 1184)
    assert ez.rse(0.33, se) == pytest.approx(se / 0.33 * 100)
    assert ez.margin_of_error(se, z=2) == pytest.approx(2 * se)


def test_diagnose_returns_one_row_per_variable():
    out = ez.diagnose(ez.podracing_survey, "demo_gender", "ratings_atmosphere")
    assert len(out) == 2
    assert {"variable", "type", "n", "estimate", "se", "rse", "moe", "precision"} <= set(out.columns)
    assert (out["se"].dropna() >= 0).all()


def test_diagnose_detects_numeric_and_categorical():
    assert ez.diagnose(ez.podracing_survey, "nps_value")["type"].tolist() == ["mean"]
    assert ez.diagnose(ez.podracing_survey, "demo_gender")["type"].tolist() == ["prop"]


def test_diagnose_groups_by():
    out = ez.diagnose(ez.podracing_survey, "nps_value", by="region")
    assert len(out) == ez.podracing_survey["region"].nunique()
    assert "region" in out.columns


def test_rse_rating_maps_to_five_bands():
    out = ez.rse_rating([3, 8, 12, 20, 40])
    assert out.tolist() == ["high precision", "precise", "satisfactory", "use with caution", "likely reliability issues"]
    assert isinstance(ez.rse_rating(float("nan")), float)


def test_diagnose_precision_uses_the_bands():
    assert ez.diagnose(ez.podracing_survey, "nps_value")["precision"].iloc[0] in BANDS


def test_precision_summary_produces_bullets():
    summary = ez.precision_summary(ez.podracing_survey)
    assert isinstance(summary, ez.diagnostics.EzrsurveyPrecision)
    assert len(summary["bullets"]) >= 3
    assert "total responses" in summary["bullets"][0]
    assert summary["rating"] in BANDS
    assert "Survey precision summary" in repr(summary)


def test_precision_summary_skips_ids_and_free_text():
    table = ez.precision_summary(ez.podracing_survey)["table"]
    assert "respondent_id" not in table["variable"].tolist()
    assert "nps_com" not in table["variable"].tolist()


def test_rse_of_a_zero_estimate_follows_r():
    assert math.isnan(ez.rse(0, 0))
    assert math.isinf(ez.rse(0, 1))
    assert ez.rse(1, 0) == 0


def test_calc_summary_with_both_infinities_gives_nan_as_r_does():
    data = pd.DataFrame({"spend": [1000.0] * 45 + [math.inf, -math.inf, math.nan, math.nan, 0.0]})
    out = ez.calc_summary(data, "spend")
    assert out["n"].tolist() == [48]
    assert math.isnan(out["mean"].iloc[0])
    assert out["median"].tolist() == [1000.0]
    assert math.isnan(out["sd"].iloc[0])
