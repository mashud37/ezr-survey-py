"""Recode raw survey answers: blanks to missing, ages to bands, worded scales to numbers, packed multi-selects to columns. The summaries and charts consume what these produce."""

import numpy as np
import pandas as pd

from .coerce import ensure_numeric
from .config import ezrsurvey_default
from .dataset import col_label, resolve_data_columns
from .rbase import as_character, as_series, character_value, cut, is_missing, message, table_desc

MULTI_DELIMITERS = [";", "|", ","]
LIKERT_LEVELS = ["Very bad", "Bad", "Ok", "Good", "Very good"]


def na_blank(x, also=None, trim=True):
    """Convert blank and boilerplate non-answers to missing.

    Survey exports are littered with empty strings and standard "non-answer"
    options such as "Prefer not to answer". This helper turns those into real
    missing values so they drop out of counts and summaries.

    The input is converted to text (so categoricals are handled), optionally
    whitespace-trimmed, and any value equal to "" or to one of `also` becomes
    missing. The default `also` reads the ``na_answers`` option, so you can
    change what counts as a non-answer package-wide with
    ``ezrsurvey_options(na_answers=...)``. Most of the ``calc_*`` helpers call
    `na_blank()` internally when ``na_rm=True``, so you usually get this clean-up
    for free.

    Parameters
    ----------
    x : list or Series
        Text (or categorical) values.
    also : str or list of str, optional
        Additional exact strings to treat as missing. None (default) uses the
        ``na_answers`` option ("Prefer not to answer"); pass ``[]`` to only blank
        out "".
    trim : bool
        Whether to trim surrounding whitespace before comparing. Default True.

    Returns
    -------
    pandas.Series
        Text the same length as `x`, with blanks and non-answers missing.

    See Also
    --------
    ensure_numeric, ezrsurvey_options

    Examples
    --------
    >>> na_blank(["Yes", "", "Prefer not to answer", "No"])
    >>> na_blank(["a", "n/a", "N/A"], also=["n/a", "N/A"])
    """
    if also is None:
        also = ezrsurvey_default("na_answers")
    drop = [""] + ([also] if isinstance(also, str) else list(also))
    values = as_character(x)
    out = []
    for value in values:
        if isinstance(value, str) and trim:
            value = value.strip()
        out.append(np.nan if value in drop else value)
    return pd.Series(out, index=values.index, dtype=object)


def drop_items(x, items, trim=True):
    """Drop unwanted answer categories from a question.

    Removes specific answer values, typically catch-all or uninformative options
    such as "Other", "Don't know" or "Not applicable", by turning them into
    missing values, so they fall out of counts, percentages and charts and the
    remaining percentages re-base on the answers you keep. The summary helpers
    (`calc_percentage()`, `calc_percentage_multi()`, `calc_percentage_batch()`)
    and `crosstab()` take a ``drop=`` argument that applies this for you before
    counting; set a session-wide default with
    ``ezrsurvey_options(drop_answers=...)``.

    Parameters
    ----------
    x : list or Series
        Text (or categorical) values.
    items : str or list of str
        Exact answer values to drop. Matching is case-insensitive.
    trim : bool
        Whether to trim surrounding whitespace before comparing. Default True.

    Returns
    -------
    pandas.Series
        Text the same length as `x`, with any value matching `items` missing.

    See Also
    --------
    na_blank, calc_percentage

    Examples
    --------
    >>> drop_items(["Yes", "No", "Other", "Don't know"], items=["Other", "Don't know"])
    """
    values = as_character(x)
    if items is None or len(items) == 0:
        return values
    wanted = [str(item).lower() for item in ([items] if isinstance(items, str) else items)]
    out = []
    for value in values:
        compared = value.strip() if isinstance(value, str) and trim else value
        if isinstance(compared, str) and compared.lower() in wanted:
            out.append(np.nan)
        else:
            out.append(value)
    return pd.Series(out, index=values.index, dtype=object)


def bin_numeric(x, breaks, labels, right=False, quiet=False):
    """Bin a numeric vector into labelled groups.

    A survey-friendly binning helper that returns text (not a categorical) and
    uses left-closed, right-open intervals by default so that age bands like
    18-21 behave intuitively.

    Bands are built as R's ``cut()`` builds them with ``include.lowest = TRUE``,
    so the very lowest break is included. With ``right=False`` (the default) a
    band runs from its lower break up to *but not including* the next, i.e.
    ``[18, 25)``. Text input is salvaged with `ensure_numeric()`, so "27 years"
    bins correctly.

    A value below the first break or above the last becomes missing and drops
    out of every chart built from the result, so the function says how many did
    and what their range was. A closed top band such as 35 to 40.5 under a
    label of "35 to 40+" is the usual cause; ``math.inf`` is what that label
    means.

    Parameters
    ----------
    x : list or Series
        Numbers.
    breaks : list of float
        Cut points. With n labels you need n + 1 breaks. Use ``math.inf`` for an
        open-ended top band.
    labels : list of str
        Group labels, one fewer than `breaks`.
    right : bool
        If True, intervals are closed on the right; if False (default) closed on
        the left.
    quiet : bool
        If True, do not report values that fell outside `breaks`.

    Returns
    -------
    pandas.Series
        Group labels; values outside the range or missing become missing.

    See Also
    --------
    recode_age, ensure_numeric

    Examples
    --------
    >>> import math
    >>> bin_numeric([15, 19, 27, 41], breaks=[0, 18, 25, 35, math.inf],
    ...             labels=["<18", "18-24", "25-34", "35+"])
    """
    if len(labels) != len(breaks) - 1:
        raise ValueError("`labels` must have length `len(breaks) - 1`.")
    values = ensure_numeric(x, quiet=True)
    out = cut(values, breaks=breaks, labels=labels, right=right, include_lowest=True)
    dropped = [value for value, label in zip(values, out) if not is_missing(value) and is_missing(label)]
    if not quiet and dropped:
        message(
            f"bin_numeric: {len(dropped)} value(s) fell outside the breaks and became NA "
            f"(range {character_value(min(dropped))} to {character_value(max(dropped))}). "
            "Widen `breaks`, e.g. with -math.inf / math.inf at the ends."
        )
    return out


def recode_age(x, breaks=None, labels=None, quiet=False):
    """Recode age into standard survey bands.

    Convenience wrapper over `bin_numeric()` using the standard survey age bands.
    Ages are first passed through `ensure_numeric()`, so messy entries like
    "22 years" or "age: 31" are handled, then binned using left-closed bands. An
    answer with no number in it at all ("young", "prefer not to say") becomes
    missing and is counted in a message, so a column that was never numeric does
    not pass for a column of missing ages. The default bands come from the
    ``age_breaks`` / ``age_labels`` options. For *generational* cohorts use
    `recode_generation()` instead.

    Parameters
    ----------
    x : list or Series
        Ages, as numbers or text.
    breaks, labels : list, optional
        Override the default bands; None (default) uses the ``age_breaks`` /
        ``age_labels`` options.
    quiet : bool
        If False (default), report answers that held no number and answers that
        fell outside the bands. Set True to silence both.

    Returns
    -------
    pandas.Series
        Age-band labels.

    See Also
    --------
    bin_numeric, recode_generation, ezrsurvey_options

    Examples
    --------
    >>> recode_age(["17", "22 years", "31", "47"])
    """
    breaks = ezrsurvey_default("age_breaks") if breaks is None else breaks
    labels = ezrsurvey_default("age_labels") if labels is None else labels
    original = as_series(x)
    numbers = ensure_numeric(original, quiet=True)
    texts = as_character(original)
    unparsed = 0
    for number, text in zip(numbers, texts):
        if is_missing(number) and not is_missing(text) and text.strip() != "":
            unparsed += 1
    if not quiet and unparsed > 0:
        message(f"recode_age: {unparsed} value(s) held no number and became NA.")
    return bin_numeric(numbers, breaks=breaks, labels=labels, quiet=quiet)


def longest_first(texts):
    return sorted(range(len(texts)), key=lambda i: -len(texts[i]))


def substring_matches(codes, lowered, needles, targets):
    """Give each still-unmatched answer the target of the longest needle it contains."""
    filled = list(codes)
    for i in longest_first(needles):
        for row, text in enumerate(lowered):
            if filled[row] is None and text is not None and needles[i] in text:
                filled[row] = targets[i]
    return filled


def recode_likert(x, levels=None, synonyms=None):  # lint-style: ignore FN001
    """Recode a worded rating scale to integers.

    Maps the worded answers of an ordinal rating question (e.g. "Very bad" ...
    "Very good") onto integers 1 to ``len(levels)``. Matching happens in three
    passes, in order: (1) an exact, case-insensitive, trimmed match against
    `levels`; (2) a substring fallback, so prefixed exports like "4 - Good"
    still resolve; (3) any `synonyms` you supply.

    The substring passes try the longest wording first, so a scale whose levels
    nest inside one another ("Likeable" inside "Very likeable", "Good" inside
    "Very good") resolves to the level the answer actually names.

    Parameters
    ----------
    x : list or Series
        Worded answers.
    levels : list of str, optional
        The scale's answer wordings in ascending order. The first maps to 1, the
        last to ``len(levels)``. Defaults to a 5-point bad-to-good scale.
    synonyms : dict, optional
        Maps a canonical level (one of `levels`) to a string or list of
        alternative spellings that should map to the same integer. Matching is by
        case-insensitive substring.

    Returns
    -------
    pandas.Series
        Nullable integers (Int64) the same length as `x`; unmatched values are
        missing.

    See Also
    --------
    nps_group, ipm_model, calc_summary

    Examples
    --------
    >>> recode_likert(["Very bad", "Ok", "Good", "Very good"])
    >>> recode_likert("4 - Good")
    >>> recode_likert(["\\U0001F642 Very good", "\\U0001F610 Good"])
    >>> recode_likert(["Dissatisfied", "Satisfied"],
    ...               synonyms={"Bad": "Dissatisfied", "Good": "Satisfied"},
    ...               levels=["Very bad", "Bad", "Ok", "Good", "Very good"])
    """
    levels = LIKERT_LEVELS if levels is None else list(levels)
    texts = as_character(x)
    lowered = [text.lower() if isinstance(text, str) else None for text in texts]
    lower_levels = [level.lower() for level in levels]
    out = []
    for text in lowered:
        stripped = None if text is None else text.strip()
        out.append(lower_levels.index(stripped) + 1 if stripped in lower_levels else None)
    out = substring_matches(out, lowered, lower_levels, list(range(1, len(levels) + 1)))
    if synonyms is not None:
        alternatives = []
        targets = []
        for canonical, spellings in synonyms.items():
            if canonical.lower() not in lower_levels:
                raise ValueError(f"Synonym target '{canonical}' is not one of `levels`.")
            for spelling in [spellings] if isinstance(spellings, str) else spellings:
                alternatives.append(spelling.lower())
                targets.append(lower_levels.index(canonical.lower()) + 1)
        out = substring_matches(out, lowered, alternatives, targets)
    return pd.Series(out, index=texts.index, dtype="Int64")


def nps_group(x, labels=False):
    """Classify Net Promoter Score answers into groups.

    Collapses a 0-10 "how likely to recommend" question into the three standard
    NPS groups: detractors (0-6), passives (7-8) and promoters (9-10). The
    signed -1/0/1 coding is deliberate: its mean, times 100, is exactly the Net
    Promoter Score, which is how `calc_nps()` computes the headline number.
    Inputs are run through `ensure_numeric()` first, so worded answers like
    "9 - very likely" are classified correctly. Values outside 0-10 (and
    missing values) return missing.

    Parameters
    ----------
    x : list or Series
        0-10 ratings (text input is coerced).
    labels : bool
        If False (default) returns the signed integer coding -1 / 0 / 1 used by
        `calc_nps()`. If True returns "Detractor" / "Passive" / "Promoter".

    Returns
    -------
    pandas.Series
        Nullable integers (Int64) or text, the same length as `x`.

    See Also
    --------
    calc_nps, plot_nps

    Examples
    --------
    >>> nps_group([0, 6, 7, 8, 9, 10])
    >>> nps_group([3, 8, 10], labels=True)
    """
    values = ensure_numeric(x, quiet=True)
    groups = []
    for value in values:
        if is_missing(value):
            groups.append(None)
        elif 0 <= value <= 6:
            groups.append(-1)
        elif 7 <= value <= 8:
            groups.append(0)
        elif 9 <= value <= 10:
            groups.append(1)
        else:
            groups.append(None)
    if not labels:
        return pd.Series(groups, index=values.index, dtype="Int64")
    names = {-1: "Detractor", 0: "Passive", 1: "Promoter"}
    return pd.Series([np.nan if group is None else names[group] for group in groups], index=values.index, dtype=object)


def detect_delimiter(values):
    present = [value for value in values if isinstance(value, str) and value != ""]
    for delimiter in MULTI_DELIMITERS:
        for value in present:
            if delimiter in value:
                return delimiter
    return None


def unpack_answers(values, delimiter):
    """The answers each respondent ticked, one list per respondent, trimmed and without blanks."""
    unpacked = []
    for value in values:
        if is_missing(value):
            parts = [value]
        elif delimiter is None:
            parts = [value]
        else:
            parts = value.split(delimiter)
        kept = []
        for part in parts:
            if is_missing(part):
                continue
            squished = " ".join(part.split())
            if squished != "":
                kept.append(squished)
        unpacked.append(kept)
    return unpacked


def split_multi(data=None, column=None, split="auto", prefix=None):  # lint-style: ignore FN001
    """Split a packed multi-select column into one column per answer.

    Turns the single cell a spreadsheet export gives a "tick all that apply"
    question ("Speed; Drivers; Betting") into the one-column-per-option layout
    the rest of the package expects, so `calc_percentage_multi()`, `crosstab()`
    and the plots all work on it.

    The new columns are named `prefix` plus the answer text verbatim, which keeps
    the labels readable all the way through to a chart:
    `calc_percentage_multi()` strips the prefix back off and uses what remains
    as the option label. Surrounding whitespace is trimmed and empty answers are
    dropped, so "Speed;  ; Drivers" yields two options. When no cell contains
    the delimiter, each cell is treated as a single answer. If you only want the
    percentages, skip this step: `calc_percentage_multi()` detects a packed
    column and splits it for you.

    Parameters
    ----------
    data : pandas.DataFrame, optional
        A data frame. If omitted, the session default (`use_dataset()`) is used.
    column : str
        The packed column.
    split : str
        The delimiter between answers inside a cell. "auto" (default) detects
        ";", "|" or ",", in that order. Pass a string to force one.
    prefix : str, optional
        Prefix for the new column names. Defaults to the column's own name
        followed by an underscore, e.g. ``motivations_``.

    Returns
    -------
    pandas.DataFrame
        The data with one new column per distinct answer, each holding the answer
        text for respondents who chose it and "" for those who did not, ordered
        most-chosen first. The packed column is kept.

    See Also
    --------
    calc_percentage_multi, na_blank

    Examples
    --------
    >>> packed = pd.DataFrame({
    ...     "respondent": [1, 2, 3, 4],
    ...     "motivations": ["Speed; Drivers", "Speed", "", "Betting; Speed"],
    ... })
    >>> split_multi(packed, "motivations")
    >>> split_multi(packed, "motivations").pipe(
    ...     calc_percentage_multi, "motivations_", id="respondent", sort="desc")
    """
    resolved = resolve_data_columns(data, [column])
    out = resolved["data"].copy()
    col_name = col_label(resolved["columns"][0], out)
    if prefix is None:
        prefix = col_name + "_"
    values = na_blank(out[col_name])
    delimiter = detect_delimiter(values) if split == "auto" else split
    chosen = unpack_answers(values, delimiter)
    flat = []
    for answers in chosen:
        flat.extend(answers)
    ranked = [answer for answer, _ in table_desc(flat)]
    if not ranked:
        raise ValueError(f"Column '{col_name}' holds no answers to split.")
    for answer in ranked:
        out[prefix + answer] = [answer if answer in picked else "" for picked in chosen]
    return out.reset_index(drop=True)
