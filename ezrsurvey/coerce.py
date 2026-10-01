"""Coerce text answers to numbers, salvaging the number inside messy exports. The helpers that need numbers call this so lightly messy data just works."""

import re

import numpy as np
import pandas as pd

from .rbase import as_character, as_series, is_missing, is_numeric_vector, message

NUMBER_PATTERN = re.compile(r"-?[0-9]*\.?[0-9]+")


def first_number(text):
    if is_missing(text):
        return np.nan
    found = NUMBER_PATTERN.search(text)
    if found is None:
        return np.nan
    return float(found.group(0))


def ensure_numeric(x, name=None, quiet=False):
    """Coerce text to numeric, salvaging embedded numbers.

    A defensive helper for the common survey-export headache where a column that
    should be numeric arrives as text: ``"25 years"``, ``"8 - very likely"``,
    ``"3.5/5"``. It returns `x` unchanged if it is already numeric; otherwise it
    pulls the first number out of each value and coerces to numeric, leaving
    genuinely unparseable entries as missing. The ezrsurvey functions that need
    numbers (e.g. `calc_nps()`, `calc_summary()`) call this for you, so they
    "just work" on lightly messy data.

    The first numeric token in each value is extracted with the pattern
    ``-?[0-9]*\\.?[0-9]+``, which captures negatives and decimals but takes only
    the *first* number it finds, so ``"8 - very likely"`` becomes ``8``, not
    ``-8``. A value that is genuinely numeric already is returned untouched (no
    copy, no message). When ``quiet=False`` a single informative message reports
    that coercion happened and how many values could not be parsed; the internal
    callers pass ``quiet=True`` so they don't spam your console. Truly blank
    entries (``""`` or missing) are not counted as parse failures.

    Parameters
    ----------
    x : list, Series or scalar
        A vector. Numeric input is returned as-is.
    name : str, optional
        Column or argument name, used only to make the message clearer.
    quiet : bool
        If False (default), emit a one-line message when coercion happens (and
        note any values that could not be parsed). Set True to silence it.

    Returns
    -------
    pandas.Series
        A numeric Series the same length as `x`.

    See Also
    --------
    recode_age, recode_likert, na_blank

    Examples
    --------
    >>> ensure_numeric(["25 years", "31", "forty"], quiet=True)
    >>> ensure_numeric(["8 - very likely", "10", "3.5/5"], quiet=True)
    >>> ensure_numeric([1, 2, 3])
    """
    values = as_series(x)
    if is_numeric_vector(values):
        return values
    raw = as_character(values)
    numbers = pd.Series([first_number(text) for text in raw], index=raw.index, dtype=float)
    if not quiet:
        label = "input" if name is None else f"'{name}'"
        lost = 0
        for text, number in zip(raw, numbers):
            if is_missing(number) and not is_missing(text) and text.strip() != "":
                lost += 1
        text = f"Auto-converted {label} to numeric."
        if lost > 0:
            text += f" {lost} value(s) could not be parsed and became NA."
        message(text)
    return numbers
