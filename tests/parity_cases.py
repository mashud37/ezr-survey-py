"""Hold the Python half of every parity case, named as in parity/cases.R. test_parity.py runs each and compares it with the golden output R wrote."""

import math

import pandas as pd

import ezrsurvey as ez
from ezrsurvey import comments
from ezrsurvey.decisions import build_plot
from ezrsurvey.theme import PT

podracing_survey = ez.podracing_survey
shopping_survey = ez.shopping_survey

PACKED = pd.DataFrame(
    {
        "respondent": [1, 2, 3, 4],
        "motivations": ["Speed; Drivers", "Speed", "", "Betting; Speed"],
    }
)
GENDER_TARGET = {"variable": "demo_gender", "Male": 0.49, "Female": 0.5, "Non-binary": 0.01}
SATIS_LEVELS = ["Very unlikely", "Unlikely", "Not sure", "Likely", "Very likely"]
NAMED_CELLS = pd.DataFrame(
    {
        "value": ["Low", "High", "High", "Low", "High", "Low"],
        "n": ["A", "A", "B", "B", "B", "A"],
    }
)
AGREE_LEVELS = ["Strongly disagree", "Disagree", "Agree", "Strongly agree"]
AGREE_FACTORS = pd.DataFrame(
    {
        "agree": pd.Categorical(["Disagree", "Agree", "Strongly agree", "Agree"], categories=AGREE_LEVELS),
        "group": pd.Categorical(["Old", "Young", "Old", "Young"], categories=["Young", "Old"]),
    }
)


# ---- Coerce and recode ----


def ensure_numeric_messy():  # lint-style: ignore MD001
    return ez.ensure_numeric(["25 years", "31", "forty"], name="age")


def ensure_numeric_scale():
    return ez.ensure_numeric(["8 - very likely", "10", "3.5/5"], quiet=True)


def na_blank_default():
    return ez.na_blank(["Yes", "", "Prefer not to answer", "No", None, "  No  "])


def na_blank_also():
    return ez.na_blank(["a", "n/a", "N/A"], also=["n/a", "N/A"])


def drop_items_basic():
    return ez.drop_items(["Yes", "No", "Other", " don't know "], items=["Other", "Don't know"])


def bin_numeric_basic():
    return ez.bin_numeric([15, 19, 27, 41, None], breaks=[0, 18, 25, 35, math.inf], labels=["<18", "18-24", "25-34", "35+"])


def bin_numeric_outside():
    return ez.bin_numeric([10, 50, 60], breaks=[18, 25, 40.5], labels=["18 to 24", "25 to 40+"])


def recode_age_messy():
    return ez.recode_age(["17", "22 years", "31", "47", "young", ""])


def recode_likert_basic():
    return ez.recode_likert(["Very bad", "Ok", "Good", "Very good", "4 - Good", "nope", None])


def recode_likert_nested():
    return ez.recode_likert(["\U0001f642 Very good", "\U0001f610 Good"])


def recode_likert_synonyms():
    return ez.recode_likert(
        ["Dissatisfied", "Satisfied", "Very dissatisfied"],
        synonyms={"Bad": "Dissatisfied", "Good": "Satisfied", "Very bad": "Very dissatisfied"},
    )


def recode_likert_bad_synonym():
    return ez.recode_likert("x", synonyms={"Great": "x"})


def nps_group_codes():
    return ez.nps_group(["0", "6", "7", "8", "9", "10", "11", None, "9 - likely"])


def nps_group_labels():
    return ez.nps_group([3, 8, 10], labels=True)


def split_multi_packed():
    return ez.split_multi(PACKED, "motivations")


def split_multi_empty():
    return ez.split_multi(pd.DataFrame({"a": ["", None]}), "a")


def clean_label_basic():
    return ez.clean_label(["Broadcast.quality...audio", "ratings_Camera.work", "ratings_Talent...analysis"], prefix="ratings_")


# ---- Generation, region, currency ----


def generation_scheme_pew():
    return ez.generation_scheme("pew")


def recode_generation_year():
    return ez.recode_generation([1990, 2001, 1968, 1900, 2020], input="year")


def recode_generation_age():
    return ez.recode_generation(["36", "25", "40 years"], input="age", year=2026)


def recode_region_spellings():
    return ez.recode_region(
        [
            "USA",
            "U.S.",
            "England",
            "Deutschland",
            "Holland",
            "NO",
            "no",
            "Timor-Leste",
            "Cote d'Ivoire",
            "the Netherlands",
            "España",
            "",
            None,
        ]
    )


def recode_region_codes():
    return ez.recode_region(["US", "GBR", "DE", "JPN", "Korea, North"])


def recode_region_unmatched():
    return ez.recode_region(["Germany", "Atlantis", "Narnia", "Mordor", "Oz", "Gondor", "Atlantis"])


def recode_subregion_basic():
    return ez.recode_subregion(["Germany", "Japan", "Brazil"])


def add_region_basic():
    return ez.add_region(pd.DataFrame({"demo_country": ["Germany", "Japan", "Brazil"]}), "demo_country", subregion=True)


def convert_currency_basic():
    return ez.convert_currency([100, 50], from_=["EUR", "GBP"], to="USD")


def convert_currency_cross():
    return ez.convert_currency(100, "EUR", "RMB")


def convert_currency_unknown():
    return ez.convert_currency([100, 10], ["EUR", "XYZ"], "USD")


def convert_currency_rates():
    return ez.convert_currency("$1,200", "EUR", "GBP", rates={"EUR": 0.9, "GBP": 0.8})


def add_currency_column():
    frame = pd.DataFrame({"spend": [100.0, 200.0, 50.0], "currency": ["EUR", "GBP", "JPY"]})
    return ez.add_currency(frame, "spend", from_="currency", to="USD")


def add_currency_constant():
    return ez.add_currency(pd.DataFrame({"spend": [100.0, 200.0]}), "spend", from_="EUR", into="spend_usd")


def list_currencies_default():
    return ez.list_currencies()


# ---- Orders ----


def order_presets_list():
    ez.register_order_presets()
    return ez.list_orders()


def order_for_prefix():
    ez.register_order("edu", ["low", "mid", "high"], prefixes="edu_")
    return ez.order_for("edu_level")


def apply_order_basic():
    ez.register_order("size", ["S", "M", "L"])
    return ez.apply_order(["L", "S", "M", "XL"], name="size")


# ---- Summaries ----


def calc_percentage_gender():
    return ez.calc_percentage(podracing_survey, "demo_gender")


def calc_percentage_desc():
    return ez.calc_percentage(podracing_survey, "demo_gender", sort="desc")


def calc_percentage_asc_digits():
    return ez.calc_percentage(podracing_survey, "demo_job", sort="asc", digits=1)


def calc_percentage_by():
    return ez.calc_percentage(podracing_survey, "satis_return", by="region")


def calc_percentage_by_two():
    return ez.calc_percentage(podracing_survey, "demo_gender", by=["region", "collector"])


def calc_percentage_wide():
    return ez.calc_percentage(podracing_survey, "satis_return", by="region", wide=True)


def calc_percentage_levels():
    return ez.calc_percentage(podracing_survey, "satis_return", levels=SATIS_LEVELS)


def calc_percentage_levels_missing():
    return ez.calc_percentage(podracing_survey, "satis_return", levels=["Likely", "Very likely"])


def calc_percentage_registered_by():
    ez.register_order_presets()
    return ez.calc_percentage(podracing_survey, "satis_return", by="demo_gender")


def calc_percentage_keep_na():
    return ez.calc_percentage(podracing_survey, "demo_gender", na_rm=False)


def calc_percentage_drop():
    return ez.calc_percentage(podracing_survey, "demo_job", drop=["Unemployed", "student"])


def calc_percentage_weighted():
    return ez.calc_percentage(podracing_survey, "satis_return", weights=GENDER_TARGET)


def calc_percentage_weighted_wide():
    target = {"region": {"Europe": 0.3, "North America": 0.3, "Asia": 0.2, "Latin America": 0.1, "Oceania": 0.1}}
    return ez.calc_percentage(podracing_survey, "satis_return", by="region", wide=True, weights=target)


def calc_percentage_default_dataset():
    ez.use_dataset(podracing_survey)
    return ez.calc_percentage("demo_edu", sort="desc")


def calc_percentage_default_by():
    ez.ezrsurvey_options(default_by="collector")
    return ez.calc_percentage(podracing_survey, "demo_gender")


def calc_percentage_bad_column():
    return ez.calc_percentage(podracing_survey, "demo_gendr")


def calc_percentage_no_data():
    return ez.calc_percentage("demo_gender")


def calc_percentage_bad_sort():
    return ez.calc_percentage(podracing_survey, "demo_gender", sort="up")


def calc_percentage_multi_block():
    return ez.calc_percentage_multi(podracing_survey, "motivations_", id="respondent_id", sort="desc")


def calc_percentage_multi_by():
    return ez.calc_percentage_multi(podracing_survey, "motivations_", by="region")


def calc_percentage_multi_raw_names():
    return ez.calc_percentage_multi(shopping_survey, "reasons_", clean_names=False, drop="Fair prices")


def calc_percentage_multi_packed():
    return ez.calc_percentage_multi(PACKED, "motivations", id="respondent", sort="desc")


def calc_percentage_multi_no_prefix():
    return ez.calc_percentage_multi(podracing_survey, "nothing_")


def calc_summary_age():
    return ez.calc_summary(podracing_survey, "demo_age")


def calc_summary_by():
    return ez.calc_summary(podracing_survey, "demo_age", by="region")


def calc_summary_text():
    return ez.calc_summary(pd.DataFrame({"a": ["25 years", "31", "forty", None]}), "a")


def calc_summary_weighted():
    target = {"variable": "demo_gender", "Female": 0.5, "Male": 0.5}
    return ez.calc_summary(shopping_survey, "weekly_spend", by="payment", weights=target)


def calc_percentage_batch_named():
    return ez.calc_percentage_batch(podracing_survey, "demo_gender", "demo_job")


def calc_percentage_batch_prefix():
    return ez.calc_percentage_batch(podracing_survey, ez.starts_with("ratings_"), prefix="ratings_")


def calc_percentage_batch_by():
    return ez.calc_percentage_batch(podracing_survey, ez.starts_with("partner_recall"), by="demo_gender", sort="desc")


def calc_percentage_factor_order():
    answers = ["Agree", "Strongly disagree", "Disagree", "Agree", "Strongly agree", ""]
    d = pd.DataFrame({"agree": pd.Categorical(answers, categories=AGREE_LEVELS + [""])})
    return ez.calc_percentage(d, "agree")


def calc_percentage_bands():
    bands = ez.bin_numeric([45, 120, 60], breaks=[40, 70, 100, 150], labels=["40-70k", "70-100k", "100-150k"])
    return ez.calc_percentage(pd.DataFrame({"band": bands}), "band")


# ---- Weights ----


def weight_vector_gender():
    return ez.weight_vector(podracing_survey, GENDER_TARGET)


def weight_vector_raked():
    target = {
        "demo_gender": {"Male": 0.49, "Female": 0.5, "Non-binary": 0.01},
        "collector": {"email": 0.25, "panel": 0.25, "socials": 0.25, "in_app": 0.25},
    }
    return ez.weight_vector(podracing_survey, target)


def set_weights_message():
    ez.use_dataset(podracing_survey)
    return ez.set_weights(GENDER_TARGET)


def set_weights_missing_category():
    ez.use_dataset(podracing_survey)
    return ez.set_weights({"variable": "demo_gender", "Male": 0.5, "Female": 0.5})


# ---- Crosstab and compare ----


def crosstab_counts():
    return ez.crosstab(podracing_survey, "demo_gender", "region")


def crosstab_row_pct():
    return ez.crosstab(podracing_survey, "region", "demo_gender", cell="row_pct")


def crosstab_col_pct_long():
    return ez.crosstab(podracing_survey, "region", "demo_gender", cell="col_pct", wide=False)


def crosstab_total_pct():
    return ez.crosstab(podracing_survey, "collector", "demo_gender", cell="total_pct", digits=1)


def crosstab_value():
    return ez.crosstab(podracing_survey, "region", "demo_gender", value="nps_value")


def crosstab_registered():
    ez.register_order_presets()
    return ez.crosstab(podracing_survey, "satis_return", "demo_edu")


def crosstab_weighted():
    target = {"variable": "collector", "email": 1, "panel": 1, "socials": 1, "in_app": 1}
    return ez.crosstab(podracing_survey, "region", "demo_gender", cell="col_pct", weights=target)


def crosstab_named_value():
    return ez.crosstab(NAMED_CELLS, "value", "n")


def crosstab_named_n_row_pct():
    return ez.crosstab(NAMED_CELLS, "n", "value", cell="row_pct")


def crosstab_named_value_long():
    return ez.crosstab(NAMED_CELLS, "value", "n", wide=False)


def crosstab_factor_order():
    return ez.crosstab(AGREE_FACTORS, "agree", "group")


def crosstab_registered_columns():
    ez.register_order("size", ["S", "M", "L"], vars="size")
    d = pd.DataFrame({"shop": ["x", "x", "y", "y"], "size": ["M", "L", "S", "M"]})
    return ez.crosstab(d, "shop", "size")


def compare_values_basic():
    current = pd.DataFrame({"feature": ["price", "quality", "new"], "performance": [2.8, 4.4, 1.0]})
    previous = pd.DataFrame({"feature": ["price", "quality", "gone"], "performance": [3.1, 4.2, 2.0]})
    return ez.compare_values(current=current, previous=previous)


# ---- Diagnostics ----


def se_mean_basic():
    return ez.se_mean([4, 5, 3, 4, 5, 2, 4])


def se_prop_basic():
    return ez.se_prop([0.33, 33], 1184, pctp=True)


def rse_rating_bands():
    return ez.rse_rating([3, 8, 12, 20, 40, None])


def diagnose_mixed():
    return ez.diagnose(podracing_survey, "demo_gender", "nps_value", ez.starts_with("ratings_"))


def diagnose_by():
    return ez.diagnose(podracing_survey, "nps_value", "demo_gender", by="region")


def precision_summary_podracing():
    return ez.precision_summary(podracing_survey)


# ---- NPS ----


def calc_nps_basic():
    return ez.calc_nps(podracing_survey, "nps_value")


def calc_nps_by():
    return ez.calc_nps(podracing_survey, "nps_value", by="region")


def calc_nps_weighted():
    target = {"variable": "demo_gender", "Female": 0.5, "Male": 0.5}
    return ez.calc_nps(shopping_survey, "recommend", weights=target)


# ---- Import ----


def select_prefix_basic():
    return ez.select_prefix(podracing_survey, ["ratings_", "partner_"], keep="respondent_id")


def select_suffix_basic():
    return ez.select_suffix(podracing_survey, "_com", keep="respondent_id")


def parse_filename_basic():
    frame = pd.DataFrame({"file": ["podracing_wave1_NA_2026.csv", "short_name.csv"]})
    return ez.parse_filename(frame, into=["survey", "wave", "locale", "year"])


# ---- Banner ----


def banner_two_by_two():
    return ez.crosstab_banner(podracing_survey, rows=["satis_return", "demo_edu"], cols=["demo_gender", "region"])


def banner_numeric():
    return ez.crosstab_banner(podracing_survey, rows=["nps_value", "demo_age"], cols="demo_gender")


def banner_diff():
    return ez.crosstab_banner(podracing_survey, rows="satis_return", cols="region", cell="diff")


def banner_long():
    return ez.crosstab_banner(
        podracing_survey,
        rows=["satis_return", ez.starts_with("motivations_")],
        cols="collector",
        long=True,
        total=False,
    )


def banner_counts_weighted():
    return ez.crosstab_banner(
        podracing_survey,
        rows=["demo_job", "demo_age"],
        cols="region",
        cell="count",
        stats=["mean", "p25", "p75"],
        weights=GENDER_TARGET,
    )


def banner_registered():
    ez.register_order_presets()
    return ez.crosstab_banner(podracing_survey, rows=["satis_return", "ratings_speed"], cols=["demo_edu", "satis_return"])


def banner_auto():
    return ez.crosstab_banner(podracing_survey)


def banner_auto_shopping():
    return ez.crosstab_banner(shopping_survey, max_levels=8)


def banner_mean_error():
    return ez.crosstab_banner(podracing_survey, rows="demo_gender", cols="region", cell="mean")


def banner_empty():
    return ez.crosstab_banner(podracing_survey.iloc[0:0], rows="demo_gender", cols="region")


def banner_named_value():
    return ez.crosstab_banner(NAMED_CELLS, rows="value", cols="n", cell="count")


def banner_factor_order():
    return ez.crosstab_banner(AGREE_FACTORS, rows="agree", cols="group")


# ---- Drivers ----


def importance_rwa():
    return ez.calc_importance(podracing_survey, "nps_value", ez.starts_with("ratings_"))


def importance_rwa_shopping():
    return ez.calc_importance(shopping_survey, "recommend", ez.starts_with("ratings_"))


def importance_correlation():
    return ez.calc_importance(podracing_survey, "nps_value", ez.starts_with("ratings_"), method="correlation")


def ipm_podracing():
    return ez.ipm_model(podracing_survey, "nps_value", "ratings_")


def ipm_shopping_correlation():
    return ez.ipm_model(shopping_survey, "recommend", "ratings_", method="correlation")


def ipm_no_prefix():
    return ez.ipm_model(podracing_survey, "nps_value", "nothing_")


# ---- Comments ----


def prep_comments_both():
    trim = {"min_chars": 30, "max_chars": 60, "exclude": "production"}
    return comments.prep_comments(podracing_survey, ["nps_com", "show_com"], trim)


def tfidf_matrix():
    trim = {"min_chars": 30, "max_chars": 400, "exclude": None}
    long = comments.prep_comments(podracing_survey, ["nps_com", "show_com"], trim)
    matrices = comments.build_tfidf(long["comment"].tolist()[:60], comments.resolve_stopwords(None))
    return pd.DataFrame(matrices["tfidf"], columns=matrices["vocab"])


def comment_info():
    trim = {"min_chars": 30, "max_chars": 400, "exclude": None}
    long = comments.prep_comments(podracing_survey, ["nps_com", "show_com"], trim)
    matrices = comments.build_tfidf(long["comment"].tolist(), comments.resolve_stopwords(None))
    entropy = [comments.shannon_bits(row) for row in matrices["tf"]]
    return pd.DataFrame({"entropy": entropy, "tfidf": matrices["tfidf"].sum(axis=1)})


# ---- Chart decisions ----


def bar_decision(table, **options):
    chart = ez.plot_bars(table, **options)
    label = chart.data.columns[0]
    built = build_plot(chart)
    bars = built.layers[0].data
    flipped = type(chart.coordinates).__name__ == "coord_flip"
    return {
        "levels": " | ".join(str(level) for level in chart.data[label].cat.categories),
        "width": float(bars["xmax"].iloc[0] - bars["xmin"].iloc[0]),
        "ymax": float(built.layout.panel_scales_y[0].limits[1]),
        "flipped": flipped,
        "text_size": float(built.layers[2].geom.aes_params["size"] / PT),
    }


def bar_decisions():
    ez.register_order_presets()
    rows = [
        bar_decision(ez.calc_percentage(podracing_survey, "demo_gender")),
        bar_decision(ez.calc_percentage(podracing_survey, "fav_driver")),
        bar_decision(ez.calc_percentage(podracing_survey, "fav_driver"), orientation="cols"),
        bar_decision(ez.calc_percentage(podracing_survey, "demo_edu")),
        bar_decision(ez.calc_percentage(podracing_survey, "demo_job", sort="desc"), sort="none"),
        bar_decision(ez.calc_percentage(podracing_survey, "race_attended"), wrap=15),
        bar_decision(ez.calc_percentage_multi(podracing_survey, "motivations_"), max=100),
    ]
    return pd.DataFrame(rows)
