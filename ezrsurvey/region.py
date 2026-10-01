"""Look up the world region of a country as people actually type it: endonyms, abbreviations and ISO codes included. Regional breakdowns of a free-text country question depend on it."""

import unicodedata

import numpy as np
import pandas as pd

from .dataset import resolve_data
from .datasets import load_dataset
from .rbase import as_character, is_missing, match_arg, warn
from .recode import na_blank

COUNTRY_ALIASES = {
    "us": "United States",
    "usa": "United States",
    "u s": "United States",
    "u s a": "United States",
    "america": "United States",
    "united states of america": "United States",
    "states": "United States",
    "estados unidos": "United States",
    "etats unis": "United States",
    "vereinigte staaten": "United States",
    "stati uniti": "United States",
    "uk": "United Kingdom",
    "gb": "United Kingdom",
    "gbr": "United Kingdom",
    "britain": "United Kingdom",
    "great britain": "United Kingdom",
    "england": "United Kingdom",
    "scotland": "United Kingdom",
    "wales": "United Kingdom",
    "northern ireland": "United Kingdom",
    "united kingdom of great britain and northern ireland": "United Kingdom",
    "reino unido": "United Kingdom",
    "royaume uni": "United Kingdom",
    "grossbritannien": "United Kingdom",
    "deutschland": "Germany",
    "de": "Germany",
    "deu": "Germany",
    "ger": "Germany",
    "holland": "Netherlands",
    "nl": "Netherlands",
    "nld": "Netherlands",
    "espana": "Spain",
    "es": "Spain",
    "esp": "Spain",
    "italia": "Italy",
    "it": "Italy",
    "ita": "Italy",
    "suisse": "Switzerland",
    "schweiz": "Switzerland",
    "ch": "Switzerland",
    "che": "Switzerland",
    "osterreich": "Austria",
    "at": "Austria",
    "aut": "Austria",
    "sverige": "Sweden",
    "se": "Sweden",
    "swe": "Sweden",
    "norge": "Norway",
    "no": "Norway",
    "nor": "Norway",
    "danmark": "Denmark",
    "dk": "Denmark",
    "dnk": "Denmark",
    "suomi": "Finland",
    "fi": "Finland",
    "fin": "Finland",
    "polska": "Poland",
    "pl": "Poland",
    "pol": "Poland",
    "eire": "Ireland",
    "republic of ireland": "Ireland",
    "ie": "Ireland",
    "irl": "Ireland",
    "brasil": "Brazil",
    "br": "Brazil",
    "bra": "Brazil",
    "nippon": "Japan",
    "jp": "Japan",
    "jpn": "Japan",
    "turkiye": "Turkey",
    "tr": "Turkey",
    "tur": "Turkey",
    "czechia": "Czech Republic",
    "cz": "Czech Republic",
    "cze": "Czech Republic",
    "aotearoa": "New Zealand",
    "nz": "New Zealand",
    "nzl": "New Zealand",
    "fr": "France",
    "fra": "France",
    "ca": "Canada",
    "can": "Canada",
    "au": "Australia",
    "aus": "Australia",
    "be": "Belgium",
    "bel": "Belgium",
    "pt": "Portugal",
    "prt": "Portugal",
    "gr": "Greece",
    "grc": "Greece",
    "ro": "Romania",
    "rou": "Romania",
    "hu": "Hungary",
    "hun": "Hungary",
    "ua": "Ukraine",
    "ukr": "Ukraine",
    "ru": "Russia",
    "rus": "Russia",
    "russian federation": "Russia",
    "cn": "China",
    "chn": "China",
    "peoples republic of china": "China",
    "in": "India",
    "ind": "India",
    "mx": "Mexico",
    "mex": "Mexico",
    "ar": "Argentina",
    "arg": "Argentina",
    "cl": "Chile",
    "chl": "Chile",
    "co": "Colombia",
    "col": "Colombia",
    "za": "South Africa",
    "zaf": "South Africa",
    "rsa": "South Africa",
    "ng": "Nigeria",
    "nga": "Nigeria",
    "ke": "Kenya",
    "ken": "Kenya",
    "eg": "Egypt",
    "egy": "Egypt",
    "il": "Israel",
    "isr": "Israel",
    "sg": "Singapore",
    "sgp": "Singapore",
    "hk": "Hong Kong",
    "hkg": "Hong Kong",
    "ph": "Philippines",
    "phl": "Philippines",
    "id": "Indonesia",
    "idn": "Indonesia",
    "my": "Malaysia",
    "mys": "Malaysia",
    "th": "Thailand",
    "tha": "Thailand",
    "vn": "Vietnam",
    "vnm": "Vietnam",
    "kr": "South Korea",
    "kor": "South Korea",
    "korea": "South Korea",
    "republic of korea": "South Korea",
    "uae": "United Arab Emirates",
    "ae": "United Arab Emirates",
    "are": "United Arab Emirates",
    "bolivia plurinational state of": "Bolivia",
    "brunei darussalam": "Brunei",
    "cabo verde": "Cape Verde",
    "eswatini": "Swaziland",
    "gambia": "Gambia, The",
    "holy see": "Holy See (Vatican City)",
    "iran islamic republic of": "Iran",
    "korea democratic peoples republic of": "Korea, North",
    "korea republic of": "Korea",
    "lao peoples democratic republic": "Laos",
    "macao": "Macau",
    "moldova republic of": "Moldova",
    "netherlands kingdom of the": "Netherlands",
    "north macedonia": "Macedonia",
    "palestine state of": "Gaza Strip",
    "pitcairn": "Pitcairn Islands",
    "syrian arab republic": "Syria",
    "taiwan province of china": "Taiwan",
    "venezuela bolivarian republic of": "Venezuela",
    "viet nam": "Vietnam",
    "virgin islands british": "British Virgin Islands",
    "virgin islands us": "Virgin Islands",
    "hong kong sar": "Hong Kong",
    "former yugoslav republic of macedonia": "Macedonia",
    "palestine": "Gaza Strip",
    "north korea": "Korea, North",
    "democratic republic of the congo": "Congo, Democratic Republic of the",
    "congo republic of the": "Congo",
    "libyan arab jamahiriya": "Libya",
    "tanzania": "Tanzania, United Republic of",
    "united republic of tanzania": "Tanzania, United Republic of",
    "republic of moldova": "Moldova",
    "democratic peoples republic of korea": "Korea, North",
    "islamic republic of iran": "Iran",
    "plurinational state of bolivia": "Bolivia",
    "bolivarian republic of venezuela": "Venezuela",
    "state of palestine": "Gaza Strip",
    "kingdom of the netherlands": "Netherlands",
    "province of china taiwan": "Taiwan",
    "\u00df": "ss",
    "\u00e6": "ae",
    "\u0153": "oe",
    "\u00fe": "th",
}

LETTER_SPELLINGS = {
    "ß": "ss",
    "æ": "ae",
    "œ": "oe",
    "þ": "th",
}

ACCENTED_LETTERS = (
    "àáâãäåāăąç"
    "ćĉċčðďđèéê"
    "ëēĕėęěĝğġģ"
    "ĥħìíîïĩīĭį"
    "ıĵķĺļľŀłñń"
    "ņňòóôõöøōŏ"
    "őŕŗřśŝşšţť"
    "ŧùúûüũūŭůű"
    "ųŵýÿŷźżž"
)

PLAIN_LETTERS = (
    "aaaaaaaaacccccdddeeeeeeeeegggghhiiiiiiiiijklllllnnnnoooooooo"
    "orrrsssstttuuuuuuuuuuwyyyzzz"
)

AMBIGUOUS_CODES = ["no", "it", "at", "be", "in", "my", "id"]
REGION_LEVELS = ["region", "subregion"]


def transliterate(text):
    """Fold what the hand-written table does not cover to ASCII, as R's iconv backstop does."""
    decomposed = unicodedata.normalize("NFKD", text)
    kept = []
    for character in decomposed:
        if unicodedata.combining(character):
            continue
        kept.append(character if character.isascii() else "?")
    return "".join(kept)


def normalise_country(x):
    """Fold typed countries down to something matchable: case, punctuation, accents and a leading "the" go."""
    out = []
    for value in as_character(x):
        if is_missing(value):
            out.append(np.nan)
            continue
        text = value.strip(" \t\r\n").lower()
        for letter, spelling in LETTER_SPELLINGS.items():
            text = text.replace(letter, spelling)
        text = text.translate(str.maketrans(ACCENTED_LETTERS, PLAIN_LETTERS))
        text = transliterate(text)
        for mark in ".,'`":
            text = text.replace(mark, "")
        text = "".join(character if "a" <= character <= "z" or character == " " else " " for character in text)
        while "  " in text:
            text = text.replace("  ", " ")
        text = text.strip(" ")
        if text.startswith("the "):
            text = text[4:]
        out.append(text)
    return pd.Series(out, dtype=object)


def canonical_country(raw):
    """The country name to look up, after the alias table; lower-case ambiguous codes stay unread."""
    keys = normalise_country(raw)
    out = []
    for value, key in zip(as_character(raw), keys):
        hit = COUNTRY_ALIASES.get(key) if isinstance(key, str) else None
        typed_lower = not is_missing(value) and value != value.upper()
        if key in AMBIGUOUS_CODES and typed_lower:
            hit = None
        out.append(key if hit is None else normalise_country([hit])[0])
    return out


def recode_region(x, which="region", quiet=False):  # lint-style: ignore FN001
    """Look up the region or subregion for a country.

    Vectorised lookup from country name to world `region` or finer `subregion`,
    using the bundled ``country_region`` table. Matching is case-insensitive and
    whitespace-tolerant, and understands the spellings people type as well as
    ISO 3166-1 alpha-2 and alpha-3 codes, so "USA", "U.S.", "us" and
    "United States" all resolve alike; blanks and non-answers (see `na_blank()`)
    become missing, and unmatched countries become missing with a one-line
    warning so spelling mismatches are easy to spot.

    A country column that people typed themselves is rarely tidy: in one real
    open salary survey, nine thousand respondents wrote "United States" and
    eight thousand wrote "USA". So the name is folded down before it is looked
    up (case, stray punctuation, accents and a leading "the" are all dropped)
    and then tried against the bundled table, then against a table of the
    spellings people actually use: endonyms ("Deutschland", "Brasil"), the
    constituent countries of the United Kingdom, and ISO 3166-1 alpha-2 and
    alpha-3 codes ("US", "USA", "DE", "DEU").

    A two-letter code is only read as a code when it was typed in capitals,
    because "NO" is Norway but "no" is an answer to a different question.
    Anything still unmatched returns missing with a warning listing the
    offenders. `region` is the coarse level (e.g. "Europe"); `subregion` is
    finer (e.g. "Western Europe").

    Parameters
    ----------
    x : list or Series
        Country names.
    which : str
        "region" (default) or "subregion".
    quiet : bool
        If False (default), warn about unmatched countries.

    Returns
    -------
    pandas.Series
        Regions (or subregions), missing where unmatched.

    See Also
    --------
    add_region, country_region

    Examples
    --------
    >>> recode_region(["Germany", "Japan", "Brazil"])
    >>> recode_region(["USA", "U.S.", "England", "Deutschland", "Holland"])
    >>> recode_region(["US", "GBR", "DE", "JPN"])
    >>> recode_subregion(["Germany", "Japan"])
    >>> recode_region(["Germany", "Atlantis"], quiet=True)
    """
    which = match_arg(which, REGION_LEVELS)
    table = load_dataset("country_region")
    raw = na_blank(as_character(x))
    table_keys = list(normalise_country(table["country"]))
    looked_up = []
    for key in canonical_country(raw):
        if isinstance(key, str) and key in table_keys:
            looked_up.append(table[which].iloc[table_keys.index(key)])
        else:
            looked_up.append(np.nan)
    out = pd.Series(looked_up, index=raw.index, dtype=object)
    if not quiet:
        missed = []
        for value, result in zip(raw, out):
            if not is_missing(value) and is_missing(result) and value not in missed:
                missed.append(value)
        if missed:
            more = ", ..." if len(missed) > 5 else ""
            warn(f"{len(missed)} country value(s) did not match a region: {', '.join(missed[:5])}{more}")
    return out


def recode_subregion(x, quiet=False):
    """Look up the subregion for a country; `recode_region()` with ``which="subregion"``.

    Parameters
    ----------
    x : list or Series
        Country names.
    quiet : bool
        If False (default), warn about unmatched countries.

    Returns
    -------
    pandas.Series
        Subregions, missing where unmatched.

    See Also
    --------
    recode_region

    Examples
    --------
    >>> recode_subregion(["Germany", "Japan"])
    """
    return recode_region(x, which="subregion", quiet=quiet)


def add_region(data=None, country=None, region_to="region", subregion=False, quiet=False):
    """Add region (and subregion) columns from a country column.

    The data-frame-friendly form of `recode_region()`: point it at an existing
    country column and it appends a region column (named via `region_to`) and,
    optionally, a ``subregion``. Handy right after `read_folder()` to enrich raw
    exports before grouping by region. The lookup, matching and
    unmatched-country warning behave exactly as in `recode_region()`.

    Parameters
    ----------
    data : pandas.DataFrame, optional
        A data frame. If omitted, the session default is used.
    country : str
        The country column.
    region_to : str
        Name of the region column to add. Defaults to "region".
    subregion : bool
        If True, also add a ``subregion`` column. Defaults to False.
    quiet : bool
        Passed to `recode_region()`.

    Returns
    -------
    pandas.DataFrame
        `data` with the new column(s) added.

    See Also
    --------
    recode_region, country_region

    Examples
    --------
    >>> df = pd.DataFrame({"demo_country": ["Germany", "Japan", "Brazil"]})
    >>> add_region(df, "demo_country", subregion=True)
    """
    out = resolve_data(data).copy()
    if country not in out.columns:
        raise ValueError(f"Column '{country}' not found in `data`.")
    out[region_to] = list(recode_region(out[country], "region", quiet=quiet))
    if subregion:
        out["subregion"] = list(recode_region(out[country], "subregion", quiet=True))
    return out
