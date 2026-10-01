"""Hold the session's default dataset and resolve which data frame and columns a helper was given. Every analysis helper starts here, so a default set once serves the whole script."""

import math

import pandas as pd

SESSION = {"dataset": None}


def resolve_data(data):
    """The data frame a helper works on: the one passed, or else the session default."""
    if data is None:
        if not has_dataset():
            raise ValueError(
                "No `data` supplied and no default dataset set. Pass `data`, pipe "
                "it in, or call use_dataset() at the top of your script."
            )
        return get_dataset()
    if not isinstance(data, pd.DataFrame):
        raise ValueError("`data` must be a data frame.")
    return data


def approximate_distance(pattern, text):
    """The fewest edits that turn `pattern` into some stretch of `text`, as R's agrepl() measures."""
    previous = [0] * (len(text) + 1)
    for i, pattern_char in enumerate(pattern, start=1):
        current = [i]
        for j, text_char in enumerate(text, start=1):
            substitute = previous[j - 1] + (pattern_char != text_char)
            insert = current[j - 1] + 1
            delete = previous[j] + 1
            current.append(min(substitute, insert, delete))
        previous = current
    return min(previous)


def check_column(name, data):
    """Stop with the column's name, and the nearest spelling the data has, when it is missing.

    Raises:
        ValueError: `name` is not a column of `data`.
    """
    names = [str(column) for column in data.columns]
    if name in names:
        return name
    allowed = math.ceil(0.3 * len(name))
    near = [column for column in names if approximate_distance(name.lower(), column.lower()) <= allowed]
    hint = f" Did you mean `{near[0]}`?" if near else ""
    raise ValueError(f"Column `{name}` not found in the data.{hint}")


def col_label(column, data=None, argument="column"):
    """The column name a helper was given, checked against the data when there is one.

    Raises:
        ValueError: `column` is not a column name, or the data does not have it.
    """
    if column is None:
        raise ValueError(f'argument "{argument}" is missing, with no default')
    if not isinstance(column, str):
        shown = repr(column)
        if len(shown) > 40:
            shown = shown[:37] + "..."
        raise ValueError(
            f"Expected a column name, got `{shown}`. Pass the name of a column of "
            "the data (and the data frame itself, or set one with use_dataset())."
        )
    if data is not None:
        check_column(column, data)
    return column


def resolve_data_columns(data, columns):
    """Resolve the leading data and column arguments, letting the data be left out.

    When a default dataset is set, a first argument that is not a data frame is
    the first column, provided the last column argument was left out.

    Args:
        data: What the caller passed as `data`.
        columns: The leading column arguments, in order.

    Returns:
        A dict with the data frame (`data`) and the column arguments (`columns`).
    """
    if data is None:
        return {"data": resolve_data(None), "columns": columns}
    if isinstance(data, pd.DataFrame):
        return {"data": data, "columns": columns}
    if columns[-1] is None:
        if not has_dataset():
            raise ValueError(
                "No `data` supplied and no default dataset set. Pass `data`, pipe "
                "it in, or call use_dataset() first."
            )
        return {"data": get_dataset(), "columns": [data] + list(columns[:-1])}
    return {"data": resolve_data(data), "columns": columns}


def resolve_data_dots(data, selections):
    """Resolve the data and a list of column selections, letting the data be left out.

    Returns:
        A dict with the data frame (`data`) and the selections (`selections`).
    """
    if data is None:
        return {"data": resolve_data(None), "selections": list(selections)}
    if isinstance(data, pd.DataFrame):
        return {"data": data, "selections": list(selections)}
    if has_dataset():
        return {"data": get_dataset(), "selections": [data] + list(selections)}
    return {"data": resolve_data(data), "selections": list(selections)}


def use_dataset(data):
    """Set a default dataset for the session.

    Registers a data frame as the session's default, so the analysis helpers can
    be called without repeating `data` every time. Set it once at the top of a
    script or Quarto document and then omit `data` (or pass it with
    ``DataFrame.pipe()``).

    With a default set you can drop `data` entirely and name the column
    positionally:

    - ``calc_percentage("demo_gender")``: data taken from the default;
    - ``podracing_survey.pipe(calc_percentage, "demo_gender")``: explicit pipe;
    - ``calc_percentage(other_survey, "demo_gender")``: an explicit data frame
      always wins over the default.

    The helpers tell a column from a data frame by looking at the first argument:
    a data frame is used as the data; anything else (a column name) is taken as
    the first column and the data comes from the default. Helpers that select
    several columns (e.g. `diagnose()`, `calc_percentage_batch()`) work the same
    way: ``diagnose(starts_with("ratings_"))`` needs no `data`.

    The default applies to the analysis helpers that read a raw survey
    (`calc_percentage()`, `calc_summary()`, `calc_nps()`, `diagnose()`,
    `crosstab()`, `ipm_model()`, `sample_comments()`, ...). It does **not** apply
    to plot/report helpers that consume an already-summarised table. The setting
    lives only in the current Python session; clear it with `clear_dataset()`.

    Parameters
    ----------
    data : pandas.DataFrame
        A data frame to use as the default.

    Returns
    -------
    pandas.DataFrame
        `data`, so it can sit in a pipe.

    See Also
    --------
    get_dataset, clear_dataset, has_dataset

    Examples
    --------
    >>> use_dataset(podracing_survey)
    >>> calc_percentage("demo_gender")
    >>> calc_nps("nps_value")
    >>> clear_dataset()
    """
    if not isinstance(data, pd.DataFrame):
        raise ValueError("`data` must be a data frame.")
    SESSION["dataset"] = data
    return data


def get_dataset():
    """Get, check or clear the default dataset.

    Companions to `use_dataset()` for inspecting and resetting the session's
    default dataset. `has_dataset()` is the safe way to check before calling
    `get_dataset()`, which errors when nothing is set. `clear_dataset()` removes
    the default so that subsequent calls require an explicit `data` again:
    useful at the end of a script or between analyses of different datasets.

    Returns
    -------
    pandas.DataFrame
        `get_dataset()` returns the default data frame (error if none is set);
        `has_dataset()` returns a bool; `clear_dataset()` returns True;
        `dataset_vars()` returns a list of column names.

    See Also
    --------
    use_dataset

    Examples
    --------
    >>> has_dataset()
    >>> use_dataset(podracing_survey)
    >>> has_dataset()
    >>> len(get_dataset())
    >>> clear_dataset()
    """
    if not has_dataset():
        raise ValueError("No default dataset set; call use_dataset() first.")
    return SESSION["dataset"]


def has_dataset():
    """Tell whether a default dataset is set. See `get_dataset()`.

    Returns
    -------
    bool
        True when `use_dataset()` has set a default.

    See Also
    --------
    get_dataset, use_dataset

    Examples
    --------
    >>> has_dataset()
    """
    return SESSION["dataset"] is not None


def clear_dataset():
    """Remove the default dataset. See `get_dataset()`.

    Returns
    -------
    bool
        True.

    See Also
    --------
    get_dataset, use_dataset

    Examples
    --------
    >>> clear_dataset()
    """
    SESSION["dataset"] = None
    return True


def dataset_vars():
    """The column names of the default dataset. See `get_dataset()`.

    Returns
    -------
    list of str
        Column names.

    See Also
    --------
    get_dataset, use_dataset

    Examples
    --------
    >>> use_dataset(podracing_survey)
    >>> dataset_vars()
    >>> clear_dataset()
    """
    if not has_dataset():
        raise ValueError("No default dataset set; call use_dataset() first.")
    return [str(column) for column in get_dataset().columns]
