"""Turn survey questions into percentage and summary tables, optionally grouped and weighted. These tables are what the charts, workbooks and reports consume."""

import numpy as np
import pandas as pd

from .coerce import ensure_numeric
from .config import ezrsurvey_default
from .dataset import col_label, resolve_data_columns, resolve_data_dots
from .orders import factor_order, order_for
from .rbase import (
    as_character,
    factor,
    is_missing,
    match_arg,
    message,
    r_mean,
    r_median,
    r_round,
    r_sd,
    unique_values,
)
from .recode import detect_delimiter, drop_items, na_blank, unpack_answers
from .select import select_columns, starts_with
from .tables import group_positions, order_rows, pivot_wider, restore_types, take_rows
from .weights import resolve_weights, weighted_mean, wtd_median, wtd_sd

SORTS = ["none", "desc", "asc"]


def clean_label(x, prefix=None):
    """Tidy an exported column name into a readable label.

    Turns the mangled column names survey tools produce back into the wording a
    reader expects: "Broadcast.quality...audio" becomes
    "Broadcast quality / audio". Drop a question prefix at the same time with
    `prefix`, so a block of ``ratings_*`` columns becomes plain feature names.

    Exporters replace every character they cannot put in a column name with a
    dot, so a slash surrounded by spaces arrives as three dots and a space
    arrives as one. This restores both, in that order, then squishes the result.
    It is the same cleaning `calc_percentage_multi()` and `ipm_model()` apply to
    their own output, so a hand-built table can match them.

    Parameters
    ----------
    x : str or list of str
        Column names.
    prefix : str, optional
        Prefix to strip from the start of each name before tidying, e.g.
        "ratings_". Names that do not start with it are left alone.

    Returns
    -------
    list of str
        Labels, the same length as `x`.

    See Also
    --------
    calc_percentage_batch, calc_percentage_multi

    Examples
    --------
    >>> clean_label("Broadcast.quality...audio")
    >>> clean_label(["ratings_Camera.work", "ratings_Talent...analysis"], prefix="ratings_")
    """
    names = [x] if isinstance(x, str) else list(x)
    out = []
    for name in names:
        if is_missing(name):
            out.append(np.nan)
            continue
        if prefix is not None and name.startswith(prefix):
            name = name[len(prefix):]
        name = name.replace("...", " / ").replace(".", " ")
        out.append(" ".join(name.split()))
    return out


def drop_rows(frame, column, drop):
    """Remove rows whose answer is in the `drop` set, falling back to the drop_answers option."""
    if drop is None:
        drop = ezrsurvey_default("drop_answers")
    if drop is None or len(drop) == 0:
        return frame
    kept = drop_items(frame[column], drop)
    dropped = kept.isna().to_numpy() & frame[column].notna().to_numpy()
    return frame[~dropped]


def packed_delimiter(frame, option_columns, split):
    if split is None or split is False or len(option_columns) != 1:
        return None
    values = na_blank(frame[option_columns[0]])
    if split == "auto":
        return detect_delimiter(values)
    return split


def unpack_long(frame, option_column, keep, delimiter):
    """One row per respondent-answer pair from a packed column; the answer text is the option."""
    chosen = unpack_answers(na_blank(frame[option_column]), delimiter)
    positions = []
    options = []
    for position, answers in enumerate(chosen):
        for answer in answers:
            positions.append(position)
            options.append(answer)
    out = frame[keep].iloc[positions].reset_index(drop=True)
    out["option"] = options
    out["value"] = options
    return out


def order_factor(frame, key, sort="none", levels=None):
    """Order the levels of `key` and the rows to match, by `levels`, by `pct`, or not at all.

    Shared by the percentage helpers and the plot wrappers so a chart inherits
    whatever order the table was built with.
    """
    sort = match_arg(sort, SORTS)
    ordered = frame.copy()
    if levels is not None:
        levels = list(levels)
        unmatched = [answer for answer in unique_values(as_character(ordered[key])) if answer not in levels]
        if unmatched:
            message(
                f"Order for '{key}' does not list {len(unmatched)} answer(s), which become NA: "
                f"{', '.join(unmatched)}. Add them to register_order() or pass `levels=`."
            )
        ordered[key] = factor(as_character(ordered[key]), levels=levels, ordered=True).values
        group_columns = [column for column in ordered.columns if column not in (key, "n", "pct", "wpct")]
        return take_rows(ordered, order_rows(ordered, group_columns + [key]))
    if sort == "none":
        return ordered
    ordering = "pct" if "pct" in ordered.columns else key
    ordered = take_rows(ordered, order_rows(ordered, [ordering], decreasing=(sort == "desc")))
    ordered[key] = factor(as_character(ordered[key]), levels=unique_values(as_character(ordered[key]))).values
    return ordered


def by_columns(frame, by):
    if by is not None:
        return select_columns(frame, by)
    default = ezrsurvey_default("default_by")
    if default is None:
        return []
    default = [default] if isinstance(default, str) else list(default)
    return [name for name in default if name in frame.columns]


def count_within(frame, by_names, col_name, weighted, digits):
    """Count each answer within each `by` group, as n and pct (and weighted wpct)."""
    rows = []
    for outer in group_positions(frame, by_names):
        block = frame.iloc[outer["positions"]]
        inner_groups = group_positions(block, [col_name])
        total = len(block)
        weight_total = block[".w"].sum() if weighted else 0
        for inner in inner_groups:
            row = dict(zip(by_names, outer["values"]))
            row[col_name] = inner["values"][0]
            row["n"] = len(inner["positions"])
            row["pct"] = r_round(row["n"] / total * 100, digits)
            if weighted:
                weight_sum = block[".w"].iloc[inner["positions"]].sum()
                row["wpct"] = r_round(weight_sum / weight_total * 100, digits)
            rows.append(row)
    columns = by_names + [col_name, "n", "pct"] + (["wpct"] if weighted else [])
    out = pd.DataFrame(rows, columns=columns)
    out["n"] = out["n"].astype("int64")
    return restore_types(out, frame, by_names + [col_name])


def calc_percentage(  # lint-style: ignore FN001,FN003
    data=None,
    column=None,
    by=None,
    sort="none",
    levels=None,
    digits=0,
    wide=False,
    na_rm=True,
    drop=None,
    weights=None,
):
    """Count a categorical question as percentages.

    The headline helper: one call that returns both the raw counts and the
    percentages, optionally grouped by one or more variables and optionally
    pivoted to a wide cross-tabulation.

    Percentages are computed *within* each group, so they sum to about 100 per
    group (subject to rounding). The order of `column` is decided in this order
    of precedence: an explicit `levels` argument; then a non-"none" `sort`; then
    a registered order for the variable (see `register_order()`); then the
    column's own categories, when it is categorical; otherwise data order. When
    `by` is omitted, the ``default_by`` option is used if set, so
    you can apply a standard breakdown without repeating it. ``wide=True``
    pivots to one row per group with a column per answer: the shape you want for
    a slide table or an Excel tab.

    Parameters
    ----------
    data : pandas.DataFrame, optional
        A data frame. If omitted, the session default set with `use_dataset()`
        is used.
    column : str
        The categorical column to tabulate.
    by : str or list of str, optional
        Grouping column(s). Percentages are computed *within* each group so they
        sum to about 100 per group.
    sort : str
        Order of `column`: "none" (default, data order), "desc" (largest
        percentage first) or "asc".
    levels : list of str, optional
        An explicit level order for `column`. Overrides `sort`. If omitted and
        ``sort="none"``, a registered order for this variable is applied
        automatically, and failing that a categorical keeps its own category
        order.
    digits : int
        Decimal places for the percentage. Default 0.
    wide : bool
        If True, pivot to one row per `by` group and one column per answer
        (dropping ``n``). Default False (tidy long form).
    na_rm : bool
        If True (default), blanks and "Prefer not to answer" responses (see
        `na_blank()`) are dropped before counting.
    drop : str or list of str, optional
        Answer values to remove before counting (e.g. ``["Other", "Don't
        know"]``), so the kept answers re-base to about 100%. Matching is
        case-insensitive (see `drop_items()`). Defaults to the ``drop_answers``
        option (None = drop nothing).
    weights : bool, dict or list, optional
        Survey weighting for this call: None (default) uses the session scheme
        from `set_weights()` if one is set; False forces unweighted; or pass an
        ad-hoc scheme (any form `set_weights()` accepts). When weighting is
        active a ``wpct`` column (weighted percentage) is added beside ``n`` and
        ``pct``.

    Returns
    -------
    pandas.DataFrame
        `column`, ``n`` and ``pct`` (and ``wpct`` when weighting is active) in
        long form, or one row per group with an answer column each (wide form).

    See Also
    --------
    calc_percentage_multi, calc_percentage_batch, calc_summary, register_order

    Examples
    --------
    >>> calc_percentage(podracing_survey, "demo_gender")
    >>> calc_percentage(podracing_survey, "demo_gender", sort="desc")
    >>> calc_percentage(podracing_survey, "satis_return", by="region", wide=True)
    """
    resolved = resolve_data_columns(data, [column])
    data = resolved["data"]
    sort = match_arg(sort, SORTS)
    col_name = col_label(resolved["columns"][0], data)
    w = resolve_weights(data, weights)
    weighted = w is not None
    frame = data.reset_index(drop=True)
    if weighted:
        frame = frame.assign(**{".w": w})
    frame = drop_rows(frame, col_name, drop)
    if na_rm:
        frame = frame.assign(**{col_name: na_blank(frame[col_name]).to_numpy()})
        frame = frame[frame[col_name].notna()]
    frame = frame.reset_index(drop=True)
    by_names = by_columns(frame, by)
    out = count_within(frame, by_names, col_name, weighted, digits)
    if levels is None and sort == "none":
        levels = order_for(col_name)
        if levels is None:
            levels = factor_order(data[col_name], out[col_name])
    out = order_factor(out, col_name, sort=sort, levels=levels)
    if wide:
        value_column = "wpct" if weighted else "pct"
        dropped = ["n", "pct"] if weighted else ["n"]
        out = pivot_wider(out.drop(columns=dropped), names_from=col_name, values_from=value_column)
    return out.reset_index(drop=True)


def long_options(frame, keep_columns, option_columns, prefix, clean_names):
    """One row per respondent and ticked option from a block of one-column-per-option."""
    cells = [frame[column].tolist() for column in option_columns]
    records = []
    for position in range(len(frame)):
        for column, values in zip(option_columns, cells):
            records.append({"position": position, "option": column, "value": values[position]})
    long = pd.DataFrame(records, columns=["position", "option", "value"])
    keep = frame[keep_columns].iloc[long["position"].tolist()].reset_index(drop=True)
    long = pd.concat([keep, long[["option", "value"]]], axis=1)
    long["value"] = na_blank(long["value"]).to_numpy()
    long = long[long["value"].notna()].reset_index(drop=True)
    stripped = [option.replace(prefix, "", 1) for option in long["option"]]
    long["option"] = clean_label(stripped) if clean_names else stripped
    return long


def distinct_count(values):
    seen = set()
    for value in values:
        seen.add("\x00missing" if is_missing(value) else value)
    return len(seen)


def calc_percentage_multi(  # lint-style: ignore FN001,FN003
    data=None,
    prefix=None,
    id=None,
    by=None,
    sort="none",
    digits=0,
    drop=None,
    clean_names=True,
    split="auto",
):
    """Tabulate a check-all-that-apply (multi-select) question as percentages.

    Multi-select questions arrive as a block of columns sharing a prefix, each
    holding the chosen option (or blank). This computes, per option, the share
    of respondents who selected it, so the percentages can (and usually do) sum
    to more than 100. The denominator is the number of distinct respondents who
    selected at least one option: if 700 of 1,000 respondents selected at least
    one motivation, each option's percentage is "out of 700". Supply `id` to
    count distinct respondents exactly; without it, each row counts as one
    respondent. With ``clean_names=True`` the option labels are stripped of
    `prefix` and exporter artefacts like "A...B" are turned back into "A / B".

    Two export shapes are handled. The usual one is a block of columns, one per
    option, named with a shared `prefix`. The other is a single column holding
    every answer a respondent ticked, joined by a delimiter, which is what
    Google Forms and most spreadsheet exports produce. If `prefix` matches
    exactly one column and a delimiter is found in it, that column is unpacked
    automatically and the answer text itself becomes the option label. Use
    `split_multi()` when you want those unpacked columns kept for other work.

    Parameters
    ----------
    data : pandas.DataFrame, optional
        A data frame. If omitted, the session default is used.
    prefix : str
        Common column-name prefix identifying the option block, e.g.
        "motivations_".
    id : str, optional
        Respondent identifier column used as the distinct-respondent
        denominator. If omitted, each row is treated as one respondent.
    by : str or list of str, optional
        Grouping column(s); percentages are computed within group.
    sort, digits
        As in `calc_percentage()`. Sorting acts on the ``option`` labels.
    drop : str or list of str, optional
        Option labels to remove before counting (matched against the cleaned
        labels, case-insensitive). Defaults to the ``drop_answers`` option.
    clean_names : bool
        If True (default), tidy the option labels by stripping `prefix` and
        un-mangling exporter artefacts ("A...B" to "A / B").
    split : str or bool
        How to handle a question packed into a single cell per respondent
        ("Speed; Drivers"). "auto" (default) detects ";", "|" or "," and splits
        on it; pass a string to force a delimiter, or False never to split. Only
        ever applies when `prefix` selects exactly one column.

    Returns
    -------
    pandas.DataFrame
        ``option``, ``n`` (respondents choosing it) and ``pct``.

    See Also
    --------
    calc_percentage, split_multi, plot_bars

    Examples
    --------
    >>> calc_percentage_multi(podracing_survey, "motivations_", id="respondent_id", sort="desc")
    >>> packed = pd.DataFrame({
    ...     "respondent": [1, 2, 3, 4],
    ...     "motivations": ["Speed; Drivers", "Speed", "", "Betting; Speed"],
    ... })
    >>> calc_percentage_multi(packed, "motivations", id="respondent", sort="desc")
    """
    resolved = resolve_data_columns(data, [prefix])
    data = resolved["data"]
    prefix = resolved["columns"][0]
    sort = match_arg(sort, SORTS)
    option_columns = select_columns(data, starts_with(prefix))
    if not option_columns:
        raise ValueError(f"No columns start with prefix '{prefix}'.")
    frame = data.reset_index(drop=True)
    id_col = ".row_id"
    if id is not None:
        id_col = col_label(id, frame, argument="id")
    else:
        frame = frame.assign(**{id_col: range(1, len(frame) + 1)})
    by_names = by_columns(frame, by)
    delimiter = packed_delimiter(frame, option_columns, split)
    if delimiter is not None:
        long = unpack_long(frame, option_columns[0], [id_col] + by_names, delimiter)
    else:
        long = long_options(frame, [id_col] + by_names, option_columns, prefix, clean_names)
    long = drop_rows(long, "option", drop).reset_index(drop=True)
    rows = []
    for outer in group_positions(long, by_names):
        block = long.iloc[outer["positions"]]
        denominator = distinct_count(block[id_col])
        for inner in group_positions(block, ["option"]):
            row = dict(zip(by_names, outer["values"]))
            row["option"] = inner["values"][0]
            row["n"] = distinct_count(block[id_col].iloc[inner["positions"]])
            row["pct"] = r_round(row["n"] / denominator * 100, digits)
            rows.append(row)
    out = pd.DataFrame(rows, columns=by_names + ["option", "n", "pct"])
    out["n"] = out["n"].astype("int64")
    out = restore_types(out, long, by_names)
    return order_factor(out, "option", sort=sort).reset_index(drop=True)


def numeric_summary(values, weights):
    values = pd.Series(values, dtype=float)
    kept = values.dropna()
    row = {"n": int(values.notna().sum())}
    if weights is None:
        row["mean"] = r_mean(kept)
        row["median"] = r_median(kept)
        row["sd"] = r_sd(kept)
        return row
    weights = np.asarray(weights, dtype=float)
    present = values.notna().to_numpy()
    row["mean"] = weighted_mean(values[present], weights[present]) if present.any() else np.nan
    row["median"] = wtd_median(values, weights)
    row["sd"] = wtd_sd(values, weights)
    return row


def calc_summary(data=None, column=None, by=None, na_rm=True, weights=None):  # lint-style: ignore FN001
    """Summarise a numeric question (mean / median / sd).

    The numeric counterpart to `calc_percentage()`, with optional grouping. The
    column is passed through `ensure_numeric()` first, so a text age column like
    "25 years" still summarises. ``n`` counts non-missing values (after that
    coercion). When a weighting scheme is active the statistics are weighted
    (and missing values are dropped); ``n`` remains the unweighted respondent
    count. For a measure of how precise the ``mean`` is, pair this with
    `diagnose()` or `se_mean()`.

    Parameters
    ----------
    data : pandas.DataFrame, optional
        A data frame. If omitted, the session default is used.
    column : str
        Numeric column to summarise.
    by : str or list of str, optional
        Grouping column(s); see `calc_percentage()`.
    na_rm : bool
        Drop missing values before summarising. Default True.
    weights : bool, dict or list, optional
        Survey weighting: None (default) uses the session scheme from
        `set_weights()` if set; False forces unweighted; or pass an ad-hoc
        scheme. When weighting is active the ``mean``, ``median`` and ``sd``
        become their weighted versions (``n`` stays the unweighted base).

    Returns
    -------
    pandas.DataFrame
        ``n`` (non-missing count), ``mean``, ``median`` and ``sd``, one row per
        group when `by` is supplied.

    See Also
    --------
    calc_percentage, diagnose

    Examples
    --------
    >>> calc_summary(podracing_survey, "demo_age")
    >>> calc_summary(podracing_survey, "demo_age", by="region")
    """
    resolved = resolve_data_columns(data, [column])
    data = resolved["data"]
    col_name = col_label(resolved["columns"][0], data)
    w = resolve_weights(data, weights)
    frame = data.reset_index(drop=True)
    frame = frame.assign(**{col_name: ensure_numeric(frame[col_name], name=col_name).to_numpy()})
    by_names = select_columns(frame, by) if by is not None else []
    rows = []
    for group in group_positions(frame, by_names):
        values = frame[col_name].iloc[group["positions"]].to_numpy()
        group_weights = None if w is None else np.asarray(w)[group["positions"]]
        if not na_rm and pd.isna(values).any() and w is None:
            summary = {"n": int((~pd.isna(values)).sum()), "mean": np.nan, "median": np.nan, "sd": np.nan}
        else:
            summary = numeric_summary(values, group_weights)
        row = dict(zip(by_names, group["values"]))
        row.update(summary)
        rows.append(row)
    out = pd.DataFrame(rows, columns=by_names + ["n", "mean", "median", "sd"])
    out["n"] = out["n"].astype("int64")
    return restore_types(out, frame, by_names)


def calc_percentage_batch(  # lint-style: ignore FN001
    data=None,
    *columns,
    by=None,
    sort="none",
    digits=0,
    na_rm=True,
    drop=None,
    weights=None,
    clean_names=False,
    prefix=None,
):
    """Percentages for a batch of questions at once.

    Runs `calc_percentage()` over several columns and stacks the results into
    one tidy table with a ``variable`` column identifying the source question and
    a shared ``answer`` column: handy for tabulating a whole block of questions
    (e.g. every ``demo_`` variable) in a single call. Answers are stacked as
    text, since level orders differ between questions. To send each question to
    its own Excel tab instead, see `export_xlsx()`.

    ``variable`` is the raw column name by default. Set ``clean_names=True`` (or
    name a `prefix`) to get the same tidied wording `calc_percentage_multi()`
    and `ipm_model()` produce, which is what lets a batch table join to a model
    table on the question name.

    Parameters
    ----------
    data : pandas.DataFrame, optional
        A data frame. If omitted, the session default is used.
    *columns : str or selector
        Columns to tabulate: names, or selectors such as
        ``starts_with("demo_")``.
    by, sort, digits, na_rm, drop, weights
        Passed to `calc_percentage()` (so a ``wpct`` column appears when
        weighting is active, and `drop` removes unwanted answers from every
        question).
    clean_names : bool
        If True, tidy each ``variable`` with `clean_label()` instead of
        reporting the raw column name.
    prefix : str, optional
        Question prefix to strip from ``variable``, e.g. "ratings_". Implies
        `clean_names`.

    Returns
    -------
    pandas.DataFrame
        ``variable``, ``answer``, ``n``, ``pct`` (plus any `by` columns).

    See Also
    --------
    calc_percentage, clean_label, export_xlsx

    Examples
    --------
    >>> calc_percentage_batch(podracing_survey, "demo_gender", "demo_job")
    >>> calc_percentage_batch(podracing_survey, starts_with("demo_"))
    >>> calc_percentage_batch(podracing_survey, starts_with("ratings_"), prefix="ratings_")
    """
    resolved = resolve_data_dots(data, columns)
    data = resolved["data"]
    sort = match_arg(sort, SORTS)
    names = select_columns(data, resolved["selections"])
    if not names:
        raise ValueError("Select at least one column to tabulate.")
    labels = names
    if clean_names or prefix is not None:
        labels = clean_label(names, prefix=prefix)
    pieces = []
    for name, label in zip(names, labels):
        result = calc_percentage(
            data,
            name,
            by=by,
            sort=sort,
            digits=digits,
            na_rm=na_rm,
            drop=drop,
            weights=weights,
        )
        result = result.rename(columns={name: "answer"})
        result["answer"] = as_character(result["answer"]).to_numpy()
        result.insert(0, "variable", label)
        pieces.append(result)
    return pd.concat(pieces, ignore_index=True)
