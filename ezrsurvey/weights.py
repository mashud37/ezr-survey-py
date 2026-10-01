"""Weight a survey to known population shares by post-stratification or raking. The summary helpers honour the session's scheme automatically."""

import hashlib
import math

import numpy as np
import pandas as pd

from .dataset import get_dataset, has_dataset, resolve_data
from .rbase import is_missing, message, r_sum
from .recode import na_blank

ACTIVE = {"weight_spec": None}
RAKE_MAX_ITER = 50
RAKE_TOLERANCE = 1e-6
WEIGHT_CACHE = {}
CACHE_LIMIT = 32


def normalize_targets(targets, var):
    shares = {name: value for name, value in targets.items() if name != "variable"}
    if any(not isinstance(name, str) or name == "" for name in shares):
        raise ValueError(f"Weight targets for '{var}' must be named by category.")
    numbers = {}
    for name, value in shares.items():
        try:
            numbers[name] = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"Weight targets for '{var}' must be numeric.") from None
        if math.isnan(numbers[name]):
            raise ValueError(f"Weight targets for '{var}' must be numeric.")
    if any(value < 0 for value in numbers.values()):
        raise ValueError(f"Weight targets for '{var}' must be non-negative.")
    total = sum(numbers.values())
    if total == 0:
        raise ValueError(f"Weight targets for '{var}' sum to zero.")
    return {name: value / total for name, value in numbers.items()}


def parse_one_spec(spec):
    if not isinstance(spec, dict) or "variable" not in spec:
        raise ValueError(
            "Each weight spec needs a 'variable' entry naming the column, e.g. "
            '{"variable": "demo_gender", "Male": 0.5, "Female": 0.5}.'
        )
    var = str(spec["variable"])
    return {"variable": var, "targets": normalize_targets(spec, var)}


def is_named_form(spec):
    return isinstance(spec, dict) and "variable" not in spec and all(isinstance(value, dict) for value in spec.values())


def parse_weight_spec(*specs, **named):
    """Normalise any accepted scheme into ``{variable: {category: share}}``.

    Accepts one spec per variable carrying a ``variable`` entry, a list of such
    specs, a dict of target dicts keyed by variable, or variables as keywords.
    """
    if not specs and not named:
        raise ValueError("Provide at least one weighting variable.")
    if len(specs) == 1 and not named and isinstance(specs[0], (list, tuple)):
        specs = tuple(specs[0])
    out = {}
    for spec in specs:
        if is_named_form(spec):
            for var, targets in spec.items():
                out[var] = normalize_targets(targets, var)
        else:
            one = parse_one_spec(spec)
            out[one["variable"]] = one["targets"]
    for var, targets in named.items():
        out[var] = normalize_targets(targets, var)
    return out


def weight_diagnostics(weights):
    weights = np.asarray(weights, dtype=float)
    deff = np.mean(weights**2) / np.mean(weights) ** 2
    return {"deff": float(deff), "n_eff": float(len(weights) / deff)}


def weight_cache_key(data, spec, max_iter, tol):
    digest = hashlib.sha256()
    digest.update(repr((spec, len(data), max_iter, tol)).encode("utf-8"))
    columns = [name for name in spec if name in data.columns]
    if columns:
        frame = data[columns].astype(object)
        digest.update(pd.util.hash_pandas_object(frame, index=False).values.tobytes())
    return digest.hexdigest()


def compute_weights(data, spec, max_iter=RAKE_MAX_ITER, tol=RAKE_TOLERANCE):
    """Per-row weights for `data` under a parsed scheme, reusing the cached vector when possible."""
    if len(spec) == 0:
        return np.ones(len(data))
    key = weight_cache_key(data, spec, max_iter, tol)
    if key in WEIGHT_CACHE:
        return WEIGHT_CACHE[key].copy()
    weights = rake_weights(data, spec, max_iter, tol)
    if len(WEIGHT_CACHE) >= CACHE_LIMIT:
        clear_weights_cache()
    WEIGHT_CACHE[key] = weights
    return weights.copy()


def rake_weights(data, spec, max_iter, tol):
    """Iterative proportional fitting: adjust each variable's margin in turn until none moves."""
    columns = {}
    for var, targets in spec.items():
        if var not in data.columns:
            raise ValueError(f"Weighting variable '{var}' is not a column in the data.")
        column = list(na_blank(data[var]))
        observed = []
        for value in column:
            if not is_missing(value) and value not in observed:
                observed.append(value)
        missing = [value for value in observed if value not in targets]
        if missing:
            raise ValueError(
                f"These categories of '{var}' have no weight target: {', '.join(missing)}. "
                "Add them to the scheme (or recode them first)."
            )
        columns[var] = np.array([None if is_missing(value) else value for value in column], dtype=object)
    weights = np.ones(len(data))
    for _ in range(max_iter):
        max_change = 0.0
        for var, targets in spec.items():
            step = rake_margin(weights, columns[var], targets)
            weights = step["weights"]
            max_change = max(max_change, step["max_change"])
        if max_change < tol:
            break
    return weights / weights.mean()


def rake_margin(weights, column, targets):
    """Scale each category's weights so this variable's weighted shares hit their targets."""
    adjusted = weights.copy()
    known = np.array([value is not None for value in column])
    total_known = adjusted[known].sum()
    max_change = 0.0
    if total_known <= 0:
        return {"weights": adjusted, "max_change": max_change}
    for category, share in targets.items():
        rows = column == category
        current = adjusted[rows].sum()
        if current > 0:
            ratio = (share * total_known) / current
            adjusted[rows] = adjusted[rows] * ratio
            max_change = max(max_change, abs(math.log(ratio)))
    return {"weights": adjusted, "max_change": max_change}


def resolve_weights(data, weights=None):
    """A helper's `weights` argument as a weight array, or None for unweighted.

    None uses the session scheme if one is set; False forces unweighted; True
    requires the session scheme; anything else is an ad-hoc scheme.
    """
    if weights is False:
        return None
    if weights is None:
        if not has_weights():
            return None
        spec = get_weights()
    elif weights is True:
        if not has_weights():
            raise ValueError("weights = True but no weighting scheme is set; call set_weights().")
        spec = get_weights()
    else:
        spec = parse_weight_spec(weights)
    return compute_weights(data, spec)


def set_weights(*specs, **named):  # lint-style: ignore FN001
    """Set a survey weighting scheme for the session.

    Defines target shares for one or more categorical variables (e.g. a known
    population split by gender or region). Once set, the summary helpers
    (`calc_percentage()`, `calc_nps()`, `calc_summary()`, `crosstab()`) weight
    their results automatically, so the weighted margins match your targets.
    Pass ``weights=False`` to any of them to opt out for a single call.

    With a single variable the weights are exact post-stratification:
    ``target_share / sample_share`` for each category. With several variables
    the weights are found by raking (iterative proportional fitting) so every
    variable's weighted margin matches its targets. Weights are normalised to
    mean 1 (so the weighted base equals the sample size), and respondents whose
    weighting value is blank or a non-answer (see `na_blank()`) are left
    unadjusted. A category that appears in the data but is missing from your
    targets is an error: give every observed category a share. If a default
    dataset is set, this reports the Kish design effect and the effective sample
    size so you can see the precision cost.

    Parameters
    ----------
    *specs : dict
        One scheme per variable carrying a ``variable`` entry and a share per
        category: ``{"variable": "demo_gender", "Male": 0.49, "Female": 0.50,
        "Non-binary": 0.01}``. A list of such dicts, or a dict of target dicts
        keyed by variable, also works. Shares need not sum to 1; they are
        normalised per variable (so raw percentages or counts work too).
    **named : dict
        The named form: ``demo_gender={"Male": 0.49, "Female": 0.50}``, where the
        keyword is the column.

    Returns
    -------
    dict
        The parsed scheme: normalised targets keyed by variable.

    See Also
    --------
    clear_weights, get_weights, weight_vector, calc_percentage

    Examples
    --------
    >>> set_weights({"variable": "demo_gender",
    ...              "Male": 0.49, "Female": 0.50, "Non-binary": 0.01})
    >>> calc_percentage(podracing_survey, "satis_return")
    >>> clear_weights()
    """
    spec = parse_weight_spec(*specs, **named)
    ACTIVE["weight_spec"] = spec
    if has_dataset():
        try:
            weights = compute_weights(get_dataset(), spec)
        except ValueError:
            ACTIVE["weight_spec"] = None
            raise
        diagnostics = weight_diagnostics(weights)
        message(
            f"Weighting on {len(spec)} variable(s): {', '.join(spec)}. "
            f"Design effect {diagnostics['deff']:.2f}, effective n = "
            f"{round(diagnostics['n_eff'])} of {len(weights)}."
        )
    else:
        message(f"Weighting scheme stored for: {', '.join(spec)}. It applies once a dataset is in play.")
    return spec


def get_weights():
    """Inspect or clear the session weighting scheme.

    Companions to `set_weights()`: read the stored scheme, test whether one is
    set, or remove it. `has_weights()` is the safe check before `get_weights()`,
    which errors when no scheme is set. `clear_weights()` turns weighting off
    again, so the helpers return purely unweighted results.

    Returns
    -------
    dict
        `get_weights()` returns the scheme (normalised targets keyed by
        variable); `has_weights()` returns a bool; `clear_weights()` returns
        True.

    See Also
    --------
    set_weights, weight_vector

    Examples
    --------
    >>> has_weights()
    >>> set_weights({"variable": "region", "Europe": 0.5, "North America": 0.5})
    >>> get_weights()
    >>> clear_weights()
    """
    if not has_weights():
        raise ValueError("No weighting scheme set; call set_weights() first.")
    return ACTIVE["weight_spec"]


def has_weights():
    """Tell whether a session weighting scheme is set. See `get_weights()`.

    Returns
    -------
    bool
        True when `set_weights()` has stored a scheme.

    See Also
    --------
    get_weights, set_weights

    Examples
    --------
    >>> has_weights()
    """
    return ACTIVE["weight_spec"] is not None


def clear_weights():
    """Remove the session weighting scheme, and the weight cache with it. See `get_weights()`.

    Returns
    -------
    bool
        True.

    See Also
    --------
    get_weights, set_weights

    Examples
    --------
    >>> clear_weights()
    """
    ACTIVE["weight_spec"] = None
    clear_weights_cache()
    return True


def clear_weights_cache():
    """Forget cached survey weights.

    Empties the session's cache of computed weight vectors. Weighting the same
    rows under the same scheme always gives the same numbers, so ezrsurvey works
    them out once and reuses them; a table crossing every question against every
    group would otherwise re-run the raking for each cell. The cache keys on the
    weighting columns' own contents, so editing the data produces different
    weights without any action from you. `clear_weights()` clears it too.

    Returns
    -------
    bool
        True.

    See Also
    --------
    set_weights, weight_vector

    Examples
    --------
    >>> clear_weights_cache()
    """
    WEIGHT_CACHE.clear()
    return True


def weight_vector(data=None, weights=None):
    """Compute the per-respondent survey weights.

    Returns the weights a scheme implies for a dataset (the same numbers the
    summary helpers use internally) so you can inspect them, attach them as a
    column, or feed them to another tool. Each respondent's weight is
    ``target_share / sample_share`` for their category (raked across variables
    when there are several), normalised so the weighted base equals the
    unweighted one.

    Parameters
    ----------
    data : pandas.DataFrame, optional
        A data frame. If omitted, the session default is used.
    weights : dict or list, optional
        A weighting scheme (any form `set_weights()` accepts). If None
        (default), the session scheme is used.

    Returns
    -------
    pandas.Series
        One weight per row of `data`, with its index, normalised to mean 1.

    See Also
    --------
    set_weights, calc_percentage

    Examples
    --------
    >>> target = {"variable": "demo_gender",
    ...           "Male": 0.49, "Female": 0.50, "Non-binary": 0.01}
    >>> w = weight_vector(podracing_survey, target)
    >>> (podracing_survey.assign(weight=w)
    ...     .groupby("demo_gender")["weight"]
    ...     .agg(unweighted_pct="size", weighted_pct="sum") / len(podracing_survey) * 100)
    """
    data = resolve_data(data)
    if weights is None:
        if not has_weights():
            raise ValueError("No `weights` given and no session scheme set; call set_weights().")
        spec = get_weights()
    else:
        spec = parse_weight_spec(weights)
    return pd.Series(compute_weights(data, spec), index=data.index)


def complete_pairs(x, w):
    values = np.asarray(pd.to_numeric(pd.Series(list(x)), errors="coerce"), dtype=float)
    weights = np.asarray(w, dtype=float)
    kept = ~np.isnan(values)
    return {"x": values[kept], "w": weights[kept]}


def wtd_quantile(x, w, p):
    """Weighted p-th quantile: the lowest value whose cumulative weight share reaches p."""
    pairs = complete_pairs(x, w)
    if len(pairs["x"]) == 0:
        return np.nan
    order = np.argsort(pairs["x"], kind="stable")
    values = pairs["x"][order]
    cumulative = np.cumsum(pairs["w"][order]) / pairs["w"].sum()
    return float(values[np.argmax(cumulative >= p)])


def wtd_median(x, w):
    return wtd_quantile(x, w, 0.5)


def wtd_sd(x, w):
    """Weighted standard deviation, with the reliability-weight denominator sum(w) - 1."""
    pairs = complete_pairs(x, w)
    if len(pairs["x"]) < 2:
        return np.nan
    mean = r_sum(pairs["w"] * pairs["x"]) / r_sum(pairs["w"])
    variance = r_sum(pairs["w"] * (pairs["x"] - mean) ** 2) / (r_sum(pairs["w"]) - 1)
    return float(math.sqrt(variance))


def weighted_mean(x, w):
    values = np.asarray(x, dtype=float)
    weights = np.asarray(w, dtype=float)
    products = values * weights
    total = r_sum(weights)
    if total == 0:
        return np.nan
    return r_sum(products[weights != 0]) / total
