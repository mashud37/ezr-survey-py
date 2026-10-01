"""Map ages or birth years onto generational cohorts such as Millennial or Gen Z. Generational reporting reads its cohort labels from here."""

import datetime
import math

import pandas as pd

from .coerce import ensure_numeric
from .config import ezrsurvey_default
from .rbase import cut, match_arg

SCHEMES = ["pew"]


def generation_scheme(scheme="pew"):
    """Generational-cohort definitions.

    Returns the birth-year boundaries for a named generational scheme, for use by
    `recode_generation()`. The "pew" scheme uses the Pew Research Center
    boundaries: Silent (1928-45), Baby Boomer (1946-64), Gen X (1965-80),
    Millennial (1981-96), Gen Z (1997-2012) and Gen Alpha (2013+). To use
    different cut-offs, build your own data frame with ``from`` and ``label``
    columns and pass it to `recode_generation()`'s `scheme` argument.

    Parameters
    ----------
    scheme : str
        Scheme name. Currently "pew".

    Returns
    -------
    pandas.DataFrame
        ``label``, ``from`` (first birth year) and ``to`` (last birth year;
        ``inf`` for the open-ended youngest cohort).

    See Also
    --------
    recode_generation

    Examples
    --------
    >>> generation_scheme("pew")
    """
    scheme = match_arg(scheme, SCHEMES)
    return pd.DataFrame(
        {
            "label": ["Silent", "Baby Boomer", "Gen X", "Millennial", "Gen Z", "Gen Alpha"],
            "from": [1928.0, 1946.0, 1965.0, 1981.0, 1997.0, 2013.0],
            "to": [1945.0, 1964.0, 1980.0, 1996.0, 2012.0, math.inf],
        }
    )


def recode_generation(x, input="age", year=None, scheme=None):  # lint-style: ignore FN001
    """Recode age or birth year into a generational cohort.

    Maps either an **age** (converted to a birth year using a reference year) or
    a **birth year** directly onto a generational cohort such as Millennial or
    Gen Z. Text input like "34 years" is salvaged with `ensure_numeric()`.

    When ``input="age"``, the birth year is ``year - age``, where `year`
    defaults to the ``current_year`` option or the system year, so set
    ``ezrsurvey_options(current_year=2026)`` to keep results stable across runs.
    When ``input="year"``, `x` is treated as the birth year directly. Birth
    years before the earliest cohort return missing. For simple age bands use
    `recode_age()`.

    Parameters
    ----------
    x : list or Series
        Ages or birth years (numbers or coercible text).
    input : str
        What `x` represents: "age" (default) or "year" (birth year).
    year : int, optional
        Reference year for the age-to-birth-year conversion. If None (default),
        uses the ``current_year`` option or the system year.
    scheme : str or pandas.DataFrame, optional
        Either a scheme name passed to `generation_scheme()` (default from the
        ``generation_scheme`` option) or your own data frame with ``from`` and
        ``label`` columns.

    Returns
    -------
    pandas.Series
        Cohort labels; values outside the scheme's range are missing.

    See Also
    --------
    generation_scheme, recode_age, ezrsurvey_options

    Examples
    --------
    >>> recode_generation([1990, 2001, 1968], input="year")
    >>> recode_generation([36, 25], input="age", year=2026)
    """
    input = match_arg(input, ["age", "year"])
    values = ensure_numeric(x, quiet=True)
    if scheme is None:
        scheme = ezrsurvey_default("generation_scheme")
    if isinstance(scheme, str):
        table = generation_scheme(scheme)
    else:
        if not {"from", "label"}.issubset(scheme.columns):
            raise ValueError("A custom `scheme` needs `from` and `label` columns.")
        table = scheme
    table = table.sort_values("from", kind="stable")
    if input == "age":
        reference = year
        if reference is None:
            reference = ezrsurvey_default("current_year")
        if reference is None:
            reference = datetime.date.today().year
        birth = reference - values
    else:
        birth = values
    breaks = list(table["from"]) + [math.inf]
    return cut(birth, breaks=breaks, labels=list(table["label"]), right=False, include_lowest=True)
