"""Port R's test-orders.R: the order registry, automatic application, profiles, and orders reaching rows and margins."""

import pandas as pd
import pytest

import ezrsurvey as ez

EDUCATION = [
    "Primary or less",
    "Lower secondary",
    "Upper secondary",
    "Short-cycle tertiary",
    "Bachelor or equivalent",
    "Master or equivalent",
    "Doctoral or equivalent",
]
SEEN = ["In the past week", "In the past month", "In the past year", "Never"]


def test_register_get_list_remove():
    ez.register_order("edu_t", ["low", "mid", "high"], vars="demo_edu", prefixes="edu_")
    assert ez.get_order("edu_t") == ["low", "mid", "high"]
    listed = ez.list_orders()
    assert "edu_t" in listed["name"].tolist()
    assert listed.loc[listed["name"] == "edu_t", "n_levels"].tolist() == [3]
    ez.remove_order("edu_t")
    assert "edu_t" not in ez.list_orders()["name"].tolist()
    with pytest.raises(ValueError):
        ez.get_order("edu_t")


def test_order_for_matches_exact_var_then_prefix():
    ez.register_order("a", ["x", "y"], vars="demo_edu")
    ez.register_order("b", ["p", "q"], prefixes="rate_")
    assert ez.order_for("demo_edu") == ["x", "y"]
    assert ez.order_for("rate_quality") == ["p", "q"]
    assert ez.order_for("unmatched_col") is None


def test_apply_order_by_name_and_by_var():
    ez.register_order("size", ["S", "M", "L"], vars="tshirt")
    assert list(ez.apply_order(["L", "S"], name="size").cat.categories) == ["S", "M", "L"]
    assert list(ez.apply_order(["M"], var="tshirt").cat.categories) == ["S", "M", "L"]
    assert ez.apply_order(["a", "b"], var="nope") == ["a", "b"]


def test_calc_percentage_applies_a_registered_order():
    ez.register_order("edu_order", levels=EDUCATION, vars="demo_edu")
    out = ez.calc_percentage(ez.podracing_survey, "demo_edu")
    assert isinstance(out["demo_edu"].dtype, pd.CategoricalDtype)
    assert out["demo_edu"].cat.categories[0] == "Primary or less"
    out2 = ez.calc_percentage(ez.podracing_survey, "demo_edu", sort="desc")
    assert out2["pct"].tolist() == sorted(out2["pct"], reverse=True)


def test_presets_register_the_expected_names():
    ez.register_order_presets()
    names = ez.list_orders()["name"].tolist()
    assert "likert_bad_good" in names
    assert "education_isced" in names


def test_orders_round_trip_through_a_profile(tmp_path):
    ez.register_order("rt", ["one", "two"], vars="x")
    path = str(tmp_path / "p.yml")
    ez.save_ezrsurvey_profile(path)
    ez.remove_order("rt")
    assert ez.order_for("x") is None
    ez.load_ezrsurvey_profile(path)
    assert ez.order_for("x") == ["one", "two"]


def test_a_registered_order_reaches_the_rows():
    answers = ["In the past week"] * 3 + ["In the past month"] * 5 + ["In the past year"] * 4 + ["Never"] * 2
    d = pd.DataFrame({"seen": answers, "arm": ["a", "b"] * 7})
    ez.register_order("seen_order", levels=SEEN, vars="seen")
    out = ez.calc_percentage(d, "seen")
    assert [str(value) for value in out["seen"]] == SEEN
    grouped = ez.calc_percentage(d, "seen", by="arm")
    assert grouped["arm"].tolist() == ["a"] * 4 + ["b"] * 4
    assert [str(value) for value in grouped.loc[grouped["arm"] == "a", "seen"]] == SEEN


def test_a_registered_order_reaches_both_crosstab_margins():
    seen = ["In the past week", "In the past month", "Never"]
    repeated = []
    for value in seen:
        repeated.extend([value] * 4)
    d = pd.DataFrame({"seen": repeated, "band": ["Under 18", "18-24"] * 6})
    ez.register_order("seen_order", levels=seen, vars="seen")
    ez.register_order("band_order", levels=["Under 18", "18-24"], vars="band")
    wide = ez.crosstab(d, "seen", "band", cell="col_pct")
    assert [str(value) for value in wide["seen"]] == seen
    assert list(wide.columns[1:]) == ["Under 18", "18-24"]
    ez.remove_order("band_order")
    assert [str(value) for value in ez.crosstab(d, "seen", "band", cell="count")["seen"]] == seen
