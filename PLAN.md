# Porting ezrsurvey to Python

`ezrsurvey` 0.7.0 is an R package of 124 exported helpers (4,408 lines of code, 3,779 lines of
roxygen documentation, 274 tests) that reduce everyday consumer-survey analysis to single lines.
This plan ports it to Python as a PyPI package, as close to one-to-one as the language allows:
the same function names, arguments, defaults, messages, results and documentation, with only the
syntax changed. The checklist that tracks the work is the "Porting ezrsurvey to Python" section of
the workspace `TODO.md`; this document holds the reasoning behind it, and is deleted when the port
ships.

## Strategy

1. **The R package is the specification.** Behaviour, argument names, defaults, error and message
   wording, result columns and help text are copied. A Python-side improvement is a later release,
   never part of the port. Where R and Python cannot agree, the gap is written down in
   [Where parity cannot be exact](#where-parity-cannot-be-exact), not decided silently.
2. **Say it is a port, everywhere.** The README opens by saying this is the Python port of the R
   package, links to it, and names the R version it matches. So do the package metadata and the
   documentation site.
3. **Parity is measured, not claimed.** An R script runs the installed R package and writes golden
   outputs (tables, messages, warnings, layout decisions). pytest runs the same calls in Python and
   compares. A function is ported when its parity cases pass, not when it looks right.
4. **Port in dependency order.** Every summary depends on the ezr core (options, dataset, weights,
   orders, recodes); every chart depends on the summaries; every report depends on the charts.
   Each milestone ends with its tests green, so nothing is built on an unverified layer.
5. **Port 0.7.0, fixes included.** NEWS records every defect the stress suite found and how it was
   fixed. The Python port starts from the fixed behaviour and ports the tests that pin it, so none
   of those defects is rediscovered.
6. **Stay in step with R mechanically.** Every R function is mapped to its Python counterpart in a
   committed index that carries a fingerprint of the R source it was ported from. When the R
   package changes, a check names every function whose R source moved since it was ported (see
   [Keeping in step with R](#keeping-in-step-with-r)).
7. **The stress suite is the acceptance test.** `misc/ezrsurvey-stress/` runs sixteen analyst
   scenarios on real data through all 124 exports, and its R outputs are already on disk. The port
   is done when the same scenarios, written in Python, produce the same CSVs.

## Decisions

| # | Decision | Status | Choice | Why |
|---|---|---|---|---|
| D1 | Repository | settled | `ezr-survey-py/` is its own git repository. `ezr-research-py/` is a family folder, not a repository: the root repository tracks only its `README.md` and `CLAUDE.md`, like the `-workers` families. This departs from R, where the whole family is one repository | Each PyPI package gets its own history, tags and release pipeline |
| D2 | Name | settled | `ezrsurvey` on PyPI and as the import name (free on PyPI as of 2026-09-30) | Same name as the R package; CRAN and PyPI are separate namespaces |
| D3 | Version | settled | First release is `0.7.0`, meaning "parity with R 0.7.0"; later versions move with R | A user can tell which R behaviour a Python version matches |
| D4 | Data frames | settled | pandas | Your stated choice, and what survey analysts meet in every tutorial |
| D5 | Charts | settled | plotnine, static output only: no interactive or browser-widget charts, in the package or in its documentation | It implements ggplot2's grammar, so themes, scales, `annotate()`, `coord_flip()` and `plot + theme_ezrsurvey()` port line by line |
| D6 | Which rules govern the code | to confirm | `CONVENTIONS.md` (translated, living in this repository as the family's reference implementation, as `ezr-survey` is in R) governs API and behaviour; the workspace coding style governs readability (undergraduate test, ruff, lint-style ceilings, no em-dashes). Four shapes the family requires are recorded as exceptions: result classes with `__repr__`, module-level session state (dataset, weights, orders, options), `*columns` selection, and lazily loaded bundled datasets | You said ezr-survey sits outside the workspace policies; readability still matters most to a maintainer who writes R |
| D7 | Profiles | to confirm | Read and write the same `.ezrsurvey.yml` files, same keys, as R | An R analyst and a Python analyst on one project share one house style |
| D8 | Stress scenarios in Python | to confirm | `misc/ezrsurvey-stress/walkthrough-py/`, beside the R walkthroughs, reusing their data | The data is 5 MB+ with mixed licences and does not belong in a package repo; the R outputs to compare against are already there. `misc/` is off-limits by default, so this needs your yes |
| D9 | Documentation site | to confirm | quartodoc (Posit's pkgdown equivalent for Python), family-grouped like `_pkgdown.yml` | Renders with Quarto, which the package already uses for its report scaffolds |
| D10 | Pipe | to confirm | `DataFrame.pipe()` only; no custom `df.ezr` accessor in the first release | `.pipe()` is standard pandas and costs nothing; an accessor is a later convenience |
| D11 | Python floor | to confirm | 3.10 | This machine runs 3.10.11; pandas 2.2 and plotnine 0.15 support it |

## Translation rules

The same rule every time, so each function reads like its R original.

| R | Python |
|---|---|
| Bare column `demo_gender` | String `"demo_gender"` |
| `by = c(year, game)` | `by="year"` or `by=["year", "game"]` |
| tidyselect in `...` (`starts_with("ratings_")`) | `*columns` taking names and the selectors `starts_with()`, `ends_with()`, `contains()`, `everything()`, `all_of()`, exported by ezrsurvey (`select.py`) |
| `data %>% fn(x)` | `data.pipe(fn, "x")` |
| First argument shifts to a column when a dataset is set | Same test: a first argument that is not a DataFrame, with a dataset set, is the first column |
| tibble | `pandas.DataFrame` with a fresh `RangeIndex` |
| factor, ordered factor | `pandas.Categorical`, `ordered=True` for registered and explicit orders |
| `NA` | `NaN` in float and text columns; nullable `Int64` where R returns an integer vector with `NA` (`recode_likert`, `nps_group`) |
| Attribute on a result (`"banner_spanners"`) | `DataFrame.attrs["banner_spanners"]` |
| S3 class with `print()` | Small class with `__repr__` and `_repr_html_` |
| `message()` | One internal `inform()` that writes to stderr |
| `warning()` | `warnings.warn(..., UserWarning)` |
| `stop()` | `raise ValueError(...)` with the R wording; no custom exception classes |
| `match.arg()` | Check against the allowed tuple, R's error wording |
| `interactive()` | Running under IPython or Jupyter, or an interactive REPL |
| `options(ezrsurvey.x = )` | `ezrsurvey_options(x=...)`, stored in one module-level dict |
| `tools::R_user_dir("ezrsurvey", ...)` | `%APPDATA%\ezrsurvey\` on Windows, XDG folders elsewhere, stdlib only |
| `rlang::hash()` | `hashlib.sha256` over `pandas.util.hash_pandas_object` |
| `agrepl()` "Did you mean" | `difflib.get_close_matches()` |
| `readr::read_csv(col_types = character)` | `pandas.read_csv(dtype=str)` with readr's `na = c("", "NA")` |
| `set.seed()` / `seed =` | `numpy.random.default_rng(seed)`; same argument, different draws |
| `.onLoad` profile loading | Profile loaded when `ezrsurvey` is imported |

## Layout

```
projects/ezr-research-py/     family folder, not a repository (D1)
  README.md                   family map; tracked by the root repository
  CLAUDE.md                   family rules for agents; tracked by the root repository
  ezr-survey-py/              this repository
    PLAN.md                   this document, deleted when the port ships
    CONVENTIONS.md            the R conventions translated to Python, plus the D6 exceptions
    pyproject.toml            hatchling build, ruff config, extras
    README.md  NEWS.md  LICENSE
    ezrsurvey/                import package, flat layout (no src/)
      __init__.py             re-exports the public surface, loads profiles
      <one module per R file> see the mapping below
      data/                   bundled datasets as CSV plus a dtype sidecar
      templates/              the two .pptx templates (copied) and Python Quarto skeletons
      examples/               the worked report and deck, rewritten in Python
    tests/                    test_<module>.py, one per R test file, plus test_docs.py
      fixtures/parity/        golden outputs written by the R parity script
    parity/make_fixtures.R    runs R ezrsurvey and writes the golden outputs
    data-raw/export_data.R    writes the bundled .rda datasets out as CSV
    sync/                     keeps the port in step with R (see below)
      index_r.R               lists every top-level R definition with its exact line span
      port-index.csv          one row per R definition: its Python home and ported fingerprint
      r-version.txt           the R version the port currently matches
      check.py                reports what changed in R since it was ported
```

R file to Python module. The names stay the same so a reader can move between the two:

| R | Python | R | Python |
|---|---|---|---|
| `config.R` | `config.py` | `percentage.R` | `percentage.py` |
| `dataset.R` | `dataset.py` | `crosstab.R` | `crosstab.py` |
| `utils-coerce.R` | `coerce.py` | `crosstab_banner.R` | `crosstab_banner.py` |
| `progress.R` | `progress.py` | `auto_select.R` | `auto_select.py` |
| `confirm.R` | `confirm.py` | `model.R` | `model.py` |
| `orders.R` | `orders.py` | `compare.R` | `compare.py` |
| `weights.R` | `weights.py` | `diagnostics.R` | `diagnostics.py` |
| `recode.R` | `recode.py` | `comments.R` | `comments.py` |
| `generation.R` | `generation.py` | `palettes.R` | `palettes.py` |
| `region.R` | `region.py` | `theme.R` | `theme.py` |
| `currency.R` | `currency.py` | `scales.R` | `scales.py` |
| `import.R` | `import_data.py` (`import` is a keyword) | `decisions.R` | `decisions.py` |
| `data.R` | `datasets.py` | `brand.R` | `brand.py` |
| `export.R` | `export.py` | `plot.R` | `plot.py` |
| `export_summary.R` | `export_summary.py` | `report_officer.R` | `report_builder.py` |
| `report_deck.R` | `report_deck.py` | `report_quarto.R` | `report_quarto.py` |
| `zzz.R`, `ezrsurvey-package.R` | `__init__.py` | `utils-pipe.R` | dropped: `DataFrame.pipe()` |
| (tidyselect) | `select.py` | | |

## Keeping in step with R

The R package will keep changing, and every fix there has to reach Python. That is a matching
problem, so it is solved with an index rather than with memory.

**The index.** `sync/port-index.csv` has one row per top-level R definition, internal ones
included, because fixes often land in helpers (`normalise_country()`, `order_factor()`):

| Column | Holds |
|---|---|
| `r_name`, `r_file`, `exported` | the R definition |
| `py_module`, `py_name` | where it lives in Python |
| `status` | `todo`, `ported`, `dropped` (no Python counterpart, such as `%>%`) or `diverged` (ported with a documented difference) |
| `r_fingerprint` | SHA-256 of the R source lines, doc comments included, at the moment it was ported |

**Finding the R source.** `sync/index_r.R` uses R's own parser (`parse(keep.source = TRUE)`), not
pattern matching, to list every top-level definition with its exact line span, and walks upward
over the comment block above it so a documentation change counts too. It needs base R only. A
probe on 2026-09-30 found 272 definitions (251 functions) in `ezr-survey/R/`, located all 124
exports (only the re-exported `%>%` has no definition of its own), and found no duplicate names,
so a name is a safe key.

**The check.** `python sync/check.py` runs `index_r.R` against `projects/ezr-research/ezr-survey`,
fingerprints the current R source, and prints four lists:

- **changed:** ported definitions whose R fingerprint no longer matches; each needs re-porting
- **new:** R definitions with no row yet
- **removed:** rows whose R definition is gone
- **missing in Python:** rows marked `ported` whose `py_name` cannot be imported from `py_module`

It also fingerprints the bundled datasets, since a data fix (such as `country_region` gaining
rows) changes results without touching a function, and prints the `NEWS.md` sections newer than
`sync/r-version.txt`, which is where the reasoning behind each change is written.

**The workflow when R changes.** Run the check; re-port each changed definition and its tests;
regenerate the parity fixtures with `parity/make_fixtures.R`, which catches any behaviour change
the fingerprints did not; run `check.py --accept <name>` to record the new fingerprint once its
tests pass; raise the version to the R version now matched. A definition is never accepted on its
fingerprint alone.

## Dependencies

R's `Depends` are hard dependencies; its `Suggests` become optional extras that fail with an
install hint, exactly as R's `requireNamespace()` guards do.

| R | Python | Where |
|---|---|---|
| dplyr, tidyr, tibble, readr, stringr, purrr | pandas, numpy | core |
| ggplot2, scales | plotnine | core |
| yaml | pyyaml | core (profiles load at import) |
| xml2 | `zipfile` + `xml.etree` | stdlib |
| systemfonts | `matplotlib.font_manager` | comes with plotnine |
| rwa | own numpy implementation of Johnson's relative weights, checked against `rwa` | core |
| randomForest | scikit-learn | extra `drivers` |
| writexl, openxlsx2 | xlsxwriter (one writer for both `save_data()` and `export_summary_xlsx()`) | extra `excel` |
| officer, flextable | python-pptx, python-docx | extra `reports` |
| treemapify | squarify for the layout, drawn with plotnine `geom_rect` | extra `quotes` |
| ggrepel | adjustText through plotnine's `geom_text(adjust_text=)` | extra `repel` |
| stopwords | the Snowball English list bundled as data (BSD), which is what R users get | core |
| quarto | Quarto CLI, called by the user | none |

`all` installs every extra. `stats::pnorm` becomes `math.erf`, so scipy is not needed.

## Parity harness

- `parity/make_fixtures.R` loads R `ezrsurvey` and runs a list of cases: every `@examples` call,
  plus the inputs the R tests use. Each case writes its result as CSV and a JSON sidecar carrying
  column types, factor levels and order, attributes, and every message and warning text.
- `tests/test_parity.py` holds the same cases as Python calls and compares: floats to 1e-9, text
  exactly, category order exactly, message wording exactly.
- Fixtures are regenerated whenever the R package changes; that is the behavioural half of
  keeping in step, where the index is the source half.
- Charts are compared on what the code decides (orientation, sort order, bar width, label sizes,
  band geometry, gauge ticks, axis limits), which R exposes through `ggplot_build()` and
  `auto_bar_layout()`, not on pixels.

## Where parity cannot be exact

Known before starting. Each is recorded in the docstring of the function it affects, and its
index row is marked `diverged`.

- **Random draws.** `sample_comments()`, `sample_comments_diverse()` and `method = "forest"` use R's
  RNG in R and numpy's in Python, so the same `seed` picks different rows. Tests check behaviour
  (counts per group, no duplicates, the diversity score), not the rows.
- **Forest importance.** R's `%IncMSE` is out-of-bag permutation importance; scikit-learn's
  permutation importance is computed differently. Rankings are compared, not values.
- **Charts.** plotnine is not pixel-identical to ggplot2. The decisions are tested exactly; the look
  is signed off once per chart on a side-by-side sheet.
- **Office files.** python-pptx tables are styled by hand where flextable had themes. Structure is
  tested (layout chosen, placeholder sizing, slide numbers, spanning banner header).
- **Transliteration backstop.** R's `iconv(..., "ASCII//TRANSLIT")` after the hand-written fold
  becomes `unicodedata` NFKD. The hand-written fold, which decides almost every case, is identical.
- **`invisible()`.** Python has none, so Jupyter prints what R would have returned silently.
- **`edit_ezrsurvey_profile()`** opens the file with the operating system's default editor.

## Milestones

The checklist in `TODO.md` breaks these into boxes. No time estimate is given: M1 is the
calibration unit, and the remaining milestones are sized from how long it actually took.

| Milestone | Contents | Done when |
|---|---|---|
| M0 Foundations | Remaining decisions; repository, `CONVENTIONS.md`, `pyproject.toml`; sync index; bundled data exported; parity harness producing its first fixture | `sync/check.py` lists all 272 definitions as `todo`; one parity case passes end to end |
| M1 ezr core | options and profiles, default dataset, coercion, progress, confirmation, output-path resolver, selectors | `test-config`, `test-dataset`, `test-coerce`, `test-progress` ported and green |
| M2 Recode and lookups | recodes, generations, order registry, country to region, currency | Their five test files ported; every example matches R |
| M3 Summaries and weighting | weights, percentages, summary, crosstab, NPS, compare, diagnostics, import, banner with checkpoints | Their test files ported; banner matches R on the podracing and stress data |
| M4 Driver models | relative weights, correlation, forest, `ipm_model()` | Relative weights match `rwa` to 1e-6 on three datasets |
| M5 Comments | random and diverse samples, TF-IDF, entropy, MMR | `test-comments` ported; TF-IDF matrices match R |
| M6 Visual layer | palettes, themes, scales, decision bands, brand, the nine plots | Four test files ported; layout decisions match; side-by-side sheet signed off |
| M7 Save and report | savers, Excel workbook, pptx and docx builders, deck, Quarto scaffolds, worked example | Three test files ported; decks open in PowerPoint; every scaffold renders |
| M8 Acceptance | Sixteen stress scenarios and the edge-case script in Python | Every CSV matches R's; every scenario runs clean |
| M9 Release | docstrings, `test_docs.py`, examples test, README tour, NEWS, five articles, quartodoc site, TestPyPI, PyPI | `pip install ezrsurvey` from PyPI runs the README tour on a clean machine; `sync/check.py` reports nothing |

The ezr core (M1) is written to be copied verbatim into later Python ports of `ezrmodel` and the
rest, as `CONVENTIONS.md` §3 requires in R.
