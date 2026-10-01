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

The documentation, with articles and a page for every function, is at
<https://mashud37.github.io/ezr-survey-py/>.

## Installation

```sh
pip install "ezrsurvey[all]"
```

The core needs pandas, numpy, plotnine and PyYAML. Extras add the optional features:

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

# 1. Percentages
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
Python warnings. Results match R's, rounding included. Where the two languages cannot agree
(random draws, chart pixels, Office table styling) `CONVENTIONS.md` lists the difference.

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
ezrsurvey/        the package, its bundled datasets and report templates
tests/            the test suite, including comparisons with the R package's own output
parity/           the R script that writes that output
data-raw/         the R script that exports the bundled datasets
sync/             which R functions changed since they were ported
docs/             the documentation site
CONVENTIONS.md    how R's conventions read in Python, and where they differ
```

## Development

| Action | Command |
| --- | --- |
| Install for development | `pip install -e ".[all,test,docs]"` |
| Run the tests | `pytest` |
| List R changes not yet ported | `python sync/check.py` |
| Rewrite the R reference output | `Rscript parity/make_fixtures.R` |
| Build the documentation site into `docs/_site/` | `cd docs`, then `quartodoc build` and `quarto render` |

## License

MIT © Andreas Schellewald
