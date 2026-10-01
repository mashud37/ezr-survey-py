"""Write a tabbed Excel workbook with each question's summary table and chart on its own sheet. It is the hand-it-to-the-client counterpart of the slide builders."""

import os
import tempfile

import pandas as pd
from plotnine import aes, geom_histogram, ggplot, labs

from .auto_select import col_kind, detect_multiselect, multiselect_label
from .coerce import ensure_numeric
from .confirm import confirm_lines, confirm_on, confirm_selection
from .dataset import resolve_data_dots
from .export import (
    default_output_path,
    require_xlsxwriter,
    resolve_output_path,
    sanitize_sheet_names,
)
from .percentage import calc_percentage, calc_percentage_multi, calc_summary
from .plot import default_fill, plot_bars
from .progress import progress_done, progress_item, progress_plan, progress_start
from .rbase import is_numeric_vector, match_arg, message
from .select import select_columns
from .theme import theme_ezrsurvey

SORTS = ["none", "desc", "asc"]
CHART_WIDTH = 6
CHART_HEIGHT = 3.4
CHART_DPI = 150
HISTOGRAM_BINS = 20


def summary_fill():
    return default_fill()


def summary_table(data, variable, settings, numeric_var):
    """The table for one question: a numeric summary for a scale, percentages otherwise."""
    if numeric_var:
        return calc_summary(data, variable, by=settings["by"], weights=settings["weights"])
    return calc_percentage(data, variable, by=settings["by"], sort=settings["sort"], digits=settings["digits"], weights=settings["weights"])


def summary_chart(data, variable, settings, numeric_var):
    """The chart for one question: a histogram for a scale, bars otherwise; None when nothing to draw."""
    if numeric_var:
        values = ensure_numeric(data[variable], quiet=True).dropna()
        if len(values) == 0:
            return None
        frame = pd.DataFrame({"x": values.tolist()})
        return ggplot(frame, aes("x")) + geom_histogram(bins=HISTOGRAM_BINS, fill=summary_fill()) + labs(x=variable, y="count", title=variable) + theme_ezrsurvey()
    table = calc_percentage(data, variable, sort=settings["sort"], digits=settings["digits"], weights=settings["weights"])
    if len(table) == 0:
        return None
    value = "wpct" if "wpct" in table.columns else "pct"
    return plot_bars(table, value=value, title=variable)


def multi_table(data, prefix, settings):
    return calc_percentage_multi(data, prefix, by=settings["by"], sort=settings["sort"], digits=settings["digits"])


def multi_chart(data, prefix, digits):
    table = calc_percentage_multi(data, prefix, sort="desc", digits=digits)
    if len(table) == 0:
        return None
    return plot_bars(table, title=multiselect_label(prefix))


def export_questions(data, selected, auto):
    """The questions to write, one per sheet, in column order; identifiers and free text skipped when automatic."""
    multi = detect_multiselect(data, selected)
    consumed = []
    for members in multi.values():
        consumed.extend(members)
    singles = [name for name in selected if name not in consumed]
    skipped = []
    if auto:
        skipped = [name for name in singles if col_kind(data[name])["kind"] not in ("numeric", "categorical")]
        singles = [name for name in singles if name not in skipped]
    names = [str(name) for name in data.columns]
    specs = [{"type": "single", "label": name, "pos": names.index(name)} for name in singles]
    for prefix, members in multi.items():
        position = min(names.index(name) for name in members)
        specs.append({"type": "multi", "prefix": prefix, "label": multiselect_label(prefix), "pos": position})
    return {"specs": sorted(specs, key=lambda spec: spec["pos"]), "skipped": skipped}


def question_output(data, spec, settings):
    """One question's table, and its chart when charts are on."""
    if spec["type"] == "multi":
        table = multi_table(data, spec["prefix"], settings)
        chart = multi_chart(data, spec["prefix"], settings["digits"]) if settings["chart"] else None
        return {"table": table, "chart": chart}
    numeric_var = is_numeric_vector(data[spec["label"]])
    table = summary_table(data, spec["label"], settings, numeric_var)
    chart = summary_chart(data, spec["label"], settings, numeric_var) if settings["chart"] else None
    return {"table": table, "chart": chart}


def write_sheet(writer, sheet, output, settings):
    """The table from A1 and, a few rows below it, the chart as an embedded picture."""
    output["table"].to_excel(writer, sheet_name=sheet, index=False)
    if output["chart"] is None:
        return None
    handle = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    handle.close()
    output["chart"].save(handle.name, width=settings["width"], height=settings["height"], dpi=CHART_DPI, units="in", verbose=False, facecolor="white")
    writer.sheets[sheet].insert_image(len(output["table"]) + 3, 0, handle.name, {"x_scale": 96 / CHART_DPI, "y_scale": 96 / CHART_DPI})
    return handle.name


def confirm_questions(questions, confirm):
    labels = [spec["label"] for spec in questions["specs"]]
    if not confirm_on(confirm) and questions["skipped"]:
        message(
            f"export_summary_xlsx: skipped {len(questions['skipped'])} identifier / free-text column(s): "
            f"{', '.join(questions['skipped'])}."
        )
    lines = confirm_lines("Questions", labels) + confirm_lines("Skipped", questions["skipped"]) + ["Name the variables yourself to change this."]
    return confirm_selection(f"Questions chosen automatically: {len(labels)} worksheet(s).", lines, confirm)


def export_summary_xlsx(  # lint-style: ignore FN001
    data=None,
    *columns,
    path=None,
    by=None,
    chart=True,
    sort="none",
    digits=0,
    weights=None,
    width=CHART_WIDTH,
    height=CHART_HEIGHT,
    confirm=None,
):
    """Export a per-question summary workbook (table + chart per sheet).

    Writes one Excel workbook with a worksheet per question, each holding that
    question's summary table and its chart. Numeric questions get a
    `calc_summary()` table and a histogram; categorical questions get a
    `calc_percentage()` table and a `plot_bars()` chart; check-all-that-apply
    blocks get a `calc_percentage_multi()` table (based on the respondents who
    picked any option) and a bar chart. This is the "hand the client a tabbed
    workbook" counterpart to the slide/Word builders (`report_deck()`). Needs
    the ``excel`` extra.

    Worksheets are named from each question (cleaned to valid, unique Excel
    names). The table is written from cell A1; the chart, when included, is
    embedded a few rows below it. With no columns named, every question in the
    data is written and identifier / free-text columns are skipped (and named
    in a message); an interactive session shows that selection and waits for a
    yes first.

    Parameters
    ----------
    data : pandas.DataFrame, optional
        A data frame. If omitted, the session default is used.
    *columns : str or selector
        Variables to summarise, one worksheet per question. If omitted, every
        question is written.
    path : str, optional
        Output .xlsx path. None (default) writes ``summary.xlsx``. A bare file
        name lands in ``ezrsurvey-outputs/`` (created on demand); a path naming
        a directory ("./x.xlsx", "charts/x.xlsx", anything absolute) is used
        exactly as given. See the ``output_dir`` option.
    by : str or list of str, optional
        Grouping column(s) for the tables. The chart is always the ungrouped
        distribution.
    chart : bool
        Include the chart beneath each table. Default True.
    sort : str
        Level ordering for categorical tables: "none" (default, respecting any
        registered order), "desc" or "asc".
    digits : int
        Decimal places for percentages. Default 0.
    weights : bool, dict or list, optional
        Survey weighting, passed to the table and chart helpers. Multi-select
        blocks are always unweighted.
    width, height : float
        Chart size in inches. Default 6 x 3.4.
    confirm : bool, optional
        When no variables are named, show which questions were chosen and which
        were skipped, and wait for a yes before writing. None (default) follows
        the ``confirm`` option. Answering no writes nothing and returns None.

    Returns
    -------
    str or None
        The path written.

    See Also
    --------
    export_xlsx, save_data, report_deck, calc_percentage_batch

    Examples
    --------
    >>> import tempfile, os
    >>> path = os.path.join(tempfile.mkdtemp(), "summary.xlsx")
    >>> export_summary_xlsx(podracing_survey, "demo_gender", "satis_return", "nps_value", path=path)
    """
    require_xlsxwriter("Exporting a summary workbook")
    resolved = resolve_data_dots(data, columns)
    data = resolved["data"]
    sort = match_arg(sort, SORTS)
    auto = len(resolved["selections"]) == 0
    selected = [str(name) for name in data.columns] if auto else select_columns(data, resolved["selections"])
    questions = export_questions(data, selected, auto)
    specs = questions["specs"]
    if not specs:
        raise ValueError("Select at least one variable to summarise.")
    if auto and not confirm_questions(questions, confirm):
        message("Cancelled. Nothing was written.")
        return None
    settings = {"by": by, "sort": sort, "digits": digits, "weights": weights, "chart": chart, "width": width, "height": height}
    path = resolve_output_path(path if path is not None else default_output_path("summary", "xlsx"))
    sheets = sanitize_sheet_names([spec["label"] for spec in specs])
    progress_plan(f"Summary workbook: {len(specs)} question(s)", [spec["label"] for spec in specs])
    run = progress_start(len(specs))
    images = []
    with pd.ExcelWriter(path, engine="xlsxwriter") as writer:
        for i, (spec, sheet) in enumerate(zip(specs, sheets), start=1):
            progress_item(run, i, spec["label"])
            images.append(write_sheet(writer, sheet, question_output(data, spec, settings), settings))
    for image in images:
        if image is not None:
            os.remove(image)
    progress_done(run)
    return path
