"""Load the four bundled datasets from their CSV copies of the R package's data. Each access returns a fresh copy, so editing one never changes the next."""

from pathlib import Path

import pandas as pd

DATA_FOLDER = Path(__file__).resolve().parent / "data"
DATASET_NAMES = ["podracing_survey", "shopping_survey", "country_region", "currency_rates"]
LOADED = {}
MISSING_MARK = "<NA>"

DATASET_DOCS = {
    "podracing_survey": """Simulated pod-racing fan survey.

A fictional consumer-feedback survey from a Boonta Eve-style pod-racing meeting,
an affectionate Star Wars parody used throughout the ezrsurvey examples and
tests. A latent enjoyment drives correlated attribute ratings and the recommend
score, the demographics use international-standard categories (ISO/IEC 5218 sex,
ISCED education, ILO labour-force status, ISIC sectors, ISO 3166 countries), and
the multi-select, sponsor and open-text columns mirror the shapes the helpers
consume. Blanks and "Prefer not to answer" responses are sprinkled in so
cleaning helpers have something to do. A DataFrame with 1,000 rows and 32
columns: respondent_id, collector, demo_age, demo_gender, demo_edu,
demo_country, region, demo_job, demo_sector, race_attended, fav_driver,
nps_value (0-10), satis_return, six worded ratings_* columns (Very bad .. Very
good), five motivations_* multi-select columns, partner_recall_* and
partner_likeability_* for three sponsors, and the open-text nps_com and
show_com.""",
    "shopping_survey": """Simulated historical shopping-behaviour survey.

A fictional survey of patrons of a turn-of-the-century (c. 1905) general
emporium, written in an Edwardian register for colour. A latent satisfaction
drives the worded attribute ratings and the recommend score together. A
DataFrame with 800 rows and 25 columns: patron_id, demo_age, demo_gender,
demo_country, region, social_class, occupation, household_size, weekly_spend
(shillings), payment, transport, visit_frequency (Never .. Always), recommend
(0-10), five worded ratings_* columns, six reasons_* multi-select columns and
the open-text comment.""",
    "country_region": """Country to region lookup.

Maps country names to a world region and a finer subregion, used by
recode_region() and add_region(). A DataFrame with 255 rows: country, iso2
(ISO 3166-1 alpha-2, missing for Kosovo), iso3, region and subregion. Namibia's
alpha-2 code is the two letters "NA", not a missing value.""",
    "currency_rates": """Currency exchange-rate snapshot.

A dated, approximate table of exchange rates used by convert_currency() and
add_currency() when no custom rates are supplied: currency (ISO 4217 code),
name, and per_usd (units of the currency per 1 US dollar). Not live rates. The
snapshot date is in currency_rates.attrs["snapshot_date"].""",
}


def column_types(name):
    meta = pd.read_csv(DATA_FOLDER / f"{name}.meta.csv", dtype=str, keep_default_na=False)
    columns = {}
    attrs = {}
    for kind, key, value in zip(meta["kind"], meta["name"], meta["value"]):
        if kind == "column":
            columns[key] = value
        else:
            attrs[key] = value
    return {"columns": columns, "attrs": attrs}


def read_dataset(name):
    types = column_types(name)
    frame = pd.read_csv(
        DATA_FOLDER / f"{name}.csv",
        dtype=str,
        keep_default_na=False,
        na_values=[MISSING_MARK],
        encoding="utf-8",
    )
    for column, r_type in types["columns"].items():
        if r_type == "integer":
            wanted = "Int64" if frame[column].isna().any() else "int64"
            frame[column] = pd.to_numeric(frame[column]).astype(wanted)
        elif r_type == "numeric":
            frame[column] = pd.to_numeric(frame[column]).astype(float)
        elif r_type == "logical":
            frame[column] = frame[column].map({"TRUE": True, "FALSE": False})
    frame.attrs.update(types["attrs"])
    return frame


def load_dataset(name):
    """One bundled dataset as a fresh DataFrame, read from disk the first time it is asked for.

    Raises:
        ValueError: `name` is not a bundled dataset.
    """
    if name not in DATASET_NAMES:
        raise ValueError(f"Unknown dataset '{name}'. Bundled: {', '.join(DATASET_NAMES)}.")
    if name not in LOADED:
        LOADED[name] = read_dataset(name)
    return LOADED[name].copy(deep=True)
