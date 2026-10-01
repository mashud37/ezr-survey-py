# ezrsurvey for Python

> **This is the Python port of the R package
> [`ezrsurvey`](https://github.com/mashud37/ezr-research/tree/main/ezr-survey).** The R package
> is the original and the specification: every function here has the same name, arguments,
> defaults and results as its R counterpart. The port tracks R version 0.7.0.

`ezrsurvey` turns the things consumer-survey analysts do over and over into single-line helpers:
loading and stacking survey exports, turning questions into percentages, recoding rating and Net
Promoter scales, weighting, cross-tabulating, modelling what drives satisfaction, checking sampling
precision, and producing static, presentation-ready charts, workbooks and decks. It is built on
pandas and plotnine, and ships the same two simulated datasets as the R package,
`podracing_survey` (a Star Wars pod-racing fan survey) and `shopping_survey` (an Edwardian
shopping survey), so every example runs out of the box.

## Installation

The port is not yet on PyPI. From a clone of this repository:

```sh
pip install -e ".[all]"
```

The core needs pandas, numpy, plotnine and PyYAML. Extras unlock the optional features, as R's
suggested packages do:

| Extra | Adds | For |
| --- | --- | --- |
| `drivers` | scikit-learn | `calc_importance(method="forest")` |
| `excel` | XlsxWriter | `.xlsx` saves, `export_xlsx()`, `export_summary_xlsx()` |
| `reports` | python-pptx, python-docx | the `report_*()` deck and Word builders |
| `quotes` | squarify | `plot_quotes_tree()` |
| `repel` | adjustText | non-overlapping labels in `plot_ipm()` |
| `all` | every extra | |

## The 60-second tour

```python
import pandas as pd
import ezrsurvey as ez

survey = ez.podracing_survey

# 1. Percentages, no groupby/value_counts/pivot ritual
ez.calc_percentage(survey, "demo_gender", sort="desc")

# Drop catch-all answers; the kept ones re-base to ~100%
ez.calc_percentage(survey, "demo_job", drop="Unemployed")

# Check-all-that-apply questions, by prefix
ez.calc_percentage_multi(survey, "motivations_", id="respondent_id", sort="desc")

# ...or packed into one cell per respondent, the way spreadsheets export them
packed = pd.DataFrame({"respondent": [1, 2, 3], "motivations": ["Speed; Drivers", "Speed", "Betting"]})
ez.calc_percentage_multi(packed, "motivations", id="respondent")
ez.split_multi(packed, "motivations")

# Grouped and pivoted to a wide cross-tab
ez.calc_percentage(survey, "satis_return", by="region", wide=True)

# A master banner table: questions down the side, groups across the top
ez.crosstab_banner(survey, rows=["satis_return", "nps_value"], cols=["demo_gender", "region"])

# 2. A labelled bar chart: orientation, wrapping and order chosen automatically
ez.calc_percentage(survey, "fav_driver").pipe(ez.plot_bars)

# A whole block of rating questions as one stacked chart
ez.plot_rating_grid(survey, "ratings_")

# 3. NPS and the gauge
ez.plot_nps_gauge(ez.calc_nps(survey, "nps_value")["nps"].iloc[0])

# 4. Importance / performance modelling
ez.ipm_model(survey, "nps_value", "ratings_").pipe(ez.plot_ipm)

# 5. Survey precision diagnostics
ez.diagnose(survey, "demo_gender", ez.starts_with("ratings_"))

# 6. Quick saves; a bare name lands in ezrsurvey-outputs/
ez.calc_percentage(survey, "demo_gender").pipe(ez.save_data, "gender.xlsx")
ez.save_plot(ez.plot_bars(ez.calc_percentage(survey, "demo_gender")), "gender.svg")
ez.export_summary_xlsx(survey, "demo_gender", "satis_return", "nps_value")
```

## From R to Python

The same call reads almost the same way. Column names become strings, `c()` becomes a list, the
tidyselect helpers are exported by the package, and `%>%` becomes `DataFrame.pipe()`:

| R | Python |
| --- | --- |
| `calc_percentage(d, demo_gender, by = c(region, collector))` | `ez.calc_percentage(d, "demo_gender", by=["region", "collector"])` |
| `diagnose(d, starts_with("ratings_"))` | `ez.diagnose(d, ez.starts_with("ratings_"))` |
| `d %>% calc_percentage(demo_gender) %>% plot_bars()` | `d.pipe(ez.calc_percentage, "demo_gender").pipe(ez.plot_bars)` |
| `set_weights(c(variable = "demo_gender", Male = 0.49, Female = 0.51))` | `ez.set_weights({"variable": "demo_gender", "Male": 0.49, "Female": 0.51})` |
| `convert_currency(100, from = "EUR")` | `ez.convert_currency(100, from_="EUR")` |

Factors become categorical columns, `NA` becomes `NaN`, messages go to stderr and warnings are
Python warnings. Results match R's to the last digit, rounding included; a test suite compares
every covered function against output written by the R package itself. Where the two languages
cannot agree (random draws, chart pixels, Office table styling) the difference is written down in
`CONVENTIONS.md`.

Options and profiles are shared: the port reads and writes the same `.ezrsurvey.yml` files, in
the same folders, as the R package, so an R user and a Python user on one project share one house
style.

## Where output goes

Every save writes into an `ezrsurvey-outputs/` folder in the working directory, created on demand,
and the first save of a session says so. A path that names a directory is used exactly as written:
`"./nps.png"` for the working directory, `"charts/nps.png"` for a folder of your own, or any
absolute path. `ez.ezrsurvey_options(output_dir=".")` puts bare names back in the working
directory.

## Layout

```
ezrsurvey/        the package: one module per R source file, plus the bundled data and templates
tests/            one test file per R test file, and the parity tests against R's own output
parity/           the R script that writes the golden outputs the parity tests compare against
data-raw/         the R script that exports the bundled datasets to CSV
sync/             the index that keeps the port in step with the R package
docs/             the documentation site: articles, the datasets page and the reference config
CONVENTIONS.md    how the R package's rules read in Python, and where the port differs
```

## Documentation site

The site is built with quartodoc, which writes a reference page per function grouped as
`ezrsurvey/families.py` groups them, and Quarto, which renders those pages and the articles:

```sh
pip install -e ".[all,docs]"
cd docs
quartodoc build
quarto render
```

The finished site lands in `docs/_site/`. `pytest` runs every article's code, so an article that
stops working fails the tests before it fails the site.

## Keeping in step with R

`python sync/check.py` compares the R package with the fingerprint recorded when each of its 272
definitions was ported, and lists anything that changed, appeared or disappeared since, with the
R package's new `NEWS.md` entries. `Rscript parity/make_fixtures.R` regenerates the golden
outputs, and `pytest` compares the port against them.

## License

MIT © Andreas Schellewald
