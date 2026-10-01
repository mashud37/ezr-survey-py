"""Copy ready-to-render Quarto report skeletons and the worked example into a project. This is the document-driven counterpart to the slide builders."""

import os
import shutil
from pathlib import Path

from .config import ezrsurvey_default
from .export import resolve_output_path
from .rbase import match_arg, message
from .report_builder import TEMPLATE_FOLDER, default_pptx_template

EXAMPLE_FOLDER = Path(__file__).resolve().parent / "examples"
REPORT_FORMATS = ["pptx", "html", "pdf", "docx"]


def list_report_templates():
    """Available Quarto report templates.

    Returns
    -------
    list of str
        The output formats ezrsurvey ships a Quarto skeleton for.

    See Also
    --------
    scaffold_report

    Examples
    --------
    >>> list_report_templates()
    """
    names = sorted(path.name for path in TEMPLATE_FOLDER.glob("report-*.qmd"))
    return [name[len("report-") : -len(".qmd")] for name in names]


def reference_line(reference_doc, format):
    if reference_doc is not None:
        return "    reference-doc: " + os.path.abspath(reference_doc).replace("\\", "/")
    return f"    # reference-doc: your-template.{format}   # or scaffold_report(reference_doc=...)"


def scaffold_report(format="pptx", path=None, title="Survey Report", author=None, reference_doc=None, overwrite=False):  # lint-style: ignore FN001,FN003
    """Scaffold a Quarto survey-report template.

    Copies a ready-to-render Quarto report skeleton into your project, wired up
    with ezrsurvey helpers against the bundled ``podracing_survey`` data: an
    executive summary, per-question sections with placeholder narrative, and a
    methodology appendix built from the precision diagnostics. The skeletons
    run Python through Quarto's Jupyter engine. Each declares one parameter,
    ``data``, the path to a CSV of your survey (empty means the bundled example
    data), set with ``quarto render <file> -P data:my-survey.csv``.

    **Corporate templates:** Quarto/Pandoc fills a ``reference-doc`` by looking
    for the *standard* layout names ("Title Slide", "Title and Content", "Two
    Content", ...). A corporate template whose layouts keep those names works
    directly; one with renamed layouts will render broken or blank slides here.
    Build the deck with `report_deck()` instead, which inspects placeholders and
    works with any template.

    Parameters
    ----------
    format : str
        Output format: one of `list_report_templates()` ("pptx", "html", "pdf",
        "docx"). Default "pptx".
    path : str, optional
        Destination .qmd path. None (default) writes
        ``survey-report-<format>.qmd``. A bare file name lands in
        ``ezrsurvey-outputs/`` (created on demand), so the scaffold sits where
        its rendered output will; a path naming a directory ("./x.qmd",
        "reports/x.qmd", anything absolute) is used exactly as given. See the
        ``output_dir`` option.
    title : str
        Title inserted into the template's YAML header.
    author : str, optional
        Author name for the YAML header. None leaves a placeholder.
    reference_doc : str, optional
        Path to a PowerPoint / Word template used as the Quarto
        ``reference-doc`` (pptx and docx only). None (default) uses the brand
        template registered by `use_brand()`, if any; pptx then falls back to
        the package's built-in 16:9 template, docx leaves the line commented.
    overwrite : bool
        Overwrite `path` if it already exists. Default False.

    Returns
    -------
    str
        The path written.

    See Also
    --------
    report_deck, use_brand, example_report

    Examples
    --------
    >>> import tempfile, os
    >>> path = os.path.join(tempfile.mkdtemp(), "report.qmd")
    >>> scaffold_report("html", path=path, title="Q2 Customer Survey")
    """
    format = match_arg(format, REPORT_FORMATS)
    source = TEMPLATE_FOLDER / f"report-{format}.qmd"
    if not source.exists():
        raise ValueError(f"No bundled template for format '{format}'.")
    path = resolve_output_path(path if path is not None else f"survey-report-{format}.qmd")
    if os.path.exists(path) and not overwrite:
        raise ValueError(f"'{path}' already exists. Use overwrite=True to replace it.")
    if format in ("pptx", "docx") and reference_doc is None:
        reference_doc = ezrsurvey_default(f"brand_template_{format}")
    if format == "pptx" and reference_doc is None:
        reference_doc = default_pptx_template()
    lines = source.read_text(encoding="utf-8").splitlines()
    out = []
    for line in lines:
        if line == "{{REFERENCE_DOC}}":
            out.append(reference_line(reference_doc, format))
        else:
            out.append(line.replace("{{TITLE}}", title).replace("{{AUTHOR}}", author or "Your name"))
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(out) + "\n")
    if shutil.which("quarto") is None:
        message(f"Template written. Install the Quarto CLI to render it: quarto render '{path}'.")
    return path


def example_report(dir="ezrsurvey-example", overwrite=False):
    """Copy the worked example report into a folder.

    Drops the package's complete worked example next to your data: a full
    Quarto report over the bundled ``podracing_survey`` (every chart type, real
    narrative) plus the matching slide-deck script on the python-pptx path.
    Two files are copied: ``podracing-report.qmd`` (render with
    ``quarto render podracing-report.qmd``) and ``podracing-deck.py`` (run with
    ``python podracing-deck.py``; writes a 16:9 deck to ``ezrsurvey-outputs/``).
    Unlike the blank `scaffold_report()` skeletons, the example ships finished
    narrative over the bundled data.

    Parameters
    ----------
    dir : str
        Destination folder. Default "ezrsurvey-example" in the working
        directory; created if missing.
    overwrite : bool
        Overwrite existing files of the same names. Default False.

    Returns
    -------
    list of str
        The paths written.

    See Also
    --------
    scaffold_report, report_deck

    Examples
    --------
    >>> import tempfile, os
    >>> example_report(os.path.join(tempfile.mkdtemp(), "ezrsurvey-example"))
    """
    files = sorted(path for path in EXAMPLE_FOLDER.iterdir() if path.is_file())
    if not files:
        raise ValueError("The installed package carries no examples folder.")
    os.makedirs(dir, exist_ok=True)
    destinations = [os.path.join(dir, path.name) for path in files]
    clashes = [os.path.basename(destination) for destination in destinations if os.path.exists(destination)]
    if clashes and not overwrite:
        raise ValueError(f"Already there: {', '.join(clashes)}. Use overwrite=True to replace.")
    for source, destination in zip(files, destinations):
        shutil.copyfile(source, destination)
    message(f"Example written to {dir}/ -- start with podracing-report.qmd.")
    return destinations
