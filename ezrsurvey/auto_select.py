"""Classify columns for the automatic "every question" selection: scales, categories, free text and multi-select blocks. The banner table and the summary workbook choose their variables with these."""

from .rbase import is_missing, is_numeric_vector
from .recode import na_blank


def col_prefix(name):
    """The prefix of a column name up to and including its final underscore; "" when it has none."""
    if "_" not in name:
        return ""
    last = name.rfind("_")
    if last == len(name) - 1:
        return name
    return name[: last + 1]


def distinct_count(values):
    return len({value for value in values if not is_missing(value)})


def col_kind(x):
    """Classify one column as numeric, constant, free text or an ordinary categorical question."""
    if is_numeric_vector(x):
        return {"kind": "numeric", "nd": distinct_count(x)}
    answers = na_blank(x)
    filled = int(answers.notna().sum())
    distinct = distinct_count(answers)
    if distinct < 2:
        return {"kind": "constant", "nd": distinct}
    if filled > 0 and distinct >= 0.5 * filled:
        return {"kind": "freetext", "nd": distinct}
    return {"kind": "categorical", "nd": distinct}


def is_indicator(values):
    answers = na_blank(values)
    return distinct_count(answers) == 1 and answers.isna().any()


def detect_multiselect(data, cols=None):
    """Find check-all-that-apply blocks: prefix-sharing columns that each hold one option or blank.

    Returns:
        A dict from prefix to its member column names, in column order.
    """
    cols = [str(name) for name in data.columns] if cols is None else list(cols)
    prefixes = [col_prefix(name) for name in cols]
    out = {}
    for prefix in prefixes:
        if prefix == "" or prefix in out:
            continue
        members = [name for name, own in zip(cols, prefixes) if own == prefix]
        if len(members) >= 2 and all(is_indicator(data[name]) for name in members):
            out[prefix] = members
    return out


def multiselect_label(prefix):
    return prefix.rstrip("_")
