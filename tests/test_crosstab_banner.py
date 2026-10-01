"""Port R's test-crosstab_banner.R: the master table, automatic selection, checkpoints and confirmation."""

import importlib
import os

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

import ezrsurvey as ez
from ezrsurvey import confirm as confirming
from ezrsurvey.confirm import confirm_lines, confirm_on, confirm_selection

banner = importlib.import_module("ezrsurvey.crosstab_banner")
podracing_survey = ez.podracing_survey
ORIGINAL_BLOCK = banner.banner_block_cat
CALLS = {"count": 0}


def interrupted_block(*arguments):
    CALLS["count"] += 1
    if CALLS["count"] == 2:
        raise RuntimeError("interrupted")
    return ORIGINAL_BLOCK(*arguments)


def answer_no(prompt):
    return "n"


def body(table):
    return table[[name for name in table.columns if name not in ("variable", "item")]]


def test_wide_master_table_with_overall_first():
    b = ez.crosstab_banner(podracing_survey, rows="satis_return", cols="region")
    assert list(b.columns[:3]) == ["variable", "item", "Overall"]
    assert (b["variable"] == "satis_return").all()


def test_each_column_sums_to_100_within_a_block():
    b = ez.crosstab_banner(podracing_survey, rows="satis_return", cols="region")
    assert (abs(body(b).sum() - 100) <= 2).all()


def test_empty_cells_are_zero():
    b = ez.crosstab_banner(podracing_survey, rows="demo_gender", cols="region", cell="count")
    assert not body(b).isna().any().any()


def test_numeric_questions_become_a_statistics_block():
    b = ez.crosstab_banner(podracing_survey, rows="nps_value", cols="demo_gender")
    assert set(b["item"]) == {"mean", "median", "sd", "p25", "p75"}
    assert ((b["Overall"] >= 0) & (b["Overall"] <= 10)).all()


def test_stats_selects_the_statistics():
    b = ez.crosstab_banner(podracing_survey, rows="nps_value", cols="demo_gender", stats=["mean", "sd"])
    assert set(b["item"]) == {"mean", "sd"}


def test_rows_mix_categorical_and_numeric():
    b = ez.crosstab_banner(podracing_survey, rows=["satis_return", "nps_value"], cols="region")
    assert set(b["variable"]) == {"satis_return", "nps_value"}


def test_diff_keeps_overall_and_shows_differences():
    raw = ez.crosstab_banner(podracing_survey, rows="satis_return", cols="region")
    diff = ez.crosstab_banner(podracing_survey, rows="satis_return", cols="region", cell="diff")
    assert diff["Overall"].tolist() == raw["Overall"].tolist()
    assert diff["Asia"].tolist() == (raw["Asia"] - raw["Overall"]).tolist()


def test_long_returns_five_columns():
    long = ez.crosstab_banner(podracing_survey, rows="satis_return", cols="region", long=True)
    assert set(long.columns) == {"variable", "item", "group", "group_item", "value"}
    assert "Overall" in long["group"].tolist()


def test_total_false_drops_overall():
    b = ez.crosstab_banner(podracing_survey, rows="satis_return", cols="region", total=False)
    assert "Overall" not in b.columns


def test_a_variable_is_never_crossed_with_itself():
    long = ez.crosstab_banner(podracing_survey, rows="demo_gender", cols=["demo_gender", "region"], long=True)
    assert "demo_gender" not in long["group"].tolist()


def test_weighting_runs():
    weights = {"variable": "demo_gender", "Male": 0.49, "Female": 0.50, "Non-binary": 0.01}
    b = ez.crosstab_banner(podracing_survey, rows="satis_return", cols="demo_gender", weights=weights)
    assert isinstance(b, pd.DataFrame)


def test_flextable_gives_a_two_row_header():
    table = ez.crosstab_banner(podracing_survey, rows="satis_return", cols=["demo_gender", "region"], flextable=True)
    assert table.columns.nlevels == 2
    assert "demo_gender" in table.columns.get_level_values(0)


def test_spanners_record_each_columns_group():
    b = ez.crosstab_banner(podracing_survey, rows="satis_return", cols=["demo_gender", "region"])
    spanners = b.attrs["banner_spanners"]
    assert {"col", "group", "label"} <= set(spanners.columns)
    assert {"Overall", "demo_gender", "region"} <= set(spanners["group"])


def test_data_only_crosses_every_eligible_variable():
    b = ez.crosstab_banner(podracing_survey)
    assert list(b.columns[:3]) == ["variable", "item", "Overall"]
    assert "respondent_id" not in b["variable"].tolist()
    assert "nps_com" not in b["variable"].tolist()
    assert "respondent_id" not in b.attrs["banner_spanners"]["group"].tolist()
    assert len(b.columns) > 10
    assert "motivations" in b["variable"].tolist()
    assert "motivations_speed" not in b["variable"].tolist()


def test_one_side_may_be_automatic():
    b = ez.crosstab_banner(podracing_survey, rows="satis_return")
    assert set(b["variable"]) == {"satis_return"}
    assert len(b.columns) > 3


def test_max_levels_bounds_the_automatic_selection():
    b = ez.crosstab_banner(podracing_survey, max_levels=5)
    groups = b.attrs["banner_spanners"]["group"].tolist()
    assert "demo_edu" not in groups
    assert "demo_gender" in groups


def test_a_multi_select_block_is_one_question():
    b = ez.crosstab_banner(podracing_survey, rows=ez.starts_with("motivations_"), cols="region")
    assert set(b["variable"]) == {"motivations"}
    assert len(b) > 1
    assert ((b["Overall"] >= 0) & (b["Overall"] <= 100)).all()


def test_mean_on_a_categorical_question_errors():
    with pytest.raises(ValueError, match="numeric"):
        ez.crosstab_banner(podracing_survey, rows="demo_gender", cols="region", cell="mean")


def test_a_checkpointed_banner_resumes(tmp_path, monkeypatch):
    d = podracing_survey[["satis_return", "demo_gender", "region"]]
    want = ez.crosstab_banner(d)
    checkpoint = str(tmp_path / "run.pkl")
    CALLS["count"] = 0
    monkeypatch.setattr(banner, "banner_block_cat", interrupted_block)
    with pytest.raises(RuntimeError, match="interrupted"):
        ez.crosstab_banner(d, checkpoint=checkpoint)
    assert os.path.exists(checkpoint)
    monkeypatch.setattr(banner, "banner_block_cat", ORIGINAL_BLOCK)
    got = ez.crosstab_banner(d, checkpoint=checkpoint)
    assert_frame_equal(got, want)


def test_a_checkpoint_from_different_data_is_discarded(tmp_path):
    d = podracing_survey[["satis_return", "demo_gender"]]
    checkpoint = str(tmp_path / "run.pkl")
    ez.crosstab_banner(d, checkpoint=checkpoint)
    d2 = d.copy()
    d2.loc[:99, "satis_return"] = "Very likely"
    assert_frame_equal(ez.crosstab_banner(d2, checkpoint=checkpoint), ez.crosstab_banner(d2))


def test_a_corrupt_checkpoint_does_not_stop_the_run(tmp_path):
    d = podracing_survey[["satis_return", "demo_gender"]]
    checkpoint = tmp_path / "run.pkl"
    checkpoint.write_text("not a pickle", encoding="utf-8")
    assert_frame_equal(ez.crosstab_banner(d, checkpoint=str(checkpoint)), ez.crosstab_banner(d))


def test_checkpoint_accepts_true_and_rejects_nonsense():
    d = podracing_survey.iloc[:80][["satis_return", "demo_gender", "region"]]
    settings = {"col_vars": ["b"], "cell": "pct", "which": None, "total": True, "na_rm": True, "drop": None, "digits": 0}
    fingerprint = banner.banner_fingerprint(d, ["a"], settings)
    assert banner.banner_checkpoint_path(None, fingerprint) is None
    assert banner.banner_checkpoint_path(False, fingerprint) is None
    assert banner.banner_checkpoint_path("my.pkl", fingerprint) == "my.pkl"
    managed = banner.banner_checkpoint_path(True, fingerprint)
    assert os.path.basename(managed).startswith("banner-")
    other_fingerprint = banner.banner_fingerprint(d, ["z"], settings)
    assert managed != banner.banner_checkpoint_path(True, other_fingerprint)
    with pytest.raises(ValueError, match="must be True, False"):
        banner.banner_checkpoint_path(1, fingerprint)


def test_confirmation_is_off_in_scripts_and_validated():
    assert confirm_on("auto") is False
    assert confirm_on(True) is True
    assert confirm_on(False) is False
    with pytest.raises(ValueError, match="must be True, False"):
        confirm_on("yes")
    assert confirm_selection("title", ["line"], setting=False) is True
    assert confirm_lines("Skipped", []) == ["Skipped: none"]
    assert confirm_lines("Questions", ["a", "b"])[0].startswith("Questions (2): a, b")
    d = podracing_survey.iloc[:80][["satis_return", "demo_gender", "region"]]
    assert isinstance(ez.crosstab_banner(d, confirm=True), pd.DataFrame)


def test_declining_the_selection_computes_nothing(monkeypatch):
    d = podracing_survey.iloc[:80][["satis_return", "demo_gender", "region"]]
    monkeypatch.setattr(confirming, "read_answer", answer_no)
    assert ez.crosstab_banner(d, confirm=True) is None
    named = ez.crosstab_banner(d, rows="satis_return", cols="demo_gender", confirm=True)
    assert isinstance(named, pd.DataFrame)


def test_a_finished_run_leaves_no_managed_checkpoint(tmp_path, monkeypatch):
    monkeypatch.setenv("R_USER_CACHE_DIR", str(tmp_path))
    d = podracing_survey.iloc[:80][["satis_return", "demo_gender"]]
    ez.crosstab_banner(d, checkpoint=True)
    assert list(tmp_path.rglob("banner-*")) == []


def test_a_checkpoint_the_caller_named_is_kept(tmp_path):
    d = podracing_survey.iloc[:80][["satis_return", "demo_gender"]]
    checkpoint = tmp_path / "mine.pkl"
    ez.crosstab_banner(d, checkpoint=str(checkpoint))
    assert checkpoint.exists()


def test_clear_checkpoints_empties_the_managed_folder(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("R_USER_CACHE_DIR", str(tmp_path))
    cache = tmp_path / "R" / "ezrsurvey"
    cache.mkdir(parents=True)
    for name in ("banner-aaa.pkl", "banner-bbb.pkl", "notes.txt"):
        (cache / name).write_text("", encoding="utf-8")
    assert ez.clear_checkpoints() == 2
    assert "Removed 2" in capsys.readouterr().err
    assert not list(cache.glob("banner-*"))
    assert (cache / "notes.txt").exists()


def test_a_frame_with_no_rows_is_refused():
    with pytest.raises(ValueError, match="needs at least one row"):
        ez.crosstab_banner(podracing_survey.iloc[0:0], rows="demo_gender", cols="region")


def test_crosstab_banner_copes_with_questions_called_value_or_n():
    d = pd.DataFrame(
        {
            "value": ["Low", "High", "High", "Low", "High", "Low"],
            "n": ["A", "A", "B", "B", "B", "A"],
        }
    )
    banner = ez.crosstab_banner(d, rows="value", cols="n", cell="count")
    assert list(banner.columns) == ["variable", "item", "Overall", "A", "B"]
    assert banner["item"].tolist() == ["High", "Low"]
    assert banner["A"].tolist() == [1, 2]
    assert banner["B"].tolist() == [2, 1]
