"""Measure how precise survey estimates are: standard errors, relative errors, margins and a plain-language verdict. Report appendices and footnotes quote these."""

import math

import numpy as np
import pandas as pd

from .coerce import ensure_numeric
from .dataset import resolve_data_dots
from .progress import progress_done, progress_item, progress_start
from .rbase import (
    as_character,
    as_series,
    is_missing,
    is_numeric_vector,
    match_arg,
    r_mean,
    r_round,
    r_sd,
    table_desc,
)
from .recode import na_blank
from .select import all_of, select_columns
from .tables import group_positions

TYPES = ["auto", "mean", "prop"]
Z_95 = 1.96
PRECISION_BANDS = [
    (5, "high precision"),
    (10, "precise"),
    (15, "satisfactory"),
    (25, "use with caution"),
]


def vector_result(values, template):
    """A Series when the caller passed several values, a single value when they passed one."""
    if isinstance(template, (list, tuple, pd.Series, np.ndarray)):
        return pd.Series(list(values))
    return list(values)[0]


def se_mean(x):
    """Standard error of a mean (point estimate).

    ``sd(x) / sqrt(n)``, the sampling error of a mean such as an average 1-5
    rating: the sample standard deviation divided by the square root of the
    (non-missing) sample size. It shrinks as the sample grows, and is the basis
    of the margin of error you quote for an average rating. Fewer than two
    values gives missing (no spread to estimate).

    Parameters
    ----------
    x : list or Series
        Numbers. Missing values are ignored.

    Returns
    -------
    float
        The standard error, or NaN if fewer than two non-missing values are
        present.

    See Also
    --------
    se_prop, rse, margin_of_error, diagnose

    Examples
    --------
    >>> se_mean([4, 5, 3, 4, 5, 2, 4])
    """
    values = pd.to_numeric(as_series(x), errors="coerce").dropna()
    if len(values) < 2:
        return np.nan
    return r_sd(values) / math.sqrt(len(values))


def se_prop(p, n, pctp=False):
    """Standard error of a proportion.

    ``sqrt(p * (1 - p) / n)``, the sampling error of a percentage. It is largest
    when p = 0.5 (a 50/50 split is the hardest to pin down) and shrinks towards
    the extremes. The result is on the same 0-1 scale as a fractional `p`; pass
    ``pctp=True`` for percentage points, the form used in report footnotes and
    the one `margin_of_error()` needs if you want the margin in points. Inputs
    above 1 are treated as percentages and divided by 100, so ``se_prop(33, n)``
    and ``se_prop(0.33, n)`` agree.

    Parameters
    ----------
    p : float or list of float
        The proportion, as a fraction in [0, 1] or a percentage in (1, 100].
    n : int or list of int
        The sample size (number of respondents).
    pctp : bool
        Return the answer in percentage points instead of on the [0, 1]
        proportion scale. Default False.

    Returns
    -------
    float or pandas.Series
        The standard error of the proportion.

    See Also
    --------
    se_mean, rse, margin_of_error, diagnose

    Examples
    --------
    >>> se_prop(0.33, 1184)
    >>> se_prop(0.33, 1184, pctp=True)
    """
    shares = []
    for value in as_series(p):
        value = np.nan if is_missing(value) else float(value)
        shares.append(value / 100 if value > 1 else value)
    if any(not math.isnan(share) and (share < 0 or share > 1) for share in shares):
        raise ValueError("`p` must be a proportion in [0, 1] (or a percentage in [0, 100]).")
    sizes = list(as_series(n))
    out = []
    for i, share in enumerate(shares):
        size = float(sizes[i % len(sizes)])
        if size > 0:
            error = math.sqrt(share * (1 - share) / size)
        elif math.isnan(share):
            error = np.nan
        else:
            error = math.inf
        out.append(error * 100 if pctp else error)
    return vector_result(out, p)


def rse(estimate, se):
    """Relative standard error.

    The standard error expressed as a percentage of the estimate,
    ``se / estimate * 100``. Dividing by the estimate makes precision comparable
    across measures on different scales (a 1-5 rating vs a percentage). A common
    rule of thumb treats an RSE under about 5% as very good precision, which is
    the threshold `diagnose()` uses for its ``precision`` flag.

    Parameters
    ----------
    estimate : float or list of float
        The point estimate (mean or proportion).
    se : float or list of float
        Its standard error, on the same scale as `estimate`.

    Returns
    -------
    float or pandas.Series
        The relative standard error, in percent.

    See Also
    --------
    se_mean, se_prop, margin_of_error, diagnose

    Examples
    --------
    >>> rse(estimate=4.1, se=se_mean([4, 5, 3, 4, 5]))
    """
    if isinstance(estimate, (list, tuple)):
        estimate = pd.Series(estimate, dtype=float)
    if isinstance(se, (list, tuple)):
        se = pd.Series(se, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.float64(se) / estimate * 100 if np.isscalar(se) else se / estimate * 100


def margin_of_error(se, z=Z_95):
    """Margin of error from a standard error.

    ``z * se``, the half-width of a confidence interval. A confidence interval
    is the estimate plus or minus this margin. ``z=1.96`` gives the standard 95%
    interval; ``z=2`` reproduces the "two standard errors" rule of thumb often
    quoted in survey reports; ``z=2.58`` gives 99%. The result is on the same
    scale as `se`, so for a proportion error in percentage points, pass
    ``se_prop(p, n, pctp=True)``.

    Parameters
    ----------
    se : float or list of float
        A standard error.
    z : float
        The critical value / multiplier. Default 1.96 (95%).

    Returns
    -------
    float or pandas.Series
        The plus-or-minus margin of error, on the same scale as `se`.

    See Also
    --------
    se_mean, se_prop, diagnose

    Examples
    --------
    >>> margin_of_error(se_prop(0.33, 1184, pctp=True))
    >>> margin_of_error(0.02, z=2)
    """
    if isinstance(se, (list, tuple)):
        se = pd.Series(se, dtype=float)
    return z * se


def rate_one(value):
    if is_missing(value):
        return np.nan
    for limit, label in PRECISION_BANDS:
        if value < limit:
            return label
    return "likely reliability issues"


def rse_rating(rse):
    """Rate precision from a relative standard error.

    Turns a relative standard error (RSE, in percent) into a plain-language
    reliability rating. The bands are: under 5% "high precision", under 10%
    "precise", under 15% "satisfactory", under 25% "use with caution", and 25%
    or more "likely reliability issues". Rating estimates by their relative
    standard error is how national statistical agencies signal whether a survey
    number is solid enough to publish: the Australian Bureau of Statistics
    treats an RSE of 25% or more as "not reliable for most purposes". The 25%
    boundary here is that same one; the tighter bands below it are specific to
    consumer-survey work. This drives the ``precision`` column of `diagnose()`
    and the overall verdict of `precision_summary()`.

    Parameters
    ----------
    rse : float or list of float
        Relative standard error(s), in percent (see `rse()`).

    Returns
    -------
    str or pandas.Series
        The rating(s).

    See Also
    --------
    rse, diagnose, precision_summary

    Examples
    --------
    >>> rse_rating([3, 8, 12, 20, 40])
    """
    ratings = [rate_one(value) for value in as_series(rse)]
    if isinstance(rse, (list, tuple, pd.Series, np.ndarray)):
        return pd.Series(ratings, dtype=object)
    return ratings[0]


def diagnose_one(x, kind, z):
    """One row of diagnostics for one column: its estimate, error, margin and rating."""
    if kind == "auto":
        kind = "mean" if is_numeric_vector(x) else "prop"
    if kind == "mean":
        numbers = ensure_numeric(x, quiet=True)
        n = int(numbers.notna().sum())
        estimate = r_mean(numbers)
        se = se_mean(numbers)
        unit = "points"
    else:
        answers = [value for value in na_blank(as_character(x)) if not is_missing(value)]
        n = len(answers)
        share = table_desc(answers)[0][1] / n if n else np.nan
        estimate = 100 * share
        se = 100 * se_prop(share, n) if n else np.nan
        unit = "ppt"
    if estimate != 0:
        relative = se / estimate * 100
    elif se > 0:
        relative = math.inf
    else:
        relative = np.nan
    return {
        "type": kind,
        "unit": unit,
        "n": n,
        "estimate": estimate,
        "se": se,
        "rse": relative,
        "moe": z * se,
        "precision": rate_one(relative),
    }


def diagnose_rows(frame, variables, kind, z):
    run = progress_start(len(variables))
    rows = []
    for i, variable in enumerate(variables, start=1):
        progress_item(run, i, variable)
        row = {"variable": variable}
        row.update(diagnose_one(frame[variable], kind, z))
        rows.append(row)
    progress_done(run)
    return rows


def diagnose(data=None, *columns, type="auto", by=None, z=Z_95, digits=2):  # lint-style: ignore FN001
    """Survey precision diagnostics for one or more columns.

    The headline diagnostics wrapper: for each selected column it auto-detects
    whether it is a point estimate (numeric, e.g. a 1-5 rating) or a proportion
    (categorical), and returns a tidy table of sample size, estimate, standard
    error, relative standard error and margin of error: the whole appendix
    "Data info" block as one call.

    For numeric columns the estimate is the mean and the error is in rating
    points; for categorical columns the estimate is the **largest answer
    category's** share, which gives a single concrete plus-or-minus
    percentage-point margin to quote (the largest category is also the worst
    case among the observed categories, so it is a sensible headline). The
    ``precision`` column is the five-band rating from `rse_rating()`. For the
    narrative bullet-point version see `precision_summary()`.

    Parameters
    ----------
    data : pandas.DataFrame, optional
        A data frame. If omitted, the session default is used.
    *columns : str or selector
        Columns to diagnose, e.g. ``starts_with("ratings_")``, "demo_gender".
    type : str
        Force the estimate type: "auto" (default, detect per column), "mean" or
        "prop".
    by : str or list of str, optional
        Grouping column(s); diagnostics are computed within group.
    z : float
        Margin-of-error multiplier passed to `margin_of_error()`. Default 1.96
        (95%).
    digits : int
        Decimal places for the numeric output columns. Default 2.

    Returns
    -------
    pandas.DataFrame
        One row per column (per group), with ``variable``, ``type``, ``unit``,
        ``n``, ``estimate``, ``se``, ``rse``, ``moe`` and ``precision``. For
        type "mean", ``unit`` is "points"; for proportions it is "ppt"
        (percentage points) and ``estimate`` is a percentage.

    See Also
    --------
    precision_summary, rse_rating, se_mean, se_prop

    Examples
    --------
    >>> diagnose(podracing_survey, "demo_gender", "nps_value")
    >>> diagnose(podracing_survey, starts_with("ratings_"))
    """
    resolved = resolve_data_dots(data, columns)
    data = resolved["data"].reset_index(drop=True)
    kind = match_arg(type, TYPES)
    variables = select_columns(data, resolved["selections"])
    if not variables:
        raise ValueError("Select at least one column to diagnose.")
    by_names = select_columns(data, by) if by is not None else []
    rows = []
    for group in group_positions(data, by_names):
        block = data.iloc[group["positions"]].reset_index(drop=True)
        for row in diagnose_rows(block, variables, kind, z):
            keyed = dict(zip(by_names, group["values"]))
            keyed.update(row)
            rows.append(keyed)
    columns_out = by_names + ["variable", "type", "unit", "n", "estimate", "se", "rse", "moe", "precision"]
    out = pd.DataFrame(rows, columns=columns_out)
    out["n"] = out["n"].astype("int64")
    for column in ("estimate", "se", "rse", "moe"):
        out[column] = r_round(out[column].astype(float), digits)
    return out


def is_categorical_like(x):
    """Tell a column of categories from free text or an identifier."""
    if is_numeric_vector(x):
        return False
    answers = [value for value in na_blank(as_character(x)) if not is_missing(value)]
    n = len(answers)
    if n == 0:
        return False
    if sum(len(answer) for answer in answers) / n > 30:
        return False
    distinct = len(set(answers))
    return 2 <= distinct <= max(15, 0.25 * n)


def pnorm(z):
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def with_commas(number):
    return f"{int(number):,}" if float(number).is_integer() else f"{number:,}"


class EzrsurveyPrecision(dict):
    """The result of `precision_summary()`: a dict of its parts that prints as bullet points."""

    def __repr__(self):
        lines = ["Survey precision summary"] + ["- " + bullet for bullet in self["bullets"]]
        return "\n".join(lines) + "\n"

    def _repr_html_(self):
        items = "".join(f"<li>{bullet}</li>" for bullet in self["bullets"])
        return f"<p><strong>Survey precision summary</strong></p><ul>{items}</ul>"


def precision_summary(data=None, *columns, z=Z_95):  # lint-style: ignore FN001
    """Plain-language survey precision summary.

    Distils a whole survey's sampling precision into a few bullet points: the
    narrative "Data info" paragraph from a report appendix, generated
    automatically. Rather than make you choose which variables to quote
    precision for, this picks them: numeric columns become point estimates
    (margins in rating points) and categorical columns become proportions
    (margins in percentage points), with free-text and id-like columns skipped.
    It then reports the **typical** and **worst** margins across each group,
    plus an overall verdict from the median relative standard error via
    `rse_rating()`. For proportions it also gives the worst-case margin at a
    50/50 split, which is the widest any percentage in the study can be.

    Parameters
    ----------
    data : pandas.DataFrame, optional
        A data frame. If omitted, the session default is used.
    *columns : str or selector
        Columns to restrict the assessment to. If omitted, all suitable columns
        are used: every numeric column, and every categorical column that is not
        free text or an identifier.
    z : float
        Confidence multiplier for the margins of error. Default 1.96 (95%).

    Returns
    -------
    EzrsurveyPrecision
        A dict with ``n``, the per-variable ``table``, ``overall_rse``,
        ``rating`` and the ``bullets``. Printing it shows the bullet points.

    See Also
    --------
    diagnose, rse_rating

    Examples
    --------
    >>> precision_summary(podracing_survey)
    """
    resolved = resolve_data_dots(data, columns)
    data = resolved["data"]
    variables = select_columns(data, resolved["selections"])
    if not variables:
        variables = [str(column) for column in data.columns]
    variables = [name for name in variables if is_numeric_vector(data[name]) or is_categorical_like(data[name])]
    if not variables:
        raise ValueError("No numeric or categorical variables found to assess.")
    table = diagnose(data, all_of(variables), z=z)
    confidence = round((2 * pnorm(z) - 1) * 100)
    n_total = len(data)
    point = table[table["type"] == "mean"]
    prop = table[table["type"] == "prop"]
    median_rse = float(table["rse"].median(skipna=True))
    rating = rate_one(median_rse)
    bullets = [
        f"Based on {with_commas(n_total)} total responses (per-question base of "
        f"{with_commas(table['n'].min())} to {with_commas(table['n'].max())})."
    ]
    if len(point) > 0:
        bullets.append(
            f"Point ratings carry a sampling margin of about +/-{point['moe'].median(skipna=True):.2f} points "
            f"(up to +/-{point['moe'].max(skipna=True):.2f}) at {confidence:g}% confidence."
        )
    if len(prop) > 0:
        worst = z * se_prop(0.5, float(prop["n"].median()), pctp=True)
        bullets.append(
            f"Percentages carry a sampling margin of about +/-{prop['moe'].median(skipna=True):.1f} percentage "
            f"points (worst case +/-{worst:.1f} at a 50/50 split)."
        )
    bullets.append(f"Overall relative standard error of about {median_rse:.1f}% -- {rating}.")
    return EzrsurveyPrecision(n=n_total, table=table, overall_rse=median_rse, rating=rating, bullets=bullets)
