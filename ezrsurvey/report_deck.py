"""Turn a dict of charts and tables into a titled deck or Word document in one call. Each item lands on its own slide, sized to the template's content placeholder."""

import pandas as pd

from .export import is_ggplot
from .progress import progress_done, progress_item, progress_start
from .rbase import match_arg
from .report_builder import (
    FORMATS,
    STYLES,
    add_empty_slide,
    fill_placeholder,
    layout_placeholders,
    report_add_plot,
    report_add_slide,
    report_add_table,
    report_new,
    report_save,
    select_layout,
    set_report_state,
)


def title_slide(doc, title, format):
    """The opening title slide on the template's title layout, or a heading in Word."""
    if format != "pptx":
        doc.add_paragraph(title, style="Heading 1")
        return doc
    selection = select_layout(doc, "title")
    add_empty_slide(doc, selection)
    set_report_state(doc, {"layout": selection["layout"], "master": selection["master"]})
    titles = layout_placeholders(doc, selection["layout"], selection["master"], ["ctrTitle", "title"])
    if titles:
        fill_placeholder(doc, titles[0], title)
    return doc


def report_deck(items, path=None, format="pptx", title=None, template=None, style="elevated"):  # lint-style: ignore FN001,FN003
    """Build a slide deck from a dict of plots and tables in one call.

    Turns a dict of charts / data frames into a titled-slide deck (or Word
    document) and saves it. Keys become slide titles; each item lands on its
    own slide, sized to the template's content placeholder. Every chart is
    rendered at the exact size of that placeholder, and `plot_bars()` draws bars
    to a constant thickness whatever the category count, so the deck reads
    consistently as you flick through it. For a deck built a slide at a time,
    with section dividers and per-slide control over the layout, use
    `report_new()` and the ``report_add_*()`` family instead.

    Parameters
    ----------
    items : dict
        Keys become slide titles. Each value is a chart (added as a plot) or a
        data frame (added as a table).
    path : str, optional
        Output file path. None (default) writes ``report.pptx`` /
        ``report.docx``. A bare file name lands in ``ezrsurvey-outputs/``
        (created on demand); a path naming a directory ("./x.pptx",
        "charts/x.pptx", anything absolute) is used exactly as given. See the
        ``output_dir`` option.
    format : str
        "pptx" (default) or "docx".
    title : str, optional
        Title-slide / document-title text.
    template : str, optional
        Reference document; None (default) uses the brand template registered
        by `use_brand()`, see `report_new()`.
    style : str
        Built-in template to fall back on: "elevated" (default, the styled
        deck) or "plain" (undecorated white).

    Returns
    -------
    str
        The path written.

    See Also
    --------
    report_new, use_brand

    Examples
    --------
    >>> import tempfile, os
    >>> path = os.path.join(tempfile.mkdtemp(), "deck.pptx")
    >>> report_deck({
    ...     "Gender": plot_bars(calc_percentage(podracing_survey, "demo_gender")),
    ...     "NPS": calc_nps(podracing_survey, "nps_value"),
    ... }, path=path)
    """
    format = match_arg(format, FORMATS)
    style = match_arg(style, STYLES)
    doc = report_new(format, template=template, style=style)
    if title is not None:
        doc = title_slide(doc, title, format)
    names = list(items.keys())
    run = progress_start(len(names), f"Building {len(names)} slide(s)")
    for i, name in enumerate(names, start=1):
        item = items[name]
        if not is_ggplot(item) and not isinstance(item, pd.DataFrame):
            raise ValueError(f"Item '{name}' must be a ggplot or a data frame.")
        progress_item(run, i, name if name else "(untitled)")
        doc = report_add_slide(doc, title=name if name else None)
        if is_ggplot(item):
            doc = report_add_plot(doc, item)
        else:
            doc = report_add_table(doc, item)
    progress_done(run)
    return report_save(doc, path)
