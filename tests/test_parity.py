"""Compare every parity case's Python result with the golden output the R package wrote. A case passes when values, types, level order, messages and warnings all match."""

import contextlib
import io
import json
import math
import warnings
from pathlib import Path

import pandas as pd
import parity_cases
import pytest

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "parity"
MISSING_MARK = "<NA>"
TOLERANCE = 1e-9

R_TO_PYTHON_WORDING = [
    ("`levels =`", "`levels=`"),
    ("-Inf / Inf", "-math.inf / math.inf"),
    ("length `length(breaks) - 1`", "length `len(breaks) - 1`"),
    ("weights = TRUE", "weights = True"),
    ('ezrsurvey_options(output_dir = ".")', 'ezrsurvey_options(output_dir=".")'),
    ("Pass an unquoted column of the data", "Pass the name of a column of the data"),
    ("overwrite = TRUE", "overwrite=True"),
    (
        'c(variable = "demo_gender", Male = 0.5, Female = 0.5)',
        '{"variable": "demo_gender", "Male": 0.5, "Female": 0.5}',
    ),
]

CASE_NAMES = sorted(path.stem for path in FIXTURES.glob("*.json"))


def to_python_wording(text):
    for r_text, python_text in R_TO_PYTHON_WORDING:
        text = text.replace(r_text, python_text)
    return text


def run_case(name):
    case = getattr(parity_cases, name, None)
    if case is None:
        pytest.fail(f"parity case {name} has no Python counterpart in parity_cases.py")
    stderr = io.StringIO()
    outcome = {"value": None, "error": None}
    with warnings.catch_warnings(record=True) as caught, contextlib.redirect_stderr(stderr):
        warnings.simplefilter("always")
        try:
            outcome["value"] = case()
        except ValueError as problem:
            outcome["error"] = str(problem)
    outcome["messages"] = [line for line in stderr.getvalue().splitlines() if line != ""]
    outcome["warnings"] = [str(item.message) for item in caught if issubclass(item.category, UserWarning)]
    return outcome


def as_frame(value):
    if isinstance(value, pd.DataFrame):
        return value.reset_index(drop=True)
    if isinstance(value, pd.Series):
        return pd.DataFrame({"value": value.reset_index(drop=True)})
    if isinstance(value, dict):
        return pd.DataFrame({key: list(inner.values()) for key, inner in value.items()})
    if isinstance(value, (list, tuple)):
        return pd.DataFrame({"value": pd.Series(list(value), dtype=object if value and isinstance(value[0], str) else None)})
    return pd.DataFrame({"value": [value]})


def is_missing_text(text):
    return text == MISSING_MARK


def same_number(expected_text, actual):
    if is_missing_text(expected_text):
        return pd.isna(actual)
    expected = float(expected_text)
    if pd.isna(actual):
        return False
    actual = float(actual)
    if math.isinf(expected):
        return expected == actual
    return abs(expected - actual) <= TOLERANCE * max(1.0, abs(expected))


def same_text(expected_text, actual):
    if is_missing_text(expected_text):
        return pd.isna(actual)
    if pd.isna(actual):
        return False
    if isinstance(actual, bool):
        actual = "TRUE" if actual else "FALSE"
    return expected_text == str(actual)


def check_column_type(name, info, column):
    kind = info["type"]
    dtype = column.dtype
    if kind in ("factor", "ordered"):
        assert isinstance(dtype, pd.CategoricalDtype), f"{name}: expected a categorical, got {dtype}"
        assert list(dtype.categories) == list(info["levels"]), f"{name}: levels differ"
        assert bool(dtype.ordered) == (kind == "ordered"), f"{name}: ordered flag differs"
    elif kind == "integer":
        assert pd.api.types.is_integer_dtype(dtype), f"{name}: expected integers, got {dtype}"
    elif kind == "numeric":
        assert pd.api.types.is_float_dtype(dtype), f"{name}: expected floats, got {dtype}"
    elif kind == "character":
        assert not isinstance(dtype, pd.CategoricalDtype), f"{name}: expected text, got a categorical"
    elif kind == "logical":
        assert pd.api.types.is_bool_dtype(dtype) or pd.api.types.is_object_dtype(dtype), f"{name}: expected logical, got {dtype}"


def compare_frame(name, meta, actual):
    expected = pd.read_csv(FIXTURES / f"{name}.csv", dtype=str, keep_default_na=False, encoding="utf-8")
    actual = as_frame(actual)
    assert [str(column) for column in actual.columns] == list(meta["names"]), "column names differ"
    assert len(actual) == len(expected), f"row count differs: R {len(expected)}, Python {len(actual)}"
    for column in meta["names"]:
        info = meta["columns"][column]
        check_column_type(column, info, actual[column])
        numeric = info["type"] in ("integer", "numeric")
        for row, (expected_text, value) in enumerate(zip(expected[column], actual[column])):
            same = same_number(expected_text, value) if numeric else same_text(expected_text, value)
            assert same, f"{column}[{row}]: R {expected_text!r}, Python {value!r}"


def compare_precision(name, meta, actual):
    for field in ("n", "rating", "bullets"):
        assert actual[field] == meta["fields"][field], f"{field} differs"
    assert abs(actual["overall_rse"] - meta["fields"]["overall_rse"]) <= TOLERANCE
    compare_frame(name, meta, actual["table"])


@pytest.mark.parametrize("name", CASE_NAMES)
def test_parity(name):
    meta = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
    outcome = run_case(name)
    if meta["kind"] == "error":
        assert outcome["error"] is not None, "R raised an error; Python did not"
        assert outcome["error"] == to_python_wording(meta["error"])
    else:
        assert outcome["error"] is None, f"Python raised: {outcome['error']}"
    assert outcome["messages"] == [to_python_wording(text) for text in meta["messages"]]
    assert outcome["warnings"] == [to_python_wording(text) for text in meta["warnings"]]
    if meta["kind"] == "null":
        assert outcome["value"] is None
    elif meta["kind"] == "precision":
        compare_precision(name, meta, outcome["value"])
    elif meta["kind"] in ("frame", "vector"):
        compare_frame(name, meta, outcome["value"])
