"""Select columns by name or by pattern, the Python form of the tidyselect helpers R users pass to ezrsurvey. Every helper that takes several columns resolves them here."""

import pandas as pd

from .rbase import is_numeric_vector


def starts_with(match, ignore_case=True):
    """Select columns whose names start with a prefix.

    The Python form of tidyselect's ``starts_with()``: pass it wherever an
    ezrsurvey helper takes several columns. Matching ignores case by default,
    as in R.

    Parameters
    ----------
    match : str or list of str
        One prefix, or several.
    ignore_case : bool
        Ignore upper and lower case when matching. Default True.

    Returns
    -------
    dict
        A selection that the helpers resolve against their data.

    See Also
    --------
    ends_with, contains, everything, all_of

    Examples
    --------
    >>> diagnose(podracing_survey, starts_with("ratings_"))
    """
    return {"selector": "starts_with", "match": as_list(match), "ignore_case": ignore_case}


def ends_with(match, ignore_case=True):
    """Select columns whose names end with a suffix.

    Parameters
    ----------
    match : str or list of str
        One suffix, or several.
    ignore_case : bool
        Ignore upper and lower case when matching. Default True.

    Returns
    -------
    dict
        A selection that the helpers resolve against their data.

    See Also
    --------
    starts_with, contains

    Examples
    --------
    >>> select_suffix(podracing_survey, "_com")
    >>> calc_percentage_batch(podracing_survey, ends_with("_gender"))
    """
    return {"selector": "ends_with", "match": as_list(match), "ignore_case": ignore_case}


def contains(match, ignore_case=True):
    """Select columns whose names contain a piece of text.

    Parameters
    ----------
    match : str or list of str
        The text to look for, or several.
    ignore_case : bool
        Ignore upper and lower case when matching. Default True.

    Returns
    -------
    dict
        A selection that the helpers resolve against their data.

    See Also
    --------
    starts_with, ends_with

    Examples
    --------
    >>> calc_percentage_batch(podracing_survey, contains("recall"))
    """
    return {"selector": "contains", "match": as_list(match), "ignore_case": ignore_case}


def everything():
    """Select every column.

    Returns
    -------
    dict
        A selection that the helpers resolve against their data.

    See Also
    --------
    starts_with, all_of

    Examples
    --------
    >>> diagnose(podracing_survey.iloc[:, :5], everything())
    """
    return {"selector": "everything"}


def all_of(names):
    """Select the columns named in a list, all of which must exist.

    Parameters
    ----------
    names : str or list of str
        Column names.

    Returns
    -------
    dict
        A selection that the helpers resolve against their data.

    See Also
    --------
    any_of, starts_with

    Examples
    --------
    >>> questions = ["demo_gender", "demo_job"]
    >>> calc_percentage_batch(podracing_survey, all_of(questions))
    """
    return {"selector": "all_of", "names": as_list(names)}


def any_of(names):
    """Select the columns named in a list that exist, skipping the ones that do not.

    Parameters
    ----------
    names : str or list of str
        Column names.

    Returns
    -------
    dict
        A selection that the helpers resolve against their data.

    See Also
    --------
    all_of

    Examples
    --------
    >>> calc_percentage_batch(podracing_survey, any_of(["demo_gender", "not_a_column"]))
    """
    return {"selector": "any_of", "names": as_list(names)}


def where(test):
    """Select the columns for which a function returns True, such as ``is_numeric``.

    Parameters
    ----------
    test : callable
        A function taking a column (a Series) and returning True or False.

    Returns
    -------
    dict
        A selection that the helpers resolve against their data.

    See Also
    --------
    everything

    Examples
    --------
    >>> diagnose(podracing_survey, where(is_numeric))
    """
    return {"selector": "where", "test": test}


def is_numeric(column):
    """Tell whether a column holds numbers, as R's ``is.numeric()`` does; for use with `where()`.

    Parameters
    ----------
    column : pandas.Series
        A column.

    Returns
    -------
    bool
        True for integer and float columns, False for text, categories and
        booleans.

    See Also
    --------
    where

    Examples
    --------
    >>> is_numeric(podracing_survey["nps_value"])
    >>> diagnose(podracing_survey, where(is_numeric))
    """
    return is_numeric_vector(column)


def as_list(value):
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def name_matches(name, selection):
    rule = selection["selector"]
    for piece in selection["match"]:
        text = name
        if selection["ignore_case"]:
            text = name.lower()
            piece = piece.lower()
        if rule == "starts_with" and text.startswith(piece):
            return True
        if rule == "ends_with" and text.endswith(piece):
            return True
        if rule == "contains" and piece in text:
            return True
    return False


def missing_column_error(name):
    return ValueError(f"Can't select columns that don't exist. Column `{name}` doesn't exist.")


def selection_names(data, selection):
    names = [str(name) for name in data.columns]
    if isinstance(selection, str):
        if selection not in names:
            raise missing_column_error(selection)
        return [selection]
    if not isinstance(selection, dict) or "selector" not in selection:
        raise ValueError(f"Can't select columns with `{selection!r}`. Pass column names or selectors such as starts_with().")
    rule = selection["selector"]
    if rule == "everything":
        return names
    if rule == "all_of":
        for name in selection["names"]:
            if name not in names:
                raise missing_column_error(name)
        return list(selection["names"])
    if rule == "any_of":
        return [name for name in selection["names"] if name in names]
    if rule == "where":
        return [name for name in names if selection["test"](data[name])]
    return [name for name in names if name_matches(name, selection)]


def flatten_selections(selections):
    flat = []
    for item in selections:
        if isinstance(item, (list, tuple)):
            flat.extend(flatten_selections(item))
        elif item is not None:
            flat.append(item)
    return flat


def select_columns(data, selections):
    """Resolve column names and selectors against a data frame, in order and without repeats.

    Args:
        data: The DataFrame to select from.
        selections: A column name, a selector, or a list mixing both.

    Returns:
        The selected column names, as tidyselect orders them.

    Raises:
        ValueError: A named column does not exist.
    """
    if not isinstance(selections, (list, tuple)):
        selections = [selections]
    chosen = []
    for selection in flatten_selections(selections):
        for name in selection_names(data, selection):
            if name not in chosen:
                chosen.append(name)
    return chosen


def select_frame(data, selections):
    return pd.DataFrame(data[select_columns(data, selections)])
