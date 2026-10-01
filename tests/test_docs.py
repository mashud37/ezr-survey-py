"""Port R's test-docs.R: every export is documented with Returns, Examples and a family, and every example runs."""

import csv
import inspect
import os
import re
import warnings
from pathlib import Path

import pandas as pd
import pytest
import yaml

import ezrsurvey as ez
from ezrsurvey.families import FAMILIES

ROOT = Path(__file__).resolve().parent.parent
DATASETS = {"podracing_survey", "shopping_survey", "country_region", "currency_rates"}
PALETTES = {"pal_neutral", "pal_nps", "pal_rating", "pal_sequential_blue"}
ARTICLES = sorted(path.name for path in (ROOT / "docs" / "articles").glob("*.qmd"))
PYTHON_CELL = re.compile(r"```\{python\}\n(.*?)```", re.S)


def exported_callables():
    names = []
    for name in ez.__all__:
        if name in DATASETS or name in PALETTES:
            continue
        if callable(getattr(ez, name)):
            names.append(name)
    return names


def example_lines(obj):
    lines = []
    for line in (inspect.getdoc(obj) or "").splitlines():
        stripped = line.strip()
        if stripped.startswith(">>> ") or stripped.startswith("... "):
            lines.append(stripped)
    return lines


def example_code(obj):
    """The docstring's example as runnable code, with lines marked +SKIP left out."""
    code = []
    skipping = False
    for line in example_lines(obj):
        text = line[4:]
        if line.startswith(">>> "):
            skipping = "doctest: +SKIP" in text
        if not skipping:
            code.append(text)
    return "\n".join(code)


def test_every_export_documents_returns_examples_and_a_family():
    names = exported_callables()
    assert len(names) > 40
    families = set()
    for family in FAMILIES.values():
        families.update(family["names"])
    functions = [name for name in names if not inspect.isclass(getattr(ez, name))]
    missing_returns = [name for name in functions if "Returns\n" not in (inspect.getdoc(getattr(ez, name)) or "")]
    missing_examples = [name for name in names if not example_lines(getattr(ez, name))]
    missing_family = [name for name in names if name not in families]
    assert missing_returns == []
    assert missing_examples == []
    assert missing_family == []


def test_every_r_export_has_a_python_counterpart():
    with open(ROOT / "sync" / "port-index.csv", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    exported = [row for row in rows if row["exported"] == "TRUE" and row["status"] != "dropped"]
    missing = [row["r_name"] for row in exported if row["py_name"] and not hasattr(ez, row["py_name"])]
    assert missing == []


def test_every_family_member_exists():
    for family in FAMILIES.values():
        for name in family["names"]:
            assert name in ez.__all__, name


@pytest.mark.parametrize("name", exported_callables())
def test_every_example_runs(name, tmp_path, monkeypatch):
    code = example_code(getattr(ez, name))
    if not code:
        pytest.skip("example skipped in full")
    monkeypatch.chdir(tmp_path)
    namespace = {"pd": pd, "os": os}
    for exported in ez.__all__:
        namespace[exported] = getattr(ez, exported)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        exec(compile(code, f"<example {name}>", "exec"), namespace)


def test_site_reference_follows_the_families():
    with open(ROOT / "docs" / "_quarto.yml", encoding="utf-8") as file:
        sections = yaml.safe_load(file)["quartodoc"]["sections"]
    expected = []
    for key, family in FAMILIES.items():
        if key != "data":
            expected.append({"title": family["title"], "desc": family["desc"], "contents": family["names"]})
    assert sections == expected


@pytest.mark.parametrize("article", ARTICLES)
def test_every_article_runs(article, tmp_path, monkeypatch):
    text = (ROOT / "docs" / "articles" / article).read_text(encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    namespace = {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for number, cell in enumerate(PYTHON_CELL.findall(text), start=1):
            exec(compile(cell, f"<{article} cell {number}>", "exec"), namespace)


def test_readme_tour_runs(tmp_path, monkeypatch):
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    tour = text[text.index("## The 60-second tour"):]
    code = tour[tour.index("```python") + len("```python"):]
    code = code[:code.index("```")]
    monkeypatch.chdir(tmp_path)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        exec(compile(code, "<README tour>", "exec"), {})
