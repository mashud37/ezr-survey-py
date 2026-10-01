"""Read folders of survey exports, pick column blocks by prefix or suffix, and parse metadata out of file names. An analysis script opens with these."""

import os
import re

import numpy as np
import pandas as pd

from .dataset import resolve_data
from .progress import progress_done, progress_item, progress_start
from .rbase import as_character, is_missing, warn
from .select import all_of, ends_with, select_columns, starts_with

EXTENSION_PATTERN = re.compile(r"\.[A-Za-z0-9]+$")


def read_one_csv(path, all_character, encoding, **kwargs):
    if not all_character:
        return pd.read_csv(path, encoding=encoding, **kwargs)
    frame = pd.read_csv(path, dtype=str, keep_default_na=False, na_values=["", "NA"], encoding=encoding, **kwargs)
    for column in frame.columns:
        frame[column] = [value.strip() if isinstance(value, str) else np.nan for value in frame[column]]
        frame[column] = frame[column].astype(object)
    return frame


def read_folder(path, pattern=r"\.csv$", id="file", all_character=True, question_row=None, encoding="utf-8", **kwargs):  # lint-style: ignore FN001,FN003
    """Read and stack every CSV in a folder.

    Loads all CSV files matching `pattern` in `path`, reading each as text (so
    survey codes never get silently coerced), tags every row with its source
    filename, and stacks the lot into one data frame, so a folder of monthly or
    per-event exports becomes one dataset. Reading every column as text is
    deliberate, because survey exports are ragged (a column that is numeric in
    one file may carry "Prefer not to answer" in another), and stacking text
    columns never fails. Recode the types you need afterwards with the
    ``recode_*()`` helpers or `ensure_numeric()`. The `id` column records which
    file each row came from; split it into metadata with `parse_filename()`.

    Survey platforms commonly write the question wording as a second header
    row, which reads back as respondent number one and quietly skews every count
    by one. A file whose first row is long, spaced prose in most columns at once
    and numeric in none is reported as such; ``question_row=True`` drops that
    row from every file, and False keeps it without comment.

    R takes a readr ``locale``; the port takes the file `encoding` directly.

    Parameters
    ----------
    path : str
        Directory to read from.
    pattern : str
        Regular expression matching the files to load. Default all CSVs.
    id : str, optional
        Name of the column in which to record each row's source filename.
        Default "file". None omits it.
    all_character : bool
        If True (default), every column is read as text, with surrounding
        whitespace trimmed and "" or "NA" read as missing, as readr does. If
        False, types are guessed per file.
    question_row : bool, optional
        What to do with a second header row of question wording. None (default)
        keeps it and warns when a file looks like it has one; True drops the
        first row of every file; False keeps it silently.
    encoding : str
        File encoding. Default "utf-8"; pass "cp1252" for legacy Windows
        exports.
    **kwargs
        Passed to ``pandas.read_csv()``.

    Returns
    -------
    pandas.DataFrame
        All files stacked together. If columns differ across files, missing
        columns are filled with missing values.

    See Also
    --------
    select_prefix, parse_filename

    Examples
    --------
    >>> import tempfile, os
    >>> folder = tempfile.mkdtemp()
    >>> podracing_survey.head(3).to_csv(os.path.join(folder, "a.csv"), index=False)
    >>> podracing_survey.head(2).to_csv(os.path.join(folder, "b.csv"), index=False)
    >>> read_folder(folder)[["file", "respondent_id"]]
    """
    if not os.path.isdir(path):
        raise ValueError(f"Directory does not exist: {path}")
    matcher = re.compile(pattern)
    files = sorted(name for name in os.listdir(path) if matcher.search(name))
    if not files:
        raise ValueError(f"No files matching '{pattern}' found in {path}")
    run = progress_start(len(files), f"Reading {len(files)} file(s) from {path}")
    pieces = []
    for i, name in enumerate(files, start=1):
        progress_item(run, i, name)
        frame = read_one_csv(os.path.join(path, name), all_character, encoding, **kwargs)
        frame = drop_question_row(frame, question_row, name)
        if id is not None:
            frame[id] = name
        pieces.append(frame)
    progress_done(run)
    return pd.concat(pieces, ignore_index=True, sort=False)


def drop_question_row(frame, question_row, file):
    if question_row is False:
        return frame
    if question_row is True:
        return frame.iloc[1:].reset_index(drop=True) if len(frame) > 0 else frame
    if looks_like_question_row(frame):
        warn(
            f"In {file}, the first row reads like question wording rather than an answer, "
            "which is how survey platforms export a second header row. Pass "
            "`question_row=True` to drop it, or False to keep it and silence this."
        )
    return frame


def looks_like_number(text):
    try:
        float(text)
    except ValueError:
        return False
    return "_" not in text


def looks_like_question_row(frame):
    """Question wording is long, spaced prose in most columns at once, and never a number."""
    if len(frame) == 0 or len(frame.columns) < 3:
        return False
    first = [text.strip() for text in as_character(frame.iloc[0]) if not is_missing(text)]
    filled = [text for text in first if text != ""]
    if len(filled) < 3:
        return False
    if any(looks_like_number(text) for text in filled):
        return False
    wordy = [len(text) > 20 and " " in text for text in filled]
    return sum(wordy) / len(wordy) >= 0.5


def select_prefix(data=None, prefix=None, keep=None):
    """Select identifier and prefixed columns.

    Keeps a handful of id columns plus every column sharing a prefix in one
    call. Survey questionnaires are usually organised by prefix (``demo_``,
    ``ratings_``, ``partner_``, ...), so this is a quick way to grab one block
    plus a couple of id columns without naming every variable. Order is `keep`
    first, then the prefix-matching columns in their original order.

    Parameters
    ----------
    data : pandas.DataFrame, optional
        A data frame. If omitted, the session default is used.
    prefix : str or list of str
        One or more column-name prefixes to keep (e.g. "demo_", or
        ``["demo_", "ratings_"]``).
    keep : str or list of str, optional
        Additional column names to retain in front of the prefixed block (e.g.
        an id column).

    Returns
    -------
    pandas.DataFrame
        The `keep` columns followed by all prefix-matching columns.

    See Also
    --------
    read_folder, calc_percentage_multi

    Examples
    --------
    >>> select_prefix(podracing_survey, "demo_", keep="respondent_id")
    >>> select_prefix(podracing_survey, ["ratings_", "partner_"])
    """
    data = resolve_data(data)
    names = select_columns(data, [all_of(keep or []), starts_with(prefix)])
    return data[names].copy()


def select_suffix(data=None, suffix=None, keep=None):
    """Select identifier and suffixed columns.

    The mirror of `select_prefix()`: keeps a handful of id columns plus every
    column sharing a suffix in one call. Some questionnaire blocks are marked by
    a trailing tag rather than a leading one (``_com`` open-text follow-ups,
    ``_score`` derived columns). Order is `keep` first, then the
    suffix-matching columns in their original order.

    Parameters
    ----------
    data : pandas.DataFrame, optional
        A data frame. If omitted, the session default is used.
    suffix : str or list of str
        One or more column-name suffixes to keep (e.g. "_com").
    keep : str or list of str, optional
        Additional column names to retain in front of the suffixed block.

    Returns
    -------
    pandas.DataFrame
        The `keep` columns followed by all suffix-matching columns.

    See Also
    --------
    select_prefix, read_folder

    Examples
    --------
    >>> select_suffix(podracing_survey, "_com", keep="respondent_id")
    """
    data = resolve_data(data)
    names = select_columns(data, [all_of(keep or []), ends_with(suffix)])
    return data[names].copy()


def parse_filename(data=None, col="file", into=None, sep="_", drop_ext=True, remove=False):  # lint-style: ignore FN003
    """Split a filename column into metadata columns.

    Survey exports often encode metadata in the filename (e.g.
    "podracing_wave1_NA_2026.csv"). This splits a filename column on a
    separator into named metadata columns, dropping the file extension first.
    Pairs naturally with `read_folder()`, whose ``file`` column carries the
    source filename: split it once and you have event, wave, locale, year, etc.
    as real columns to group by. The split is on a fixed string (not a regular
    expression), and rows with fewer fields than `into` are padded with missing
    values so a stray filename never derails the parse.

    Parameters
    ----------
    data : pandas.DataFrame, optional
        A data frame. If omitted, the session default is used.
    col : str
        The column holding the filename. Default "file".
    into : list of str
        New column names, one per field you expect after splitting.
    sep : str
        Separator to split on. Default "_".
    drop_ext : bool
        If True (default), strip a trailing file extension before splitting.
    remove : bool
        If True, drop the original filename column. Default False.

    Returns
    -------
    pandas.DataFrame
        The data with the new metadata columns added.

    See Also
    --------
    read_folder

    Examples
    --------
    >>> df = pd.DataFrame({"file": ["podracing_wave1_NA_2026.csv"]})
    >>> parse_filename(df, into=["survey", "wave", "locale", "year"])
    """
    data = resolve_data(data)
    if col not in data.columns:
        raise ValueError(f"Column '{col}' not found in `data`.")
    out = data.copy()
    fields = {name: [] for name in into}
    for source in as_character(out[col]):
        if is_missing(source):
            parts = [np.nan]
        else:
            if drop_ext:
                source = EXTENSION_PATTERN.sub("", source)
            parts = source.split(sep)
        parts = (parts + [np.nan] * len(into))[: len(into)]
        for name, part in zip(into, parts):
            fields[name].append(part)
    for name in into:
        out[name] = pd.Series(fields[name], index=out.index, dtype=object)
    if remove:
        out = out.drop(columns=[col])
    return out
