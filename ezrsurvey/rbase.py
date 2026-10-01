"""Reproduce the base R behaviours the port depends on: vectors, text, rounding, sorting, binning, messages and user folders. Every other module leans on these so results match R's."""

import math
import os
import platform
import sys
import unicodedata
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

STR_WRAP_WIDTH = 80
SYMBOL_RANK = 0
DIGIT_RANK = 1
LETTER_RANK = 2


def is_missing(value):
    if isinstance(value, str):
        return False
    if value is None or value is pd.NA or value is pd.NaT:
        return True
    if isinstance(value, (float, np.floating)):
        return math.isnan(value)
    return False


def as_series(x):
    """Turn anything vector-like into a pandas Series, as R treats every value as a vector.

    Args:
        x: A Series, a list or tuple, a numpy array, a Categorical, a single value, or None.

    Returns:
        The Series itself when given one, otherwise a new Series holding the values.
    """
    if isinstance(x, pd.Series):
        return x
    if x is None:
        return pd.Series([], dtype=object)
    if isinstance(x, (str, bytes, int, float, bool, np.generic)):
        return pd.Series([x])
    if isinstance(x, (pd.Categorical, pd.Index)):
        return pd.Series(x)
    return pd.Series(list(x))


def is_numeric_vector(values):
    dtype = as_series(values).dtype
    if pd.api.types.is_bool_dtype(dtype):
        return False
    return pd.api.types.is_numeric_dtype(dtype)


def is_categorical(values):
    return isinstance(as_series(values).dtype, pd.CategoricalDtype)


def character_value(value):
    if isinstance(value, str):
        return value
    if is_missing(value):
        return np.nan
    if isinstance(value, (bool, np.bool_)):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (float, np.floating)):
        if math.isinf(value):
            return "Inf" if value > 0 else "-Inf"
        if float(value).is_integer() and abs(value) < 1e15:
            return str(int(value))
        return format(float(value), ".15g")
    if isinstance(value, (int, np.integer)):
        return str(int(value))
    return str(value)


def as_character(x):
    """Convert values to text the way R's as.character() does, keeping missing values missing.

    Args:
        x: Anything as_series() accepts.

    Returns:
        A Series of Python strings and NaN, with the index of `x` when it was a Series.
    """
    values = as_series(x)
    if is_categorical(values):
        values = values.astype(object)
    return pd.Series([character_value(value) for value in values], index=values.index, dtype=object)


def round_value(value, digits):
    """One number rounded by R's algorithm: the nearer of the two candidates, ties to the even one.

    R measures "nearer" in double arithmetic, so 6.325 is a tie that goes to 6.32,
    where Python's round() sees the binary value's excess and gives 6.33.
    """
    if is_missing(value):
        return np.nan
    value = float(value)
    if not math.isfinite(value) or value == 0:
        return value
    if digits == 0:
        return float(round(value))
    sign = -1.0 if value < 0 else 1.0
    value = abs(value)
    if digits + math.log10(2) * (0.5 + math.frexp(value)[1] - 1) > 15:
        return sign * value
    power = 10.0**digits
    scaled = power * value
    lower = math.floor(scaled)
    down = lower / power
    up = math.ceil(scaled) / power
    distance_up = up - value
    distance_down = value - down
    if distance_up < distance_down or (distance_up == distance_down and lower % 2 == 1):
        return sign * up
    return sign * down


def r_round(x, digits=0):
    """Round as R's round() does, number by number.

    Args:
        x: A number, or a Series of numbers.
        digits: Decimal places to keep.

    Returns:
        A float, or a float Series with the index of `x`.
    """
    digits = int(math.floor(digits + 0.5))
    if isinstance(x, pd.Series):
        return pd.Series([round_value(value, digits) for value in x], index=x.index, dtype=float)
    return round_value(x, digits)


def present_numbers(values):
    return [float(value) for value in values if not is_missing(value)]


def r_sum(values):
    """The sum as R's sum() gets it: accumulated beyond double precision, then rounded once.

    An infinite value makes the sum infinite, or NaN when both infinities are present, as in R.
    """
    numbers = present_numbers(values)
    if all(math.isfinite(number) for number in numbers):
        return math.fsum(numbers)
    return float(sum(numbers))


def r_mean(values):
    """The mean of the non-missing values as R's mean(na.rm = TRUE) computes it; NaN when there are none."""
    numbers = present_numbers(values)
    if not numbers:
        return np.nan
    mean = r_sum(numbers) / len(numbers)
    if not math.isfinite(mean):
        return mean
    return mean + math.fsum(number - mean for number in numbers) / len(numbers)


def r_sd(values):
    """The sample standard deviation of the non-missing values, as R's sd(na.rm = TRUE)."""
    numbers = present_numbers(values)
    if len(numbers) < 2:
        return np.nan
    mean = r_mean(numbers)
    return math.sqrt(math.fsum((number - mean) ** 2 for number in numbers) / (len(numbers) - 1))


def r_quantile(values, p):
    """The p-th quantile of the non-missing values by R's default method (type 7)."""
    numbers = sorted(present_numbers(values))
    if not numbers:
        return np.nan
    index = (len(numbers) - 1) * p
    low = math.floor(index)
    high = math.ceil(index)
    share = index - low
    if high == low or numbers[high] == numbers[low]:
        return numbers[low]
    return (1 - share) * numbers[low] + share * numbers[high]


def r_median(values):
    numbers = sorted(present_numbers(values))
    if not numbers:
        return np.nan
    middle = len(numbers) // 2
    if len(numbers) % 2 == 1:
        return numbers[middle]
    return r_mean(numbers[middle - 1 : middle + 1])


def sort_key(text):
    """The key R's English collation sorts text by: symbols before digits before letters.

    Letters compare without case or accents first, so "apple" sorts before "Banana";
    ties then go to the unaccented and the lower-case spelling.
    """
    primary = []
    accents = []
    cases = []
    for character in str(text):
        base = unicodedata.normalize("NFKD", character)[0]
        if base.isalpha():
            primary.append((LETTER_RANK, base.casefold()))
        elif base.isdigit():
            primary.append((DIGIT_RANK, base))
        else:
            primary.append((SYMBOL_RANK, base))
        accents.append(0 if base == character else 1)
        cases.append(0 if character.islower() or not character.isalpha() else 1)
    return (primary, accents, cases, str(text))


def r_sort(values, decreasing=False):
    """Sort text as R's sort() does in an English session, dropping missing values."""
    kept = [value for value in values if not is_missing(value)]
    return sorted(kept, key=sort_key, reverse=decreasing)


def match_arg(value, choices):
    """Check a choice argument as R's match.arg() does, allowing an unambiguous abbreviation.

    Args:
        value: The caller's choice; None means the first choice.
        choices: The allowed values.

    Returns:
        The matched choice.

    Raises:
        ValueError: `value` matches none of `choices`, in R's wording.
    """
    if value is None:
        return choices[0]
    if value in choices:
        return value
    if isinstance(value, str) and value != "":
        partial = [choice for choice in choices if choice.startswith(value)]
        if len(partial) == 1:
            return partial[0]
    quoted = ", ".join(f'"{choice}"' for choice in choices)
    raise ValueError(f"'arg' should be one of {quoted}")


def unique_values(values):
    """The distinct non-missing values in order of first appearance, as R's unique() keeps them."""
    seen = []
    for value in values:
        if not is_missing(value) and value not in seen:
            seen.append(value)
    return seen


def factor(values, levels=None, ordered=False):
    """Make a categorical Series as R's factor() does: unlisted values become missing.

    Args:
        values: Anything as_series() accepts.
        levels: The categories in order; by default the sorted distinct values.
        ordered: Mark the categories as ordered, as R's ordered factors are.

    Returns:
        A categorical Series with the index of `values`.
    """
    series = as_series(values)
    if is_categorical(series):
        series = series.astype(object)
    if levels is None:
        distinct = unique_values(series)
        if distinct and all(isinstance(value, str) for value in distinct):
            levels = r_sort(distinct)
        else:
            levels = sorted(distinct)
    levels = [level for level in levels if not is_missing(level)]
    cleaned = [value if value in levels else np.nan for value in series]
    categories = pd.Categorical(cleaned, categories=levels, ordered=ordered)
    return pd.Series(categories, index=series.index)


def factor_levels(values):
    """The levels of a categorical Series, or the distinct values in order of appearance otherwise."""
    series = as_series(values)
    if is_categorical(series):
        return list(series.cat.categories)
    return unique_values(as_character(series))


def table_desc(values):
    """Count each distinct value, largest count first, as R's sort(table(x), decreasing = TRUE).

    Ties keep R's alphabetical order of the values.

    Returns:
        A list of (value, count) pairs.
    """
    counts = {}
    for value in values:
        if not is_missing(value):
            counts[value] = counts.get(value, 0) + 1
    names = r_sort(counts.keys())
    ranked = sorted(names, key=lambda name: -counts[name])
    return [(name, counts[name]) for name in ranked]


def make_unique(names, sep="."):
    """Make names unique as R's make.unique() does: later repeats gain a counter suffix."""
    seen = set(names)
    counts = {}
    used = set()
    out = []
    for name in names:
        if name not in used:
            used.add(name)
            out.append(name)
            continue
        counter = counts.get(name, 0)
        candidate = name
        while candidate in used or candidate in seen:
            counter += 1
            candidate = f"{name}{sep}{counter}"
        counts[name] = counter
        used.add(candidate)
        out.append(candidate)
    return out


def cut(values, breaks, labels, right=True, include_lowest=False):
    """Bin numbers into labelled intervals exactly as R's cut() does with explicit breaks.

    Args:
        values: Numbers to bin; missing values stay missing.
        breaks: Interval boundaries; they are sorted first, as R does.
        labels: One label per interval.
        right: Close intervals on the right (True) or on the left (False).
        include_lowest: Close the outermost interval on its open side too.

    Returns:
        A Series of labels, missing where a value falls outside every interval.
    """
    series = as_series(values)
    edges = sorted(float(edge) for edge in breaks)
    out = []
    for value in series:
        if is_missing(value):
            out.append(np.nan)
            continue
        out.append(interval_label(float(value), edges, labels, right, include_lowest))
    return pd.Series(out, index=series.index, dtype=object)


def interval_label(value, edges, labels, right, include_lowest):
    last = len(edges) - 2
    for i in range(len(edges) - 1):
        low = edges[i]
        high = edges[i + 1]
        if right:
            inside = low < value <= high
            if include_lowest and i == 0:
                inside = low <= value <= high
        else:
            inside = low <= value < high
            if include_lowest and i == last:
                inside = low <= value <= high
        if inside:
            return labels[i]
    return np.nan


def strwrap(text, width, exdent=0):
    """Wrap text as R's strwrap() does: words joined greedily into lines shorter than `width`."""
    words = str(text).split()
    lines = []
    current = ""
    for word in words:
        indent = 0 if not lines else exdent
        candidate = word if not current else current + " " + word
        if current and indent + len(candidate) >= width:
            lines.append(" " * indent + current)
            current = word
        else:
            current = candidate
    if current or not lines:
        indent = 0 if not lines else exdent
        lines.append(" " * indent + current)
    return lines


def str_wrap(text, width=STR_WRAP_WIDTH):
    """Wrap text as stringr's str_wrap() does: lines of at most `width` characters joined by newlines."""
    if is_missing(text):
        return text
    words = str(text).split()
    lines = []
    current = ""
    for word in words:
        candidate = word if not current else current + " " + word
        if current and len(candidate) > width:
            lines.append(current)
            current = word
        else:
            current = candidate
    lines.append(current)
    return "\n".join(lines)


def message(*parts):
    """Write one line to stderr, as R's message() does, so it never lands in a result."""
    print("".join(str(part) for part in parts), file=sys.stderr)


def warn(text):
    warnings.warn(text, UserWarning, stacklevel=3)


def interactive():
    """Tell whether a person is at the console, as R's interactive() does."""
    if hasattr(sys, "ps1") or sys.flags.interactive:
        return True
    shell = sys.modules.get("IPython")
    if shell is None:
        return False
    return shell.get_ipython() is not None


def home_dir():
    for variable in ("R_USER", "HOME"):
        if os.environ.get(variable):
            return Path(os.environ[variable])
    return Path.home()


def r_user_dir(which):
    """The folder R's tools::R_user_dir("ezrsurvey", which) names, so R and Python share it.

    Args:
        which: "config", "data" or "cache".

    Returns:
        The folder as a Path; it is not created here.
    """
    system = platform.system()
    homes = {
        "config": ("R_USER_CONFIG_DIR", "XDG_CONFIG_HOME", "APPDATA", ["R", "config"], ["Library", "Preferences", "org.R-project.R"], [".config"]),
        "data": ("R_USER_DATA_DIR", "XDG_DATA_HOME", "APPDATA", ["R", "data"], ["Library", "Application Support", "org.R-project.R"], [".local", "share"]),
        "cache": ("R_USER_CACHE_DIR", "XDG_CACHE_HOME", "LOCALAPPDATA", ["R", "cache"], ["Library", "Caches", "org.R-project.R"], [".cache"]),
    }
    own, xdg, windows_root, windows_parts, mac_parts, unix_parts = homes[which]
    if os.environ.get(own):
        base = Path(os.environ[own])
    elif os.environ.get(xdg):
        base = Path(os.environ[xdg])
    elif system == "Windows":
        base = Path(os.environ.get(windows_root, str(Path.home()))).joinpath(*windows_parts)
    elif system == "Darwin":
        base = home_dir().joinpath(*mac_parts)
    else:
        base = home_dir().joinpath(*unix_parts)
    return base / "R" / "ezrsurvey"
