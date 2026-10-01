"""Convert amounts between currencies through a table of rates per US dollar. Spend questions answered in several currencies become comparable with these."""

import numpy as np
import pandas as pd

from .coerce import ensure_numeric
from .dataset import resolve_data
from .datasets import load_dataset
from .rbase import as_character, as_series, is_missing, warn

CURRENCY_ALIASES = {
    "RMB": "CNY",
    "YUAN": "CNY",
    "RENMINBI": "CNY",
    "DOLLAR": "USD",
    "EURO": "EUR",
    "STERLING": "GBP",
    "QUID": "GBP",
    "YEN": "JPY",
    "NIS": "ILS",
}


def normalize_currency(x):
    out = []
    for code in as_character(x):
        if is_missing(code):
            out.append(np.nan)
            continue
        code = code.strip().upper()
        out.append(CURRENCY_ALIASES.get(code, code))
    return out


def resolve_rates(rates=None):
    """The `rates` argument as a dict of units per US dollar, keyed by upper-case code."""
    if rates is None:
        table = load_dataset("currency_rates")
        return dict(zip(table["currency"], table["per_usd"].astype(float)))
    if isinstance(rates, dict):
        return {str(code).upper(): float(rate) for code, rate in rates.items()}
    if isinstance(rates, pd.Series) and pd.api.types.is_numeric_dtype(rates):
        return {str(code).upper(): float(rate) for code, rate in rates.items()}
    if isinstance(rates, pd.DataFrame):
        column = None
        if "per_usd" in rates.columns:
            column = "per_usd"
        elif "rate" in rates.columns:
            column = "rate"
        if "currency" not in rates.columns or column is None:
            raise ValueError("A `rates` data frame needs a `currency` column and a `per_usd` (or `rate`) column.")
        return {str(code).upper(): float(rate) for code, rate in zip(rates["currency"], rates[column])}
    raise ValueError("`rates` must be None, a dict of rates by currency code, or a data frame.")


def convert_currency(amount, from_, to="USD", rates=None):  # lint-style: ignore FN001
    """Convert amounts between currencies.

    Converts monetary amounts from one currency to another using a table of
    exchange rates. By default it uses the bundled ``currency_rates`` snapshot
    (units per US dollar); pass your own `rates` for up-to-date or custom
    figures. Because rates share the USD base, any pair is converted as a
    cross-rate through USD automatically: a conversion is
    ``amount / rate(from) * rate(to)``. `amount`, `from_` and `to` are
    vectorised and recycled, so you can convert a whole column with per-row
    source currencies at once. Codes are upper-cased and resolved through a
    small alias map ("RMB" to "CNY", "EURO" to "EUR", ...), and any unknown code
    yields missing with a warning rather than a silent wrong number.

    The source-currency argument is ``from_`` because ``from`` is a Python
    keyword; R names it ``from``.

    Parameters
    ----------
    amount : number, list or Series
        Amounts (text like "$1,200" is salvaged with `ensure_numeric()`).
    from_ : str or list of str
        Source currency code(s), e.g. "EUR" (case-insensitive).
    to : str or list of str
        Target currency code(s). Defaults to "USD".
    rates : dict or pandas.DataFrame, optional
        None (default) for the bundled snapshot, a dict of units per USD (e.g.
        ``{"EUR": 0.92, "GBP": 0.79}``), or a data frame with ``currency`` and
        ``per_usd`` columns.

    Returns
    -------
    pandas.Series
        Converted amounts; unknown currency codes yield missing with a warning.

    See Also
    --------
    add_currency, list_currencies, currency_rates

    Examples
    --------
    >>> convert_currency(100, "EUR", "USD")
    >>> convert_currency([100, 50], from_=["EUR", "GBP"], to="USD")
    >>> convert_currency(100, "EUR", "CNY")
    >>> convert_currency(100, "EUR", "RMB")
    """
    table = resolve_rates(rates)
    amounts = list(ensure_numeric(amount, quiet=True))
    sources = normalize_currency(as_series(from_))
    targets = normalize_currency(as_series(to))
    unknown = []
    for code in sources + targets:
        if not is_missing(code) and code not in table and code not in unknown:
            unknown.append(code)
    if unknown:
        warn("Unknown currency code(s): " + ", ".join(unknown) + ". Add them via `rates`.")
    length = max(len(amounts), len(sources), len(targets))
    if min(len(amounts), len(sources), len(targets)) == 0:
        length = 0
    out = []
    for i in range(length):
        value = amounts[i % len(amounts)]
        per_from = table.get(sources[i % len(sources)], np.nan)
        per_to = table.get(targets[i % len(targets)], np.nan)
        out.append(float(value) / per_from * per_to)
    return pd.Series(out, dtype=float)


def add_currency(data=None, amount=None, from_=None, to="USD", into=None, rates=None):  # lint-style: ignore FN003
    """Add a converted-currency column to a data frame.

    Convenience wrapper around `convert_currency()` that appends a converted
    column to `data`. The source currency can be a fixed code or a per-row
    column: a `from_` that names a column of `data` is read as a per-row
    source-currency column, while any other string ("EUR") is a fixed code
    applied to every row. This is the common case where each respondent reported
    spend in their own currency. The new column defaults to ``<amount>_<to>``
    (e.g. ``spend_usd``); override with `into`.

    R tells the two apart by quoting (a bare name is a column, a quoted string a
    constant); Python strings cannot, so a column name wins.

    Parameters
    ----------
    data : pandas.DataFrame, optional
        A data frame. If omitted, the session default is used.
    amount : str
        The amount column to convert.
    from_ : str
        Source currency: a column holding per-row codes (e.g. "currency") or a
        constant code (e.g. "EUR").
    to : str
        Target currency code. Defaults to "USD".
    into : str, optional
        Name of the new column. Defaults to ``"<amount>_<to>"``.
    rates : dict or pandas.DataFrame, optional
        Passed to `convert_currency()`.

    Returns
    -------
    pandas.DataFrame
        `data` with the converted column added.

    See Also
    --------
    convert_currency

    Examples
    --------
    >>> df = pd.DataFrame({"spend": [100, 200, 50], "currency": ["EUR", "GBP", "JPY"]})
    >>> add_currency(df, "spend", from_="currency", to="USD")
    >>> add_currency(df, "spend", from_="EUR", to="USD", into="spend_usd")
    """
    out = resolve_data(data).copy()
    if isinstance(from_, str) and from_ in out.columns:
        sources = out[from_]
    else:
        sources = from_
    if into is None:
        into = f"{amount}_{str(to).lower()}"
    out[into] = list(convert_currency(out[amount], from_=sources, to=to, rates=rates))
    return out


def list_currencies(rates=None):
    """List the currencies in a rate table.

    A quick way to see which codes `convert_currency()` will accept from the
    bundled snapshot (or from a `rates` table you pass). Aliases such as "RMB"
    are *not* listed; they resolve to their ISO code (here "CNY").

    Parameters
    ----------
    rates : dict or pandas.DataFrame, optional
        Rate table; None (default) for the bundled ``currency_rates``.

    Returns
    -------
    list of str
        Currency codes.

    See Also
    --------
    currency_rates, convert_currency

    Examples
    --------
    >>> list_currencies()
    """
    return list(resolve_rates(rates).keys())
