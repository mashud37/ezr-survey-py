"""Port R's test-model.R and the table half of test-compare.R: NPS, driver importance, IPM and comparisons."""

import numpy as np
import pandas as pd
import pytest

import ezrsurvey as ez
from ezrsurvey.export import sanitize_sheet_names
from ezrsurvey.model import cut_perf_band

GENDER = {"variable": "demo_gender", "Male": 0.49, "Female": 0.50, "Non-binary": 0.01}


def ten_answers():
    return pd.DataFrame({"v": [10] * 5 + [8] * 3 + [3] * 2})


def test_calc_nps_is_promoters_minus_detractors():
    out = ez.calc_nps(ten_answers(), "v")
    assert out["nps"].tolist() == [30]
    assert out["n"].tolist() == [10]


def test_calc_nps_groups_by():
    out = ez.calc_nps(ez.podracing_survey, "nps_value", by="region")
    assert len(out) == ez.podracing_survey["region"].nunique()
    assert out["nps"].between(-100, 100).all()


def test_calc_nps_reports_the_group_counts_and_shares():
    out = ez.calc_nps(ten_answers(), "v").iloc[0]
    assert (out["promoters"], out["passives"], out["detractors"]) == (5, 3, 2)
    assert (out["pct_promoters"], out["pct_passives"], out["pct_detractors"]) == (50, 30, 20)
    assert out["promoters"] + out["passives"] + out["detractors"] == out["n"]
    assert out["pct_promoters"] - out["pct_detractors"] == out["nps"]


def test_calc_nps_counts_stay_unweighted():
    plain = ez.calc_nps(ez.podracing_survey, "nps_value", weights=False)
    weighted = ez.calc_nps(ez.podracing_survey, "nps_value", weights=GENDER)
    for column in ("n", "promoters", "passives", "detractors"):
        assert weighted[column].tolist() == plain[column].tolist()
    shares = ["pct_detractors", "pct_passives", "pct_promoters"]
    assert weighted[shares].values.tolist() != plain[shares].values.tolist()


@pytest.mark.parametrize("method", ["rwa", "forest", "correlation"])
def test_importance_methods_rescale_to_100_strongest_first(method):
    np.random.seed(1)
    out = ez.calc_importance(ez.podracing_survey, "nps_value", ez.starts_with("ratings_"), method=method)
    assert list(out.columns) == ["feature", "importance"]
    assert len(out) == 6
    assert out["importance"].sum() == pytest.approx(100)
    assert (out["importance"] >= 0).all()
    assert out["importance"].tolist() == sorted(out["importance"], reverse=True)


def test_forest_ranks_the_strongest_driver_as_relative_weights_do():
    np.random.seed(1)
    forest = ez.calc_importance(ez.podracing_survey, "nps_value", ez.starts_with("ratings_"), method="forest")
    weights = ez.calc_importance(ez.podracing_survey, "nps_value", ez.starts_with("ratings_"))
    assert forest["feature"].iloc[0] == weights["feature"].iloc[0]


def test_calc_importance_rejects_an_unknown_method():
    with pytest.raises(ValueError):
        ez.calc_importance(ez.podracing_survey, "nps_value", ez.starts_with("ratings_"), method="magic")


def test_ipm_model_accepts_another_method():
    np.random.seed(1)
    model = ez.ipm_model(ez.podracing_survey, "nps_value", "ratings_", method="forest")
    assert len(model) == 6
    assert model["importance"].sum() == pytest.approx(100)


def test_ipm_model_returns_the_expected_columns():
    model = ez.ipm_model(ez.podracing_survey, "nps_value", "ratings_")
    assert {"feature", "importance", "performance", "perf_class"} <= set(model.columns)
    assert len(model) == 6
    assert isinstance(model["perf_class"].dtype, pd.CategoricalDtype)
    assert model["performance"].between(1, 5).all()


def test_ipm_model_errors_on_a_missing_prefix():
    with pytest.raises(ValueError):
        ez.ipm_model(ez.podracing_survey, "nps_value", "nope_")


def test_perf_class_buckets_by_integer_part():
    model = ez.ipm_model(ez.podracing_survey, "nps_value", "ratings_")
    assert [str(band) for band in model["perf_class"]] == [str(int(np.floor(value))) for value in model["performance"]]
    assert cut_perf_band([3.57]).astype(str).tolist() == ["3"]
    assert cut_perf_band([3.0]).astype(str).tolist() == ["3"]
    assert cut_perf_band([4.99]).astype(str).tolist() == ["4"]


def test_calc_nps_survives_an_empty_frame():
    out = ez.calc_nps(pd.DataFrame({"nps_value": pd.Series([], dtype=float), "region": pd.Series([], dtype=object)}), "nps_value")
    assert out["n"].tolist() == [0]


def test_compare_values_computes_current_minus_previous():
    a = pd.DataFrame({"feature": ["price", "quality"], "performance": [3.0, 4.0]})
    b = pd.DataFrame({"feature": ["price", "quality"], "performance": [2.5, 4.5]})
    out = ez.compare_values(current=b, previous=a)
    assert set(out.columns) == {"feature", "previous", "current", "difference"}
    assert out["difference"].tolist() == [-0.5, 0.5]


def test_compare_values_works_on_percentage_tables():
    data = ez.podracing_survey
    a = ez.calc_percentage(data[data["region"] == "Europe"], "demo_gender")
    b = ez.calc_percentage(data[data["region"] == "North America"], "demo_gender")
    assert "difference" in ez.compare_values(b, a, by="demo_gender", value="pct").columns


def test_compare_values_errors_on_missing_columns():
    with pytest.raises(ValueError):
        ez.compare_values(pd.DataFrame({"feature": ["x"], "score": [1]}), pd.DataFrame({"feature": ["x"], "performance": [1]}))


def test_export_xlsx_writes_one_tab_per_table(tmp_path):
    path = str(tmp_path / "out.xlsx")
    out = ez.export_xlsx(
        ez.calc_percentage(ez.podracing_survey, "demo_job"),
        gender=ez.calc_percentage(ez.podracing_survey, "demo_gender"),
        path=path,
    )
    assert out == path
    assert (tmp_path / "out.xlsx").exists()


def test_sheet_names_are_sanitised_and_unique():
    names = sanitize_sheet_names(["a/b", "a/b", "this is a really long sheet name over limit"])
    assert all(len(name) <= 31 for name in names)
    assert len(set(names)) == len(names)
    assert not any("/" in name for name in names)
