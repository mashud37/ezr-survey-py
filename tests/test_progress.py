"""Port R's test-progress.R: progress stays silent in scripts, can be forced, and never switches on mid-run."""

import sys
import time

import ezrsurvey as ez
from ezrsurvey.progress import (
    format_duration,
    progress_done,
    progress_eta,
    progress_item,
    progress_note,
    progress_on,
    progress_plan,
    progress_start,
)
from ezrsurvey.rbase import interactive


def test_progress_is_off_outside_an_interactive_session(capsys):
    ez.ezrsurvey_options(progress="auto")
    assert progress_on() is False
    run = progress_start(3, "starting")
    progress_item(run, 1, "first")
    progress_note("anything")
    progress_done(run)
    assert capsys.readouterr().err == ""


def test_progress_can_be_forced_on_and_off(capsys):
    ez.ezrsurvey_options(progress=True)
    assert progress_on() is True
    run = progress_start(2)
    progress_item(run, 1, "first")
    assert "[1/2] first" in capsys.readouterr().err
    progress_plan("Plan", ["a", "b"])
    assert "Plan" in capsys.readouterr().err
    ez.ezrsurvey_options(progress=False)
    assert progress_on() is False
    progress_item(progress_start(2), 1, "first")
    assert capsys.readouterr().err == ""


def test_a_run_that_starts_quiet_stays_quiet(capsys):
    ez.ezrsurvey_options(progress=False)
    run = progress_start(2)
    ez.ezrsurvey_options(progress=True)
    progress_item(run, 1, "first")
    assert capsys.readouterr().err == ""


def test_format_duration_reads_in_sensible_units():
    assert format_duration(12) == "12s"
    assert format_duration(300) == "5m"
    assert format_duration(7200) == "2h"
    assert format_duration(float("nan")) == "?"


def test_eta_is_empty_until_there_is_something_to_measure():
    run = progress_start(10)
    assert progress_eta(run, 1) == ""
    run["started"] = time.monotonic() - 100
    assert "left" in progress_eta(run, 5)


def test_a_document_quarto_renders_counts_as_a_script(monkeypatch):
    monkeypatch.setattr(sys, "ps1", ">>> ", raising=False)
    assert interactive()
    monkeypatch.setenv("QUARTO_DOCUMENT_PATH", "report.qmd")
    assert not interactive()
