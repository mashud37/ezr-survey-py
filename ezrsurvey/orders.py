"""Register the answer order of survey scales once, linked to the columns it applies to. The tabulating helpers look orders up here and apply them automatically."""

import numpy as np
import pandas as pd

from .rbase import as_character, factor, is_categorical, r_sort, unique_values

ORDERS = {}


def register_order(name, levels, vars=None, prefixes=None, overwrite=True):
    """Register a reusable ordinal level order.

    Survey scales (education, Likert, frequency, ...) have a natural order that
    is tedious to retype as ``levels=[...]`` every time. Register an order once,
    link it to the variable names and/or column prefixes it applies to, and the
    tabulating helpers (e.g. `calc_percentage()`) will look it up and apply it
    automatically. Persist your orders in a profile with
    `save_ezrsurvey_profile()`.

    An order links a set of `levels` to the columns it applies to, by exact name
    (`vars`) and/or by prefix (`prefixes`). Once registered, `calc_percentage()`,
    `calc_percentage_multi()` and `crosstab()` look it up automatically (via
    `order_for()`) whenever you don't pass an explicit `levels`/`sort`, so a
    question always comes out in the right order without retyping it.

    Parameters
    ----------
    name : str
        Short name for the order (e.g. "education").
    levels : list of str
        The levels in ascending order.
    vars : str or list of str, optional
        Exact column names this order applies to (e.g. "demo_edu").
    prefixes : str or list of str, optional
        Column-name prefixes this order applies to (e.g. "edu_"). A variable
        matches if its name starts with any prefix.
    overwrite : bool
        Overwrite an existing order of the same name. Default True.

    Returns
    -------
    str
        The order `name`.

    See Also
    --------
    order_for, apply_order, list_orders, register_order_presets

    Examples
    --------
    >>> register_order(
    ...     "education",
    ...     levels=["Primary or less", "Lower secondary", "Upper secondary",
    ...             "Short-cycle tertiary", "Bachelor or equivalent",
    ...             "Master or equivalent", "Doctoral or equivalent"],
    ...     vars="demo_edu",
    ... )
    >>> calc_percentage(podracing_survey, "demo_edu")
    >>> remove_order("education")
    """
    if not overwrite and name in ORDERS:
        raise ValueError(f"Order '{name}' already exists; set overwrite=True.")
    ORDERS[name] = {
        "levels": [str(level) for level in as_text_list(levels)],
        "vars": as_text_list(vars),
        "prefixes": as_text_list(prefixes),
    }
    return name


def as_text_list(value):
    if value is None:
        return None
    if isinstance(value, str):
        return [value]
    return list(value)


def registry_names():
    return r_sort(ORDERS.keys())


def list_orders():
    """List registered orders.

    Returns
    -------
    pandas.DataFrame
        One row per order with `name`, `n_levels`, `vars` and `prefixes` (the
        last two comma-joined).

    See Also
    --------
    register_order

    Examples
    --------
    >>> register_order("yesno", ["No", "Yes"], vars="agree")
    >>> list_orders()
    >>> remove_order("yesno")
    """
    rows = []
    for name in registry_names():
        order = ORDERS[name]
        rows.append(
            {
                "name": name,
                "n_levels": len(order["levels"]),
                "vars": np.nan if order["vars"] is None else ", ".join(order["vars"]),
                "prefixes": np.nan if order["prefixes"] is None else ", ".join(order["prefixes"]),
            }
        )
    return pd.DataFrame(rows, columns=["name", "n_levels", "vars", "prefixes"])


def get_order(name):
    """Get the levels of a registered order.

    Parameters
    ----------
    name : str
        Order name.

    Returns
    -------
    list of str
        The levels.

    See Also
    --------
    register_order

    Examples
    --------
    >>> register_order("yesno", ["No", "Yes"])
    >>> get_order("yesno")
    >>> remove_order("yesno")
    """
    if name not in ORDERS:
        raise ValueError(f"Unknown order '{name}'. See list_orders().")
    return list(ORDERS[name]["levels"])


def remove_order(name):
    """Remove a registered order.

    Parameters
    ----------
    name : str
        Order name.

    Returns
    -------
    bool
        True.

    See Also
    --------
    register_order

    Examples
    --------
    >>> register_order("yesno", ["No", "Yes"])
    >>> remove_order("yesno")
    """
    ORDERS.pop(name, None)
    return True


def order_for(var):
    """Find the order that applies to a variable.

    Looks up the registered order for a column: an exact `vars` match wins,
    otherwise the first matching `prefixes` entry. Used internally by
    `calc_percentage()` to apply orders automatically; exposed so you can check
    what would be applied.

    Parameters
    ----------
    var : str
        A column name.

    Returns
    -------
    list of str or None
        The matching levels, or None if none is registered.

    See Also
    --------
    register_order, apply_order

    Examples
    --------
    >>> register_order("edu", ["low", "mid", "high"], prefixes="edu_")
    >>> order_for("edu_level")
    >>> remove_order("edu")
    """
    if not isinstance(var, str) or var == "":
        return None
    for name in registry_names():
        order = ORDERS[name]
        if order["vars"] is not None and var in order["vars"]:
            return list(order["levels"])
    for name in registry_names():
        order = ORDERS[name]
        for prefix in order["prefixes"] or []:
            if var.startswith(prefix):
                return list(order["levels"])
    return None


def factor_order(column, answers):
    """The answer order a categorical column carries, or None when it is not categorical.

    Only answers still present are kept, so a level that was blanked or dropped
    does not come back as an empty row, and an answer the levels do not list
    goes at the end rather than turning missing.
    """
    if not is_categorical(column):
        return None
    present = unique_values(as_character(answers))
    levels = as_character(list(column.cat.categories))
    in_order = [level for level in levels if level in present]
    unlisted = [answer for answer in present if answer not in in_order]
    return in_order + unlisted


def apply_order(x, name=None, var=None):
    """Apply a registered order to a vector.

    Turns a vector into an ordered categorical using a registered order,
    selected either by order `name` or by looking up the order linked to a
    variable name.

    Parameters
    ----------
    x : list or Series
        A vector.
    name : str, optional
        Order name (see `register_order()`). Takes precedence over `var`.
    var : str, optional
        A variable name to look up via `order_for()`.

    Returns
    -------
    pandas.Series
        An ordered categorical with the registered levels, or `x` unchanged if
        no order is found.

    See Also
    --------
    register_order, order_for

    Examples
    --------
    >>> register_order("size", ["S", "M", "L"])
    >>> apply_order(["L", "S", "M"], name="size")
    >>> remove_order("size")
    """
    levels = get_order(name) if name is not None else order_for(var)
    if levels is None:
        return x
    return factor(as_character(x), levels=levels, ordered=True)


def register_order_presets():
    """Register a set of common ordinal scales.

    A convenience that registers a handful of frequently used orders, linked to
    sensible default variable names/prefixes, so common surveys work out of the
    box. Override any of them afterwards with `register_order()`.

    Registers: ``likert_bad_good``, ``likert_agree``, ``frequency``,
    ``likelihood`` and ``education_isced``.

    Returns
    -------
    list of str
        The names registered.

    See Also
    --------
    register_order

    Examples
    --------
    >>> register_order_presets()
    >>> list_orders()
    """
    register_order("likert_bad_good", ["Very bad", "Bad", "Ok", "Good", "Very good"], prefixes="ratings_")
    register_order(
        "likert_agree",
        ["Strongly disagree", "Disagree", "Neither agree nor disagree", "Agree", "Strongly agree"],
    )
    register_order("frequency", ["Never", "Rarely", "Sometimes", "Often", "Always"])
    register_order(
        "likelihood",
        ["Very unlikely", "Unlikely", "Not sure", "Likely", "Very likely"],
        vars="satis_return",
    )
    register_order(
        "education_isced",
        [
            "Primary or less",
            "Lower secondary",
            "Upper secondary",
            "Short-cycle tertiary",
            "Bachelor or equivalent",
            "Master or equivalent",
            "Doctoral or equivalent",
        ],
        vars=["demo_edu", "education"],
        prefixes="edu_",
    )
    return ["likert_bad_good", "likert_agree", "frequency", "likelihood", "education_isced"]


def apply_orders_config(orders):
    if orders is None:
        return False
    for name, spec in orders.items():
        register_order(name, levels=spec.get("levels"), vars=spec.get("vars"), prefixes=spec.get("prefixes"))
    return True


def orders_to_list():
    out = {}
    for name in registry_names():
        order = ORDERS[name]
        spec = {"levels": list(order["levels"])}
        if order["vars"] is not None:
            spec["vars"] = list(order["vars"])
        if order["prefixes"] is not None:
            spec["prefixes"] = list(order["prefixes"])
        out[name] = spec
    return out
