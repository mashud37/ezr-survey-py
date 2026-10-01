"""Cross-tabulate two survey questions as counts, percentages or an aggregate of a third column. The banner table builds its blocks from these crosstabs."""

import numpy as np
import pandas as pd

from .coerce import ensure_numeric
from .dataset import col_label, resolve_data_columns
from .orders import order_for
from .percentage import drop_rows
from .rbase import as_character, factor, is_missing, match_arg, r_mean, r_round, unique_values, warn
from .recode import na_blank
from .tables import group_positions, pivot_wider, restore_types
from .weights import resolve_weights, weighted_mean

CELLS = ["count", "row_pct", "col_pct", "total_pct"]


def summarise_cell(values, fn, na_rm):
    numbers = ensure_numeric(pd.Series(list(values)), quiet=True)
    if na_rm:
        numbers = numbers.dropna()
    if len(numbers) == 0:
        return np.nan
    return fn(numbers)


def summarise_cell_wtd(values, weights, na_rm):
    numbers = ensure_numeric(pd.Series(list(values)), quiet=True).to_numpy(dtype=float)
    weights = np.asarray(weights, dtype=float)
    if na_rm:
        kept = ~np.isnan(numbers)
        numbers = numbers[kept]
        weights = weights[kept]
    if len(numbers) == 0:
        return np.nan
    return weighted_mean(numbers, weights)


def mean_or_missing(values):
    """The mean, as R's mean(): missing when any value is missing."""
    if pd.Series(list(values)).isna().any():
        return np.nan
    return r_mean(values)


def order_rank(values, levels=None):
    """Each value's position in `levels`, or in its own order of appearance when there are none."""
    texts = list(as_character(values))
    reference = levels if levels is not None else unique_values(texts)
    ranks = []
    for text in texts:
        ranks.append(reference.index(text) if text in reference else len(reference))
    return ranks


def group_cells(frame, x_name, y_name):
    return group_positions(frame, [x_name, y_name])


def value_cells(frame, x_name, y_name, request):
    """Each x-by-y cell's aggregate of the value column: fn, or the weighted mean when weighted."""
    rows = []
    for group in group_cells(frame, x_name, y_name):
        block = frame.iloc[group["positions"]]
        values = block[request["value"]]
        if request["weighted"]:
            cell = summarise_cell_wtd(values, block[".w"], request["na_rm"])
        else:
            cell = summarise_cell(values, request["fn"], request["na_rm"])
        rows.append({x_name: group["values"][0], y_name: group["values"][1], "value": r_round(cell, request["digits"])})
    return pd.DataFrame(rows, columns=[x_name, y_name, "value"])


def count_cells(frame, x_name, y_name, weighted):
    rows = []
    for group in group_cells(frame, x_name, y_name):
        if weighted:
            count = float(frame[".w"].iloc[group["positions"]].sum())
        else:
            count = len(group["positions"])
        rows.append({x_name: group["values"][0], y_name: group["values"][1], "n": count})
    return pd.DataFrame(rows, columns=[x_name, y_name, "n"])


def share_within(counts, group_name, digits):
    values = []
    totals = {}
    for key, n in zip(counts[group_name].tolist(), counts["n"].tolist()):
        marker = "\x00missing" if is_missing(key) else key
        totals[marker] = totals.get(marker, 0) + n
    for key, n in zip(counts[group_name].tolist(), counts["n"].tolist()):
        marker = "\x00missing" if is_missing(key) else key
        values.append(r_round(n / totals[marker] * 100, digits))
    return values


def cell_values(counts, cell, x_name, y_name, digits):
    if cell == "count":
        return [r_round(n, 0) for n in counts["n"]]
    if cell == "row_pct":
        return share_within(counts, x_name, digits)
    if cell == "col_pct":
        return share_within(counts, y_name, digits)
    total = counts["n"].sum()
    return [r_round(n / total * 100, digits) for n in counts["n"]]


def crosstab(  # lint-style: ignore FN001,FN003
    data=None,
    x=None,
    y=None,
    cell="count",
    value=None,
    fn=None,
    wide=True,
    digits=None,
    na_rm=True,
    drop=None,
    weights=None,
):
    """Cross-tabulate two survey questions.

    Builds a crosstab from two categorical columns: `x` forms the rows and `y`
    the columns. Choose what the cells mean with `cell`: "row_pct" makes each
    **row** sum to 100 (the distribution of `y` within each `x`), "col_pct"
    makes each **column** sum to 100, "total_pct" is the share of the whole
    table, and "count" is the raw frequency. Supplying a numeric `value` switches
    the cells to an aggregate of that column (by default the mean), which
    answers questions like "what is the average NPS for each region by gender?".
    Blanks and non-answers in `x`/`y` are dropped when ``na_rm=True``, and any
    registered orders (`register_order()`) set the row and column ordering
    automatically.

    Parameters
    ----------
    data : pandas.DataFrame, optional
        A data frame. If omitted, the session default is used.
    x : str
        Row variable.
    y : str
        Column variable.
    cell : str
        What to put in each cell when `value` is not given: "count" (default),
        "row_pct", "col_pct" or "total_pct".
    value : str, optional
        Numeric column to aggregate per cell instead of counting.
    fn : callable, optional
        Aggregation function used with `value`, given each cell's numbers as a
        Series. Default: the mean.
    wide : bool
        If True (default), return one row per `x` with a column per `y` level;
        if False, return the tidy long form.
    digits : int, optional
        Decimal places for percentage / aggregated cells. Default 0 for
        percentages, 2 when `value` is supplied.
    na_rm : bool
        Drop blanks / non-answers in `x`, `y` (and missing `value`). Default
        True.
    drop : str or list of str, optional
        Answer values to remove from both `x` and `y` before tabulating (e.g.
        ``["Other"]``), matched case-insensitively. Defaults to the
        ``drop_answers`` option. See `drop_items()`.
    weights : bool, dict or list, optional
        Survey weighting: None (default) uses the session scheme from
        `set_weights()` if set; False forces unweighted; or pass an ad-hoc
        scheme. When weighting is active the cells are weighted: weighted
        counts, weighted percentages, or (for a numeric `value`) the weighted
        mean.

    Returns
    -------
    pandas.DataFrame
        Wide (`x` plus one column per `y` level) or long (`x`, `y`, ``value``).

    See Also
    --------
    calc_percentage, compare_values, register_order

    Examples
    --------
    >>> crosstab(podracing_survey, "demo_gender", "region")
    >>> crosstab(podracing_survey, "region", "demo_gender", cell="row_pct")
    >>> crosstab(podracing_survey, "region", "demo_gender", value="nps_value")
    """
    resolved = resolve_data_columns(data, [x, y])
    data = resolved["data"]
    cell = match_arg(cell, CELLS)
    x_name = col_label(resolved["columns"][0], data, argument="x")
    y_name = col_label(resolved["columns"][1], data, argument="y")
    has_value = value is not None
    if digits is None:
        digits = 2 if has_value else 0
    w = resolve_weights(data, weights)
    weighted = w is not None
    frame = data.reset_index(drop=True)
    if weighted:
        frame = frame.assign(**{".w": w})
    if na_rm:
        frame = frame.assign(**{x_name: na_blank(frame[x_name]).to_numpy(), y_name: na_blank(frame[y_name]).to_numpy()})
        frame = frame[frame[x_name].notna() & frame[y_name].notna()]
    frame = drop_rows(frame, x_name, drop)
    frame = drop_rows(frame, y_name, drop).reset_index(drop=True)
    if has_value:
        value_name = col_label(value, frame, argument="value")
        if weighted and fn is not None:
            warn("Weighted crosstab aggregates `value` with the weighted mean; `fn` is ignored.")
        request = {
            "value": value_name,
            "fn": fn or mean_or_missing,
            "weighted": weighted,
            "na_rm": na_rm,
            "digits": digits,
        }
        out = value_cells(frame, x_name, y_name, request)
    else:
        counts = count_cells(frame, x_name, y_name, weighted)
        counts["value"] = cell_values(counts, cell, x_name, y_name, digits)
        out = counts[[x_name, y_name, "value"]]
    out = restore_types(out.copy(), frame, [x_name, y_name])
    out = apply_margin_orders(out, x_name, y_name)
    if wide:
        out = pivot_wider(out, names_from=y_name, values_from="value")
    return out.reset_index(drop=True)


def apply_margin_orders(out, x_name, y_name):
    """Put both margins in their registered order, levels and rows alike."""
    x_levels = order_for(x_name)
    y_levels = order_for(y_name)
    ordered = out.copy()
    if x_levels is not None:
        ordered[x_name] = factor(as_character(ordered[x_name]), levels=x_levels).values
    if y_levels is not None:
        ordered[y_name] = factor(as_character(ordered[y_name]), levels=y_levels).values
    if x_levels is None and y_levels is None:
        return ordered
    x_ranks = order_rank(ordered[x_name], x_levels)
    y_ranks = order_rank(ordered[y_name], y_levels)
    positions = sorted(range(len(ordered)), key=lambda row: (x_ranks[row], y_ranks[row]))
    return ordered.iloc[positions].reset_index(drop=True)
