"""Reset ezrsurvey's session state around every test, as R's test run starts each file clean. Tests then never see a dataset, weights, option or order another test left behind."""

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("MPLBACKEND", "Agg")

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ezrsurvey as ez  # noqa: E402


def reset_session():
    ez.clear_dataset()
    ez.clear_weights()
    ez.reset_ezrsurvey_options()
    for name in list(ez.list_orders()["name"]):
        ez.remove_order(name)


@pytest.fixture(autouse=True)
def clean_session():
    reset_session()
    yield  # lint-style: ignore FN006
    reset_session()
