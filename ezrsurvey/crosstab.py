"""Cross-tabulate two survey questions as counts, percentages or an aggregate of a third column. The banner table builds its blocks from these crosstabs."""

import numpy as np
import pandas as pd

from .coerce import ensure_numeric
from .dataset import col_label, resolve_data_columns
from .orders import factor_order, order_for
from .percentage import drop_rows
from .rbase import (
    as_character,
    factor,
    is_categorical,
    is_missing,
    match_arg,
    r_mean,
    r_round,
    unique_values,
    warn,
)
from .recode import na_blank
from .tables import group_positions, pivot_wider
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


def value_cells(frame, weighted, request):
    """Each x-by-y cell's aggregate of the value column: fn, or the weighted mean when weighted."""
    rows = []
    for group in group_positions(frame, [".x", ".y"]):
        block = frame.iloc[group["positions"]]
        if weighted:
            cell = summarise_cell_wtd(block[".v"], block[".w"], request["na_rm"])
        else:
            cell = summarise_cell(block[".v"], request["fn"] or mean_or_missing, request["na_rm"])
        rows.append({".x": group["values"][0], ".y": group["values"][1], ".value": r_round(cell, request["digits"])})
    return pd.DataFrame(rows, columns=[".x", ".y", ".value"])


def count_cells(frame, weighted):
    rows = []
    for group in group_positions(frame, [".x", ".y"]):
        if weighted:
            count = float(frame[".w"].iloc[group["positions"]].sum())
        else:
            count = len(group["positions"])
        rows.append({".x": group["values"][0], ".y": group["values"][1], "n": count})
    return pd.DataFrame(rows, columns=[".x", ".y", "n"])


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


def cell_values(counts, cell, digits):
    if cell == "count":
        return [r_round(n, 0) for n in counts["n"]]
    if cell == "row_pct":
        return share_within(counts, ".x", digits)
    if cell == "col_pct":
        return share_within(counts, ".y", digits)
    total = counts["n"].sum()
    return [r_round(n / total * 100, digits) for n in counts["n"]]


def crosstab_long(data, x_name, y_name, request):
    """The crosstab cells in long form, under the fixed names ``.x``, ``.y`` and ``.value``.

    The counting runs on a frame built here from only the columns it needs, so
    a survey column called ``value`` or ``n`` cannot collide with the names the
    counting uses. The banner table reads this directly for the same reason.

    Args:
        data: The survey DataFrame.
        x_name: The row question.
        y_name: The column question.
        request: A dict of ``cell``, ``value`` (a column name or None), ``fn``,
            ``digits``, ``na_rm``, ``drop`` and ``weights``.

    Returns:
        A DataFrame of ``.x``, ``.y`` and ``.value``, one row per cell, with
        categorical margins wherever an order applies.
    """
    w = resolve_weights(data, request["weights"])
    weighted = w is not None
    frame = pd.DataFrame({".x": data[x_name].to_numpy(), ".y": data[y_name].to_numpy()})
    if request["value"] is not None:
        frame[".v"] = data[request["value"]].to_numpy()
    if weighted:
        frame[".w"] = w
    if request["na_rm"]:
        frame[".x"] = na_blank(frame[".x"]).to_numpy()
        frame[".y"] = na_blank(frame[".y"]).to_numpy()
        frame = frame[frame[".x"].notna() & frame[".y"].notna()]
    frame = drop_rows(frame, ".x", request["drop"])
    frame = drop_rows(frame, ".y", request["drop"]).reset_index(drop=True)
    if request["value"] is not None:
        if weighted and request["fn"] is not None:
            warn("Weighted crosstab aggregates `value` with the weighted mean; `fn` is ignored.")
        out = value_cells(frame, weighted, request)
    else:
        counts = count_cells(frame, weighted)
        counts[".value"] = cell_values(counts, request["cell"], request["digits"])
        out = counts[[".x", ".y", ".value"]]
    x_levels = order_for(x_name)
    if x_levels is None:
        x_levels = factor_order(data[x_name], out[".x"])
    y_levels = order_for(y_name)
    if y_levels is None:
        y_levels = factor_order(data[y_name], out[".y"])
    return apply_margin_orders(out, x_levels, y_levels)


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
    Blanks and non-answers in `x`/`y` are dropped when ``na_rm=True``. Any
    registered orders (`register_order()`) set the row and column ordering
    automatically; a categorical without one keeps its own category order;
    anything else stays in data order.

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
        The long form refuses an `x` or `y` that is itself called ``value``,
        since the two columns would share a name.

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
    value_name = None
    if value is not None:
        value_name = col_label(value, data, argument="value")
    if digits is None:
        digits = 0 if value_name is None else 2
    request = {
        "cell": cell,
        "value": value_name,
        "fn": fn,
        "digits": digits,
        "na_rm": na_rm,
        "drop": drop,
        "weights": weights,
    }
    out = crosstab_long(data, x_name, y_name, request)
    if wide:
        out = pivot_wider(out, names_from=".y", values_from=".value", names_sort=is_categorical(out[".y"]))
        return out.rename(columns={".x": x_name})
    if "value" in (x_name, y_name):
        raise ValueError(
            "crosstab(wide=False) puts the cells in a column called `value`, which is also "
            "the name of a question here. Rename that column, or use wide=True."
        )
    out.columns = [x_name, y_name, "value"]
    return out


def apply_margin_orders(out, x_levels, y_levels):
    """Put both margins in their order, levels and rows alike, where they have one."""
    ordered = out.copy()
    if x_levels is not None:
        ordered[".x"] = factor(as_character(ordered[".x"]), levels=x_levels).values
    if y_levels is not None:
        ordered[".y"] = factor(as_character(ordered[".y"]), levels=y_levels).values
    if x_levels is None and y_levels is None:
        return ordered.reset_index(drop=True)
    x_ranks = order_rank(ordered[".x"], x_levels)
    y_ranks = order_rank(ordered[".y"], y_levels)
    positions = sorted(range(len(ordered)), key=lambda row: (x_ranks[row], y_ranks[row]))
    return ordered.iloc[positions].reset_index(drop=True)
