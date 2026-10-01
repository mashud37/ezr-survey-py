"""Score Net Promoter and rank what drives an outcome, as relative weights, a random forest or plain correlation. The importance/performance chart plots these results."""

import numpy as np
import pandas as pd

from .coerce import ensure_numeric
from .dataset import col_label, resolve_data_columns
from .percentage import clean_label
from .rbase import factor, is_numeric_vector, match_arg, r_mean, r_round, warn
from .recode import nps_group, recode_likert
from .select import select_columns, starts_with
from .tables import group_positions, restore_types
from .weights import resolve_weights, weighted_mean

METHODS = ["rwa", "forest", "correlation"]
LIKERT_LEVELS = ["Very bad", "Bad", "Ok", "Good", "Very good"]
FOREST_TREES = 500
FOREST_LEAF = 5


def nps_row(groups, weights):
    groups = np.asarray(groups, dtype=float)
    return {
        "n": len(groups),
        "nps": r_round(weighted_mean(groups, weights) * 100),
        "pct_detractors": r_round(weighted_mean(groups == -1, weights) * 100),
        "pct_passives": r_round(weighted_mean(groups == 0, weights) * 100),
        "pct_promoters": r_round(weighted_mean(groups == 1, weights) * 100),
        "detractors": int((groups == -1).sum()),
        "passives": int((groups == 0).sum()),
        "promoters": int((groups == 1).sum()),
    }


def calc_nps(data=None, value=None, by=None, weights=None):  # lint-style: ignore FN001
    """Net Promoter Score.

    Computes NPS from a 0-10 recommendation question. Respondents are bucketed
    by `nps_group()` into detractors (0-6), passives (7-8) and promoters
    (9-10); the score is the percentage of promoters minus the percentage of
    detractors, which equals ``100 * mean()`` of the signed -1/0/1 coding.
    Missing or out-of-range scores are dropped before the mean. Text answers are
    coerced with `ensure_numeric()`.

    The three group counts and shares are reported alongside the score because
    a single NPS hides how it was reached: +20 from 40% promoters and 20%
    detractors is a different picture from +20 with 25% and 5%. Counts are
    always unweighted respondent counts; the shares follow ``nps``, so they are
    weighted when a weighting scheme is active. All three shares and ``nps`` are
    rounded to whole numbers independently, so
    ``pct_promoters - pct_detractors`` can land one point away from ``nps``.

    Parameters
    ----------
    data : pandas.DataFrame, optional
        A data frame. If omitted, the session default is used.
    value : str
        The 0-10 recommendation column.
    by : str or list of str, optional
        Grouping column(s); see `calc_percentage()`.
    weights : bool, dict or list, optional
        Survey weighting: None (default) uses the session scheme from
        `set_weights()` if set; False forces unweighted; or pass an ad-hoc
        scheme. When weighting is active ``nps`` is the weighted score (``n``
        stays the unweighted base).

    Returns
    -------
    pandas.DataFrame
        ``n`` (valid responses), ``nps`` (-100 to 100), the three group shares
        (``pct_detractors``, ``pct_passives``, ``pct_promoters``) and the counts
        behind them (``detractors``, ``passives``, ``promoters``), one row per
        group when `by` is given.

    See Also
    --------
    nps_group, plot_nps, plot_nps_gauge

    Examples
    --------
    >>> calc_nps(podracing_survey, "nps_value")
    >>> calc_nps(podracing_survey, "nps_value", by="region")
    """
    resolved = resolve_data_columns(data, [value])
    data = resolved["data"]
    col_name = col_label(resolved["columns"][0], data, argument="value")
    w = resolve_weights(data, weights)
    frame = data.reset_index(drop=True)
    frame = frame.assign(**{".w": np.ones(len(frame)) if w is None else w})
    frame = frame.assign(**{col_name: ensure_numeric(frame[col_name], name=col_name).to_numpy()})
    frame = frame.assign(**{".nps_group": nps_group(frame[col_name]).to_numpy()})
    frame = frame[frame[".nps_group"].notna()].reset_index(drop=True)
    by_names = select_columns(frame, by) if by is not None else []
    rows = []
    for group in group_positions(frame, by_names):
        block = frame.iloc[group["positions"]]
        row = dict(zip(by_names, group["values"]))
        row.update(nps_row(block[".nps_group"].astype(float), block[".w"]))
        rows.append(row)
    columns = by_names + [
        "n",
        "nps",
        "pct_detractors",
        "pct_passives",
        "pct_promoters",
        "detractors",
        "passives",
        "promoters",
    ]
    out = pd.DataFrame(rows, columns=columns)
    for column in ("n", "detractors", "passives", "promoters"):
        out[column] = out[column].astype("int64")
    return restore_types(out, frame, by_names)


def importance_frame(frame, outcome, predictors):
    """The complete numeric cases every importance method works from."""
    numbers = pd.DataFrame({name: pd.to_numeric(frame[name], errors="coerce").astype(float) for name in [outcome] + predictors})
    return numbers.dropna().reset_index(drop=True)


def rescale_importance(features, values):
    """Put any importance measure onto the relative-weights scale: floored at zero, summing to 100."""
    values = np.asarray(values, dtype=float)
    values = np.where(np.isnan(values) | (values < 0), 0.0, values)
    total = values.sum()
    if total == 0:
        raise ValueError("No predictor carries any signal; importance is undefined.")
    return pd.DataFrame({"feature": list(features), "importance": values / total * 100})


def check_variance(frame, outcome, predictors):
    if not frame[outcome].var(ddof=1) > 0:
        raise ValueError(f"Outcome variable '{outcome}' has zero variance.")
    flat = [name for name in predictors if not frame[name].var(ddof=1) > 0]
    if flat:
        raise ValueError("Predictor variable(s) with zero variance: " + ", ".join(flat))


def relative_weights(frame, outcome, predictors):
    """Johnson's relative weights, computed as the rwa package computes them.

    The predictors' correlation matrix is replaced by its symmetric square root
    (lambda); the outcome is regressed on that orthogonal version (beta); each
    predictor's weight is its squared loadings times the squared betas, as a
    share of the explained variance.
    """
    check_variance(frame, outcome, predictors)
    correlation = np.corrcoef(frame[[outcome] + predictors].to_numpy(), rowvar=False)
    rxx = correlation[1:, 1:]
    rxy = correlation[1:, 0]
    if abs(np.linalg.det(rxx)) < np.finfo(float).eps * 100:
        raise ValueError(
            "Predictor correlation matrix is singular or near-singular. This usually indicates "
            "perfect or near-perfect collinearity among predictors. Consider removing highly "
            "correlated predictors."
        )
    eigenvalues, eigenvectors = np.linalg.eigh(rxx)
    if (eigenvalues < 0).any():
        warn(
            "Correlation matrix has negative eigenvalues, which may indicate numerical instability. "
            "Results should be interpreted with caution."
        )
    lam = eigenvectors @ np.diag(np.sqrt(eigenvalues)) @ eigenvectors.T
    beta = np.linalg.solve(lam, rxy)
    rsquare = (beta**2).sum()
    raw = (lam**2) @ (beta**2)
    return pd.DataFrame({"feature": predictors, "importance": raw / rsquare * 100})


def rwa_importance(frame, outcome, predictors):
    numbers = importance_frame(frame, outcome, predictors)
    result = relative_weights(numbers, outcome, predictors)
    return result.sort_values("importance", ascending=False, kind="stable").reset_index(drop=True)


def oob_permutation_importance(model, x, y):
    """Mean rise in out-of-bag squared error when each predictor is permuted, scaled by its spread.

    This is randomForest's %IncMSE with its default scaling, computed tree by
    tree on the rows each tree never saw.
    """
    rng = np.random.default_rng(np.random.randint(0, 2**31 - 1))
    rows = np.arange(len(y))
    rises = np.zeros((len(model.estimators_), x.shape[1]))
    for t, (tree, sample) in enumerate(zip(model.estimators_, model.estimators_samples_)):
        unseen = np.setdiff1d(rows, sample)
        if len(unseen) == 0:
            continue
        base = np.mean((tree.predict(x[unseen]) - y[unseen]) ** 2)
        for j in range(x.shape[1]):
            shuffled = x[unseen].copy()
            shuffled[:, j] = rng.permutation(shuffled[:, j])
            rises[t, j] = np.mean((tree.predict(shuffled) - y[unseen]) ** 2) - base
    spread = rises.std(axis=0, ddof=1) / np.sqrt(len(model.estimators_))
    mean_rise = rises.mean(axis=0)
    return np.where(spread > 0, mean_rise / np.where(spread > 0, spread, 1), 0.0)


def forest_importance(frame, outcome, predictors):
    try:
        from sklearn.ensemble import RandomForestRegressor
    except ImportError:
        raise ValueError(
            'Package \'scikit-learn\' is required for method = "forest". Install it with pip install scikit-learn.'
        ) from None
    numbers = importance_frame(frame, outcome, predictors)
    x = numbers[predictors].to_numpy()
    y = numbers[outcome].to_numpy()
    features = max(1, len(predictors) // 3)
    model = RandomForestRegressor(
        n_estimators=FOREST_TREES,
        max_features=features,
        min_samples_leaf=FOREST_LEAF,
        bootstrap=True,
        random_state=np.random.randint(0, 2**31 - 1),
    )
    model.fit(x, y)
    return rescale_importance(predictors, oob_permutation_importance(model, x, y))


def correlation_importance(frame, outcome, predictors):
    numbers = importance_frame(frame, outcome, predictors)
    raw = [abs(np.corrcoef(numbers[name], numbers[outcome])[0, 1]) for name in predictors]
    return rescale_importance(predictors, raw)


def compute_importance(frame, outcome, predictors, method):
    if method == "rwa":
        out = rwa_importance(frame, outcome, predictors)
    elif method == "forest":
        out = forest_importance(frame, outcome, predictors)
    else:
        out = correlation_importance(frame, outcome, predictors)
    return out.sort_values("importance", ascending=False, kind="stable").reset_index(drop=True)


def recode_ratings(frame, columns, likert_levels):
    recoded = frame.copy()
    for name in columns:
        if not is_numeric_vector(recoded[name]):
            recoded[name] = recode_likert(recoded[name], levels=likert_levels).astype(float).to_numpy()
    return recoded


def calc_importance(data=None, outcome=None, predictors=None, method="rwa", recode=True, likert_levels=None):  # lint-style: ignore FN001,FN003
    """Driver importance.

    Ranks how much each predictor drives an outcome such as the NPS rating, as
    importance scores summing to 100. All three methods answer the same question
    and are scaled the same way, so each feature's ``importance`` reads as "this
    feature accounts for X% of what drives the outcome" and any of them can be
    fed to `plot_ipm()`. They differ in what they can see:

    - "rwa", relative weights analysis (Johnson's epsilon), shares out the linear
      model's explained variance between correlated predictors, which ordinary
      regression coefficients handle poorly. This is the default because rating
      batteries are almost always heavily correlated. The port computes it with
      numpy exactly as R's ``rwa`` package does.
    - "forest" grows a random forest and measures how much prediction error rises
      when each predictor is permuted, so it picks up non-linear effects and
      interactions that relative weights cannot. It is the useful cross-check: if
      a feature ranks high here and low under "rwa", its effect is not linear.
      Being a random method, it moves a little between runs; call
      ``numpy.random.seed()`` first for a figure you intend to publish. Python
      draws different random numbers from R, so the values differ from R's
      while the ranking agrees.
    - "correlation" is the crude one, ignoring the other predictors entirely, so
      correlated features double-count. It needs no optional package and cannot
      fail to converge, which makes it a reasonable sanity check.

    Only complete cases are used. Worded rating columns are recoded to 1-5
    automatically (``recode=True``). Negative importances are floored at zero
    before rescaling. Most users call `ipm_model()`, which pairs this with
    performance for the importance/performance matrix.

    Parameters
    ----------
    data : pandas.DataFrame, optional
        A data frame. If omitted, the session default is used.
    outcome : str
        The outcome column, e.g. "nps_value".
    predictors : str, selector or list
        The predictor columns, e.g. ``starts_with("ratings_")``.
    method : str
        "rwa" (default), "forest" (needs scikit-learn) or "correlation".
    recode : bool
        If True (default), text predictor columns are mapped to 1-5 with
        `recode_likert()`; numeric columns are left as-is.
    likert_levels : list of str, optional
        Scale wordings passed to `recode_likert()` when recoding.

    Returns
    -------
    pandas.DataFrame
        ``feature`` and ``importance``, the latter rescaled to sum to 100,
        strongest driver first.

    See Also
    --------
    ipm_model, plot_ipm

    Examples
    --------
    >>> calc_importance(podracing_survey, "nps_value", starts_with("ratings_"))
    >>> import numpy as np
    >>> np.random.seed(1)
    >>> calc_importance(podracing_survey, "nps_value", starts_with("ratings_"), method="forest")
    """
    resolved = resolve_data_columns(data, [outcome, predictors])
    data = resolved["data"]
    method = match_arg(method, METHODS)
    out_name = col_label(resolved["columns"][0], data, argument="outcome")
    pred_names = select_columns(data, resolved["columns"][1])
    if not pred_names:
        raise ValueError("No predictor columns selected.")
    levels = LIKERT_LEVELS if likert_levels is None else likert_levels
    frame = recode_ratings(data, pred_names, levels) if recode else data
    return compute_importance(frame, out_name, pred_names, method)


def cut_perf_band(performance):
    """Bucket a 1-5 mean rating into its performance band by integer part: 3.57 is band 3."""
    bands = [str(int(np.floor(value))) if not np.isnan(value) else np.nan for value in performance]
    return factor(bands, levels=["1", "2", "3", "4", "5"])


def ipm_model(data=None, outcome=None, rating_prefix=None, method="rwa", recode=True, likert_levels=None):  # lint-style: ignore FN001,FN003
    """Build an importance / performance model.

    Combines driver **importance** (against `outcome`) with feature
    **performance** (mean rating) into the table `plot_ipm()` draws. An
    importance/performance model answers two questions per feature at once: how
    much does it drive the outcome (importance, via `calc_importance()`) and how
    well are we doing on it (performance, the mean 1-5 rating). Plotting one
    against the other reveals priorities: high-importance, low-performance
    features are where to invest. Worded rating columns are mapped to 1-5 with
    `recode_likert()` automatically; the prefix is stripped from feature names;
    and ``perf_class`` buckets performance into a 1-5 categorical by its integer
    part (a 3.57 mean is band 3, not 4) for colouring.

    Parameters
    ----------
    data : pandas.DataFrame, optional
        A data frame. If omitted, the session default is used.
    outcome : str
        The outcome column, e.g. "nps_value".
    rating_prefix : str
        Column-name prefix identifying the rating block, e.g. "ratings_".
    method : str
        How to measure importance, passed to `calc_importance()`. Default "rwa".
    recode : bool
        If True (default), text rating columns are mapped to 1-5 with
        `recode_likert()`; numeric columns are left as-is.
    likert_levels : list of str, optional
        Scale wordings passed to `recode_likert()` when recoding.

    Returns
    -------
    pandas.DataFrame
        ``feature``, ``importance``, ``performance`` and ``perf_class`` (the
        performance band as a 1-5 categorical).

    See Also
    --------
    calc_importance, plot_ipm, compare_values

    Examples
    --------
    >>> ipm_model(podracing_survey, "nps_value", "ratings_")
    """
    resolved = resolve_data_columns(data, [outcome, rating_prefix])
    data = resolved["data"]
    method = match_arg(method, METHODS)
    out_name = col_label(resolved["columns"][0], data, argument="outcome")
    rating_prefix = resolved["columns"][1]
    rate_cols = select_columns(data, starts_with(rating_prefix))
    if not rate_cols:
        raise ValueError(f"No columns start with prefix '{rating_prefix}'.")
    levels = LIKERT_LEVELS if likert_levels is None else likert_levels
    frame = recode_ratings(data, rate_cols, levels) if recode else data.copy()
    for name in [out_name] + rate_cols:
        frame[name] = ensure_numeric(frame[name], quiet=True).astype(float).to_numpy()
    performance = {name: r_mean(frame[name]) for name in rate_cols}
    out = compute_importance(frame, out_name, rate_cols, method)
    out["performance"] = [performance[name] for name in out["feature"]]
    out["feature"] = clean_label([name.replace(rating_prefix, "", 1) for name in out["feature"]])
    out["perf_class"] = cut_perf_band(out["performance"]).values
    return out
