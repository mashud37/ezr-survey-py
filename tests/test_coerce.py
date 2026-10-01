"""Port R's test-coerce.R: salvaging numbers from text, and the helpers that rely on it."""

import math

import pandas as pd

import ezrsurvey as ez


def same(values, expected):
    for value, wanted in zip(values, expected):
        if wanted is None:
            assert math.isnan(value)
        else:
            assert value == wanted
    assert len(values) == len(expected)


def test_ensure_numeric_salvages_embedded_numbers():
    same(ez.ensure_numeric(["25 years", "31", "forty"], quiet=True).tolist(), [25, 31, None])
    same(ez.ensure_numeric(["8 - very likely", "10", "3.5/5"], quiet=True).tolist(), [8, 10, 3.5])
    same(ez.ensure_numeric(["-2 pts", "x"], quiet=True).tolist(), [-2, None])


def test_ensure_numeric_leaves_numbers_untouched_and_silent(capsys):
    numbers = pd.Series([1.0, 2.0, 3.0])
    assert ez.ensure_numeric(numbers) is numbers
    ez.ensure_numeric([1, 2])
    assert capsys.readouterr().err == ""


def test_ensure_numeric_messages_unless_quiet(capsys):
    ez.ensure_numeric(["25 years", "x"], name="age")
    assert "Auto-converted 'age' to numeric" in capsys.readouterr().err
    ez.ensure_numeric(["25 years"], quiet=True)
    assert capsys.readouterr().err == ""


def test_nps_group_tolerates_worded_answers():
    assert ez.nps_group(["9 - very likely", "3 (unlikely)", "8"]).tolist() == [1, -1, 0]


def test_calc_nps_coerces_text_scores():
    df = pd.DataFrame({"score": ["10", "9 - promoter", "3 detractor", "8"]})
    out = ez.calc_nps(df, "score")
    assert out["nps"].tolist() == [25]
    assert out["n"].tolist() == [4]


def test_calc_summary_coerces_text_numbers():
    df = pd.DataFrame({"age": ["25 years", "35", "45 yo"]})
    out = ez.calc_summary(df, "age")
    assert out["mean"].tolist() == [35]
    assert out["n"].tolist() == [3]
