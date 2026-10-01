"""Port R's test-percentage.R and test-crosstab.R: percentages, multi-selects, summaries, batches and crosstabs."""

import pandas as pd
import pytest

import ezrsurvey as ez


def test_calc_percentage_matches_a_hand_computed_table():
    out = ez.calc_percentage(pd.DataFrame({"g": ["a", "a", "a", "b", ""]}), "g")
    assert set(out.columns) == {"g", "n", "pct"}
    assert out.loc[out["g"] == "a", "pct"].tolist() == [75]
    assert out.loc[out["g"] == "b", "pct"].tolist() == [25]
    assert out["pct"].sum() == 100


def test_calc_percentage_groups_within_by():
    out = ez.calc_percentage(ez.podracing_survey, "satis_return", by="region")
    assert (abs(out.groupby("region")["pct"].sum() - 100) <= 2).all()


def test_wide_pivots_one_row_per_group():
    out = ez.calc_percentage(ez.podracing_survey, "satis_return", by="region", wide=True)
    assert len(out) == ez.podracing_survey["region"].nunique()
    assert "region" in out.columns
    assert "n" not in out.columns


def test_sort_sets_the_level_order():
    out = ez.calc_percentage(ez.podracing_survey, "demo_gender", sort="desc")
    assert isinstance(out["demo_gender"].dtype, pd.CategoricalDtype)
    assert out["pct"].tolist() == sorted(out["pct"], reverse=True)


def test_multi_uses_the_distinct_respondent_denominator():
    df = pd.DataFrame({"respondent_id": ["r1", "r2", "r3"], "m_a": ["A", "A", ""], "m_b": ["B", "", ""]})
    out = ez.calc_percentage_multi(df, "m_", id="respondent_id")
    assert out.loc[out["option"] == "a", "pct"].tolist() == [100]
    assert out.loc[out["option"] == "b", "pct"].tolist() == [50]


def test_multi_errors_on_a_missing_prefix():
    with pytest.raises(ValueError):
        ez.calc_percentage_multi(ez.podracing_survey, "nope_")


def test_multi_unpacks_a_single_delimited_column():
    df = pd.DataFrame({"respondent_id": ["r1", "r2", "r3", "r4"], "why": ["Speed; Drivers", "Speed", "", "Betting; Speed"]})
    out = ez.calc_percentage_multi(df, "why", id="respondent_id", sort="desc")
    assert [str(option) for option in out["option"]] == ["Speed", "Betting", "Drivers"]
    assert out["n"].tolist() == [3, 1, 1]
    assert out["pct"].tolist() == [100, 33, 33]


def test_multi_detects_each_delimiter_and_trims():
    for packed in (["A; B", "B"], ["A|B", "B"], ["A,  , B", "B"]):
        out = ez.calc_percentage_multi(pd.DataFrame({"id": [1, 2], "why": packed}), "why", id="id", sort="desc")
        assert [str(option) for option in out["option"]] == ["B", "A"]
        assert out["n"].tolist() == [2, 1]


def test_a_semicolon_wins_over_commas_inside_answers():
    df = pd.DataFrame({"id": [1, 2], "why": ["Speed, noise and dust; Friends", "Friends"]})
    out = ez.calc_percentage_multi(df, "why", id="id", sort="desc")
    assert [str(option) for option in out["option"]] == ["Friends", "Speed, noise and dust"]


def test_split_false_and_a_block_keep_the_old_behaviour():
    df = pd.DataFrame({"id": [1, 2], "why": ["A; B", "B"]})
    unsplit = ez.calc_percentage_multi(df, "why", id="id", split=False)
    assert len(unsplit) == 1
    assert unsplit["pct"].tolist() == [100]
    block = ez.calc_percentage_multi(ez.podracing_survey, "motivations_", id="respondent_id", sort="desc")
    assert str(block["option"].iloc[0]) == "speed"


def test_calc_summary_returns_mean_median_sd():
    out = ez.calc_summary(ez.podracing_survey, "demo_age")
    assert set(out.columns) == {"n", "mean", "median", "sd"}
    assert out["n"].iloc[0] == ez.podracing_survey["demo_age"].notna().sum()
    assert out["mean"].iloc[0] == pytest.approx(ez.podracing_survey["demo_age"].mean())


def test_drop_removes_answers_and_rebases():
    df = pd.DataFrame({"g": ["a", "a", "b", "Other", "Other"]})
    full = ez.calc_percentage(df, "g")
    dropped = ez.calc_percentage(df, "g", drop="Other")
    assert "Other" not in dropped["g"].astype(str).tolist()
    assert "Other" in full["g"].astype(str).tolist()
    assert dropped.loc[dropped["g"] == "a", "pct"].tolist() == [67]
    assert dropped["pct"].sum() == 100


def test_drop_works_for_multi_and_reads_the_option():
    multi = ez.calc_percentage_multi(ez.podracing_survey, "motivations_", id="respondent_id", drop="Boonta Eve tradition")
    assert "Boonta Eve tradition" not in multi["option"].astype(str).tolist()
    ez.ezrsurvey_options(drop_answers="Unemployed")
    out = ez.calc_percentage(ez.podracing_survey, "demo_job")
    assert "Unemployed" not in out["demo_job"].astype(str).tolist()


def test_clean_label_undoes_mangling_and_strips_a_prefix():
    assert ez.clean_label("Broadcast.quality...audio") == ["Broadcast quality / audio"]
    assert ez.clean_label("ratings_Camera.work", prefix="ratings_") == ["Camera work"]
    assert ez.clean_label("other_thing", prefix="ratings_") == ["other_thing"]


def test_batch_can_tidy_its_variable_names():
    raw = ez.calc_percentage_batch(ez.podracing_survey, ez.starts_with("ratings_"))
    assert all(name.startswith("ratings_") for name in raw["variable"].unique())
    tidy = ez.calc_percentage_batch(ez.podracing_survey, ez.starts_with("ratings_"), prefix="ratings_")
    assert not any(name.startswith("ratings_") for name in tidy["variable"].unique())
    assert tidy["pct"].tolist() == raw["pct"].tolist()


def test_batch_names_match_ipm_models():
    model = ez.ipm_model(ez.podracing_survey, "nps_value", "ratings_")
    table = ez.calc_percentage_batch(ez.podracing_survey, ez.starts_with("ratings_"), prefix="ratings_")
    assert set(model["feature"]) <= set(table["variable"])


def test_crosstab_counts_one_row_per_x():
    table = ez.crosstab(ez.podracing_survey, "demo_gender", "region")
    assert table.columns[0] == "demo_gender"
    assert len(table) == ez.na_blank(ez.podracing_survey["demo_gender"]).nunique()


def test_crosstab_row_percentages_sum_to_100():
    table = ez.crosstab(ez.podracing_survey, "region", "demo_gender", cell="row_pct")
    numbers = table.select_dtypes("number")
    assert (abs(numbers.sum(axis=1) - 100) <= 2).all()


def test_crosstab_aggregates_a_value_column():
    table = ez.crosstab(ez.podracing_survey, "region", "demo_gender", value="nps_value")
    numbers = table.select_dtypes("number").stack().dropna()
    assert ((numbers >= 0) & (numbers <= 10)).all()


def test_crosstab_long_form():
    table = ez.crosstab(ez.podracing_survey, "demo_gender", "region", wide=False)
    assert set(table.columns) == {"demo_gender", "region", "value"}


def test_default_by_groups_calc_percentage():
    ez.ezrsurvey_options(default_by="region")
    assert "region" in ez.calc_percentage(ez.podracing_survey, "demo_gender").columns


def test_batch_stacks_several_questions():
    out = ez.calc_percentage_batch(ez.podracing_survey, "demo_gender", "demo_job")
    assert {"variable", "answer", "n", "pct"} <= set(out.columns)
    assert set(out["variable"]) == {"demo_gender", "demo_job"}


def test_levels_from_drop_items_leave_the_dropped_answer_out():
    data = pd.DataFrame({"age": ["18-24", "25-34", "25-34", "35+"]})
    levels = ez.drop_items(["18-24", "25-34", "35+", "Prefer not to answer"], items="Prefer not to answer")
    out = ez.calc_percentage(data, "age", levels=levels)
    assert list(out["age"].cat.categories) == ["18-24", "25-34", "35+"]
    assert out["n"].tolist() == [1, 2, 1]


def test_calc_percentage_keeps_a_categoricals_own_answer_order():
    levels = ["Strongly disagree", "Disagree", "Agree", "Strongly agree"]
    answers = ["Agree", "Strongly disagree", "Disagree", "Agree", "Strongly agree", ""]
    d = pd.DataFrame({"agree": pd.Categorical(answers, categories=levels + [""])})
    assert ez.calc_percentage(d, "agree")["agree"].tolist() == levels


def test_crosstab_copes_with_questions_called_value_or_n():
    d = pd.DataFrame({"value": ["Low", "High", "High", "Low", "High"], "n": ["A", "A", "B", "B", "B"]})
    table = ez.crosstab(d, "value", "n")
    assert list(table.columns) == ["value", "A", "B"]
    assert table["value"].tolist() == ["High", "Low"]
    assert table["A"].tolist() == [1, 1]
    assert table["B"].tolist() == [2, 1]
    flipped = ez.crosstab(d, "n", "value", cell="row_pct")
    assert list(flipped.columns) == ["n", "High", "Low"]
    assert flipped["High"].tolist() == [50, 67]
    long = ez.crosstab(d, "n", "n", wide=False)
    assert long["value"].tolist() == [2, 3]
    with pytest.raises(ValueError, match="Rename that column"):
        ez.crosstab(d, "value", "n", wide=False)


def test_crosstab_keeps_a_categoricals_own_answer_order():
    levels = ["Strongly disagree", "Disagree", "Agree", "Strongly agree"]
    d = pd.DataFrame(
        {
            "agree": pd.Categorical(["Disagree", "Agree", "Strongly agree", "Agree"], categories=levels),
            "group": pd.Categorical(["Old", "Young", "Old", "Young"], categories=["Young", "Old"]),
        }
    )
    table = ez.crosstab(d, "agree", "group")
    assert table["agree"].tolist() == ["Disagree", "Agree", "Strongly agree"]
    assert list(table.columns) == ["agree", "Young", "Old"]
