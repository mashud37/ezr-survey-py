"""Draw the survey deck's charts as static plotnine figures: bars, stacked ratings, NPS, gauges, the importance/performance matrix and quote treemaps. Layout decisions follow the R package exactly."""

import math

import numpy as np
import pandas as pd
from plotnine import (
    aes,
    annotate,
    coord_flip,
    element_blank,
    element_text,
    geom_col,
    geom_hline,
    geom_point,
    geom_rect,
    geom_segment,
    geom_text,
    geom_vline,
    ggplot,
    guide_legend,
    guides,
    labs,
    position_stack,
    scale_colour_identity,
    scale_fill_identity,
    scale_fill_manual,
    scale_size_identity,
    scale_x_continuous,
    scale_y_continuous,
    theme,
)

from .coerce import ensure_numeric
from .config import ezrsurvey_default
from .dataset import col_label, resolve_data_columns
from .decisions import annotate_bands, band_colour, band_label, bands_nps_score, bands_rating_3
from .orders import order_for
from .palettes import pal_neutral, pal_nps, rating_palette
from .percentage import calc_percentage_batch
from .rbase import (
    as_character,
    character_value,
    factor,
    factor_levels,
    is_categorical,
    is_missing,
    match_arg,
    message,
    r_mean,
    r_round,
    r_sum,
    str_wrap,
    unique_values,
)
from .recode import LIKERT_LEVELS, nps_group, recode_likert
from .scales import PercentLabels, blank_labels, label_pct, nice_max, scale_y_pct
from .select import all_of
from .tables import group_positions, order_rows
from .theme import PT, theme_ezrsurvey, theme_ezrsurvey_xy, theme_ezrsurvey_y

ORIENTATIONS = ["auto", "cols", "bars"]
BAR_SORTS = ["auto", "none", "asc", "desc"]
GAUGE_SCALES = ["nps", "rating"]
MAX_BAR_WIDTH = 0.9
BASE_TEXT = 11
GAUGE_HEIGHT = 0.5
GAUGE_TEXT = 10
TICK_TEXT = 8
CHAR_WIDTH_SHARE = 0.030
TEXT_NUDGE_SHARE = 0.02
IPM_POINT_SIZE = 6
IPM_LABEL_SIZE = 4
QUOTE_PADDING_INCHES = 4 / 25.4
QUOTE_WIDTH_INCHES = 8
QUOTE_HEIGHT_INCHES = 4.5
QUOTE_MAX_SIZE = 28


def consistent_bar_width(n_items):
    """The column width that keeps drawn bar thickness constant however many bars a chart has."""
    base = ezrsurvey_default("bar_width") or 0.66
    reference = ezrsurvey_default("bar_ref_items") or 6
    if not math.isfinite(n_items) or n_items < 1 or not math.isfinite(reference) or reference < 1:
        return base
    return min(MAX_BAR_WIDTH, base * n_items / reference)


def auto_bar_layout(labels, n_items, request):
    """Choose orientation, wrap width, label size and sort direction for plot_bars().

    Args:
        labels: The bar labels, as text.
        n_items: How many bars.
        request: ``orientation`` and ``sort`` ("auto" or a choice), ``is_ordinal``,
            and ``wrap`` and ``label_size`` (None to decide here).

    Returns:
        A dict with ``orientation``, ``wrap``, ``sort`` and ``size``.
    """
    lengths = [len(label) for label in labels if not is_missing(label)]
    max_label = max(lengths) if lengths else 0
    orientation = request["orientation"]
    if orientation == "auto":
        use_bars = n_items > ezrsurvey_default("bar_cols_max_items") or max_label > ezrsurvey_default("bar_cols_max_label")
        orientation = "bars" if use_bars else "cols"
    wrap = request["wrap"]
    if wrap is None:
        wrap = ezrsurvey_default("bar_wrap_bars") if orientation == "bars" else ezrsurvey_default("bar_wrap_cols")
    sort = request["sort"]
    if sort == "auto":
        if request["is_ordinal"]:
            sort = "none"
        elif orientation == "bars":
            sort = "asc"
        else:
            sort = "desc"
    size = request["label_size"]
    if size is None:
        threshold = ezrsurvey_default("bar_cols_max_items")
        stepped = ezrsurvey_default("bar_label_size") - ezrsurvey_default("bar_size_step") * max(0, n_items - threshold)
        size = max(ezrsurvey_default("bar_size_min"), stepped)
    return {"orientation": orientation, "wrap": wrap, "sort": sort, "size": size}


def default_fill():
    primary = ezrsurvey_default("brand_color_primary")
    if primary is not None:
        return primary
    colours = ezrsurvey_default("brand_colors")
    if colours:
        return colours if isinstance(colours, str) else colours[0]
    return pal_neutral


def detect_label(data, label, value):
    if label is not None:
        return label
    candidates = [str(name) for name in data.columns if name not in ("n", value)]
    if not candidates:
        raise ValueError("Could not auto-detect a label column; pass `label`.")
    return candidates[0]


def bar_order(data, label, value, sort):
    """The rows in plotting order, and the category order the bars should follow."""
    if sort != "none":
        ordered = data.iloc[order_rows(data, [value], decreasing=(sort == "desc"))].reset_index(drop=True)
        return {"data": ordered, "levels": unique_values(as_character(ordered[label]))}
    return {"data": data.reset_index(drop=True), "levels": factor_levels(data[label])}


def plot_bars(  # lint-style: ignore FN001,FN003
    data,
    label=None,
    value="pct",
    orientation="auto",
    sort="auto",
    wrap=None,
    flip=None,
    avg_line=False,
    axis_labels=False,
    unit=None,
    max=None,
    fill=None,
    title=None,
    label_size=None,
):
    """Bar chart of a percentage table (auto-laid-out).

    Plots the output of `calc_percentage()` (or `calc_percentage_multi()`) as a
    labelled bar chart, with a tidy auto-scaled axis (`nice_max()`) and the
    ezrsurvey theme. By default the **layout is chosen for you**: vertical
    columns for a few short labels, horizontal bars for many or long ones, with
    long labels wrapped, the text size stepped down as bars multiply, and the
    bars ordered so the longest sits at the top (bars) or on the left (cols).

    The label column is auto-detected as the first column that is neither ``n``
    nor the value, so a piped percentage table just works. The layout decisions
    all read from the ``bar_*`` options (`ezrsurvey_options()`), and
    ``sort="auto"`` leaves an ordered categorical (a registered or explicit
    order) as it is. Bars are drawn to a constant thickness regardless of how
    many there are (``bar_width`` / ``bar_ref_items``), so a three-answer chart
    and a ten-answer chart look like they belong in the same deck. Add decision
    guidance with `annotate_bands()`.

    Parameters
    ----------
    data : pandas.DataFrame
        A table with a category column and a value column.
    label : str, optional
        Category column. None (default) uses the first non-``n``, non-value
        column.
    value : str
        Value column. Default "pct".
    orientation : str
        "auto" (default), "cols" (vertical) or "bars" (horizontal).
    sort : str
        "auto" (default), "none", "asc" or "desc".
    wrap : int, optional
        Label wrap width in characters. None uses ``bar_wrap_cols`` /
        ``bar_wrap_bars`` for the chosen orientation.
    flip : bool, optional
        Back-compatible shortcut: True forces "bars", False forces "cols".
    avg_line : bool
        Add a reference line at the mean value. Default False.
    axis_labels : bool
        Show the percentage axis. Default False (the bars carry data labels).
    unit : float, optional
        Axis rounding step for `nice_max()`. None uses the ``pct_axis_unit``
        option.
    max : float, optional
        Fixed y-axis maximum (e.g. 100). None uses the ``pct_axis_max`` option.
    fill : str, optional
        Bar colour. None uses the brand primary colour when a brand is set,
        else ``pal_neutral``.
    title : str, optional
        Plot title.
    label_size : float, optional
        Data-label size, in R's millimetre units as the ``bar_*`` options are.
        None steps down from ``bar_label_size`` as bars multiply.

    Returns
    -------
    plotnine.ggplot
        The chart.

    See Also
    --------
    calc_percentage, scale_y_pct, annotate_bands

    Examples
    --------
    >>> plot_bars(calc_percentage(podracing_survey, "demo_gender"))
    >>> plot_bars(calc_percentage(podracing_survey, "fav_driver"))
    >>> plot_bars(calc_percentage(podracing_survey, "demo_edu"), orientation="bars")
    """
    fill = fill or default_fill()
    orientation = match_arg(orientation, ORIENTATIONS)
    sort = match_arg(sort, BAR_SORTS)
    unit = ezrsurvey_default("pct_axis_unit") if unit is None else unit
    max = ezrsurvey_default("pct_axis_max") if max is None else max
    if flip is not None:
        orientation = "bars" if flip else "cols"
    label = detect_label(data, label, value)
    n_items = len(data)
    is_ordinal = is_categorical(data[label]) and bool(data[label].cat.ordered)
    request = {"orientation": orientation, "is_ordinal": is_ordinal, "sort": sort, "wrap": wrap, "label_size": label_size}
    layout = auto_bar_layout(list(as_character(data[label])), n_items, request)
    ordered = bar_order(data, label, value, layout["sort"])
    frame = ordered["data"].copy()
    values = frame[value].tolist()
    wrapped_levels = unique_values([str_wrap(level, layout["wrap"]) for level in ordered["levels"]])
    frame[label] = factor([str_wrap(text, layout["wrap"]) for text in as_character(frame[label])], levels=wrapped_levels).values
    frame["bar_label_"] = label_pct()(values)
    frame["bar_fill_"] = "bar"
    pad = unit * 0.5 if layout["orientation"] == "bars" else 0
    axis_size = max_of(6, 11 - 0.6 * max_of(0, n_items - ezrsurvey_default("bar_cols_max_items")))
    top = max if max is not None else nice_max(values, unit=unit, pad=pad)
    nudge = TEXT_NUDGE_SHARE * top if isinstance(top, (int, float)) and math.isfinite(top) else 0
    chart = (
        ggplot(frame, aes(label, value))
        + geom_col(aes(fill="bar_fill_"), width=consistent_bar_width(n_items))
        + geom_hline(yintercept=0)
        + labs(x="", y="", title=title)
        + scale_y_pct(values=values, unit=unit, pad=pad, max=max, labels=axis_labels)
        + scale_fill_manual(values=[fill])
        + theme_ezrsurvey(transparent=True)
    )
    if layout["orientation"] == "bars":
        chart = chart + theme(axis_text_y=element_text(size=axis_size))
        chart = chart + geom_text(aes(label="bar_label_"), ha="left", nudge_y=nudge, size=layout["size"] * PT) + coord_flip()
    else:
        chart = chart + theme(axis_text_x=element_text(size=axis_size))
        chart = chart + geom_text(aes(label="bar_label_"), va="bottom", nudge_y=nudge, size=layout["size"] * PT)
    if avg_line:
        chart = chart + geom_hline(yintercept=r_mean(values))
    return chart


def max_of(first, second):
    return first if first >= second else second


def feature_averages(frame, feature, value, show_average):
    """Each feature's weighted-mean rating and its label, best-rated first."""
    rows = []
    for group in group_positions(frame, [feature]):
        block = frame.iloc[group["positions"]]
        products = [number * share / 100 for number, share in zip(block["num_"], block[value]) if not is_missing(number) and not is_missing(share)]
        rows.append({feature: group["values"][0], "avg": r_sum(products)})
    averages = pd.DataFrame(rows, columns=[feature, "avg"])
    averages = averages.iloc[order_rows(averages, ["avg"], decreasing=True)].reset_index(drop=True)
    if show_average:
        averages["flabel_"] = [f"{name} - {r_round(avg, 2):.2f}" for name, avg in zip(as_character(averages[feature]), averages["avg"])]
    else:
        averages["flabel_"] = list(as_character(averages[feature]))
    return averages


def segment_label(share, label_min):
    rounded = r_round(share)
    if is_missing(rounded) or rounded <= label_min:
        return ""
    return character_value(rounded) + "%"


def plot_stacked_rating(data, feature=None, level=None, value="pct", palette=None, label_min=1, show_average=True):  # lint-style: ignore FN001,FN003
    """Stacked rating bars with weighted-average ordering.

    Draws a 100%-stacked bar per feature across an ordinal rating scale, labels
    each segment, and orders features by their weighted mean rating (the
    leading digit of each `level` is the weight), so the best-rated feature sits
    at the top. The weighted mean is appended to each feature label when
    ``show_average=True``. Feed it a long table with one row per feature and
    rating level; `plot_rating_grid()` builds one from a block of columns.

    Parameters
    ----------
    data : pandas.DataFrame
        Long data with one row per feature and rating level.
    feature : str
        Feature column.
    level : str
        Rating-level column, e.g. "1 - Very bad" .. "5 - Very good". The
        leading digit is used as the numeric weight.
    value : str
        Percentage column. Default "pct".
    palette : dict, optional
        Fill colours keyed by level label. None (default) derives a red, amber,
        green palette from the level labels themselves.
    label_min : float
        Hide segment labels at or below this percentage. Default 1.
    show_average : bool
        Append the weighted mean to each feature label. Default True.

    Returns
    -------
    plotnine.ggplot
        The chart.

    See Also
    --------
    plot_rating_grid, scale_fill_rating

    Examples
    --------
    >>> long = calc_percentage_batch(podracing_survey, starts_with("ratings_"), digits=2)
    >>> long["answer"] = recode_likert(long["answer"]).astype(str) + " - " + long["answer"]
    >>> plot_stacked_rating(long, "variable", "answer")
    """
    if feature is None or level is None:
        raise ValueError(
            "plot_stacked_rating() needs `feature` and `level`: the columns holding the question and its answer. "
            "It takes one row per question and answer, which plot_rating_grid(data, prefix) builds for you from a "
            "block of rating columns."
        )
    frame = data.reset_index(drop=True).copy()
    frame["num_"] = [first_digit_number(text) for text in as_character(frame[level])]
    averages = feature_averages(frame, feature, value, show_average)
    flabel_levels = list(reversed(unique_values(averages["flabel_"])))
    lookup = dict(zip(as_character(averages[feature]), averages["flabel_"]))
    frame["flabel_"] = factor([lookup.get(name) for name in as_character(frame[feature])], levels=flabel_levels).values
    frame["seg_label_"] = [segment_label(share, label_min) for share in frame[value]]
    if not is_categorical(frame[level]):
        frame[level] = factor(frame[level]).values
    colours = palette if palette is not None else rating_palette(frame[level])
    return (
        ggplot(frame, aes("flabel_", value, fill=level))
        + geom_col()
        + geom_text(aes(label="seg_label_"), position=position_stack(vjust=0.5))
        + scale_y_continuous(labels=label_pct())
        + coord_flip()
        + labs(x="", y="")
        + guides(fill=guide_legend(reverse=True))
        + theme_ezrsurvey(transparent=True)
        + theme(legend_position="top", legend_title=element_blank())
        + scale_fill_manual(values=colours)
    )


def first_digit_number(text):
    if is_missing(text):
        return np.nan
    for character in text:
        if "1" <= character <= "9":
            return int(character)
    return np.nan


def report_rank_clashes(ranks, answers, prefix):
    """Say when two different answers came out on one rank: `levels` is short of a level."""
    seen = []
    for rank, answer in zip(ranks, answers):
        if not is_missing(rank) and (rank, answer) not in seen:
            seen.append((rank, answer))
    counted = []
    clashes = []
    for rank, _ in seen:
        if rank in counted and rank not in clashes:
            clashes.append(rank)
        counted.append(rank)
    for clash in clashes:
        names = [answer for rank, answer in seen if rank == clash]
        message(
            f"plot_rating_grid: {' and '.join(names)} both came out as {clash} on the '{prefix}' scale. "
            "`levels` is missing one of them."
        )


def plot_rating_grid(data=None, prefix=None, levels=None, digits=2, **kwargs):  # lint-style: ignore FN001
    """A stacked rating chart for a whole block of questions.

    The one-line form of `plot_stacked_rating()` for the common case: a block of
    columns sharing a prefix, each asking the same rating question about a
    different feature or brand. Tabulates the block, tidies the question names,
    numbers the answers by their position on the scale and stacks the result.

    A wording that is not on the scale cannot be numbered, so it is reported
    rather than silently dropped into an unlabelled segment, and two different
    answers landing on one rank (which means `levels` is short of a level) are
    reported too. Registering the block once with `register_order()` removes the
    `levels` argument from every later call.

    Parameters
    ----------
    data : pandas.DataFrame, optional
        A data frame. If omitted, the session default is used.
    prefix : str
        The block's shared column prefix, e.g. "ratings_". It is stripped from
        the feature labels.
    levels : list of str, optional
        The scale's answer wordings, worst first. None (default) looks the block
        up in the order registry, falling back to the five-point default of
        `recode_likert()`.
    digits : int
        Decimal places kept in the underlying percentages. Default 2.
    **kwargs
        Passed to `plot_stacked_rating()` (``palette``, ``label_min``,
        ``show_average``).

    Returns
    -------
    plotnine.ggplot
        The chart.

    See Also
    --------
    plot_stacked_rating, calc_percentage_batch, register_order

    Examples
    --------
    >>> plot_rating_grid(podracing_survey, "ratings_")
    >>> plot_rating_grid(podracing_survey, "partner_likeability_",
    ...                  levels=["Very unlikeable", "Unlikeable", "Likeable", "Very likeable"])
    """
    resolved = resolve_data_columns(data, [prefix])
    data = resolved["data"]
    prefix = resolved["columns"][0]
    columns = [str(name) for name in data.columns if str(name).startswith(prefix)]
    if not columns:
        raise ValueError(f"No columns start with '{prefix}'.")
    if levels is None:
        levels = order_for(columns[0]) or LIKERT_LEVELS
    table = calc_percentage_batch(data, all_of(columns), digits=digits, prefix=prefix)
    ranks = recode_likert(table["answer"], levels=levels).tolist()
    unknown = unique_values([answer for answer, rank in zip(table["answer"], ranks) if is_missing(rank)])
    if unknown:
        message(
            f"plot_rating_grid: {len(unknown)} answer(s) are not on the '{prefix}' scale and cannot be ranked: "
            f"{', '.join(unknown)}. Check `levels` against the data."
        )
    report_rank_clashes(ranks, table["answer"].tolist(), prefix)
    table["answer"] = [f"{'NA' if is_missing(rank) else rank} - {answer}" for rank, answer in zip(ranks, table["answer"])]
    return plot_stacked_rating(table, "variable", "answer", **kwargs)


def gauge_frame(bands):
    frame = pd.DataFrame({"xmin": bands["from"], "xmax": bands["to"], "label": bands["label"], "colour": bands["colour"]})
    frame["xmid"] = (frame["xmin"] + frame["xmax"]) / 2
    return frame


def plot_nps_gauge(score, scale="nps", title=None, height=GAUGE_HEIGHT, label_size=None):
    """Score gauge with decision bands and a value marker.

    A horizontal gauge that places a single score (NPS or mean rating) onto a
    banded scale with a black "you are here" marker, for the headline "where do
    we stand" slide. "nps" uses a -100..100 scale banded from needs-work to
    excellent; "rating" uses a 1..5 scale with BAD/OK/GOOD bands. Pair it with
    `calc_nps()` for the score.

    Parameters
    ----------
    score : float
        The score to mark (NPS on -100..100, or a mean rating on 1..5).
    scale : str
        "nps" (default) or "rating".
    title : str, optional
        Title; a sensible default is generated from `score`.
    height : float
        Bar thickness in plot units. Default 0.5.
    label_size : float, optional
        Band-label size in points. None (default) matches the theme's base font
        size (11 pt).

    Returns
    -------
    plotnine.ggplot
        The chart.

    See Also
    --------
    calc_nps, plot_nps, plot_gauges

    Examples
    --------
    >>> plot_nps_gauge(calc_nps(podracing_survey, "nps_value")["nps"].iloc[0])
    >>> plot_nps_gauge(3.8, scale="rating")
    """
    scale = match_arg(scale, GAUGE_SCALES)
    label_size = BASE_TEXT if label_size is None else label_size
    if scale == "nps":
        bands = bands_nps_score()
        limits = (-100, 100)
        default_title = f"Net Promoter Score of: {character_value(r_round(score))}"
    else:
        bands = bands_rating_3()
        limits = (1, 5)
        default_title = f"Quality rating of: {character_value(r_round(score, 2))}"
    frame = gauge_frame(bands)
    marker = pd.DataFrame({"score": [score], "bottom": [0], "top": [height]})
    return (
        ggplot(frame)
        + geom_rect(aes(xmin="xmin", xmax="xmax", ymin=0, ymax=height, fill="label"))
        + geom_text(aes(x="xmid", y=height / 2, label="label"), color="white", fontweight="bold", size=label_size)
        + geom_segment(aes(x="score", xend="score", y="bottom", yend="top"), data=marker, color="black", size=1.2 * PT * 0.75, inherit_aes=False)
        + scale_fill_manual(values=dict(zip(bands["label"], bands["colour"])))
        + scale_x_continuous(limits=limits)
        + scale_y_continuous(limits=(0, height))
        + labs(title=title or default_title, x="", y="")
        + theme_ezrsurvey(transparent=True)
        + theme(axis_text_y=element_blank())
    )


def nps_score_text(score):
    return f"{int(r_round(score)):+d}"


def rating_score_text(score):
    return f"{score:.2f} / 5"


def gauge_scale(scale):
    """Band layout, axis limits and score format for one gauge scale."""
    if scale == "nps":
        return {"bands": bands_nps_score(), "lo": -100, "hi": 100, "fmt": nps_score_text}
    return {"bands": bands_rating_3(), "lo": 1, "hi": 5, "fmt": rating_score_text}


def infer_gauge_scale(score):
    if not math.isfinite(score) or score < 1 or score > 5:
        return "nps"
    return "rating"


def norm_gauge(value, scale):
    return (value - scale["lo"]) / (scale["hi"] - scale["lo"])


def band_fits(width, label):
    """Whether a band has room for its name, estimated from its character count on a 6-inch panel."""
    return width > len(label) * CHAR_WIDTH_SHARE


def format_edges(values):
    """Numbers formatted to a common number of decimals, as R's format() prints a vector."""
    texts = [character_value(float(value)) for value in values]
    decimals = max(len(text.split(".")[1]) if "." in text else 0 for text in texts)
    return [f"{float(value):.{decimals}f}" for value in values]


def gauge_rows(score, scale, centre, height):
    """The bands, ticks and marker of one gauge, drawn around the row at `centre`."""
    bands = scale["bands"]
    rects = []
    for start, end, colour, label in zip(bands["from"], bands["to"], bands["colour"], bands["label"]):
        xmin = max(0, norm_gauge(start, scale))
        xmax = min(1, norm_gauge(end, scale))
        rects.append(
            {
                "xmin": xmin,
                "xmax": xmax,
                "xmid": (xmin + xmax) / 2,
                "ymin": centre - height / 2,
                "ymax": centre + height / 2,
                "colour": colour,
                "label": label,
                "wide": band_fits(xmax - xmin, label),
            }
        )
    edges = sorted(set(bands["from"]) | set(bands["to"]))
    ticks = []
    for edge, text in zip(edges, format_edges(edges)):
        ticks.append({"x": norm_gauge(edge, scale), "y": centre - height / 2 - 0.09, "label": text})
    position = min(1, max(0, norm_gauge(score, scale)))
    marker = {"x": position, "ymin": centre - height / 2 - 0.06, "ymax": centre + height / 2 + 0.06}
    return {"rects": rects, "ticks": ticks, "marker": marker}


def gauge_layout(scores, scales, height):
    """Geometry for every gauge row: bands, marker, break numbers and the label beside it.

    Args:
        scores: The scores, keyed by gauge label; the first is drawn on top.
        scales: "nps" or "rating" for each score.
        height: Bar thickness.

    Returns:
        A dict with ``rects``, ``markers`` and ``ticks`` data frames, and the
        ``ybreaks`` and ``ylabels`` of the rows.
    """
    rects = []
    markers = []
    ticks = []
    ybreaks = []
    ylabels = []
    names = list(scores.keys())
    for i, name in enumerate(names):
        centre = len(names) - i
        scale = gauge_scale(scales[i])
        rows = gauge_rows(scores[name], scale, centre, height)
        rects.extend(rows["rects"])
        ticks.extend(rows["ticks"])
        markers.append(rows["marker"])
        ybreaks.append(centre)
        ylabels.append(f"{name}\n{scale['fmt'](scores[name])}")
    return {
        "rects": pd.DataFrame(rects),
        "markers": pd.DataFrame(markers),
        "ticks": pd.DataFrame(ticks),
        "ybreaks": ybreaks,
        "ylabels": ylabels,
    }


def as_score_dict(scores):
    if isinstance(scores, pd.Series):
        scores = scores.to_dict()
    valid = isinstance(scores, dict) and scores and all(isinstance(name, str) and name for name in scores)
    if not valid or not all(isinstance(value, (int, float, np.number)) for value in scores.values()):
        raise ValueError("`scores` must be a named numeric vector (a dict); the names label the gauges.")
    return {name: float(value) for name, value in scores.items()}


def plot_gauges(scores, scales=None, title=None, height=GAUGE_HEIGHT, label_size=None):  # lint-style: ignore FN001
    """Stacked score gauges (NPS over average quality, etc.).

    Draws two or more scores as thin banded gauge bars stacked one above
    another, each on its own scale with a "you are here" marker: the headline
    summary slide, with the Net Promoter Score on top and the average quality
    rating below it. Each gauge is normalised to its own scale, so an NPS of +23
    and a rating of 3.4 line up on a shared panel with the band boundaries drawn
    where each scale puts them. Each bar carries its own band boundaries as small
    numbers underneath, and a band too narrow to hold its name is left
    unlabelled rather than having the text run over its neighbours.

    Parameters
    ----------
    scores : dict or pandas.Series
        Scores keyed by gauge label; the first is drawn at the top.
    scales : str or list of str, optional
        "nps" (a -100..100 scale) or "rating" (a 1..5 scale) per gauge, one
        value recycled or one per score. None (default) infers "rating" for a
        value in 1..5 and "nps" otherwise.
    title : str, optional
        Title. None (default) draws none.
    height : float
        Bar thickness in plot units (row spacing is 1). Default 0.5.
    label_size : float, optional
        Band-label size in points. None (default) is a compact 10 pt.

    Returns
    -------
    plotnine.ggplot
        The chart.

    See Also
    --------
    plot_nps_gauge, calc_nps, ipm_model

    Examples
    --------
    >>> nps = calc_nps(podracing_survey, "nps_value")["nps"].iloc[0]
    >>> plot_gauges({"Net Promoter Score": nps, "Average quality rating": 3.4})
    """
    scores = as_score_dict(scores)
    if scales is None:
        scales = [infer_gauge_scale(value) for value in scores.values()]
    else:
        scales = [scales] if isinstance(scales, str) else list(scales)
        scales = [scales[i % len(scales)] for i in range(len(scores))]
    label_size = GAUGE_TEXT if label_size is None else label_size
    layout = gauge_layout(scores, scales, height)
    rects = layout["rects"]
    return (
        ggplot()
        + geom_rect(aes(xmin="xmin", xmax="xmax", ymin="ymin", ymax="ymax", fill="colour"), data=rects)
        + geom_text(aes(x="xmid", y="(ymin + ymax) / 2", label="label"), data=rects[rects["wide"]], color="white", fontweight="bold", size=label_size)
        + geom_text(aes(x="x", y="y", label="label"), data=layout["ticks"], color="#595959", size=TICK_TEXT, va="top")
        + geom_segment(aes(x="x", xend="x", y="ymin", yend="ymax"), data=layout["markers"], color="black", size=1.2 * PT * 0.75)
        + scale_fill_identity()
        + scale_x_continuous(limits=(-0.05, 1.05), expand=(0, 0))
        + scale_y_continuous(
            breaks=layout["ybreaks"],
            labels=layout["ylabels"],
            limits=(min(layout["ybreaks"]) - height, max(layout["ybreaks"]) + height),
        )
        + labs(title=title, x="", y="")
        + theme_ezrsurvey(transparent=True)
        + theme(axis_text_x=element_blank(), axis_text_y=element_text(weight="bold", ha="right"), panel_grid=element_blank())
    )


def nps_distribution(values):
    """Counts and shares of each 0-10 answer, with its NPS group."""
    total = len(values)
    counts = [0] * 11
    for value in values:
        counts[int(r_round(value))] += 1
    table = pd.DataFrame({"nps_value": list(range(11)), "n": counts})
    table["pct"] = [r_round(n / total * 100) for n in counts]
    table["group"] = nps_group(table["nps_value"]).astype(str).tolist()
    return table


def plot_nps(data=None, value=None, title=None):
    """NPS distribution slide (0-10 scale with group labels).

    The canonical Net Promoter Score chart: the full 0-10 recommendation
    distribution as labelled bars coloured by NPS group, with the detractor /
    passive / promoter shares called out across the top and the overall NPS in
    the title. Unlike `plot_nps_gauge()` (which takes a single score), this reads
    the raw 0-10 column; it is the detailed companion slide to the gauge.

    Parameters
    ----------
    data : pandas.DataFrame, optional
        A data frame. If omitted, the session default is used.
    value : str
        The 0-10 recommendation column. Text such as "8 - likely" is salvaged
        with `ensure_numeric()`.
    title : str, optional
        Title; defaults to "Net Promoter Score of: <score>".

    Returns
    -------
    plotnine.ggplot
        The chart.

    See Also
    --------
    calc_nps, plot_nps_gauge

    Examples
    --------
    >>> plot_nps(podracing_survey, "nps_value")
    """
    resolved = resolve_data_columns(data, [value])
    data = resolved["data"]
    col_name = col_label(resolved["columns"][0], data, argument="value")
    numbers = [number for number in ensure_numeric(data[col_name], quiet=True) if not is_missing(number) and 0 <= number <= 10]
    if not numbers:
        raise ValueError(f"No valid 0-10 values in '{col_name}'.")
    table = nps_distribution(numbers)
    score = r_round(r_mean(nps_group(numbers).astype(float)) * 100)
    shares = {group: r_sum(table.loc[table["group"] == group, "pct"]) for group in ("-1", "0", "1")}
    top = nice_max(table["pct"], unit=5) + 12
    table["score_"] = factor([str(value) for value in table["nps_value"]], levels=[str(value) for value in range(11)]).values
    table["bar_label_"] = [f"{character_value(pct)}%" for pct in table["pct"]]
    callout = {"fontweight": "bold", "size": GAUGE_TEXT, "va": "top", "lineheight": 0.9}
    return (
        ggplot(table, aes("score_", "pct", fill="group"))
        + geom_col(width=consistent_bar_width(len(table)))
        + geom_text(aes(label="bar_label_"), va="bottom", nudge_y=TEXT_NUDGE_SHARE * top)
        + geom_hline(yintercept=0)
        + annotate("text", x=4, y=top, label=f"{character_value(shares['-1'])}% DETRACTOR\nNot likely", color=pal_nps["-1"], **callout)
        + annotate("text", x=8.5, y=top, label=f"{character_value(shares['0'])}% PASSIVE\nSomewhat likely", color=pal_nps["0"], **callout)
        + annotate("text", x=10.5, y=top, label=f"{character_value(shares['1'])}% PROMOTER\nVery likely", color=pal_nps["1"], **callout)
        + scale_y_continuous(limits=(0, top), labels=blank_labels)
        + scale_fill_manual(values=pal_nps)
        + labs(title=title or f"Net Promoter Score of: {character_value(score)}", x="", y="")
        + theme_ezrsurvey_y(transparent=True)
    )


def ipm_labels(repel):
    if repel:
        try:
            import adjustText  # noqa: F401
        except ImportError:
            repel = False
    if repel:
        return geom_text(aes(label="feature"), size=IPM_LABEL_SIZE * PT, adjust_text={"arrowprops": {"arrowstyle": "-"}})
    return geom_text(aes(label="feature"), va="bottom", size=IPM_LABEL_SIZE * PT)


def plot_ipm(model, title=None, repel=True, bands=None):  # lint-style: ignore FN001
    """Importance / performance matrix.

    Plots an `ipm_model()` table as a scatter of feature performance (x)
    against importance (y), with decision bands across the top. Each point takes
    the colour of the decision band it falls in, so a feature averaging 2.4 is
    red because it sits in the BAD band: the point and the band behind it can
    never disagree. Read it by quadrant: high-importance, low-performance
    features (upper left) are the priorities to fix, while high-importance,
    high-performance features (upper right) are strengths to protect. The
    performance axis runs over the scale the bands describe; a point outside it
    is reported, and `rescale_bands()` moves the bands onto the scale the answers
    were collected on. Uses adjustText (the ``repel`` extra) for
    non-overlapping labels when it is installed.

    Parameters
    ----------
    model : pandas.DataFrame
        An `ipm_model()` output (``feature``, ``importance``, ``performance``,
        ``perf_class``).
    title : str, optional
        Title; defaults to the average performance.
    repel : bool
        Keep labels from overlapping when adjustText is installed. Default True.
    bands : pandas.DataFrame, optional
        Decision bands drawn across the top and used to colour the points.
        Default `bands_rating_3()` (BAD 1-3, OK 3-4, GOOD 4-5).

    Returns
    -------
    plotnine.ggplot
        The chart.

    See Also
    --------
    ipm_model, compare_values, rescale_bands

    Examples
    --------
    >>> plot_ipm(ipm_model(podracing_survey, "nps_value", "ratings_"))
    """
    bands = bands_rating_3() if bands is None else bands
    top = nice_max([value + 1 for value in model["importance"]], unit=5)
    average = r_round(r_mean(model["performance"]), 2)
    if title is None:
        title = f"Average performance of: {character_value(average)} ({band_label([average], bands)[0].lower()})"
    frame = model.copy()
    frame["band_"] = band_colour(frame["performance"].tolist(), bands)
    edges = list(bands["from"]) + list(bands["to"])
    span = (min(edges), max(edges))
    outside = [feature for feature, value in zip(frame["feature"], frame["performance"]) if not is_missing(value) and (value < span[0] or value > span[1])]
    if outside:
        message(
            f"plot_ipm: {', '.join(outside)} fall outside the {character_value(span[0])} to {character_value(span[1])} "
            "performance scale these bands describe, so they are not drawn. rescale_bands() moves the bands onto "
            "the scale the answers were collected on."
        )
    chart = (
        ggplot(frame, aes("performance", "importance"))
        + geom_point(aes(color="band_"), size=IPM_POINT_SIZE, shape="s")
        + geom_vline(xintercept=r_mean(frame["performance"]))
        + labs(title=title, x="\nperformance", y="importance\n")
        + scale_colour_identity()
        + scale_y_continuous(limits=(0, top), labels=PercentLabels(0, "%"))
        + scale_x_continuous(limits=span)
        + theme_ezrsurvey_xy(transparent=True)
        + ipm_labels(repel)
    )
    return annotate_bands(chart, bands, axis="x", at=top, label_offset=top * 0.04)


def fitted_text(text, width, height):
    """The wrap and font size at which a quote fills its tile without overflowing it."""
    best = {"text": text, "size": 1.0}
    for columns in range(4, max(5, len(text)) + 1):
        wrapped = str_wrap(text, columns)
        lines = wrapped.split("\n")
        longest = max(len(line) for line in lines)
        by_width = width * 72 / (0.55 * longest)
        by_height = height * 72 / (1.2 * len(lines))
        size = min(by_width, by_height, QUOTE_MAX_SIZE)
        if size > best["size"]:
            best = {"text": wrapped, "size": size}
    return best


def quote_tiles(data, label, area):
    """Squarified treemap tiles for the quotes, largest first, as treemapify lays them out."""
    try:
        import squarify
    except ImportError:
        raise ValueError(
            "Package 'squarify' is required for plot_quotes_tree(). Install it with pip install squarify."
        ) from None
    frame = data.reset_index(drop=True)
    order = sorted(range(len(frame)), key=lambda row: -float(frame[area].iloc[row]))
    frame = frame.iloc[order].reset_index(drop=True)
    sizes = squarify.normalize_sizes([float(value) for value in frame[area]], QUOTE_WIDTH_INCHES, QUOTE_HEIGHT_INCHES)
    tiles = squarify.squarify(sizes, 0, 0, QUOTE_WIDTH_INCHES, QUOTE_HEIGHT_INCHES)
    rows = []
    for tile, text in zip(tiles, as_character(frame[label])):
        width = tile["dx"] - 2 * QUOTE_PADDING_INCHES
        height = tile["dy"] - 2 * QUOTE_PADDING_INCHES
        fitted = fitted_text(text, max(width, 0.1), max(height, 0.1))
        rows.append(
            {
                "xmin": tile["x"],
                "xmax": tile["x"] + tile["dx"],
                "ymin": tile["y"],
                "ymax": tile["y"] + tile["dy"],
                "xmid": tile["x"] + tile["dx"] / 2,
                "ymid": tile["y"] + tile["dy"] / 2,
                "text": fitted["text"],
                "size": fitted["size"],
            }
        )
    return pd.DataFrame(rows)


def plot_quotes_tree(data, label="comment", area="length", colour="black"):
    """Treemap of selected quotes.

    Lays selected verbatims out as a treemap, each tile a comment sized by its
    length, so a slide can show real customer voice at a glance. Each quote is
    wrapped and sized to fill its tile. Pair it with `sample_comments()` or
    `sample_comments_diverse()`, which produce the ``comment`` / ``length``
    columns it expects. Needs the ``quotes`` extra (squarify).

    Parameters
    ----------
    data : pandas.DataFrame
        Quotes, e.g. from `sample_comments()`.
    label : str
        Text column. Default "comment".
    area : str
        Tile-size column. Default "length".
    colour : str
        Tile border colour. Default "black".

    Returns
    -------
    plotnine.ggplot
        The chart.

    See Also
    --------
    sample_comments, sample_comments_diverse

    Examples
    --------
    >>> plot_quotes_tree(sample_comments(podracing_survey, "nps_com", "show_com", n=5))
    """
    for column in (label, area):
        if column not in data.columns:
            raise ValueError(
                f"plot_quotes_tree() needs a `{column}` column, and the data has none. It expects what "
                "sample_comments() returns, which carries `comment` and `length`; name your own columns with "
                "`label=` and `area=`."
            )
    tiles = quote_tiles(data, label, area)
    return (
        ggplot(tiles)
        + geom_rect(aes(xmin="xmin", xmax="xmax", ymin="ymin", ymax="ymax"), fill="none", color=colour)
        + geom_text(aes(x="xmid", y="ymid", label="text", size="size"), color="black")
        + scale_size_identity()
        + scale_x_continuous(expand=(0, 0))
        + scale_y_continuous(expand=(0, 0))
        + labs(x="", y="")
        + theme_ezrsurvey(transparent=True)
        + theme(axis_text=element_blank())
    )
