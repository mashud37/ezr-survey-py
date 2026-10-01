"""Give charts the ezrsurvey look: no ticks or chart junk, bold centred titles, optional faint gridlines and transparency. Every plot helper applies one of these themes."""

import warnings

from matplotlib import font_manager
from plotnine import element_blank, element_line, element_rect, element_text, theme

from .config import ezrsurvey_default
from .rbase import message

PT = 72.27 / 25.4
BASE_SIZE = 11
FALLBACK_FAMILY = "sans-serif"
GRID_COLOUR = "#F7F7F7"
MARGIN_WIDE = 0.025
MARGIN_TALL = 0.045
NOTIFIED_FONTS = set()


def font_installed(family):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            font_manager.findfont(font_manager.FontProperties(family=family), fallback_to_default=False)
        except ValueError:
            return False
    return True


def notify_brand_font(family, why):
    if family not in NOTIFIED_FONTS:
        message(f"Brand font '{family}' not applied ({why}); using 'sans'.")
        NOTIFIED_FONTS.add(family)


def resolve_brand_family():
    """The brand body font, only when brand fonts are on and the typeface is installed here."""
    if ezrsurvey_default("brand_fonts_enabled") is not True:
        return None
    family = ezrsurvey_default("brand_font_minor")
    if not family:
        return None
    if not font_installed(family):
        notify_brand_font(family, "font not installed on this machine")
        return None
    return family


def theme_transparent():
    """Transparent-background theme fragment.

    A small theme fragment that makes the plot, panel and legend backgrounds
    transparent. Add it to any theme for slide-friendly exports; the
    `transparent` argument of `theme_ezrsurvey()` applies it for you.

    Returns
    -------
    plotnine.theme
        A theme fragment.

    See Also
    --------
    theme_ezrsurvey

    Examples
    --------
    >>> p = plot_bars(calc_percentage(podracing_survey, "demo_gender"))
    >>> p + theme_transparent()
    """
    return theme(
        plot_background=element_rect(fill="none", color="none"),
        panel_background=element_rect(fill="none", color="none"),
        legend_background=element_rect(fill="none", color="none"),
    )


def theme_ezrsurvey(base_size=BASE_SIZE, base_family=None, transparent=False):  # lint-style: ignore FN001
    """ezrsurvey plotnine themes.

    A clean, presentation-first look for survey reporting: no axis ticks, no
    chart junk, bold centred titles, and faint gridlines only where you ask for
    them. The base `theme_ezrsurvey()` strips gridlines entirely (best for bar
    charts that carry their own data labels); the `theme_ezrsurvey_x()`,
    `theme_ezrsurvey_y()` and `theme_ezrsurvey_xy()` variants add back faint
    major gridlines on the named axes. ``transparent=True`` makes the
    backgrounds transparent for slides. All the ``plot_*()`` helpers apply one of
    these for you.

    R's "sans" family is matplotlib's "sans-serif".

    Parameters
    ----------
    base_size : float
        Base font size in points. Default 11.
    base_family : str, optional
        Base font family. None (default) uses the brand body font when one is
        set and installed (see `use_brand()`), else "sans-serif".
    transparent : bool
        Make the plot, panel and legend backgrounds transparent. Default False.

    Returns
    -------
    plotnine.theme
        A theme to add to a plot with ``+``.

    See Also
    --------
    theme_transparent

    Examples
    --------
    >>> from plotnine import ggplot, aes, geom_col
    >>> df = calc_percentage(podracing_survey, "demo_gender")
    >>> ggplot(df, aes("demo_gender", "pct")) + geom_col() + theme_ezrsurvey()
    >>> ggplot(df, aes("demo_gender", "pct")) + geom_col() + theme_ezrsurvey_y()
    """
    family = base_family or resolve_brand_family() or FALLBACK_FAMILY
    look = theme(
        axis_ticks=element_blank(),
        axis_title=element_text(style="italic"),
        axis_text=element_text(size=base_size * 1.25),
        legend_position="none",
        plot_margin_left=MARGIN_WIDE,
        plot_margin_right=MARGIN_WIDE,
        plot_margin_top=MARGIN_TALL,
        plot_margin_bottom=MARGIN_TALL,
        plot_title=element_text(weight="bold", size=base_size * 1.5, ha="center"),
        plot_subtitle=element_text(weight="bold", size=base_size * 1.5, ha="center"),
        panel_background=element_rect(fill="none", color="white"),
        panel_grid_minor_x=element_blank(),
        panel_grid_minor_y=element_blank(),
        panel_grid_major_x=element_blank(),
        panel_grid_major_y=element_blank(),
        text=element_text(family=family, size=base_size),
        plot_title_position="plot",
        plot_caption_position="plot",
    )
    if transparent:
        look = look + theme_transparent()
    return look


def ezrsurvey_grid():
    return element_line(color=GRID_COLOUR, size=0.1)


def theme_ezrsurvey_x(base_size=BASE_SIZE, base_family=None, transparent=False):
    """The ezrsurvey theme with faint vertical gridlines. See `theme_ezrsurvey()`.

    Parameters
    ----------
    base_size, base_family, transparent
        As in `theme_ezrsurvey()`.

    Returns
    -------
    plotnine.theme
        A theme.

    See Also
    --------
    theme_ezrsurvey

    Examples
    --------
    >>> theme_ezrsurvey_x()
    """
    return theme_ezrsurvey(base_size, base_family, transparent) + theme(
        panel_grid_major_x=ezrsurvey_grid(),
        panel_grid_major_y=element_blank(),
        axis_text_y=element_text(ha="left"),
    )


def theme_ezrsurvey_y(base_size=BASE_SIZE, base_family=None, transparent=False):
    """The ezrsurvey theme with faint horizontal gridlines. See `theme_ezrsurvey()`.

    Parameters
    ----------
    base_size, base_family, transparent
        As in `theme_ezrsurvey()`.

    Returns
    -------
    plotnine.theme
        A theme.

    See Also
    --------
    theme_ezrsurvey

    Examples
    --------
    >>> theme_ezrsurvey_y()
    """
    return theme_ezrsurvey(base_size, base_family, transparent) + theme(
        panel_grid_major_x=element_blank(),
        panel_grid_major_y=ezrsurvey_grid(),
    )


def theme_ezrsurvey_xy(base_size=BASE_SIZE, base_family=None, transparent=False):
    """The ezrsurvey theme with faint gridlines both ways. See `theme_ezrsurvey()`.

    Parameters
    ----------
    base_size, base_family, transparent
        As in `theme_ezrsurvey()`.

    Returns
    -------
    plotnine.theme
        A theme.

    See Also
    --------
    theme_ezrsurvey

    Examples
    --------
    >>> theme_ezrsurvey_xy(transparent=True)
    """
    return theme_ezrsurvey(base_size, base_family, transparent) + theme(
        panel_grid_major_x=ezrsurvey_grid(),
        panel_grid_major_y=ezrsurvey_grid(),
    )
