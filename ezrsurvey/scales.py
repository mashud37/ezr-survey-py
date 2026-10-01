"""Round axis ceilings up to tidy values and format percentage labels. The bar charts use these so data labels never touch the top of the panel."""

import math

from plotnine import scale_y_continuous

from .rbase import as_series, is_missing

PCT_UNIT = 25


def nice_max(x, unit=PCT_UNIT, pad=0):
    """Round an axis maximum up to a "nice" value.

    Picks the next multiple of `unit` strictly above ``max(x)``: the dynamic
    y-axis trick survey reports use, where bar charts get a tidy ceiling in units
    of 25 (percentages) or 5 (NPS counts) so data labels never collide with the
    top of the panel. The ceiling is ``(floor(max(x) / unit) + 1) * unit + pad``,
    so an exact multiple still advances (``nice_max(75)`` is 100, not 75). An
    all-missing input returns missing. This is the engine behind `scale_y_pct()`
    and the percentage plot wrappers.

    Parameters
    ----------
    x : number or list of numbers
        Values; missing ones are ignored.
    unit : float
        Size of the rounding step, e.g. 25 for percentages, 5 for smaller
        counts. Must be positive.
    pad : float
        Extra headroom added to the result, in the units of `x`. Default 0.

    Returns
    -------
    float
        The padded, rounded-up ceiling, or NaN when `x` is empty or all missing.

    See Also
    --------
    scale_y_pct, label_pct

    Examples
    --------
    >>> nice_max([12, 63, 40])
    >>> nice_max(80, unit=25)
    >>> nice_max(75, unit=25)
    >>> nice_max([8, 17], unit=5, pad=10)
    """
    values = []
    for value in as_series(x):
        if is_missing(value):
            continue
        if isinstance(value, (str, bytes)) or isinstance(value, bool):
            raise ValueError("`x` must be numeric.")
        values.append(float(value))
    if isinstance(unit, bool) or not isinstance(unit, (int, float)) or unit <= 0:
        raise ValueError("`unit` must be a single positive number.")
    if not values:
        return math.nan
    largest = max(values)
    if not math.isfinite(largest):
        return largest + pad
    steps = math.floor(largest / unit) + 1
    return steps * unit + pad


def label_pct(digits=0, suffix="%"):
    """Percent label formatter.

    Returns a function that turns numbers on a 0-100 scale into percent
    strings: 42 becomes "42%". It returns a *function*, the form plotnine
    scales expect for their `labels` argument. The number is rounded to
    `digits` places as C's printf does and `suffix` appended.

    Parameters
    ----------
    digits : int
        Decimal places to keep. Default 0.
    suffix : str
        Text appended after the number. Default "%".

    Returns
    -------
    callable
        A function from a list of numbers to a list of strings.

    See Also
    --------
    scale_y_pct

    Examples
    --------
    >>> label_pct()([0, 33.4, 100])
    >>> label_pct(1)([33.45])
    """
    return PercentLabels(digits, suffix)


class PercentLabels:
    """The label function `label_pct()` returns: numbers in, "42%" strings out."""

    def __init__(self, digits, suffix):
        self.digits = digits
        self.suffix = suffix

    def __call__(self, values):
        labels = []
        for value in as_series(values):
            labels.append("NA" + self.suffix if is_missing(value) else f"{float(value):.{self.digits}f}{self.suffix}")
        return labels


def blank_labels(breaks):
    return [""] * len(breaks)


def scale_y_pct(values=None, unit=PCT_UNIT, pad=0, max=None, labels=True, **kwargs):
    """Continuous y-scale capped at a nice maximum, with percent labels.

    A thin wrapper around plotnine's ``scale_y_continuous()`` that sets the
    upper limit with `nice_max()` and, by default, formats the axis as
    percentages. The upper limit is chosen in order of precedence: a fixed
    `max`; otherwise `nice_max()` of `values`; otherwise left to plotnine.
    `plot_bars()` calls this for you, reading `unit` and `max` from the
    ``pct_axis_unit`` / ``pct_axis_max`` options.

    Parameters
    ----------
    values : list of numbers, optional
        Values that set the axis ceiling, usually the column being plotted.
    unit, pad
        Passed to `nice_max()`.
    max : float, optional
        Fixed upper limit (e.g. 100), overriding the dynamic ceiling.
    labels : bool or callable
        True (default) formats breaks as "42%"; False hides the axis labels; a
        function is used as the labels directly.
    **kwargs
        Passed to plotnine's ``scale_y_continuous()``.

    Returns
    -------
    plotnine scale
        A continuous y scale.

    See Also
    --------
    nice_max, label_pct, plot_bars

    Examples
    --------
    >>> from plotnine import ggplot, aes, geom_col
    >>> df = calc_percentage(podracing_survey, "demo_gender")
    >>> ggplot(df, aes("demo_gender", "pct")) + geom_col() + scale_y_pct(df["pct"])
    """
    if labels is True:
        label_function = label_pct()
    elif labels is False:
        label_function = None
    elif callable(labels):
        label_function = labels
    else:
        raise ValueError("`labels` must be True, False or a function.")
    limits = None
    if max is not None:
        limits = (0, max)
    elif values is not None:
        limits = (0, nice_max(values, unit=unit, pad=pad))
    if label_function is None:
        return scale_y_continuous(limits=limits, labels=blank_labels, **kwargs)
    return scale_y_continuous(limits=limits, labels=label_function, **kwargs)
