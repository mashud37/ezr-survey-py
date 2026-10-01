"""Port R's test-region.R: country spellings, ISO codes, the letter fold and the lookup table's coverage."""

import pytest

import ezrsurvey as ez
from ezrsurvey.region import ACCENTED_LETTERS, PLAIN_LETTERS, normalise_country


def region(values, quiet=False):
    return ez.recode_region(values, quiet=quiet).tolist()


def fold(text):
    return normalise_country([text])[0]


def test_recode_region_maps_countries():
    assert region(["Germany", "Japan", "Brazil"]) == ["Europe", "Asia", "South America"]
    assert region("United States") == ["North America"]


def test_recode_region_ignores_case_and_whitespace():
    assert region(["  germany ", "JAPAN"]) == ["Europe", "Asia"]


def test_recode_subregion_returns_the_finer_level():
    assert ez.recode_subregion("Germany").tolist() == ["Western Europe"]
    assert ez.recode_subregion("Japan").tolist() == ["East Asia"]


def test_non_answers_and_unmatched_become_missing(recwarn):
    assert ez.recode_region("Prefer not to answer", quiet=True).isna().all()
    assert ez.recode_region("", quiet=True).isna().all()
    with pytest.warns(UserWarning):
        ez.recode_region(["Germany", "Atlantis"])
    recwarn.clear()
    ez.recode_region(["Germany", "Atlantis"], quiet=True)
    assert len(recwarn) == 0


def test_add_region_appends_columns():
    import pandas as pd

    df = pd.DataFrame({"demo_country": ["Germany", "Japan", "Brazil"]})
    out = ez.add_region(df, "demo_country", subregion=True)
    assert out["region"].tolist() == ["Europe", "Asia", "South America"]
    assert "subregion" in out.columns
    with pytest.raises(ValueError):
        ez.add_region(df, "not_a_column")


def test_country_region_ships_with_the_expected_shape():
    table = ez.country_region
    assert set(table.columns) == {"country", "iso2", "iso3", "region", "subregion"}
    assert len(table) > 150
    assert not table["country"].duplicated().any()


def test_every_country_carries_its_iso_codes():
    table = ez.country_region
    codes = table[table["country"].isin(["Germany", "United States", "Japan"])].sort_values("country")
    assert codes["iso2"].tolist() == ["DE", "JP", "US"]
    assert codes["iso3"].tolist() == ["DEU", "JPN", "USA"]
    assert table.loc[table["iso2"].isna(), "country"].tolist() == ["Kosovo"]
    assert table.loc[table["country"] == "Namibia", "iso2"].tolist() == ["NA"]


def test_the_misspelled_countries_were_corrected():
    countries = set(ez.country_region["country"])
    assert {"Isle of Man", "American Samoa", "Kazakhstan", "Bermuda"} <= countries
    assert not {"Ise of Man", "America Samoa", "Kazakstan"} & countries
    assert region(["Isle of Man", "Bermuda"]) == ["Europe", "North America"]


def test_the_spellings_people_type_resolve():
    assert region(["USA", "U.S.", "Usa", "usa", "United States of America"]) == ["North America"] * 5
    assert region(["UK", "England", "Scotland", "Great Britain"]) == ["Europe"] * 4
    assert region(["Deutschland", "Holland", "Brasil", "Espana"]) == ["Europe", "Europe", "South America", "Europe"]


def test_iso_codes_resolve():
    assert region(["US", "GBR", "DEU", "JPN", "BRA"]) == ["North America", "Europe", "Europe", "Asia", "South America"]
    assert region(["FR", "CA", "AU"]) == ["Europe", "North America", "Oceania"]


def test_a_code_that_is_also_a_word_needs_capitals():
    assert region("NO") == ["Europe"]
    assert ez.recode_region("no", quiet=True).isna().all()
    assert ez.recode_region("it", quiet=True).isna().all()
    assert region("IT") == ["Europe"]
    assert region(["Uk", "us"]) == ["Europe", "North America"]


def test_a_leading_the_and_punctuation_do_not_matter():
    assert region(["The Netherlands", "U.K.", "U S A"]) == ["Europe", "Europe", "North America"]


def test_the_fold_does_not_depend_on_the_platform():
    assert fold("Großbritannien") == "grossbritannien"
    assert fold("Weißrussland") == "weissrussland"
    assert fold("Malmø") == "malmo"
    assert fold("ÆRØ") == "aero"
    assert fold("Łódz") == "lodz"
    assert region("Großbritannien", quiet=True) == ["Europe"]
    assert fold("Côte d'Ivoire") == "cote divoire"
    assert fold("Réunion") == "reunion"
    assert fold("Curaçao") == "curacao"
    assert fold("Türkiye") == "turkiye"
    assert fold("São Tomé") == "sao tome"
    folded = ACCENTED_LETTERS.translate(str.maketrans(ACCENTED_LETTERS, PLAIN_LETTERS))
    assert folded.isascii()


def test_the_endonyms_of_the_most_answered_countries_match():
    assert region(["Estados Unidos", "Etats-Unis", "Vereinigte Staaten", "Stati Uniti"], quiet=True) == ["North America"] * 4
    assert region(["Reino Unido", "Royaume-Uni", "Großbritannien"], quiet=True) == ["Europe"] * 3


def test_a_country_whose_name_carries_punctuation_matches():
    assert region("Timor-Leste", quiet=True) == ["Asia"]
    assert region("Guinea-Bissau", quiet=True) == ["Africa"]
    assert region("Cote d'Ivoire", quiet=True) == ["Africa"]
    assert region("Côte d'Ivoire", quiet=True) == ["Africa"]
    assert region("Korea, North", quiet=True) == ["Asia"]
    assert region("Gambia, The", quiet=True) == ["Africa"]


def test_the_table_covers_iso_3166():
    plain = [
        "Ghana",
        "Ethiopia",
        "Senegal",
        "Rwanda",
        "Yemen",
        "Benin",
        "Botswana",
        "Haiti",
        "Samoa",
        "San Marino",
        "Monaco",
        "Suriname",
        "Barbados",
        "Turkmenistan",
        "Papua New Guinea",
        "South Sudan",
        "Sierra Leone",
        "Mali",
    ]
    assert not ez.recode_region(plain, quiet=True).isna().any()
    table = ez.country_region
    assert len(table) >= 249
    assert table["country"].duplicated().sum() == 0
    assert table["iso3"].isna().sum() == 1


def test_the_official_iso_names_match_in_either_order():
    iso_order = [
        "Viet Nam",
        "Syrian Arab Republic",
        "Moldova, Republic of",
        "Iran, Islamic Republic of",
        "Lao People's Democratic Republic",
        "Brunei Darussalam",
        "Cabo Verde",
        "Eswatini",
        "North Macedonia",
        "Taiwan, Province of China",
    ]
    assert not ez.recode_region(iso_order, quiet=True).isna().any()
    said = [
        "Republic of Moldova",
        "United Republic of Tanzania",
        "Islamic Republic of Iran",
        "Democratic Republic of the Congo",
        "Democratic People's Republic of Korea",
    ]
    assert not ez.recode_region(said, quiet=True).isna().any()


def test_countries_sit_in_the_agreed_region():
    assert region("Algeria", quiet=True) == ["Africa"]
    assert region("Laos", quiet=True) == ["Asia"]
    assert ez.recode_subregion("Laos", quiet=True).tolist() == ["South East Asia"]
    assert region("Mauritius", quiet=True) == ["Africa"]
    assert region("Reunion", quiet=True) == ["Africa"]
    assert region("Egypt", quiet=True) == ["Middle East"]
    assert region("Turkey", quiet=True) == ["Europe"]
