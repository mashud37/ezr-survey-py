"""Port R's test-currency.R: the USD base, cross-rates, aliases, custom rates and the column helper."""

import pandas as pd
import pytest

import ezrsurvey as ez
from ezrsurvey.currency import normalize_currency
from ezrsurvey.rbase import r_round


def one(value):
    return value.tolist()[0]


def test_convert_currency_uses_the_usd_base():
    assert one(ez.convert_currency(100, "USD", "EUR")) == pytest.approx(92)
    assert one(ez.convert_currency(ez.convert_currency(100, "USD", "EUR"), "EUR", "USD")) == pytest.approx(100)
    assert one(ez.convert_currency(250, "GBP", "GBP")) == pytest.approx(250)


def test_convert_currency_is_vectorised_and_case_insensitive():
    out = ez.convert_currency([100, 100], from_=["eur", "gbp"], to="USD")
    assert r_round(out).tolist() == [109, 127]


def test_convert_currency_salvages_text_amounts():
    assert one(ez.convert_currency("$100", "USD", "EUR")) == pytest.approx(92)


def test_unknown_currencies_warn_and_return_missing():
    with pytest.warns(UserWarning):
        result = ez.convert_currency(100, "ZZZ", "USD")
    assert result.isna().all()


def test_custom_rates_override_the_snapshot():
    assert one(ez.convert_currency(100, "EUR", "USD", rates={"USD": 1, "EUR": 0.5})) == pytest.approx(200)


def test_add_currency_with_a_column_and_a_constant():
    df = pd.DataFrame({"spend": [100, 200, 50], "currency": ["EUR", "GBP", "JPY"]})
    out = ez.add_currency(df, "spend", from_="currency", to="USD")
    assert "spend_usd" in out.columns
    assert r_round(out["spend_usd"]).tolist() == [109, 253, 0]
    out2 = ez.add_currency(df, "spend", from_="EUR", to="USD", into="usd")
    assert r_round(out2["usd"].iloc[0]) == 109


def test_cross_rates_convert_via_usd():
    assert one(ez.convert_currency(100, "EUR", "CNY")) == pytest.approx(100 / 0.92 * 7.2)


def test_aliases_resolve_to_iso_codes():
    assert one(ez.convert_currency(100, "EUR", "RMB")) == one(ez.convert_currency(100, "EUR", "CNY"))
    assert normalize_currency(["rmb", "yen", "USD"]) == ["CNY", "JPY", "USD"]


def test_list_currencies_includes_the_majors():
    assert {"USD", "EUR", "GBP", "JPY"} <= set(ez.list_currencies())
