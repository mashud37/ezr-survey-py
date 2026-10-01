"""Save charts and tables to disk, routing every written file through one output-folder rule. A bare file name lands in the outputs folder so a session's results collect together."""

import os

import pandas as pd

from .config import ezrsurvey_default
from .rbase import character_value, is_categorical, make_unique, message

SESSION_OUTPUT = {"announced": False}
PLOT_WIDTH = 8
PLOT_HEIGHT = 4.5
PLOT_DPI = 300
SHEET_NAME_CHARACTERS = ["\\", "/", "?", "*", ":", "[", "]"]


def file_ext(path):
    return os.path.splitext(str(path))[1].lstrip(".").lower()


def default_output_path(name, ext):
    return f"{name}.{ext}"


def resolve_output_path(path):
    """Where a file actually gets written: a bare name goes into the outputs folder.

    A path that names a directory ("./out.pptx", "charts/x.png", anything
    absolute) is taken exactly as written. The folder is created if missing.
    """
    path = str(path)
    folder = ezrsurvey_default("output_dir")
    bare = os.path.dirname(path) == ""
    if bare and folder != ".":
        path = f"{folder}/{path}"
        announce_output_dir(folder)
    directory = os.path.dirname(path)
    if directory not in ("", ".") and not os.path.isdir(directory):
        os.makedirs(directory, exist_ok=True)
    return path


def announce_output_dir(folder):
    if SESSION_OUTPUT["announced"]:
        return None
    SESSION_OUTPUT["announced"] = True
    message(
        f"Saving to {folder}/. Pass a path that names a folder "
        '("./name.png", "charts/name.png") to choose somewhere else, '
        'or set ezrsurvey_options(output_dir=".").'
    )
    return None


def is_ggplot(value):
    from plotnine import ggplot

    return isinstance(value, ggplot)


def save_plot(plot, path=None, width=PLOT_WIDTH, height=PLOT_HEIGHT, dpi=PLOT_DPI, bg="transparent", **kwargs):  # lint-style: ignore FN003
    """Quick-save a plot to PNG, SVG or PDF.

    A thin, pipe-friendly wrapper around plotnine's ``ggplot.save()`` that picks
    the format from the file extension and uses presentation-friendly defaults
    (transparent background, generous size). Returns the plot, so it drops into
    a pipeline without breaking it (``p.pipe(save_plot, "p.png")``).

    Parameters
    ----------
    plot : plotnine.ggplot
        A plotnine chart.
    path : str, optional
        Output path; the extension sets the format (.png, .svg, .pdf, .jpg,
        .jpeg, .tiff). None (default) writes ``plot.png``. A bare file name lands
        in ``ezrsurvey-outputs/`` (created on demand); a path naming a directory
        ("./x.png", "charts/x.png", anything absolute) is used exactly as given.
        See the ``output_dir`` option.
    width, height : float
        Size in inches. Default 8 x 4.5.
    dpi : int
        Raster resolution for PNG/JPG/TIFF. Default 300.
    bg : str
        Background fill. Default "transparent" (matches the ezrsurvey themes);
        use "white" for a solid background.
    **kwargs
        Passed to ``ggplot.save()``.

    Returns
    -------
    plotnine.ggplot
        The `plot`.

    See Also
    --------
    save_data, save_output

    Examples
    --------
    >>> import tempfile, os
    >>> p = plot_bars(calc_percentage(podracing_survey, "demo_gender"))
    >>> tmp = os.path.join(tempfile.mkdtemp(), "chart.png")
    >>> save_plot(p, tmp)
    >>> os.path.exists(tmp)
    """
    if not is_ggplot(plot):
        raise ValueError("`plot` must be a ggplot object.")
    path = resolve_output_path(path if path is not None else default_output_path("plot", "png"))
    facecolor = "none" if bg == "transparent" else bg
    plot.save(path, width=width, height=height, dpi=dpi, units="in", verbose=False, facecolor=facecolor, **kwargs)
    return plot


def csv_value(value, na):
    text = character_value(value)
    if isinstance(value, float) and isinstance(text, str) and not float(value).is_integer():
        text = repr(float(value))
    if not isinstance(text, str):
        return na
    return text


def csv_ready(data, na):
    ready = pd.DataFrame(index=data.index)
    for column in data.columns:
        values = data[column]
        if is_categorical(values):
            values = values.astype(object)
        ready[column] = [csv_value(value, na) for value in values]
    return ready


def require_xlsxwriter(action):
    try:
        import xlsxwriter  # noqa: F401
    except ImportError:
        raise ValueError(f"{action} needs the 'xlsxwriter' package. Install it with pip install xlsxwriter.") from None


def write_xlsx(sheets, path):
    with pd.ExcelWriter(path, engine="xlsxwriter") as writer:
        for name, frame in sheets.items():
            frame.to_excel(writer, sheet_name=name, index=False)


def save_data(data, path=None, na="", **kwargs):
    """Quick-save a table to CSV, TSV or XLSX.

    A pipe-friendly one-liner for dropping a summary table to disk. The format is
    taken from the file extension. For .xlsx, pass a single data frame for one
    sheet, or a dict of data frames to write one sheet per element. Returns its
    input so it can sit mid-pipeline. To send several separate calls to their own
    tabs in one line, see `export_xlsx()`.

    CSV and TSV are written the way R's readr writes them: no row index, missing
    values as `na`, whole numbers without a decimal point.

    Parameters
    ----------
    data : pandas.DataFrame or dict of DataFrame
        A data frame, or (for .xlsx) a dict of them keyed by sheet name.
    path : str, optional
        Output path; the extension sets the format (.csv, .tsv, .xlsx). None
        (default) writes ``data.csv``. A bare file name lands in
        ``ezrsurvey-outputs/`` (created on demand); a path naming a directory
        ("./x.csv", "charts/x.csv", anything absolute) is used exactly as given.
        See the ``output_dir`` option.
    na : str
        String to write for missing values. Default "".
    **kwargs
        Passed to ``DataFrame.to_csv()``.

    Returns
    -------
    pandas.DataFrame or dict
        `data`.

    See Also
    --------
    save_plot, save_output, export_xlsx

    Examples
    --------
    >>> import tempfile, os
    >>> tab = calc_percentage(podracing_survey, "demo_gender")
    >>> tmp = os.path.join(tempfile.mkdtemp(), "table.csv")
    >>> save_data(tab, tmp)
    >>> os.path.exists(tmp)
    """
    path = resolve_output_path(path if path is not None else default_output_path("data", "csv"))
    ext = file_ext(path)
    if ext == "csv":
        csv_ready(data, na).to_csv(path, index=False, lineterminator="\n", **kwargs)
    elif ext == "tsv":
        csv_ready(data, na).to_csv(path, index=False, sep="\t", lineterminator="\n", **kwargs)
    elif ext == "xlsx":
        require_xlsxwriter("Saving XLSX")
        sheets = data if isinstance(data, dict) else {"Sheet1": data}
        write_xlsx(sheets, path)
    else:
        raise ValueError(f"Unsupported data extension '{ext}'. Use .csv, .tsv or .xlsx.")
    return data


def save_output(x, path=None, **kwargs):
    """Quick-save any ezrsurvey output (plot or table).

    Convenience dispatcher: routes plotnine charts to `save_plot()` and data
    frames / dicts of them to `save_data()`, choosing by the object type. Handy
    at the end of a pipe when you do not want to think about which saver to call.

    Parameters
    ----------
    x : plotnine.ggplot, pandas.DataFrame or dict of DataFrame
        What to save.
    path : str, optional
        Output path; the extension picks the format. None (default) writes
        ``plot.png`` or ``data.csv``. A bare file name lands in
        ``ezrsurvey-outputs/`` (created on demand); a path naming a directory
        ("./x.png", "charts/x.png", anything absolute) is used exactly as given.
        See the ``output_dir`` option.
    **kwargs
        Passed to `save_plot()` or `save_data()`.

    Returns
    -------
    object
        `x`.

    See Also
    --------
    save_plot, save_data

    Examples
    --------
    >>> import tempfile, os
    >>> tmp_csv = os.path.join(tempfile.mkdtemp(), "table.csv")
    >>> calc_percentage(podracing_survey, "demo_gender").pipe(save_output, tmp_csv)
    """
    if is_ggplot(x):
        save_plot(x, path, **kwargs)
    elif isinstance(x, (pd.DataFrame, dict, list)):
        save_data(x, path, **kwargs)
    else:
        raise ValueError(f"Don't know how to save an object of class '{type(x).__name__}'.")
    return x


def sanitize_sheet_names(names):
    cleaned = []
    for name in names:
        text = "" if name is None else str(name)
        for character in SHEET_NAME_CHARACTERS:
            text = text.replace(character, "_")
        if text == "":
            text = "Sheet"
        cleaned.append(text[:28])
    return make_unique(cleaned, sep="_")


def derive_sheet_name(frame, i):
    name = None
    if "variable" in frame.columns and frame["variable"].nunique(dropna=False) == 1:
        name = character_value(frame["variable"].iloc[0])
    elif len(frame.columns) > 0:
        name = str(frame.columns[0])
    if not isinstance(name, str) or name == "":
        name = f"Sheet{i}"
    return name


def export_xlsx(*tables, path=None, sheet_names=None, **named_tables):  # lint-style: ignore FN001
    """Export several tables to one Excel workbook, a tab each.

    A quick way to drop a handful of summaries into a single .xlsx, one per
    worksheet, e.g. ``export_xlsx(calc_percentage(d, "a"), calc_percentage(d,
    "b"), path="out.xlsx")``. Each argument becomes one worksheet: unnamed
    tables first, in order, then named ones. Tab names are taken from the
    argument names you give (``gender=...``), otherwise from each table's
    ``variable`` column or first column, otherwise Sheet1, Sheet2, ...; they are
    then cleaned to valid, unique Excel names (at most 31 characters, with
    ``[ ] : * ? / \\`` replaced).

    Parameters
    ----------
    *tables : pandas.DataFrame
        Data frames to write, one per tab.
    path : str, optional
        Output .xlsx path. None (default) writes ``tables.xlsx``. A bare file
        name lands in ``ezrsurvey-outputs/`` (created on demand); a path naming a
        directory ("./x.xlsx", "charts/x.xlsx", anything absolute) is used
        exactly as given. See the ``output_dir`` option.
    sheet_names : list of str, optional
        Tab names (overrides argument names).
    **named_tables : pandas.DataFrame
        Data frames to write under the argument's name.

    Returns
    -------
    str
        `path`.

    See Also
    --------
    save_data

    Examples
    --------
    >>> import tempfile, os
    >>> tmp = os.path.join(tempfile.mkdtemp(), "tables.xlsx")
    >>> export_xlsx(
    ...     calc_percentage(podracing_survey, "demo_job"),
    ...     gender=calc_percentage(podracing_survey, "demo_gender"),
    ...     path=tmp,
    ... )
    >>> os.path.exists(tmp)
    """
    require_xlsxwriter("Exporting XLSX")
    path = resolve_output_path(path if path is not None else default_output_path("tables", "xlsx"))
    items = [("", table) for table in tables] + list(named_tables.items())
    if not items:
        raise ValueError("Provide at least one data frame to export.")
    for _, table in items:
        if not isinstance(table, pd.DataFrame):
            raise ValueError("All tables must be data frames.")
    names = []
    for i, (given, table) in enumerate(items, start=1):
        if sheet_names is not None and len(sheet_names) >= i and sheet_names[i - 1]:
            names.append(sheet_names[i - 1])
        elif given:
            names.append(given)
        else:
            names.append(derive_sheet_name(table, i))
    sheets = dict(zip(sanitize_sheet_names(names), [table for _, table in items]))
    write_xlsx(sheets, path)
    return path
