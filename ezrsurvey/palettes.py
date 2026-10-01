"""Hold the semantic colour palettes (rating, NPS, neutral) and the brand palette, with plotnine scales for each. Every chart takes its colours from here."""

from dataclasses import dataclass

from plotnine import scale_colour_manual, scale_fill_manual
from plotnine.scales.scale_discrete import scale_discrete

from .config import ezrsurvey_default
from .rbase import as_character, factor_levels, is_categorical, is_missing

pal_rating = {
    "1": "#FF3300",
    "2": "#FF3300",
    "3": "#FFCB3E",
    "4": "#A7C23D",
    "5": "#86A33B",
}

pal_nps = {
    "-1": "#FF3300",
    "0": "#FFCB3E",
    "1": "#86A33B",
}

pal_sequential_blue = ["#8FE2FF", "#43CEFF", "#00B0F0", "#0070C0"]

pal_neutral = "#D9D9D9"

pal_rating5 = {
    "1": "#EC2000",
    "2": "#FF3300",
    "3": "#FFCB3E",
    "4": "#A7C23D",
    "5": "#86A33B",
}

RATING_RAMP = ["#FF3300", "#FFCB3E", "#86A33B"]


def hex_to_rgb(colour):
    colour = colour.lstrip("#")
    return [int(colour[i : i + 2], 16) for i in (0, 2, 4)]


def colour_ramp(colours, n):
    """n colours evenly spread along the given anchors, as R's colorRampPalette(colours)(n)."""
    anchors = [hex_to_rgb(colour) for colour in colours]
    if n == 1:
        positions = [0.0]
    else:
        positions = [i / (n - 1) for i in range(n)]
    out = []
    for position in positions:
        scaled = position * (len(anchors) - 1)
        low = min(int(scaled), len(anchors) - 2)
        share = scaled - low
        channels = []
        for start, end in zip(anchors[low], anchors[low + 1]):
            channels.append(int(start + (end - start) * share + 0.5))
        out.append("#{:02X}{:02X}{:02X}".format(*channels))
    return out


def first_digit(label):
    for character in str(label):
        if "1" <= character <= "9":
            return int(character)
    return None


def rating_palette(level_labels):
    """A red, amber, green fill for each level, placed by the level's leading digit (1 to 9)."""
    if is_categorical(level_labels):
        labels = factor_levels(level_labels)
    else:
        labels = []
        for label in as_character(level_labels):
            if not is_missing(label) and label not in labels:
                labels.append(label)
    numbers = [first_digit(label) for label in labels]
    if labels and None not in numbers and max(numbers) <= 5:
        colours = [pal_rating5[str(number)] for number in numbers]
    else:
        ramp = colour_ramp(RATING_RAMP, len(labels))
        order = sorted(range(len(labels)), key=lambda i: (numbers[i] is None, numbers[i] or 0, i))
        colours = [None] * len(labels)
        for rank, position in enumerate(order):
            colours[position] = ramp[rank]
    return dict(zip(labels, colours))


def pal_brand(n=None):
    """Brand colour palette.

    Returns the organisation's accent colours set by `use_brand()` (or the
    ``brand_colors`` option), ready for manual scales or direct use. Without a
    brand, it falls back to ``pal_sequential_blue`` so it always returns
    something usable. Only the *categorical* brand accents live here: the
    semantic palettes (``pal_rating``, ``pal_nps``) keep their red-amber-green
    vocabulary regardless of brand, because recolouring "bad to good" with
    corporate accents would destroy the meaning the colours carry.

    Parameters
    ----------
    n : int, optional
        Number of colours wanted. None (default) returns the full accent list;
        when `n` exceeds the available colours the palette is interpolated, as
        R's ``colorRampPalette()`` does.

    Returns
    -------
    list of str
        Hex colours.

    See Also
    --------
    use_brand, scale_fill_brand

    Examples
    --------
    >>> pal_brand()
    >>> pal_brand(2)
    """
    colours = ezrsurvey_default("brand_colors")
    if colours is None:
        colours = ezrsurvey_default("brand_color_primary")
    if colours is None:
        colours = pal_sequential_blue
    colours = [colours] if isinstance(colours, str) else list(colours)
    if n is None:
        return colours
    if n <= len(colours):
        return colours[:n]
    return colour_ramp(colours, n)


@dataclass
class scale_fill_brand(scale_discrete):
    """Brand fill scale: discrete fills from `pal_brand()`, interpolated when a chart needs more colours.

    Without a brand set, the scale falls back to the ``pal_sequential_blue``
    defaults via `pal_brand()`. `scale_color_brand` is an alias of
    `scale_colour_brand`.

    Examples
    --------
    >>> from plotnine import ggplot, aes, geom_col
    >>> df = calc_percentage(podracing_survey, "demo_gender")
    >>> ggplot(df, aes("demo_gender", "pct", fill="demo_gender")) + geom_col() + scale_fill_brand()
    """

    _aesthetics = ["fill"]

    def __post_init__(self):
        super().__post_init__()
        self.palette = pal_brand


@dataclass
class scale_colour_brand(scale_discrete):
    """Brand colour scale: discrete colours from `pal_brand()`. See `scale_fill_brand`.

    Examples
    --------
    >>> scale_colour_brand()
    """

    _aesthetics = ["color"]

    def __post_init__(self):
        super().__post_init__()
        self.palette = pal_brand


scale_color_brand = scale_colour_brand


def scale_fill_rating(distinct=False, **kwargs):
    """Rating fill scale.

    Maps the rating codes "1" to "5" onto ``pal_rating``, which uses the
    `bands_rating_3()` thresholds (1-2 bad, 3 ok, 4-5 good). Set
    ``distinct=True`` for a fully distinct five-colour ramp, which reads better
    on stacked bars where adjacent segments must be separable.
    `scale_color_rating` is an alias of `scale_colour_rating`.

    Parameters
    ----------
    distinct : bool
        Use a distinct shade per point instead of ``pal_rating``, where 1 and 2
        share red and 4 and 5 share green. Default False.
    **kwargs
        Passed to plotnine's ``scale_fill_manual()``.

    Returns
    -------
    plotnine scale
        A manual fill scale.

    See Also
    --------
    scale_fill_nps

    Examples
    --------
    >>> from plotnine import ggplot, aes, geom_col
    >>> df = pd.DataFrame({"feature": ["a", "b"], "pct": [60, 40], "rating": ["4", "2"]})
    >>> ggplot(df, aes("feature", "pct", fill="rating")) + geom_col() + scale_fill_rating()
    """
    return scale_fill_manual(values=pal_rating5 if distinct else pal_rating, **kwargs)


def scale_colour_rating(distinct=False, **kwargs):
    """Rating colour scale; the colour counterpart of `scale_fill_rating()`.

    Parameters
    ----------
    distinct : bool
        Use a distinct shade per point. Default False.
    **kwargs
        Passed to plotnine's ``scale_colour_manual()``.

    Returns
    -------
    plotnine scale
        A manual colour scale.

    See Also
    --------
    scale_fill_rating

    Examples
    --------
    >>> scale_colour_rating()
    """
    return scale_colour_manual(values=pal_rating5 if distinct else pal_rating, **kwargs)


scale_color_rating = scale_colour_rating


def scale_fill_nps(**kwargs):
    """NPS group fill scale.

    Maps the NPS-group coding from `nps_group()` ("-1" detractor, "0" passive,
    "1" promoter) onto the ``pal_nps`` red, amber and green palette, so the
    colours carry their usual meaning. Used by `plot_nps()`.

    Parameters
    ----------
    **kwargs
        Passed to plotnine's ``scale_fill_manual()``.

    Returns
    -------
    plotnine scale
        A manual fill scale.

    See Also
    --------
    nps_group, plot_nps

    Examples
    --------
    >>> from plotnine import ggplot, aes, geom_col
    >>> df = pd.DataFrame({"score": ["0", "1", "2"], "pct": [20, 30, 50], "group": ["-1", "0", "1"]})
    >>> ggplot(df, aes("score", "pct", fill="group")) + geom_col() + scale_fill_nps()
    """
    return scale_fill_manual(values=pal_nps, **kwargs)
