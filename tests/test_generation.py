"""Port R's test-generation.R: cohort schemes, birth years, ages and custom schemes."""

import pandas as pd

import ezrsurvey as ez


def test_generation_scheme_returns_ordered_bands():
    scheme = ez.generation_scheme("pew")
    assert {"label", "from", "to"}.issubset(scheme.columns)
    assert scheme.loc[scheme["from"] == 1981, "label"].tolist() == ["Millennial"]


def test_recode_generation_maps_birth_years():
    out = ez.recode_generation([1935, 1950, 1968, 1990, 2001, 2015], input="year")
    assert out.tolist() == ["Silent", "Baby Boomer", "Gen X", "Millennial", "Gen Z", "Gen Alpha"]
    assert ez.recode_generation([1900], input="year").isna().all()


def test_recode_generation_maps_ages_with_a_reference_year():
    assert ez.recode_generation([36, 25], input="age", year=2026).tolist() == ["Millennial", "Gen Z"]


def test_recode_generation_salvages_text_and_uses_current_year():
    ez.ezrsurvey_options(current_year=2026)
    assert ez.recode_generation(["36 years"]).tolist() == ["Millennial"]


def test_recode_generation_accepts_a_custom_scheme():
    scheme = pd.DataFrame({"label": ["Young", "Old"], "from": [2000, 1900]})
    assert ez.recode_generation([2005, 1950], input="year", scheme=scheme).tolist() == ["Young", "Old"]
