"""Build the market-research banner table: questions down the side, groups across the top, an Overall column first. Long runs report progress, confirm automatic selections and can resume from a checkpoint."""

import glob
import hashlib
import os
import pickle

import numpy as np
import pandas as pd

from .auto_select import col_kind, detect_multiselect, multiselect_label
from .coerce import ensure_numeric
from .confirm import confirm_lines, confirm_on, confirm_selection
from .crosstab import crosstab
from .dataset import resolve_data
from .percentage import calc_percentage_multi
from .progress import progress_done, progress_item, progress_note, progress_plan, progress_start
from .rbase import (
    as_character,
    factor_levels,
    make_unique,
    match_arg,
    message,
    r_mean,
    r_median,
    r_quantile,
    r_round,
    r_sd,
    r_user_dir,
)
from .recode import na_blank
from .select import select_columns
from .weights import resolve_weights, weighted_mean, wtd_median, wtd_quantile, wtd_sd

CELLS = ["auto", "pct", "count", "mean", "diff"]
STATS = ["mean", "median", "sd", "p25", "p75"]
LONG_COLUMNS = ["variable", "item", "group", "group_item", "value"]
MAX_LEVELS = 20


def plain_stat(numbers, stat):
    if stat == "mean":
        return r_mean(numbers)
    if stat == "median":
        return r_median(numbers)
    if stat == "sd":
        return r_sd(numbers)
    return r_quantile(numbers, 0.25 if stat == "p25" else 0.75)


def weighted_stat(numbers, weights, stat):
    if stat == "mean":
        kept = ~np.isnan(numbers)
        return weighted_mean(numbers[kept], weights[kept]) if kept.any() else np.nan
    if stat == "median":
        return wtd_median(numbers, weights)
    if stat == "sd":
        return wtd_sd(numbers, weights)
    return wtd_quantile(numbers, weights, 0.25 if stat == "p25" else 0.75)


def banner_numeric_stats(x, weights, which, digits):
    """The chosen statistics of a numeric column, weighted when `weights` is given, in `which` order."""
    numbers = ensure_numeric(pd.Series(list(x)), quiet=True).to_numpy(dtype=float)
    out = {}
    for stat in which:
        if weights is None:
            value = plain_stat(numbers, stat)
        else:
            value = weighted_stat(numbers, np.asarray(weights, dtype=float), stat)
        out[stat] = r_round(value, digits)
    return out


def banner_is_numeric(data, variable, cell):
    numeric = pd.api.types.is_numeric_dtype(data[variable]) and not pd.api.types.is_bool_dtype(data[variable])
    if cell == "mean":
        if not numeric:
            raise ValueError(f"cell = \"mean\" needs a numeric column, but '{variable}' is not numeric.")
        return True
    if cell in ("pct", "count"):
        return False
    return numeric


def fill_grid(variable, group, items, group_items, seen):
    """Every item crossed with every group item, taking seen values and filling the rest with 0."""
    rows = []
    for item in items:
        for group_item in group_items:
            rows.append(
                {
                    "variable": variable,
                    "item": item,
                    "group": group,
                    "group_item": group_item,
                    "value": seen.get((item, group_item), 0),
                }
            )
    return rows


def banner_block_cat(d_all, variable, settings):
    """One categorical question as column percentages (or counts) within Overall and each group."""
    mode = "count" if settings["cell"] == "count" else "col_pct"
    rows = []
    item_levels = None
    for group in [".overall"] + list(settings["col_vars"]):
        if group != ".overall" and group == variable:
            continue
        across = ".all" if group == ".overall" else group
        table = crosstab(
            d_all,
            variable,
            across,
            cell=mode,
            wide=False,
            na_rm=settings["na_rm"],
            drop=settings["drop"],
            weights=settings["weights"],
            digits=settings["pct_digits"],
        )
        if item_levels is None:
            item_levels = factor_levels(table[variable])
        group_items = ["Overall"] if group == ".overall" else settings["group_levels"][group]
        seen = {}
        for item, group_item, value in zip(as_character(table[variable]), as_character(table[across]), table["value"]):
            label = "Overall" if group == ".overall" else group_item
            seen[(item, label)] = value
        rows.extend(fill_grid(variable, group, item_levels, group_items, seen))
    return {"rows": rows, "item_levels": item_levels}


def stat_rows(variable, group, group_item, stats):
    rows = []
    for stat, value in stats.items():
        rows.append({"variable": variable, "item": stat, "group": group, "group_item": group_item, "value": value})
    return rows


def banner_block_num(data, variable, settings):
    """One numeric question as a statistics block for Overall and within each group."""
    which = settings["which"]
    digits = settings["num_digits"]
    all_weights = resolve_weights(data, settings["weights"])
    x = data[variable].reset_index(drop=True)
    overall = banner_numeric_stats(x, all_weights, which, digits)
    rows = stat_rows(variable, ".overall", "Overall", overall)
    for group in settings["col_vars"]:
        if group == variable:
            continue
        group_values = list(na_blank(data[group]))
        for group_item in settings["group_levels"][group]:
            positions = [i for i, value in enumerate(group_values) if value == group_item]
            group_weights = None if all_weights is None else np.asarray(all_weights)[positions]
            stats = banner_numeric_stats(x.iloc[positions], group_weights, which, digits)
            rows.extend(stat_rows(variable, group, group_item, stats))
    return {"rows": rows, "item_levels": list(which)}


def banner_block_multi(data, prefix, settings):
    """One check-all-that-apply question: each option's share of the respondents who ticked any."""
    value_column = "n" if settings["cell"] == "count" else "pct"
    drop = settings["drop"]
    digits = settings["pct_digits"]
    label = multiselect_label(prefix)
    overall = calc_percentage_multi(data, prefix, drop=drop, digits=digits)
    item_levels = list(as_character(overall["option"]))
    rows = []
    for item, value in zip(item_levels, overall[value_column]):
        rows.append({"variable": label, "item": item, "group": ".overall", "group_item": "Overall", "value": value})
    for group in settings["col_vars"]:
        table = calc_percentage_multi(data, prefix, by=group, drop=drop, digits=digits)
        seen = {}
        for item, group_item, value in zip(as_character(table["option"]), as_character(table[group]), table[value_column]):
            seen[(item, group_item)] = value
        rows.extend(fill_grid(label, group, item_levels, settings["group_levels"][group], seen))
    return {"rows": rows, "item_levels": item_levels}


def banner_assemble_wide(long, row_keys, col_vars, group_levels, total):
    """Spread the long banner into the master table, recording each column's group in attrs."""
    specs = []
    if total:
        specs.append({"group": "Overall", "label": "Overall", "source": ".overall", "group_item": "Overall"})
    for group in col_vars:
        for group_item in group_levels[group]:
            specs.append({"group": group, "label": group_item, "source": group, "group_item": group_item})
    labels = [spec["label"] for spec in specs]
    col_names = make_unique(labels, sep=" ")
    lookup = {}
    for row in long.itertuples(index=False):
        lookup[(row.group, row.group_item, row.variable, row.item)] = row.value
    columns = {"variable": list(row_keys["variable"]), "item": list(row_keys["item"])}
    for name, spec in zip(col_names, specs):
        values = []
        for variable, item in zip(row_keys["variable"], row_keys["item"]):
            values.append(lookup.get((spec["source"], spec["group_item"], variable, item), np.nan))
        columns[name] = values
    wide = pd.DataFrame(columns)
    wide.attrs["banner_spanners"] = pd.DataFrame(
        {"col": col_names, "group": [spec["group"] for spec in specs], "label": labels}
    )
    return wide


def banner_table(wide):
    """The wide banner with a two-row header: each grouping variable spanning its items."""
    spanners = wide.attrs["banner_spanners"]
    groups = {"variable": "Variable", "item": "Item"}
    labels = {"variable": "Variable", "item": "Item"}
    for col, group, label in zip(spanners["col"], spanners["group"], spanners["label"]):
        groups[col] = group
        labels[col] = label
    table = wide.copy()
    table.columns = pd.MultiIndex.from_tuples([(groups[name], labels[name]) for name in wide.columns])
    return table


def block_members(multi):
    """Every column that belongs to one of the multi-select blocks."""
    members = []
    for columns in multi.values():
        members.extend(columns)
    return members


def banner_auto_select(data, max_levels):
    """The default questions and groups when the caller names none, and what was skipped."""
    multi = detect_multiselect(data)
    consumed = block_members(multi)
    names = [str(name) for name in data.columns]
    kinds = []
    for name in names:
        if name not in consumed:
            kind = col_kind(data[name])
            kind["name"] = name
            kinds.append(kind)
    cols = []
    rows = []
    for kind in kinds:
        small = kind["nd"] <= max_levels
        if kind["kind"] in ("categorical", "numeric") and small:
            cols.append(kind["name"])
        if kind["kind"] == "numeric" or (kind["kind"] == "categorical" and small):
            rows.append(kind["name"])
    used = set(consumed) | set(cols) | set(rows)
    skipped = [name for name in names if name not in used]
    return {"rows": rows, "cols": cols, "multi": multi, "skipped": skipped}


def banner_fingerprint(data, labels, settings):
    """What a saved run must match before any of it is reused: the data and every shaping argument."""
    shaping = [settings[name] for name in ("col_vars", "cell", "which", "total", "na_rm", "drop", "digits")]
    digest = hashlib.sha256()
    digest.update(pd.util.hash_pandas_object(data.astype(object), index=False).values.tobytes())
    digest.update(repr((list(data.columns), labels, shaping, "banner-v1")).encode("utf-8"))
    return digest.hexdigest()


def banner_checkpoint_path(checkpoint, fingerprint):
    if checkpoint is None or checkpoint is False:
        return None
    if checkpoint is True:
        return str(r_user_dir("cache") / f"banner-{fingerprint[:16]}.pkl")
    if isinstance(checkpoint, (str, os.PathLike)):
        return str(checkpoint)
    raise ValueError(f"`checkpoint` must be True, False, or a single file path, not {type(checkpoint).__name__}.")


def banner_checkpoint_load(path, fingerprint):
    """Pick up an interrupted run; a checkpoint from a different run is discarded, never blended in."""
    empty = {"blocks": [], "row_keys": [], "finished": []}
    if path is None or not os.path.exists(path):
        return empty
    try:
        with open(path, "rb") as handle:
            saved = pickle.load(handle)
    except (OSError, pickle.UnpicklingError, EOFError):
        saved = None
    if not isinstance(saved, dict) or saved.get("fingerprint") != fingerprint:
        progress_note("Checkpoint at ", path, " belongs to a different run; starting over.")
        return empty
    return {"blocks": saved["blocks"], "row_keys": saved["row_keys"], "finished": saved["finished"]}


def banner_checkpoint_save(path, fingerprint, finished, blocks, row_keys):
    """Record what is done so far, through a neighbouring temporary file so a crash cannot half-write it."""
    if path is None:
        return False
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    part = path + ".part"
    with open(part, "wb") as handle:
        pickle.dump({"fingerprint": fingerprint, "finished": finished, "blocks": blocks, "row_keys": row_keys}, handle)
    os.replace(part, path)
    return True


def banner_checkpoint_clear(ours, path):
    if ours and path is not None and os.path.exists(path):
        os.remove(path)


def clear_checkpoints():
    """Delete saved cross-tab checkpoints.

    Removes the checkpoint files that ``crosstab_banner(checkpoint=True)`` keeps
    in the ezrsurvey cache folder (the folder R's ``tools::R_user_dir()``
    names). A finished run clears its own checkpoint, so anything left is from a
    run that was interrupted and never repeated; this empties the folder in one
    call. A checkpoint you pointed somewhere yourself
    (``checkpoint="my-run.pkl"``) is your file and is never touched.

    Returns
    -------
    int
        The number of files removed.

    See Also
    --------
    crosstab_banner, clear_weights_cache

    Examples
    --------
    >>> clear_checkpoints()  # doctest: +SKIP
    """
    files = glob.glob(str(r_user_dir("cache") / "banner-*.pkl"))
    for path in files:
        os.remove(path)
    message(f"Removed {len(files)} checkpoint file(s).")
    return len(files)


def group_levels_for(d_all, col_vars, na_rm, drop):
    levels = {}
    for group in col_vars:
        table = crosstab(d_all, group, ".all", cell="count", wide=False, na_rm=na_rm, drop=drop)
        levels[group] = factor_levels(table[group])
    return levels


def stub_specs(data, row_singles, multi):
    """The stub questions in column order: single variables and multi-select blocks."""
    names = [str(name) for name in data.columns]
    specs = []
    for name in row_singles:
        specs.append({"type": "single", "label": name, "pos": names.index(name)})
    for prefix, members in multi.items():
        specs.append({"type": "multi", "label": prefix, "pos": min(names.index(name) for name in members)})
    return sorted(specs, key=lambda spec: spec["pos"])


def build_block(data, d_all, spec, settings):
    """One question's block, by its kind: multi-select, numeric statistics, or categorical percentages."""
    if spec["type"] == "multi":
        return banner_block_multi(data, spec["label"], settings)
    if banner_is_numeric(data, spec["label"], settings["cell"]):
        return banner_block_num(data, spec["label"], settings)
    return banner_block_cat(d_all, spec["label"], settings)


def check_stats(stats):
    if stats is None:
        return list(STATS)
    stats = [stats] if isinstance(stats, str) else list(stats)
    return [match_arg(stat, STATS) for stat in stats]


def resolve_selection(data, rows, cols, max_levels):
    auto = rows is None or cols is None
    selection = banner_auto_select(data, max_levels) if auto else None
    if rows is None:
        row_singles = selection["rows"]
        multi = selection["multi"]
    else:
        raw = select_columns(data, rows)
        multi = detect_multiselect(data, raw)
        consumed = block_members(multi)
        row_singles = [name for name in raw if name not in consumed]
    col_vars = selection["cols"] if cols is None else select_columns(data, cols)
    skipped = selection["skipped"] if auto else []
    return {"auto": auto, "row_singles": row_singles, "multi": multi, "col_vars": col_vars, "skipped": skipped}


def run_blocks(data, specs, settings, saved):
    """Build each question's block in turn, announcing it first and checkpointing after it.

    Args:
        data: The survey data.
        specs: The stub questions, from stub_specs().
        settings: The run's options.
        saved: The checkpoint path, fingerprint and what an earlier run finished.

    Returns:
        The finished question labels, their long blocks and their row keys.
    """
    d_all = data.assign(**{".all": "Overall"})
    state = {"finished": list(saved["finished"]), "blocks": list(saved["blocks"]), "row_keys": list(saved["row_keys"])}
    run = progress_start(len(specs))
    for i, spec in enumerate(specs, start=1):
        if spec["label"] in state["finished"]:
            continue
        progress_item(run, i, spec["label"])
        block = build_block(data, d_all, spec, settings)
        state["finished"].append(spec["label"])
        if block["item_levels"]:
            variable = block["rows"][0]["variable"] if block["rows"] else spec["label"]
            state["row_keys"].append(pd.DataFrame({"variable": variable, "item": block["item_levels"]}))
            state["blocks"].append(pd.DataFrame(block["rows"], columns=LONG_COLUMNS))
        banner_checkpoint_save(saved["path"], saved["fingerprint"], state["finished"], state["blocks"], state["row_keys"])
    progress_done(run)
    return state


def confirm_banner(chosen, specs, max_levels, confirm):
    """Show an automatic selection and ask before the run; a named selection is never questioned."""
    if not chosen["auto"]:
        return True
    labels = [spec["label"] for spec in specs]
    lines = (
        confirm_lines("Questions", labels)
        + confirm_lines("Grouping variables", chosen["col_vars"])
        + confirm_lines("Skipped", chosen["skipped"])
        + [f"Name `rows` / `cols` yourself, or raise `max_levels` (now {max_levels}), to change this."]
    )
    title = (
        f"Banner variables chosen automatically: {len(specs)} question(s) across "
        f"{len(chosen['col_vars'])} grouping variable(s)."
    )
    return confirm_selection(title, lines, confirm)


def check_selection(chosen, confirm):
    if chosen["auto"] and not confirm_on(confirm) and chosen["skipped"]:
        message(
            f"crosstab_banner: skipped {len(chosen['skipped'])} identifier / free-text / high-cardinality "
            f"column(s): {', '.join(chosen['skipped'])}. Raise max_levels or name them in rows/cols to include them."
        )
    if not chosen["row_singles"] and not chosen["multi"]:
        raise ValueError("No `rows` variables (none selected or eligible). Name some in `rows` or raise `max_levels`.")
    if not chosen["col_vars"]:
        raise ValueError("No `cols` variables (none selected or eligible). Name some in `cols` or raise `max_levels`.")


def open_checkpoint(data, specs, settings, checkpoint):
    """The checkpoint this run writes to, and whatever an interrupted identical run left in it."""
    labels = [spec["label"] for spec in specs]
    fingerprint = banner_fingerprint(data, labels, settings)
    path = banner_checkpoint_path(checkpoint, fingerprint)
    saved = banner_checkpoint_load(path, fingerprint)
    progress_plan(f"Banner table: {len(specs)} question(s) across {len(settings['col_vars'])} grouping variable(s)", labels)
    if path is not None:
        progress_note("Checkpoint: ", path)
    if saved["finished"]:
        progress_note(f"Resuming: {len(saved['finished'])} of {len(specs)} question(s) already done.")
    saved.update({"path": path, "fingerprint": fingerprint, "ours": checkpoint is True})
    return saved


def banner_output(state, settings, long, flextable):
    """Shape the finished blocks into the long form, the wide table, or the two-row-header table."""
    long_frame = pd.concat(state["blocks"], ignore_index=True) if state["blocks"] else pd.DataFrame(columns=LONG_COLUMNS)
    row_keys = pd.concat(state["row_keys"], ignore_index=True) if state["row_keys"] else pd.DataFrame(columns=["variable", "item"])
    if settings["cell"] == "diff":
        long_frame = difference_from_overall(long_frame)
    if long:
        long_frame["group"] = long_frame["group"].replace(".overall", "Overall")
        if not settings["total"]:
            long_frame = long_frame[long_frame["group"] != "Overall"].reset_index(drop=True)
        return long_frame
    wide = banner_assemble_wide(long_frame, row_keys, settings["col_vars"], settings["group_levels"], settings["total"])
    if flextable:
        return banner_table(wide)
    return wide


def crosstab_banner(  # lint-style: ignore FN001,FN003
    data=None,
    rows=None,
    cols=None,
    cell="auto",
    stats=None,
    total=True,
    digits=None,
    na_rm=True,
    drop=None,
    weights=None,
    max_levels=MAX_LEVELS,
    long=False,
    flextable=False,
    checkpoint=None,
    confirm=None,
):
    """Build a master banner (cross-tab) table.

    Produces the market-research "banner" table: one master table with a stack
    of question variables down the side (`rows`) and one or more grouping
    variables across the top (`cols`), plus an **Overall** column for the whole
    sample. Categorical questions become column-percentage blocks (each banner
    column sums to about 100 within the block); numeric questions become a mean
    / median / sd / quartile block. It generalises `crosstab()` from a single
    pair to a whole table, and picks the cell content per question
    automatically.

    A DataFrame has a single header row, so the two-row banner header (each
    grouping variable's name spanning its items) is carried in
    ``.attrs["banner_spanners"]``, and ``flextable=True`` returns the table with
    a real two-level header. Registered orders (`register_order()`) set the item
    and banner-column ordering automatically. Supplying only the data frame
    builds the full every-question-by-every-question matrix: every variable with
    at most `max_levels` distinct answers becomes both a stub and a banner
    group, numeric scales are added as stub statistics blocks, and identifier /
    free-text columns are skipped (and named in a message). That selection
    decides the whole table, so an interactive session prints it and waits for a
    yes before starting the run (see `confirm`). Check-all-that-apply blocks
    are recognised as one multi-select stub question and tabulated with
    `calc_percentage_multi()`, whose base is the respondents who picked any
    option (so those rows can sum past 100); they appear as stubs only and are
    unweighted.

    A full every-variable banner is one `crosstab()` per question per grouping
    variable, so a wide survey takes a while. In an interactive session it
    reports which question it is on, with an estimate of the time left;
    ``ezrsurvey_options(progress=False)`` turns that off, and scripts are silent
    by default. ``checkpoint=True`` saves each question as it completes, so
    re-running the identical call after an interruption resumes instead of
    starting again; that file is deleted as soon as the table is built. Pass a
    path instead to choose the location yourself; that file is yours, and is
    never deleted. `clear_checkpoints()` empties the managed folder.

    Parameters
    ----------
    data : pandas.DataFrame, optional
        A data frame. If omitted, the session default is used.
    rows : str, selector or list, optional
        Stub variables, down the side (e.g. ``["satis_return", "demo_edu"]`` or
        ``starts_with("ratings_")``). If omitted, every eligible variable is
        used.
    cols : str, selector or list, optional
        Banner / grouping variables, across the top. Pass several to get several
        spanning column groups. If omitted, every eligible variable is used.
    cell : str
        What each body cell holds: "auto" (default) uses column percentages for
        categorical questions and a statistics block for numeric ones; "pct"
        forces column percentages; "count" uses (weighted) counts; "mean" forces
        a numeric mean (errors on a categorical question); "diff" shows each
        cell's difference from the Overall column.
    stats : list of str, optional
        For numeric questions, which statistics form the block: any of "mean",
        "median", "sd", "p25", "p75". Default all five.
    total : bool
        Include the whole-sample **Overall** column. Default True.
    digits : int, optional
        Decimal places. None (default) uses 0 for percentages / counts and 2 for
        numeric statistics; a value overrides both.
    na_rm : bool
        Drop blanks / non-answers in the questions and banner variables.
        Default True.
    drop : str or list of str, optional
        Answer values to remove before tabulating (see `drop_items()`).
    weights : bool, dict or list, optional
        Survey weighting: None (default) uses the session scheme from
        `set_weights()` if set; False forces unweighted; or pass an ad-hoc
        scheme.
    max_levels : int
        When `rows` / `cols` are omitted, the largest number of distinct answers
        a categorical variable may have to be used automatically (default 20).
    long : bool
        If True, return the tidy long form (``variable``, ``item``, ``group``,
        ``group_item``, ``value``). Default False.
    flextable : bool
        If True, return the table with a two-level column header (each grouping
        variable spanning its items), pandas' form of R's flextable. Default
        False.
    checkpoint : bool or str, optional
        Save each question as it finishes, so re-running the same call picks up
        where an interrupted run stopped. True keeps the file in the ezrsurvey
        cache folder and deletes it once the run completes; a file path puts it
        where you choose and leaves it there. None (default) or False writes
        nothing.
    confirm : bool, optional
        When `rows` / `cols` are left to the automatic selection, show which
        variables were chosen and which were skipped, and wait for a yes before
        the run starts. None (default) follows the ``confirm`` option, which asks
        in an interactive session and never asks in a script. Answering no
        returns None and computes nothing.

    Returns
    -------
    pandas.DataFrame or None
        By default the wide table: ``variable``, ``item``, ``Overall``, then one
        column per banner item, with ``.attrs["banner_spanners"]`` naming each
        column's group. With ``long=True``, the tidy long form.

    See Also
    --------
    crosstab, calc_percentage_batch, export_summary_xlsx, register_order

    Examples
    --------
    >>> crosstab_banner(podracing_survey,
    ...                 rows=["satis_return", "demo_edu"],
    ...                 cols=["demo_gender", "region"])
    >>> crosstab_banner(podracing_survey, rows=["nps_value", "demo_age"], cols="demo_gender")
    >>> crosstab_banner(podracing_survey, rows="satis_return", cols="region", cell="diff")
    >>> crosstab_banner(podracing_survey)  # doctest: +SKIP
    """
    data = resolve_data(data).reset_index(drop=True)
    cell = match_arg(cell, CELLS)
    which = check_stats(stats)
    if len(data) == 0:
        raise ValueError(
            "crosstab_banner() needs at least one row; the data has none. "
            "A filter that matched no respondents is the usual cause."
        )
    chosen = resolve_selection(data, rows, cols, max_levels)
    check_selection(chosen, confirm)
    d_all = data.assign(**{".all": "Overall"})
    settings = {
        "col_vars": chosen["col_vars"],
        "group_levels": group_levels_for(d_all, chosen["col_vars"], na_rm, drop),
        "cell": cell,
        "which": which,
        "total": total,
        "na_rm": na_rm,
        "drop": drop,
        "weights": weights,
        "digits": digits,
        "pct_digits": 0 if digits is None else digits,
        "num_digits": 2 if digits is None else digits,
    }
    specs = stub_specs(data, chosen["row_singles"], chosen["multi"])
    if not confirm_banner(chosen, specs, max_levels, confirm):
        message("Cancelled. Nothing was computed.")
        return None
    saved = open_checkpoint(data, specs, settings, checkpoint)
    state = run_blocks(data, specs, settings, saved)
    banner_checkpoint_clear(saved["ours"], saved["path"])
    return banner_output(state, settings, long, flextable)


def difference_from_overall(long_frame):
    overall = {}
    for row in long_frame.itertuples(index=False):
        if row.group == ".overall":
            overall[(row.variable, row.item)] = row.value
    values = []
    for row in long_frame.itertuples(index=False):
        if row.group == ".overall":
            values.append(row.value)
        else:
            values.append(row.value - overall.get((row.variable, row.item), np.nan))
    return long_frame.assign(value=values)
