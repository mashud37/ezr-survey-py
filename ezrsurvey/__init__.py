"""The Python port of the R package ezrsurvey: single-line helpers for consumer survey analysis. Importing it loads any ezrsurvey profile, exactly as attaching the R package does."""

from .brand import brand_info, clear_brand, use_brand
from .coerce import ensure_numeric
from .comments import sample_comments, sample_comments_diverse
from .compare import compare_values, plot_diff
from .config import (
    edit_ezrsurvey_profile,
    ezrsurvey_options,
    ezrsurvey_profile_paths,
    load_ezrsurvey_profile,
    reset_ezrsurvey_options,
    save_ezrsurvey_profile,
    use_ezrsurvey_profile,
)
from .crosstab import crosstab
from .crosstab_banner import clear_checkpoints, crosstab_banner
from .currency import add_currency, convert_currency, list_currencies
from .dataset import clear_dataset, dataset_vars, get_dataset, has_dataset, use_dataset
from .datasets import DATASET_NAMES, load_dataset
from .decisions import (
    annotate_bands,
    bands_nps,
    bands_nps_score,
    bands_rating_3,
    bands_rating_5,
    mark_value,
    rescale_bands,
)
from .diagnostics import (
    diagnose,
    margin_of_error,
    precision_summary,
    rse,
    rse_rating,
    se_mean,
    se_prop,
)
from .export import export_xlsx, save_data, save_output, save_plot
from .export_summary import export_summary_xlsx
from .generation import generation_scheme, recode_generation
from .import_data import parse_filename, read_folder, select_prefix, select_suffix
from .model import calc_importance, calc_nps, ipm_model
from .orders import (
    apply_order,
    get_order,
    list_orders,
    order_for,
    register_order,
    register_order_presets,
    remove_order,
)
from .palettes import (
    pal_brand,
    pal_neutral,
    pal_nps,
    pal_rating,
    pal_sequential_blue,
    scale_color_brand,
    scale_color_rating,
    scale_colour_brand,
    scale_colour_rating,
    scale_fill_brand,
    scale_fill_nps,
    scale_fill_rating,
)
from .percentage import (
    calc_percentage,
    calc_percentage_batch,
    calc_percentage_multi,
    calc_summary,
    clean_label,
)
from .plot import (
    plot_bars,
    plot_gauges,
    plot_ipm,
    plot_nps,
    plot_nps_gauge,
    plot_quotes_tree,
    plot_rating_grid,
    plot_stacked_rating,
)
from .recode import (
    bin_numeric,
    drop_items,
    na_blank,
    nps_group,
    recode_age,
    recode_likert,
    split_multi,
)
from .region import add_region, recode_region, recode_subregion
from .report_builder import (
    report_add_plot,
    report_add_slide,
    report_add_table,
    report_add_text,
    report_layouts,
    report_new,
    report_save,
    report_section,
    report_slide,
    report_title_slide,
)
from .report_deck import report_deck
from .report_quarto import example_report, list_report_templates, scaffold_report
from .scales import label_pct, nice_max, scale_y_pct
from .select import all_of, any_of, contains, ends_with, everything, is_numeric, starts_with, where
from .theme import (
    theme_ezrsurvey,
    theme_ezrsurvey_x,
    theme_ezrsurvey_xy,
    theme_ezrsurvey_y,
    theme_transparent,
)
from .weights import (
    clear_weights,
    clear_weights_cache,
    get_weights,
    has_weights,
    set_weights,
    weight_vector,
)

__version__ = "0.7.0"

__all__ = [
    "add_currency",
    "add_region",
    "all_of",
    "annotate_bands",
    "any_of",
    "apply_order",
    "bands_nps",
    "bands_nps_score",
    "bands_rating_3",
    "bands_rating_5",
    "bin_numeric",
    "brand_info",
    "calc_importance",
    "calc_nps",
    "calc_percentage",
    "calc_percentage_batch",
    "calc_percentage_multi",
    "calc_summary",
    "clean_label",
    "clear_brand",
    "clear_checkpoints",
    "clear_dataset",
    "clear_weights",
    "clear_weights_cache",
    "compare_values",
    "contains",
    "convert_currency",
    "country_region",
    "crosstab",
    "crosstab_banner",
    "currency_rates",
    "dataset_vars",
    "diagnose",
    "drop_items",
    "edit_ezrsurvey_profile",
    "ends_with",
    "ensure_numeric",
    "everything",
    "example_report",
    "export_summary_xlsx",
    "export_xlsx",
    "ezrsurvey_options",
    "ezrsurvey_profile_paths",
    "generation_scheme",
    "get_dataset",
    "get_order",
    "get_weights",
    "has_dataset",
    "has_weights",
    "ipm_model",
    "is_numeric",
    "label_pct",
    "list_currencies",
    "list_orders",
    "list_report_templates",
    "load_ezrsurvey_profile",
    "margin_of_error",
    "mark_value",
    "na_blank",
    "nice_max",
    "nps_group",
    "order_for",
    "pal_brand",
    "pal_neutral",
    "pal_nps",
    "pal_rating",
    "pal_sequential_blue",
    "parse_filename",
    "plot_bars",
    "plot_diff",
    "plot_gauges",
    "plot_ipm",
    "plot_nps",
    "plot_nps_gauge",
    "plot_quotes_tree",
    "plot_rating_grid",
    "plot_stacked_rating",
    "podracing_survey",
    "precision_summary",
    "read_folder",
    "recode_age",
    "recode_generation",
    "recode_likert",
    "recode_region",
    "recode_subregion",
    "register_order",
    "register_order_presets",
    "remove_order",
    "report_add_plot",
    "report_add_slide",
    "report_add_table",
    "report_add_text",
    "report_deck",
    "report_layouts",
    "report_new",
    "report_save",
    "report_section",
    "report_slide",
    "report_title_slide",
    "rescale_bands",
    "reset_ezrsurvey_options",
    "rse",
    "rse_rating",
    "sample_comments",
    "sample_comments_diverse",
    "save_data",
    "save_ezrsurvey_profile",
    "save_output",
    "save_plot",
    "scaffold_report",
    "scale_color_brand",
    "scale_color_rating",
    "scale_colour_brand",
    "scale_colour_rating",
    "scale_fill_brand",
    "scale_fill_nps",
    "scale_fill_rating",
    "scale_y_pct",
    "se_mean",
    "se_prop",
    "select_prefix",
    "select_suffix",
    "set_weights",
    "shopping_survey",
    "split_multi",
    "starts_with",
    "theme_ezrsurvey",
    "theme_ezrsurvey_x",
    "theme_ezrsurvey_xy",
    "theme_ezrsurvey_y",
    "theme_transparent",
    "use_brand",
    "use_dataset",
    "use_ezrsurvey_profile",
    "weight_vector",
    "where",
]


def __getattr__(name):
    if name in DATASET_NAMES:
        return load_dataset(name)
    raise AttributeError(f"module 'ezrsurvey' has no attribute '{name}'")


try:
    load_ezrsurvey_profile(quiet=True)
except Exception:
    pass
