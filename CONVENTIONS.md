# ezrsurvey for Python: conventions

The contract every module in this port follows. The R family's
[`CONVENTIONS.md`](https://github.com/mashud37/ezr-research/blob/main/CONVENTIONS.md) governs what
the package does; this file says how each of its rules reads in Python. The workspace coding style
governs how the code reads, with the exceptions listed at the end.

## 1. The R package is the specification

- **Same names, arguments, defaults and results.** A function keeps its R name and its R argument
  names in R's order. A result has the same columns, in the same order, with the same values.
- **Same words.** Errors, warnings and messages copy R's wording. Where the wording quotes R syntax
  it becomes the Python equivalent (`levels =` becomes `levels=`, `TRUE` becomes `True`, `NULL`
  becomes `None`), and nothing else changes.
- **A difference the language forces is written down**: in the function's docstring, in `PLAN.md`,
  and as `diverged` in `sync/port-index.csv`. The ones so far are listed in section 5.

## 2. How R reads in Python

| R | Python |
|---|---|
| Bare column `demo_gender` | the string `"demo_gender"` |
| `by = c(year, game)` | `by="year"` or `by=["year", "game"]` |
| tidyselect in `...` | `*columns`, taking names and `starts_with()`, `ends_with()`, `contains()`, `everything()`, `all_of()`, `any_of()`, `where()` |
| `data %>% f(x)` | `data.pipe(f, "x")` |
| tibble | `pandas.DataFrame` with a fresh `RangeIndex` |
| factor / ordered factor | categorical column, `ordered=True` for an explicit or registered order |
| `NA` | `NaN` in number and text columns; nullable `Int64` where R returns an integer vector with `NA` |
| an attribute (`attr(x, "banner_spanners")`) | `DataFrame.attrs["banner_spanners"]` |
| an S3 result with `print()` | a small class with `__repr__` and `_repr_html_` |
| `message()` | one line on stderr |
| `warning()` | `warnings.warn(..., UserWarning)` |
| `stop()` | `raise ValueError(...)`; no custom exception classes |
| `options(ezrsurvey.x = )` | `ezrsurvey_options(x=...)` |
| `set.seed()` | `numpy.random.seed()`, or the function's own `seed=` |

A function that returns a column-like vector in R returns a pandas `Series`; one that returns a
single number returns a float.

## 3. R's arithmetic, reproduced

`ezrsurvey/rbase.py` holds the base R behaviours results depend on, and every module uses it
rather than the pandas or numpy equivalent where the two disagree:

- **Rounding** follows R's `round()` algorithm, which breaks ties differently from Python's
  `round()` (6.325 to two places is 6.32 in R and 6.33 in Python).
- **Sums, means, standard deviations and quantiles** accumulate as R does (`r_sum`, `r_mean`,
  `r_sd`, `r_quantile`), so a value on a rounding boundary rounds the same way.
- **Grouped summaries** come out in dplyr's order (`tables.py`): by factor level, else by text in
  the C locale, missing values last. Base R's `order()` and `sort()` use English collation instead
  (`sort_key()`), and `pivot_wider()` names columns in order of first appearance.
- **Text conversion** matches `as.character()` (`25`, not `25.0`).

## 4. The ezr core in Python

- **Options and profiles** read and write the same `.ezrsurvey.yml` files as R, in the same
  folders: the per-user folder R's `tools::R_user_dir()` names, the home directory, and the
  project. An R user and a Python user on one project share one house style.
- **The default dataset, weights, orders and options** are session state, held in one
  module-level dict each and changed only through their verbs.
- **Output paths** go through `resolve_output_path()`: a bare file name lands in
  `ezrsurvey-outputs/`, said once per session; a path naming a folder is used as written.
- **Progress, confirmation and checkpoints** follow R's section 9: announce before each item, stay
  silent and never prompt outside an interactive session, checkpoint after each item through a
  `.part` file, and delete only the checkpoints the package named itself.
- **Optional dependencies** are extras (`drivers`, `excel`, `reports`, `quotes`, `repel`) imported
  inside the function that needs them, failing with a `pip install` hint.
- **Charts are static**: plotnine, rendered to images. Nothing interactive.

## 5. Differences the language forces

| Where | R | Python | Why |
|---|---|---|---|
| `convert_currency()`, `add_currency()` | `from` | `from_` | `from` is a Python keyword |
| `add_currency()` | bare name is a column, quoted string a constant | a string naming a column of `data` is a column, any other string a constant | Python strings cannot tell the two apart |
| `sample_comments_diverse()` | `lambda` | `lambda_` | `lambda` is a Python keyword |
| `export_xlsx()` | tables named or not, in argument order | unnamed tables first, then named ones | Python puts keyword arguments after positional ones |
| `read_folder()` | `locale = readr::locale(...)` | `encoding=` | pandas takes the encoding directly |
| `crosstab_banner(flextable = TRUE)` | a flextable | a DataFrame with a two-level column header | the pandas form of a spanning header |
| random draws (`seed =`, `method = "forest"`) | R's generator | numpy's | same seed, different rows; tests check behaviour |
| forest importance | out-of-bag `%IncMSE` from randomForest | the same measure computed on scikit-learn's trees | values differ, rankings agree |
| sorting text | the session locale | a fixed English collation (`sort_key()`) | Python has no portable locale sort |
| checkpoints | `.rds` | `.pkl` | each language reads its own format |

## 6. Where the workspace style bends

The workspace coding style applies in full, with these exceptions, each forced by the R API:

1. **Result classes** with `__repr__`, for R's S3 results.
2. **Module-level session state** for the dataset, weights, orders, options and output notice.
3. **`*columns`** for R's tidyselect `...`, and **`**kwargs`** only where R passes `...` on to the
   function it wraps (`save_plot()` to `ggplot.save()`, `read_folder()` to `pandas.read_csv()`).
4. **Bundled datasets load lazily** through the package's `__getattr__`.
5. **An exported function takes R's arguments**, so it may exceed the five-parameter ceiling
   (`FN003`).
6. **An exported function carries R's help page in its docstring**, so its length counts code
   only; one that exceeds sixty lines through its docstring alone is marked
   `# lint-style: ignore FN001` on its `def` line.
7. **plotnine scale classes** (`scale_fill_brand`, `scale_colour_brand`) are `@dataclass`
   subclasses, because that is the only shape plotnine accepts for a scale whose palette is
   computed when the chart is drawn.

Internal helpers have none of these exceptions: more than five inputs travel as one dict.

## 7. Documentation and tests

- Every exported function has a numpydoc docstring: description, details, Parameters, Returns,
  See Also and Examples, translated from its roxygen block. Examples carry code only, never pasted
  output.
- `tests/test_<module>.py` ports R's `test-<module>.R` case by case.
- `tests/test_parity.py` compares Python with golden outputs written by the R package
  (`parity/make_fixtures.R`): numbers to 1e-9, text, types, level order, messages and warnings
  exactly. A tolerance is never loosened and a fixture never edited to make a case pass.
