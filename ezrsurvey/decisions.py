"""Draw decision bands (BAD / OK / GOOD) and single-value markers onto charts, with ready-made band presets. They turn a chart into a decision aid."""

import copy
import math

import pandas as pd
from plotnine import annotate, geom_hline, geom_vline

from .palettes import pal_nps, pal_rating, pal_rating5
from .rbase import match_arg
from .theme import PT

AXES = ["x", "y"]
BAND_TEXT_SIZE = 11
LABEL_OFFSET_SHARE = 0.04


def build_plot(plot):
    """A built copy of a plotnine chart, whose layout and layer data can be read; None if it fails."""
    built = copy.deepcopy(plot)
    try:
        built._build()
    except Exception:
        return None
    return built


def normalize_bands(bands):
    """A band spec as a data frame with from, to, label and colour columns."""
    frame = pd.DataFrame(bands).reset_index(drop=True)
    if not {"from", "to", "label"}.issubset(frame.columns):
        raise ValueError("`bands` must have columns `from`, `to` and `label`.")
    if "colour" not in frame.columns:
        frame["colour"] = frame["color"] if "color" in frame.columns else "black"
    return frame


def infer_panel_range(plot, axis):
    """The drawn range of the axis opposite `axis`, read by building the plot; None if it cannot be built."""
    built = build_plot(plot)
    if built is None:
        return None
    panel = built.layout.panel_params[0]
    opposite = panel.y if axis == "x" else panel.x
    return list(opposite.range)


def band_layers(band, axis, at, label_offset, style):
    """The marker line and label for one band."""
    centre = (band["from"] + band["to"]) / 2
    colour = style["text_colour"] or band["colour"]
    if axis == "x":
        line = annotate("rect", xmin=band["from"], xmax=band["to"], ymin=at, ymax=at, fill="none", color=band["colour"], size=style["linewidth"])
        label = annotate("text", x=centre, y=at - label_offset, label=band["label"], color=colour, size=style["text_size"], fontweight="bold", va="top", lineheight=0.9)
    else:
        line = annotate("rect", ymin=band["from"], ymax=band["to"], xmin=at, xmax=at, fill="none", color=band["colour"], size=style["linewidth"])
        label = annotate("text", y=centre, x=at - label_offset, label=band["label"], color=colour, size=style["text_size"], fontweight="bold", ha="right", lineheight=0.9)
    return {"line": line, "label": label}


def annotate_bands(plot, bands, axis="x", at=None, label_offset=None, labels=True, text_colour=None, text_size=None, linewidth=1):  # lint-style: ignore FN001,FN003
    """Annotate a plot with labelled decision bands.

    Adds the BAD / OK / GOOD style decision markers survey charts carry: for
    each band a thin coloured marker line runs along one axis, with a bold
    centred label, so a reader instantly sees where "good" and "bad" lie.
    Supply a band spec (a data frame with ``from``, ``to``, ``label`` and
    optional ``colour``, or one of the `bands_rating_3()` presets), the `axis`
    the bands run along, and `at`: the position on the opposite axis for the
    marker line (usually the top of the panel; inferred from the plot when
    omitted).

    Parameters
    ----------
    plot : plotnine.ggplot
        A chart.
    bands : pandas.DataFrame or dict
        A band specification.
    axis : str
        Which axis the bands run along: "x" (default) or "y".
    at : float, optional
        Position on the *opposite* axis at which to draw the marker line and
        labels. If None, the top of the plot's panel range.
    label_offset : float, optional
        Distance to nudge labels away from the marker line, in data units of the
        opposite axis. None (default) is 4% of the opposite axis range.
    labels : bool
        Whether to draw the band labels. Default True.
    text_colour : str, optional
        Label colour; None (default) uses each band's own colour.
    text_size : float, optional
        Label size in points; None (default) matches the theme's base font size
        (11 pt).
    linewidth : float
        Marker line width. Default 1.

    Returns
    -------
    plotnine.ggplot
        The chart with the band layers added.

    See Also
    --------
    mark_value, bands_rating_3

    Examples
    --------
    >>> model = ipm_model(podracing_survey, "nps_value", "ratings_")
    >>> annotate_bands(plot_ipm(model), bands_rating_3(), axis="x")
    """
    axis = match_arg(axis, AXES)
    bands = normalize_bands(bands)
    if at is None or label_offset is None:
        panel_range = infer_panel_range(plot, axis)
        if panel_range is None:
            raise ValueError("Could not read the plot's panel range; please supply `at` (and `label_offset`) explicitly.")
        if at is None:
            at = max(panel_range)
        if label_offset is None:
            label_offset = LABEL_OFFSET_SHARE * (max(panel_range) - min(panel_range))
    style = {
        "text_colour": text_colour,
        "text_size": BAND_TEXT_SIZE if text_size is None else text_size,
        "linewidth": linewidth * PT * 0.75,
    }
    out = plot
    for band in bands.to_dict("records"):
        layers = band_layers(band, axis, at, label_offset, style)
        out = out + layers["line"]
        if labels:
            out = out + layers["label"]
    return out


def mark_value(plot, value, axis="x", colour="black", linewidth=1, label=None, **kwargs):  # lint-style: ignore FN003
    """Mark a single value on a plot.

    Adds a reference line (and optional label) at a single value: the "you are
    here" marker used on the NPS and quality gauges. The label is justified into
    the panel next to the marker line, so it is not clipped at the edge.

    Parameters
    ----------
    plot : plotnine.ggplot
        A chart.
    value : float
        Position of the marker.
    axis : str
        Axis the value is on: "x" (default, a vertical line) or "y" (a
        horizontal line).
    colour, linewidth
        Line appearance.
    label : str, optional
        Text drawn at the marker.
    **kwargs
        Passed to plotnine's ``annotate()`` for the label, overriding the
        default placement.

    Returns
    -------
    plotnine.ggplot
        The chart with the marker added.

    See Also
    --------
    annotate_bands

    Examples
    --------
    >>> p = plot_bars(calc_percentage(podracing_survey, "demo_gender"))
    >>> mark_value(p, 20, axis="y", label="Target 20%")
    """
    axis = match_arg(axis, AXES)
    size = linewidth * PT * 0.75
    if axis == "x":
        out = plot + geom_vline(xintercept=value, color=colour, size=size)
    else:
        out = plot + geom_hline(yintercept=value, color=colour, size=size)
    if label is None:
        return out
    placement = {
        "x": value if axis == "x" else math.inf,
        "y": math.inf if axis == "x" else value,
        "label": label,
        "fontweight": "bold",
        "ha": "left" if axis == "x" else "right",
        "va": "top" if axis == "x" else "bottom",
    }
    placement.update(kwargs)
    return out + annotate("text", **placement)


def band_index(values, bands):
    """Which band each value falls in (0-based), clamped to the first and last band."""
    starts = list(bands["from"])
    out = []
    for value in values:
        index = 0
        for i, start in enumerate(starts):
            if not math.isnan(value) and value >= start:
                index = i
        out.append(index)
    return out


def band_colour(values, bands):
    colours = list(bands["colour"])
    return [colours[i] for i in band_index(values, bands)]


def band_label(values, bands):
    labels = list(bands["label"])
    return [labels[i] for i in band_index(values, bands)]


def clip_bands(bands, lower=None, upper=None):
    """Keep only the part of a band set the chart's axis actually shows."""
    clipped = bands.copy()
    if lower is not None:
        clipped = clipped[clipped["to"] > lower].copy()
        clipped["from"] = [max(start, lower) for start in clipped["from"]]
    if upper is not None:
        clipped = clipped[clipped["from"] < upper].copy()
        clipped["to"] = [min(end, upper) for end in clipped["to"]]
    return clipped.reset_index(drop=True)


def band_frame(labels, starts, ends, colours):
    return pd.DataFrame({"label": labels, "from": [float(v) for v in starts], "to": [float(v) for v in ends], "colour": colours})


def bands_rating_3(from_=None, to=None):
    """Built-in decision-band presets.

    Ready-made band specifications for `annotate_bands()`:

    - `bands_rating_3()`: BAD / OK / GOOD over a 1-5 rating axis.
    - `bands_rating_5()`: per-point labels (1 Very bad .. 5 Very good) over 1-5.
    - `bands_nps()`: Detractor / Passive / Promoter over a 0-10 answer axis.
    - `bands_nps_score()`: Needs work / Good / Great / Excellent over a -100..100
      Net Promoter Score axis (the scale a headline NPS sits on, not the 0-10
      answers it is computed from).

    Pass `from_` / `to` when the chart's panel is narrower than the full scale:
    a band reaching past them is trimmed and a band entirely outside them is
    dropped. R names the first argument ``from``, a Python keyword.

    Parameters
    ----------
    from_, to : float, optional
        Axis limits to clip the bands to.

    Returns
    -------
    pandas.DataFrame
        ``label``, ``from``, ``to`` and ``colour``.

    See Also
    --------
    annotate_bands, rescale_bands

    Examples
    --------
    >>> bands_rating_3()
    >>> bands_rating_3(from_=2)
    >>> bands_nps_score()
    """
    bands = band_frame(["BAD", "OK", "GOOD"], [1, 3, 4], [3, 4, 5], ["#FF3300", "#FFCB3E", "#86A33B"])
    return clip_bands(bands, from_, to)


def bands_rating_5(from_=None, to=None):
    """Per-point bands over a 1-5 rating axis. See `bands_rating_3()`.

    Parameters
    ----------
    from_, to : float, optional
        Axis limits to clip the bands to.

    Returns
    -------
    pandas.DataFrame
        ``label``, ``from``, ``to`` and ``colour``.

    See Also
    --------
    bands_rating_3

    Examples
    --------
    >>> bands_rating_5()
    """
    labels = ["1\nVery bad", "2", "3\nOk", "4", "5\nVery good"]
    bands = band_frame(labels, [0.5, 1.5, 2.5, 3.5, 4.5], [1.5, 2.5, 3.5, 4.5, 5.5], list(pal_rating5.values()))
    return clip_bands(bands, from_, to)


def bands_nps(from_=None, to=None):
    """Detractor / Passive / Promoter bands over the 0-10 answer axis. See `bands_rating_3()`.

    Parameters
    ----------
    from_, to : float, optional
        Axis limits to clip the bands to.

    Returns
    -------
    pandas.DataFrame
        ``label``, ``from``, ``to`` and ``colour``.

    See Also
    --------
    bands_rating_3

    Examples
    --------
    >>> bands_nps()
    """
    bands = band_frame(["DETRACTOR", "PASSIVE", "PROMOTER"], [-0.5, 6.5, 8.5], [6.5, 8.5, 10.5], list(pal_nps.values()))
    return clip_bands(bands, from_, to)


def bands_nps_score(from_=None, to=None):
    """Needs work / Good / Great / Excellent bands over the -100..100 score axis. See `bands_rating_3()`.

    Parameters
    ----------
    from_, to : float, optional
        Axis limits to clip the bands to.

    Returns
    -------
    pandas.DataFrame
        ``label``, ``from``, ``to`` and ``colour``.

    See Also
    --------
    bands_rating_3

    Examples
    --------
    >>> bands_nps_score()
    """
    colours = [pal_rating["1"], pal_rating["3"], pal_rating["4"], pal_rating["5"]]
    bands = band_frame(["NEEDS WORK", "GOOD", "GREAT", "EXCELLENT"], [-100, 0, 30, 70], [0, 30, 70, 100], colours)
    return clip_bands(bands, from_, to)


def two_numbers(value):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return False
    return all(isinstance(number, (int, float)) and not math.isnan(number) for number in value)


def rescale_bands(bands, to, from_=None):
    """Move a band specification onto another scale.

    The band presets are written on the scales survey work uses most: 1-5 for a
    rating, 0-10 for the Net Promoter answer, -100 to 100 for the score. Plenty
    of real questionnaires do not use those. `rescale_bands()` stretches a band
    specification onto the scale the chart is actually drawn on, so the
    thresholds stay where they are instead of the data being divided to meet
    them. The mapping is linear and proportional: a band covering the top fifth
    of its own scale covers the top fifth of the new one. Labels and colours are
    untouched.

    Parameters
    ----------
    bands : pandas.DataFrame
        A band specification: one of the presets, or any data frame with
        ``from`` and ``to`` columns.
    to : list of float
        The scale the chart uses, as ``[min, max]``.
    from_ : list of float, optional
        The scale `bands` is written on. Read from the band edges when omitted,
        which is what you want for the presets. R names it ``from``.

    Returns
    -------
    pandas.DataFrame
        `bands` with ``from`` and ``to`` moved onto the new scale.

    See Also
    --------
    bands_rating_3, annotate_bands

    Examples
    --------
    >>> bands_rating_3().pipe(rescale_bands, to=[0, 100])
    >>> bands_rating_3().pipe(rescale_bands, to=[1, 7])
    """
    moved = normalize_bands(bands)
    if not two_numbers(to):
        raise ValueError("`to` must be two numbers, the low and high end of the scale the chart uses, such as `[0, 100]`.")
    if from_ is None:
        edges = list(moved["from"]) + list(moved["to"])
        from_ = [min(edges), max(edges)]
    if not two_numbers(from_):
        raise ValueError("`from_` must be two numbers, the low and high end of the scale the bands are written on.")
    if max(from_) - min(from_) == 0:
        raise ValueError("The bands cover no range, so there is nothing to rescale from.")
    stretch = (to[1] - to[0]) / (from_[1] - from_[0])
    moved["from"] = [to[0] + (value - from_[0]) * stretch for value in moved["from"]]
    moved["to"] = [to[0] + (value - from_[0]) * stretch for value in moved["to"]]
    return moved
