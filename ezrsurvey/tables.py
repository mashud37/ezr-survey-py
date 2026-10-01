"""Group, order and pivot tables the way dplyr and tidyr do, so summaries come out in R's row and column order. The percentage, crosstab and banner helpers build on these."""

import pandas as pd

from .rbase import as_character, is_categorical, is_missing, sort_key


def category_positions(column):
    if not is_categorical(column):
        return None
    return {category: i for i, category in enumerate(column.cat.categories)}


def dplyr_key(value, positions):
    """How dplyr sorts one value: by factor level, else by C-locale text or by number, missing last."""
    if is_missing(value):
        return [1, 0, ""]
    if positions is not None:
        return [0, positions.get(value, len(positions)), ""]
    if isinstance(value, str):
        return [0, 0, value]
    return [0, float(value), ""]


def base_key(value, positions):
    """How base R's order() sorts one value: by factor level, else by English collation, missing last."""
    if is_missing(value):
        return [1, 0, ()]
    if positions is not None:
        return [0, positions.get(value, len(positions)), ()]
    if isinstance(value, str):
        return [0, 0, sort_key(value)]
    return [0, float(value), ()]


def missing_marker(value):
    return "\x00missing" if is_missing(value) else value


def group_positions(frame, keys):
    """The groups dplyr's group_by() forms, sorted as dplyr sorts them.

    Args:
        frame: A DataFrame.
        keys: Column names to group by; an empty list gives one group of every row.

    Returns:
        A list of dicts, one per group, with the group's `values` (a tuple, in
        the order of `keys`) and the row `positions` it holds.
    """
    if not keys:
        return [{"values": (), "positions": list(range(len(frame)))}]
    columns = [frame[key].tolist() for key in keys]
    positions_by_column = [category_positions(frame[key]) for key in keys]
    groups = {}
    for position in range(len(frame)):
        values = tuple(column[position] for column in columns)
        marker = tuple(missing_marker(value) for value in values)
        if marker not in groups:
            groups[marker] = {"values": values, "positions": []}
        groups[marker]["positions"].append(position)
    ordered = list(groups.values())
    ordered.sort(key=lambda group: [dplyr_key(value, positions_by_column[i]) for i, value in enumerate(group["values"])])
    return ordered


def restore_types(out, source, keys):
    """Give grouping columns in a summary the categorical type they had in the source."""
    typed = out.copy()
    for key in keys:
        if is_categorical(source[key]):
            dtype = source[key].dtype
            typed[key] = pd.Categorical(typed[key], categories=dtype.categories, ordered=dtype.ordered)
    return typed


def row_keys(frame, columns):
    """One sort key per row: the base R sort key of each of `columns`, in order."""
    lists = [frame[column].tolist() for column in columns]
    positions_by_column = [category_positions(frame[column]) for column in columns]
    keys = []
    for row in range(len(frame)):
        keys.append([base_key(values[row], positions_by_column[i]) for i, values in enumerate(lists)])
    return keys


def order_rows(frame, columns, decreasing=False):
    """Row positions in base R's order() for these columns: stable, missing values last."""
    keys = row_keys(frame, columns)
    complete = [row for row in range(len(frame)) if keys[row][0][0] == 0]
    missing = [row for row in range(len(frame)) if keys[row][0][0] == 1]
    ordered = sorted(complete, key=lambda row: keys[row], reverse=decreasing)
    return ordered + missing


def take_rows(frame, positions):
    return frame.iloc[positions].reset_index(drop=True)


def pivot_wider(frame, names_from, values_from):
    """Spread one column into many, as tidyr's pivot_wider(): names and rows in order of first appearance.

    Args:
        frame: A long DataFrame.
        names_from: The column whose values become the new column names.
        values_from: The column that fills the new columns.

    Returns:
        A DataFrame with one row per combination of the remaining columns.
    """
    id_columns = [column for column in frame.columns if column not in (names_from, values_from)]
    names = []
    for name in as_character(frame[names_from]):
        label = "NA" if is_missing(name) else name
        if label not in names:
            names.append(label)
    rows = {}
    row_values = {}
    id_lists = [frame[column].tolist() for column in id_columns]
    name_list = as_character(frame[names_from]).tolist()
    value_list = frame[values_from].tolist()
    for position in range(len(frame)):
        ids = tuple(values[position] for values in id_lists)
        marker = tuple(missing_marker(value) for value in ids)
        if marker not in rows:
            rows[marker] = {}
            row_values[marker] = ids
        name = "NA" if is_missing(name_list[position]) else name_list[position]
        rows[marker][name] = value_list[position]
    records = []
    for marker, cells in rows.items():
        record = dict(zip(id_columns, row_values[marker]))
        for name in names:
            record[name] = cells.get(name, float("nan"))
        records.append(record)
    out = pd.DataFrame(records, columns=id_columns + names)
    return restore_types(out, frame, id_columns)
