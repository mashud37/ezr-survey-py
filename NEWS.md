# ezrsurvey for Python 0.7.0 (unreleased)

The first release: the Python port of the R package `ezrsurvey` 0.7.0.

* Every one of the R package's 124 exports has a Python counterpart with the same name, arguments,
  defaults and results, documented with R's help text translated to Python.
* Results are checked against output written by the R package itself: tables, types, level
  order, messages and warnings, numbers to 1e-9. Base R's rounding, sorting and summation are
  reproduced so values on a rounding boundary come out as R's do.
* Charts are static plotnine figures whose layout decisions (orientation, order, wrapping, bar
  width, axis ceilings, label sizes) match the R package's.
* Decks and Word documents are built with python-pptx and python-docx on the same templates, and
  the Quarto skeletons run Python through Quarto's Jupyter engine.
* Options and YAML profiles are shared with the R package, in the same files and folders.
* The language-forced differences are listed in `CONVENTIONS.md`.
