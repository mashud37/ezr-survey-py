"""Port R's test-comments.R: random and diverse comment samples, checked by behaviour since the draws differ from R's."""

import numpy as np

import ezrsurvey as ez
from ezrsurvey.comments import resolve_stopwords


def test_sample_comments_pulls_from_several_columns():
    out = ez.sample_comments(ez.podracing_survey, "nps_com", "show_com", n=3, by_column=True)
    assert {"source", "comment", "length"} <= set(out.columns)
    assert set(out["source"]) == {"nps_com", "show_com"}
    assert (out["length"] > 30).all()
    assert (out["comment"].str.len() <= 400).all()


def test_sample_comments_exclude_drops_matches():
    out = ez.sample_comments(ez.podracing_survey, "nps_com", "show_com", n=50, by_column=False, exclude=["production"])
    assert not out["comment"].str.lower().str.contains("production").any()


def test_diverse_returns_n_scored_distinct_comments():
    out = ez.sample_comments_diverse(ez.podracing_survey, "nps_com", "show_com", n=5, seed=1)
    assert len(out) <= 5
    assert "info" in out.columns
    assert not out["comment"].duplicated().any()


def test_diverse_is_reproducible_with_a_seed():
    a = ez.sample_comments_diverse(ez.podracing_survey, "nps_com", "show_com", n=5, seed=42)
    b = ez.sample_comments_diverse(ez.podracing_survey, "nps_com", "show_com", n=5, seed=42)
    assert a["comment"].tolist() == b["comment"].tolist()


def test_a_seed_leaves_the_shared_generator_alone():
    np.random.seed(123)
    before = np.random.get_state()[1].copy()
    ez.sample_comments_diverse(ez.podracing_survey, "nps_com", n=3, seed=7)
    assert (np.random.get_state()[1] == before).all()


def test_the_entropy_method_works():
    out = ez.sample_comments_diverse(ez.podracing_survey, "nps_com", "show_com", n=4, method="entropy", seed=2)
    assert len(out) <= 4


def test_stopwords_accepts_a_list_and_false(capsys):
    ez.sample_comments_diverse(ez.podracing_survey, "nps_com", "show_com", n=3, stopwords=["the", "and"], seed=3)
    ez.sample_comments_diverse(ez.podracing_survey, "nps_com", "show_com", n=3, stopwords=False, seed=3)
    assert capsys.readouterr().err == ""


def test_resolve_stopwords_honours_false_lists_and_the_default():
    assert resolve_stopwords(False) == []
    assert resolve_stopwords(["A", "B"]) == ["a", "b"]
    assert len(resolve_stopwords(None)) > 10


def test_sample_comments_samples_per_group():
    d = ez.podracing_survey.assign(group=ez.nps_group(ez.podracing_survey["nps_value"], labels=True))
    d = d[d["group"].notna()]
    out = ez.sample_comments(d, "nps_com", n=2, by="group", seed=1)
    assert "group" in out.columns
    assert (out["group"].value_counts() <= 2).all()
    assert set(out["group"]) <= {"Detractor", "Passive", "Promoter"}


def test_diverse_shortlists_a_large_corpus():
    many = ez.podracing_survey.loc[list(range(1000)) * 2].reset_index(drop=True)
    out = ez.sample_comments_diverse(many, "nps_com", n=5, max_candidates=50, seed=1)
    assert len(out) == 5
    assert {"source", "comment", "length", "info"} <= set(out.columns)
