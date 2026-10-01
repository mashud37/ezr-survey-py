"""Hold ezrsurvey's session options and read and write the YAML profiles that set them. Every helper reads its defaults here, and R and Python share the same profile files."""

import math
import os
import subprocess
import sys
from pathlib import Path

from .rbase import home_dir, interactive, message, r_user_dir, warn

DEFAULTS = {
    "pct_axis_unit": 25,
    "pct_axis_max": None,
    "bar_cols_max_items": 6,
    "bar_cols_max_label": 12,
    "bar_wrap_cols": 12,
    "bar_wrap_bars": 28,
    "bar_label_size": 3.5,
    "bar_size_step": 0.15,
    "bar_size_min": 2.4,
    "bar_width": 0.66,
    "bar_ref_items": 6,
    "age_breaks": [0, 18, 22, 26, 30, 35, math.inf],
    "age_labels": [
        "17 or younger",
        "18 to 21",
        "22 to 25",
        "26 to 29",
        "30 to 34",
        "35+",
    ],
    "na_answers": "Prefer not to answer",
    "drop_answers": None,
    "generation_scheme": "pew",
    "current_year": None,
    "default_by": None,
    "brand_colors": None,
    "brand_color_primary": None,
    "brand_font_major": None,
    "brand_font_minor": None,
    "brand_fonts_enabled": True,
    "brand_template_pptx": None,
    "brand_template_docx": None,
    "progress": "auto",
    "confirm": "auto",
    "output_dir": "ezrsurvey-outputs",
}

SESSION_OPTIONS = {}

PROFILE_TEMPLATE = [
    "# ezrsurvey profile -- set persistent defaults here.",
    "# Edit values and uncomment the lines you want to change.",
    "",
    "# pct_axis_unit: 25       # rounding step for percentage y-axes",
    "# pct_axis_max: 100       # fix every percentage y-axis at 100",
    "# generation_scheme: pew  # cohort scheme for recode_generation()",
    "# current_year: 2026      # reference year for age -> cohort",
    "# progress: auto          # auto | true | false: per-item progress lines",
    "# confirm: auto           # auto | true | false: confirm an automatic variable selection",
    "# output_dir: ezrsurvey-outputs   # folder a bare output file name lands in",
    "# na_answers:",
    "#   - Prefer not to answer",
    "#   - Don't know",
    "",
    "# Organisation brand -- usually set per project via use_brand(), but the",
    "# values can live here too. Template paths are machine-specific: keep them",
    "# in the project-level .ezrsurvey.yml, not this user-level file.",
    "# brand_colors: ['#4472C4', '#ED7D31', '#A5A5A5', '#FFC000']",
    "# brand_color_primary: '#4472C4'",
    "# brand_font_minor: Calibri",
    "# brand_fonts_enabled: true",
    "# brand_template_pptx: C:/path/to/org-template.pptx",
    "",
    "# Reusable level orders, linked to variable names and/or prefixes.",
    "# orders:",
    "#   education:",
    "#     levels:",
    "#       - Primary or less",
    "#       - Lower secondary",
    "#       - Upper secondary",
    "#       - Bachelor or equivalent",
    "#       - Master or equivalent",
    "#     vars: [demo_edu]",
    "#   likert_bad_good:",
    "#     levels: [Very bad, Bad, Ok, Good, Very good]",
    "#     prefixes: [ratings_]",
]


def ezrsurvey_default(name):
    """The effective value of one option: the session setting first, then the built-in default."""
    if SESSION_OPTIONS.get(name) is not None:
        return SESSION_OPTIONS[name]
    if name not in DEFAULTS:
        raise ValueError(f"Unknown ezrsurvey option '{name}'.")
    return DEFAULTS[name]


def ezrsurvey_options(**options):  # lint-style: ignore FN001
    """Get or set ezrsurvey defaults.

    ezrsurvey reads a handful of defaults from its session options, so you can
    tune behaviour once instead of repeating arguments. Call with no arguments
    to see the current effective values; call with ``name=value`` pairs to set
    them for the session. Persist them across sessions with a YAML profile (see
    `use_ezrsurvey_profile()`).

    Recognised options:

    - ``pct_axis_unit``: rounding step for percentage y-axes (default 25).
    - ``pct_axis_max``: fixed percentage y-axis maximum, e.g. 100; None
      (default) means dynamic via `nice_max()`.
    - ``bar_cols_max_items``, ``bar_cols_max_label``: thresholds that switch
      `plot_bars()` (``orientation="auto"``) from vertical columns to horizontal
      bars: more than ``bar_cols_max_items`` bars (6) or any label longer than
      ``bar_cols_max_label`` characters (12).
    - ``bar_wrap_cols``, ``bar_wrap_bars``: wrap widths used by `plot_bars()`
      for column (12) and bar (28) labels.
    - ``bar_label_size``, ``bar_size_step``, ``bar_size_min``: data-label text
      sizing in `plot_bars()`: base size (3.5), reduction per item past the item
      threshold (0.15) and the floor (2.4).
    - ``bar_width``, ``bar_ref_items``: bar thickness. Bars are drawn at
      ``bar_width`` (0.66) of a category slot when a chart has ``bar_ref_items``
      (6) bars, and the fraction scales with the bar count so the *drawn*
      thickness stays the same on every chart.
    - ``age_breaks``, ``age_labels``: default bands used by `recode_age()`.
    - ``na_answers``: strings treated as non-answers by `na_blank()`.
    - ``drop_answers``: answer values dropped by the ``drop=`` argument of
      `calc_percentage()` and friends when ``drop`` is not given; None (default)
      means drop nothing. See `drop_items()`.
    - ``generation_scheme``: default scheme for `recode_generation()`.
    - ``current_year``: reference year for age-to-cohort conversion; None uses
      the system year.
    - ``default_by``: default grouping column name(s) applied by
      `calc_percentage()` / `calc_percentage_multi()` when ``by`` is omitted.
    - ``brand_colors``, ``brand_color_primary``: organisation brand colours,
      usually set by `use_brand()`.
    - ``brand_font_major``, ``brand_font_minor``: brand heading and body
      typefaces; ``brand_font_minor`` becomes the default ``base_family`` of
      `theme_ezrsurvey()` when the font is installed.
    - ``brand_fonts_enabled``: set False to keep brand colours but ignore brand
      fonts (default True).
    - ``brand_template_pptx``, ``brand_template_docx``: paths to the brand
      PowerPoint / Word template used by `report_new()`, `report_deck()` and
      `scaffold_report()`.
    - ``progress``: whether the slow helpers report which item they are on.
      "auto" (default) reports in an interactive session and stays silent in
      scripts; True or False force it either way.
    - ``confirm``: whether a call that picks its own variables shows the
      selection and waits for a yes before a long run. "auto" (default) asks in
      an interactive session and never in a script.
    - ``output_dir``: folder that a bare output file name lands in, created on
      demand (default "ezrsurvey-outputs"). A path that names a directory
      ("./chart.png", "charts/chart.png", anything absolute) is written exactly
      where it says. Set to "." to put bare names back in the working directory.

    Options last for the session. Reading returns every recognised option's
    current effective value; setting returns the previous values, so you can
    restore them. To make settings permanent, write them to a YAML profile, which
    is loaded automatically when ezrsurvey is imported.

    Parameters
    ----------
    **options
        Either nothing (to read all values) or ``option=value`` pairs to set.

    Returns
    -------
    dict
        When reading, all current values. When setting, the previous values.

    See Also
    --------
    use_ezrsurvey_profile, load_ezrsurvey_profile, reset_ezrsurvey_options

    Examples
    --------
    >>> ezrsurvey_options()
    >>> ezrsurvey_options(pct_axis_max=100)
    >>> ezrsurvey_options()["pct_axis_max"]
    >>> reset_ezrsurvey_options()
    """
    if not options:
        return {name: ezrsurvey_default(name) for name in DEFAULTS}
    unknown = [name for name in options if name not in DEFAULTS]
    if unknown:
        warn("Unknown ezrsurvey option(s): " + ", ".join(unknown))
    old = {name: SESSION_OPTIONS.get(name) for name in options}
    for name, value in options.items():
        if value is None:
            SESSION_OPTIONS.pop(name, None)
        else:
            SESSION_OPTIONS[name] = value
    return old


def reset_ezrsurvey_options():
    """Reset all ezrsurvey options to their built-in defaults.

    Returns
    -------
    bool
        True.

    See Also
    --------
    ezrsurvey_options

    Examples
    --------
    >>> ezrsurvey_options(pct_axis_max=100)
    >>> reset_ezrsurvey_options()
    >>> ezrsurvey_options()["pct_axis_max"]
    """
    SESSION_OPTIONS.clear()
    return True


def ezrsurvey_profile_paths():
    """Profile file locations ezrsurvey looks in.

    When it is imported, ezrsurvey reads a YAML profile from each of these paths
    in turn (later paths override earlier ones), if present: the per-user config
    directory, your home directory, then the current project. These are the same
    files the R package reads.

    Returns
    -------
    list of str
        Candidate profile paths.

    See Also
    --------
    use_ezrsurvey_profile, load_ezrsurvey_profile

    Examples
    --------
    >>> ezrsurvey_profile_paths()
    """
    return [
        str(r_user_dir("config") / "ezrsurvey.yml"),
        str(home_dir() / ".ezrsurvey.yml"),
        str(Path.cwd() / ".ezrsurvey.yml"),
    ]


def read_profile(path):
    import yaml

    try:
        with open(path, encoding="utf-8") as handle:
            return yaml.safe_load(handle)
    except (OSError, yaml.YAMLError):
        return None


def load_ezrsurvey_profile(path=None, quiet=True):
    """Load ezrsurvey defaults from a YAML profile.

    Reads a YAML file of ``option: value`` pairs and applies them with
    `ezrsurvey_options()`. Called automatically when the package is imported
    (over the standard `ezrsurvey_profile_paths()`); call it manually to load a
    specific file.

    Parameters
    ----------
    path : str or list of str, optional
        Profile path(s). If None (default), the standard locations are tried in
        order (later files override earlier ones).
    quiet : bool
        If True (default), load silently; if False, report which file(s) were
        loaded.

    Returns
    -------
    bool
        True if any profile was applied, else False.

    See Also
    --------
    use_ezrsurvey_profile

    Examples
    --------
    >>> load_ezrsurvey_profile("~/.ezrsurvey.yml", quiet=False)  # doctest: +SKIP
    """
    from .orders import apply_orders_config

    if path is None:
        paths = ezrsurvey_profile_paths()
    elif isinstance(path, (str, os.PathLike)):
        paths = [path]
    else:
        paths = list(path)
    loaded = False
    for candidate in paths:
        candidate = os.path.expanduser(str(candidate))
        if not os.path.exists(candidate):
            continue
        settings = read_profile(candidate)
        if not isinstance(settings, dict) or not settings:
            continue
        if settings.get("orders") is not None:
            apply_orders_config(settings["orders"])
        settings.pop("orders", None)
        if settings:
            ezrsurvey_options(**settings)
        loaded = True
        if not quiet:
            message("Loaded ezrsurvey profile: ", candidate)
    return loaded


def user_profile_path():
    folder = r_user_dir("config")
    folder.mkdir(parents=True, exist_ok=True)
    return str(folder / "ezrsurvey.yml")


def use_ezrsurvey_profile(path=None, overwrite=False):
    """Create a starter ezrsurvey profile.

    Writes a commented YAML profile (pre-filled with the current defaults) you
    can edit to set persistent options. By default it is written to the per-user
    config directory, which is where ezrsurvey looks first.

    Parameters
    ----------
    path : str, optional
        Destination path. If None (default), the per-user config file
        ``ezrsurvey.yml`` is used.
    overwrite : bool
        Overwrite an existing file. Defaults to False.

    Returns
    -------
    str
        The path written.

    See Also
    --------
    load_ezrsurvey_profile, ezrsurvey_options

    Examples
    --------
    >>> use_ezrsurvey_profile()  # doctest: +SKIP
    >>> use_ezrsurvey_profile("~/.ezrsurvey.yml")  # doctest: +SKIP
    """
    path = user_profile_path() if path is None else os.path.expanduser(str(path))
    if os.path.exists(path) and not overwrite:
        raise ValueError(f"'{path}' already exists. Use overwrite=True to replace it.")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(PROFILE_TEMPLATE) + "\n")
    message("Wrote ezrsurvey profile template to ", path)
    return path


def open_in_editor(path):
    if sys.platform == "win32":
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.run(["open", path], check=False)
    else:
        subprocess.run(["xdg-open", path], check=False)


def edit_ezrsurvey_profile(path=None):
    """Open the ezrsurvey profile for editing.

    Opens your ezrsurvey YAML profile in the system's editor for YAML files,
    creating it from a template first if it does not exist. After saving,
    reload it with `load_ezrsurvey_profile()` or by restarting the session.
    Outside an interactive session it only reports where the file is.

    Parameters
    ----------
    path : str, optional
        Profile path. If None (default), the first existing profile among
        `ezrsurvey_profile_paths()` is used, or the per-user config file is
        created.

    Returns
    -------
    str
        The path opened.

    See Also
    --------
    use_ezrsurvey_profile, save_ezrsurvey_profile, load_ezrsurvey_profile

    Examples
    --------
    >>> edit_ezrsurvey_profile()  # doctest: +SKIP
    """
    if path is None:
        existing = [candidate for candidate in ezrsurvey_profile_paths() if os.path.exists(candidate)]
        path = existing[0] if existing else use_ezrsurvey_profile()
    else:
        path = os.path.expanduser(str(path))
        if not os.path.exists(path):
            use_ezrsurvey_profile(path)
    if interactive():
        open_in_editor(path)
    else:
        message("ezrsurvey profile is at: ", path)
    return path


def save_ezrsurvey_profile(path=None, include_options=True, include_orders=True):
    """Save current options and orders to a profile.

    Writes your current non-default `ezrsurvey_options()` and all registered
    orders (see `register_order()`) to a YAML profile, so they persist across
    sessions.

    Parameters
    ----------
    path : str, optional
        Destination path. If None (default), the per-user config file is used.
    include_options : bool
        Write changed options. Default True.
    include_orders : bool
        Write registered orders. Default True.

    Returns
    -------
    str
        The path written.

    See Also
    --------
    load_ezrsurvey_profile, edit_ezrsurvey_profile, register_order

    Examples
    --------
    >>> register_order("education", ["low", "mid", "high"], vars="demo_edu")  # doctest: +SKIP
    >>> ezrsurvey_options(pct_axis_max=100)  # doctest: +SKIP
    >>> save_ezrsurvey_profile()  # doctest: +SKIP
    """
    import yaml

    from .orders import orders_to_list

    path = user_profile_path() if path is None else os.path.expanduser(str(path))
    settings = {}
    if include_options:
        for name, default in DEFAULTS.items():
            current = ezrsurvey_default(name)
            if current != default:
                settings[name] = current
    if include_orders:
        orders = orders_to_list()
        if orders:
            settings["orders"] = orders
    with open(path, "w", encoding="utf-8") as handle:
        yaml.safe_dump(settings, handle, sort_keys=False, allow_unicode=True)
    message("Saved ezrsurvey profile to ", path)
    return path
