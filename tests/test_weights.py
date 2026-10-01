"""Port R's test-weights.R: the session scheme, post-stratification, raking, opt-outs and the weight cache."""

import pandas as pd
import pytest

import ezrsurvey as ez
from ezrsurvey import weights as weighting

GENDER = {"variable": "demo_gender", "Male": 0.49, "Female": 0.50, "Non-binary": 0.01}
REGION = {"variable": "region", "North America": 0.30, "Europe": 0.30, "Asia": 0.20, "Latin America": 0.10, "Oceania": 0.10}


def test_the_scheme_can_be_set_read_and_cleared():
    assert ez.has_weights() is False
    ez.set_weights(GENDER)
    assert ez.has_weights() is True
    spec = ez.get_weights()
    assert list(spec) == ["demo_gender"]
    assert sum(spec["demo_gender"].values()) == pytest.approx(1)
    ez.clear_weights()
    assert ez.has_weights() is False


def test_single_variable_weights_are_exact():
    ez.set_weights(GENDER)
    p = ez.calc_percentage(ez.podracing_survey, "demo_gender")
    assert "wpct" in p.columns
    got = dict(zip(p["demo_gender"].astype(str), p["wpct"]))
    assert got["Male"] == 49
    assert got["Female"] == 50
    assert got["Non-binary"] == 1


def test_weight_vector_is_normalised_to_mean_one():
    w = ez.weight_vector(ez.podracing_survey, GENDER)
    assert len(w) == len(ez.podracing_survey)
    assert w.mean() == pytest.approx(1, abs=1e-8)
    assert (w > 0).all()


def test_raking_matches_every_margin():
    ez.set_weights(GENDER, REGION)
    g = ez.calc_percentage(ez.podracing_survey, "demo_gender")
    r = ez.calc_percentage(ez.podracing_survey, "region")
    assert sorted(g["wpct"]) == [1, 49, 50]
    assert sorted(r["wpct"]) == [10, 10, 20, 30, 30]


def test_false_forces_unweighted_and_true_needs_a_scheme():
    ez.set_weights(GENDER)
    p = ez.calc_percentage(ez.podracing_survey, "satis_return", weights=False)
    assert "wpct" not in p.columns
    ez.clear_weights()
    with pytest.raises(ValueError, match="no weighting scheme"):
        ez.calc_percentage(ez.podracing_survey, "satis_return", weights=True)


def test_an_ad_hoc_scheme_sets_no_state():
    p = ez.calc_percentage(ez.podracing_survey, "demo_gender", weights=GENDER)
    assert "wpct" in p.columns
    assert ez.has_weights() is False


def test_a_category_with_no_target_is_an_error():
    with pytest.raises(ValueError, match="no weight target"):
        ez.weight_vector(ez.podracing_survey, {"variable": "demo_gender", "Male": 1})


def test_nps_and_summary_are_weighted():
    base_nps_mean = ez.calc_summary(ez.podracing_survey, "nps_value")["mean"].iloc[0]
    base_mean = ez.calc_summary(ez.podracing_survey, "demo_age")["mean"].iloc[0]
    ez.set_weights(GENDER)
    weighted_nps = ez.calc_nps(ez.podracing_survey, "nps_value")
    weighted_summary = ez.calc_summary(ez.podracing_survey, "demo_age")
    assert list(weighted_nps.columns) == [
        "n",
        "nps",
        "pct_detractors",
        "pct_passives",
        "pct_promoters",
        "detractors",
        "passives",
        "promoters",
    ]
    assert list(weighted_summary.columns) == ["n", "mean", "median", "sd"]
    assert ez.calc_summary(ez.podracing_survey, "nps_value")["mean"].iloc[0] != base_nps_mean
    assert weighted_summary["mean"].iloc[0] != base_mean
    assert weighted_nps["n"].tolist() == [1000]


def test_crosstab_defaults_to_weighted_cells():
    base = ez.crosstab(ez.podracing_survey, "region", "demo_gender", cell="row_pct")
    ez.set_weights(GENDER)
    weighted = ez.crosstab(ez.podracing_survey, "region", "demo_gender", cell="row_pct")
    assert base.shape == weighted.shape
    assert not base.equals(weighted)
    assert (weighted["Non-binary"].dropna() <= 4).all()


def test_the_named_form_equals_the_vector_form():
    a = ez.weight_vector(ez.podracing_survey, GENDER)
    b = ez.weight_vector(ez.podracing_survey, {"demo_gender": {"Male": 0.49, "Female": 0.50, "Non-binary": 0.01}})
    pd.testing.assert_series_equal(a, b)


def test_weights_are_computed_once_and_reused():
    ez.clear_weights_cache()
    spec = weighting.parse_weight_spec(GENDER)
    a = weighting.compute_weights(ez.podracing_survey, spec)
    assert len(weighting.WEIGHT_CACHE) == 1
    b = weighting.compute_weights(ez.podracing_survey, spec)
    assert (a == b).all()
    assert len(weighting.WEIGHT_CACHE) == 1


def test_editing_the_weighting_column_invalidates_the_cache():
    ez.clear_weights_cache()
    spec = weighting.parse_weight_spec(GENDER)
    a = weighting.compute_weights(ez.podracing_survey, spec)
    edited = ez.podracing_survey
    edited.loc[:199, "demo_gender"] = "Female"
    b = weighting.compute_weights(edited, spec)
    assert not (a == b).all()
    assert (b == weighting.rake_weights(edited, spec, 50, 1e-6)).all()


def test_clear_weights_cache_empties_the_cache():
    weighting.compute_weights(ez.podracing_survey, weighting.parse_weight_spec(GENDER))
    assert len(weighting.WEIGHT_CACHE) > 0
    ez.clear_weights_cache()
    assert len(weighting.WEIGHT_CACHE) == 0
