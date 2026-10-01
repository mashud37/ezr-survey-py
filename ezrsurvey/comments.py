"""Pick presentable open-text comments: a random sample, or a varied and informative one. Quote slides and the quote treemap are built from these."""

import re

import numpy as np
import pandas as pd

from .dataset import resolve_data_dots
from .datasets import DATA_FOLDER
from .progress import progress_note
from .rbase import match_arg, r_sort
from .recode import na_blank
from .select import select_columns
from .tables import group_positions

METHODS = ["mmr", "entropy"]
SCORES = ["entropy", "tfidf"]
TOKEN_PATTERN = re.compile(r"[^a-z0-9' ]")
SAMPLE_SIZE = 8
MIN_CHARS = 30
MAX_CHARS = 400
DIVERSITY_LAMBDA = 0.6
MAX_CANDIDATES = 500


def resolve_stopwords(stopwords=None):
    """The stop-word set: yours, none (False), or the bundled English list R users get."""
    if stopwords is False:
        return []
    if stopwords is not None:
        return [word.lower() for word in ([stopwords] if isinstance(stopwords, str) else stopwords)]
    return (DATA_FOLDER / "stopwords-en.txt").read_text(encoding="utf-8").split()


def random_source(seed):
    """Seeded draws for reproducible sampling; numpy's shared generator when no seed is given."""
    if seed is None:
        return np.random.default_rng(np.random.randint(0, 2**31 - 1))
    return np.random.default_rng(seed)


def truncate(text, width):
    if len(text) <= width:
        return text
    return text[: width - 3] + "..."


def prep_comments(data, cols, trim, by=None):
    """Stack the comment columns into one table: blanks, short answers and excluded terms removed.

    Args:
        data: The survey data.
        cols: The comment columns.
        trim: ``min_chars``, ``max_chars`` and ``exclude``, as the samplers take them.
        by: Grouping columns to carry along.
    """
    min_chars = trim["min_chars"]
    max_chars = trim["max_chars"]
    exclude = trim["exclude"]
    if not cols:
        raise ValueError("Select at least one comment column.")
    keep = [] if by is None else list(by)
    texts = {column: na_blank(data[column]).tolist() for column in cols}
    group_values = {column: data[column].tolist() for column in keep}
    pattern = None
    if exclude:
        terms = [exclude] if isinstance(exclude, str) else list(exclude)
        pattern = re.compile("|".join(terms).lower())
    rows = []
    for position in range(len(data)):
        for column in cols:
            comment = texts[column][position]
            if not isinstance(comment, str) or len(comment) <= min_chars:
                continue
            if pattern is not None and pattern.search(comment.lower()):
                continue
            row = {name: group_values[name][position] for name in keep}
            row["source"] = column
            row["comment"] = truncate(comment, max_chars)
            row["length"] = len(row["comment"])
            rows.append(row)
    return pd.DataFrame(rows, columns=keep + ["source", "comment", "length"])


def sample_comments(  # lint-style: ignore FN001
    data=None,
    *columns,
    n=SAMPLE_SIZE,
    min_chars=MIN_CHARS,
    max_chars=MAX_CHARS,
    exclude=None,
    by_column=True,
    by=None,
    seed=None,
):
    """Pick a random sample of open-text comments.

    Pulls a tidy, presentation-ready sample of comments out of one or more
    free-text columns, applying the usual clean-ups: drop blanks and very short
    answers, optionally exclude comments matching unwanted terms, and truncate to
    a maximum length. With ``by_column=True`` you get `n` from each source
    column (e.g. an even split across ``nps_com`` and ``show_com``); with False,
    `n` from the pooled set. The result feeds `plot_quotes_tree()`. For a set
    that is varied rather than uniformly random, use `sample_comments_diverse()`.

    Python draws different random numbers from R, so the same `seed` picks
    different comments than it does in R, equally at random.

    Parameters
    ----------
    data : pandas.DataFrame, optional
        A data frame. If omitted, the session default is used.
    *columns : str or selector
        One or more comment columns, e.g. "nps_com", "show_com", or
        ``ends_with("_com")``.
    n : int
        Number of comments to sample. With ``by_column=True``, this is per
        column.
    min_chars : int
        Drop comments with this many characters or fewer. Default 30.
    max_chars : int
        Truncate longer comments to this length. Default 400.
    exclude : str or list of str, optional
        Case-insensitive regular expressions; comments matching any are
        dropped (e.g. ``["friend", "recommend"]``).
    by_column : bool
        If True (default), sample `n` from each column; if False, sample `n`
        from the pooled comments.
    by : str, optional
        Grouping column, e.g. an NPS group. Sampling then takes `n` from each
        group, and the group is kept as a column of the result.
    seed : int, optional
        Seed for reproducible sampling. Without one, numpy's shared random
        generator is used (see ``numpy.random.seed()``).

    Returns
    -------
    pandas.DataFrame
        ``source``, ``comment`` and ``length``, plus the `by` column when one
        is given.

    See Also
    --------
    sample_comments_diverse, plot_quotes_tree

    Examples
    --------
    >>> sample_comments(podracing_survey, "nps_com", "show_com", n=3)
    >>> grouped = podracing_survey.assign(group=nps_group(podracing_survey["nps_value"], labels=True))
    >>> sample_comments(grouped.dropna(subset=["group"]), "nps_com", n=3, by="group")
    """
    resolved = resolve_data_dots(data, columns)
    data = resolved["data"]
    rng = random_source(seed)
    cols = select_columns(data, resolved["selections"])
    by_col = select_columns(data, by) if by is not None else []
    trim = {"min_chars": min_chars, "max_chars": max_chars, "exclude": exclude}
    long = prep_comments(data, cols, trim, by_col)
    if len(long) == 0:
        return long
    groups = (["source"] if by_column else []) + by_col
    picked = []
    for group in group_positions(long, groups):
        positions = group["positions"]
        size = min(n, len(positions))
        picked.extend(rng.choice(positions, size=size, replace=False).tolist())
    return long.iloc[picked].reset_index(drop=True)


def tokenize_comments(comments, stopset=()):
    """Words of three or more letters, lower-cased, each counted once per comment, stop-words removed."""
    tokens = []
    for comment in comments:
        cleaned = TOKEN_PATTERN.sub(" ", comment.lower())
        words = []
        for word in cleaned.split():
            if len(word) > 2 and word not in stopset and word not in words:
                words.append(word)
        tokens.append(words)
    return tokens


def build_tfidf(comments, stopset=()):
    """Term-presence and row-normalised TF-IDF matrices, with smoothed IDF as R's version computes it.

    Returns:
        A dict with ``tf``, ``tfidf`` (numpy arrays, one row per comment) and
        the sorted ``vocab``, or None when no comment has a usable word.
    """
    tokens = tokenize_comments(comments, set(stopset))
    words_used = set()
    for words in tokens:
        words_used.update(words)
    vocab = r_sort(words_used)
    if not vocab:
        return None
    column = {word: j for j, word in enumerate(vocab)}
    tf = np.zeros((len(comments), len(vocab)))
    for i, words in enumerate(tokens):
        for word in words:
            tf[i, column[word]] += 1
    document_frequency = (tf > 0).sum(axis=0)
    idf = np.log((1 + len(comments)) / (1 + document_frequency)) + 1
    tfidf = tf * idf
    norms = np.sqrt((tfidf**2).sum(axis=1))
    norms[norms == 0] = 1
    return {"tf": tf, "tfidf": tfidf / norms[:, None], "vocab": vocab}


def shannon_bits(tf_row):
    counts = tf_row[tf_row > 0]
    if len(counts) == 0:
        return 0.0
    shares = counts / counts.sum()
    return float(-(shares * np.log2(shares)).sum())


def select_diverse(tfidf, info, n, lam, rng):
    """Maximal-marginal-relevance picks with a randomised draw: informative and unlike those already chosen."""
    count = tfidf.shape[0]
    similarity = tfidf @ tfidf.T
    spread = info.max() - info.min()
    info_scaled = np.full(count, 0.5) if spread == 0 else (info - info.min()) / spread
    selected = []
    remaining = list(range(count))
    while len(selected) < min(n, count):
        if selected:
            max_similarity = similarity[np.ix_(remaining, selected)].max(axis=1)
        else:
            max_similarity = np.zeros(len(remaining))
        score = lam * info_scaled[remaining] - (1 - lam) * max_similarity
        probabilities = np.exp(score - score.max())
        probabilities = probabilities / probabilities.sum()
        pick = remaining[rng.choice(len(remaining), p=probabilities)]
        selected.append(pick)
        remaining.remove(pick)
    return selected


def sample_comments_diverse(  # lint-style: ignore FN001
    data=None,
    *columns,
    n=SAMPLE_SIZE,
    min_chars=MIN_CHARS,
    max_chars=MAX_CHARS,
    exclude=None,
    lambda_=DIVERSITY_LAMBDA,
    method="mmr",
    score="entropy",
    stopwords=None,
    max_candidates=MAX_CANDIDATES,
    seed=None,
):
    """Pick a diverse, information-rich sample of comments.

    A smarter alternative to `sample_comments()`: instead of sampling uniformly,
    it scores each comment and selects a set that is both **informative** and
    **varied**, so a quote slide isn't five ways of saying the same thing.
    Scoring is lexical: comments are turned into TF-IDF vectors, an information
    score is computed (Shannon entropy of the word distribution, or TF-IDF
    mass), and a randomised maximal-marginal-relevance pass trades off
    informativeness against similarity to already-picked comments. The same
    sentence is never picked twice.

    The trade-off argument is ``lambda_`` because ``lambda`` is a Python
    keyword; R names it ``lambda``. Python draws different random numbers from
    R, so the same `seed` picks a different (equally varied) set.

    Parameters
    ----------
    data : pandas.DataFrame, optional
        A data frame. If omitted, the session default is used.
    *columns : str or selector
        One or more comment columns.
    n, min_chars, max_chars, exclude
        As in `sample_comments()`.
    lambda_ : float
        Diversity/informativeness trade-off in [0, 1] for ``method="mmr"``:
        higher favours informative comments, lower favours dissimilar ones.
        Default 0.6.
    method : str
        "mmr" (default) for the diversity-aware greedy selection, or "entropy"
        to weight a random sample by each comment's information score.
    score : str
        How to measure information: "entropy" (default, Shannon bits) or
        "tfidf" (summed TF-IDF weight).
    stopwords : list of str or bool, optional
        None (default) uses the English Snowball list, as R's stopwords package
        supplies it; a list supplies your own; False disables removal.
    max_candidates : int
        Largest number of comments compared with one another (default 500). A
        bigger corpus is narrowed to a random shortlist of this size first,
        because the comparison grows with the square of the number kept.
    seed : int, optional
        Seed for reproducible sampling.

    Returns
    -------
    pandas.DataFrame
        ``source``, ``comment``, ``length`` and the ``info`` score, ordered by
        selection.

    See Also
    --------
    sample_comments, plot_quotes_tree

    Examples
    --------
    >>> sample_comments_diverse(podracing_survey, "nps_com", "show_com", n=5, seed=1)
    """
    resolved = resolve_data_dots(data, columns)
    data = resolved["data"]
    method = match_arg(method, METHODS)
    score = match_arg(score, SCORES)
    rng = random_source(seed)
    cols = select_columns(data, resolved["selections"])
    trim = {"min_chars": min_chars, "max_chars": max_chars, "exclude": exclude}
    long = prep_comments(data, cols, trim)
    long = long.drop_duplicates(subset="comment", keep="first").reset_index(drop=True)
    if len(long) <= n:
        long["info"] = np.nan
        return long
    if len(long) > max_candidates:
        progress_note(f"Scoring a random {max_candidates} of {len(long)} comments. Raise `max_candidates` to widen the shortlist.")
        shortlist = rng.choice(len(long), size=max_candidates, replace=False)
        long = long.iloc[shortlist].reset_index(drop=True)
    progress_note(f"Comparing {len(long)} comments to pick {n}.")
    matrices = build_tfidf(long["comment"].tolist(), resolve_stopwords(stopwords))
    if matrices is None:
        out = long.iloc[rng.choice(len(long), size=n, replace=False)].reset_index(drop=True)
        out["info"] = np.nan
        return out
    if score == "entropy":
        info = np.array([shannon_bits(row) for row in matrices["tf"]])
    else:
        info = matrices["tfidf"].sum(axis=1)
    if method == "mmr":
        chosen = select_diverse(matrices["tfidf"], info, n, lambda_, rng)
    else:
        weights = info - info.min() + 1e-6
        chosen = rng.choice(len(long), size=n, replace=False, p=weights / weights.sum()).tolist()
    out = long.iloc[chosen].reset_index(drop=True)
    out["info"] = info[chosen]
    return out
