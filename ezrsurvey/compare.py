"""Compare a metric between two waves or events, and chart what improved and what slipped. The comparison table feeds straight into the diverging bar chart."""

import math

import pandas as pd
from plotnine import (
    aes,
    coord_flip,
    geom_col,
    geom_hline,
    geom_text,
    ggplot,
    labs,
    scale_fill_manual,
    scale_y_continuous,
)

from .rbase import character_value, factor, r_round, unique_values
from .tables import order_rows
from .theme import theme_ezrsurvey

POSITIVE_COLOUR = "#A7C23D"
NEGATIVE_COLOUR = "#FFCB3E"


def compare_values(current, previous, by="feature", value="performance"):
    """Compare a metric between two datasets (e.g. two events or waves).

    Joins a `current` and a `previous` table on a key column and computes the
    difference of a metric: for example feature ``performance`` from two
    `ipm_model()` outputs, or ``pct`` from two `calc_percentage()` tables for two
    events. The result feeds straight into `plot_diff()`.

    The join is a left join keyed on `by` with `previous` on the left, so the
    row set follows the previous period and ``difference`` is
    ``current - previous`` (a positive number means it went up). Keys present
    only in `current` are dropped; keys missing from `current` get a missing
    difference.

    Parameters
    ----------
    current, previous : pandas.DataFrame
        Tables sharing a key column and a metric column.
    by : str
        Name of the key column to join on. Default "feature".
    value : str
        Name of the metric column to compare. Default "performance".

    Returns
    -------
    pandas.DataFrame
        The key column, ``previous``, ``current`` and ``difference``
        (``current - previous``).

    See Also
    --------
    plot_diff, ipm_model, calc_percentage

    Examples
    --------
    >>> a = pd.DataFrame({"feature": ["price", "quality"], "performance": [3.1, 4.2]})
    >>> b = pd.DataFrame({"feature": ["price", "quality"], "performance": [2.8, 4.4]})
    >>> compare_values(current=b, previous=a)
    """
    for table in (current, previous):
        if by not in table.columns or value not in table.columns:
            raise ValueError(f"Both `current` and `previous` need columns '{by}' and '{value}'.")
    now = current[[by, value]].rename(columns={value: "current"})
    before = previous[[by, value]].rename(columns={value: "previous"})
    out = pd.merge(before, now, on=by, how="left", sort=False)
    out["difference"] = out["current"] - out["previous"]
    return out.reset_index(drop=True)


def signed_label(value, digits):
    rounded = r_round(value, digits)
    if value > 0:
        return "+" + character_value(rounded)
    return character_value(rounded)


def plot_diff(  # lint-style: ignore FN001,FN003
    data,
    label="feature",
    difference="difference",
    limits=None,
    digits=2,
    pos_colour=POSITIVE_COLOUR,
    neg_colour=NEGATIVE_COLOUR,
    title=None,
):
    """Diverging bar chart of differences.

    Plots a column of differences (e.g. from `compare_values()`) as a sorted,
    diverging horizontal bar chart: the standard "what improved, what slipped"
    change chart. Bars are sorted by the difference and drawn horizontally
    (largest gain at the top), green for positive and amber for negative
    changes, with signed value labels (+0.2 / -0.3) just outside each bar and a
    zero reference line. When `limits` is None the axis is made symmetric around
    zero from the data so gains and losses are visually comparable.

    Parameters
    ----------
    data : pandas.DataFrame
        A table with a label column and a difference column.
    label : str
        Category column. Default "feature".
    difference : str
        Difference column. Default "difference".
    limits : list of float, optional
        Axis limits. None (default) chooses a symmetric range from the data.
    digits : int
        Decimal places for the value labels. Default 2.
    pos_colour, neg_colour : str
        Bar colours for positive and negative differences.
    title : str, optional
        Plot title.

    Returns
    -------
    plotnine.ggplot
        The chart.

    See Also
    --------
    compare_values

    Examples
    --------
    >>> a = pd.DataFrame({"feature": ["price", "quality", "service"], "performance": [3.1, 4.2, 3.5]})
    >>> b = pd.DataFrame({"feature": ["price", "quality", "service"], "performance": [2.8, 4.4, 3.9]})
    >>> compare_values(b, a).pipe(plot_diff)
    """
    frame = data[data[difference].notna()].reset_index(drop=True)
    frame = frame.iloc[order_rows(frame, [difference], decreasing=True)].reset_index(drop=True)
    names = [character_value(name) for name in frame[label]]
    frame[label] = factor(names, levels=list(reversed(unique_values(names)))).values
    frame["cls_"] = ["pos" if value > 0 else "neg" for value in frame[difference]]
    frame["lab_"] = [signed_label(value, digits) for value in frame[difference]]
    if limits is None:
        largest = max((abs(value) for value in frame[difference]), default=math.nan)
        if not math.isfinite(largest) or largest == 0:
            largest = 1
        limits = (-largest * 1.25, largest * 1.25)
    nudge = 0.02 * (limits[1] - limits[0])
    frame["text_y_"] = [value + nudge if value > 0 else value - nudge for value in frame[difference]]
    positive = frame[frame["cls_"] == "pos"]
    negative = frame[frame["cls_"] == "neg"]
    return (
        ggplot(frame, aes(label, difference, fill="cls_"))
        + geom_col()
        + geom_text(aes(y="text_y_", label="lab_"), data=positive, ha="left")
        + geom_text(aes(y="text_y_", label="lab_"), data=negative, ha="right")
        + geom_hline(yintercept=0)
        + scale_y_continuous(limits=limits)
        + scale_fill_manual(values={"pos": pos_colour, "neg": neg_colour})
        + labs(x="", y="", title=title)
        + coord_flip()
        + theme_ezrsurvey(transparent=True)
    )
