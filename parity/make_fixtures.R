# Run the R package on every parity case and write its result, messages and
# warnings to tests/fixtures/parity/, for tests/test_parity.py to compare the
# Python port against. Cases live in parity/cases.R, one named expression each.
# Usage: Rscript parity/make_fixtures.R [case name ...]

suppressMessages(library(ezrsurvey))
suppressMessages(library(jsonlite))

args <- commandArgs(trailingOnly = TRUE)
here <- dirname(sub("--file=", "", grep("--file=", commandArgs(FALSE), value = TRUE)))
out_dir <- file.path(here, "..", "tests", "fixtures", "parity")
dir.create(out_dir, showWarnings = FALSE, recursive = TRUE)
source(file.path(here, "cases.R"))

column_info <- function(x) {
  if (is.factor(x)) {
    return(list(type = if (is.ordered(x)) "ordered" else "factor",
                levels = levels(x)))
  }
  list(type = class(x)[1])
}

column_text <- function(x) {
  if (is.factor(x)) x <- as.character(x)
  if (is.double(x)) {
    short <- sprintf("%.15g", x)
    exact <- suppressWarnings(as.numeric(short)) == x
    x <- ifelse(!is.na(exact) & exact, short, sprintf("%.17g", x))
    x[is.na(exact)] <- NA
  }
  x <- as.character(x)
  x[is.na(x)] <- "<NA>"
  x
}

as_frame <- function(value) {
  if (is.data.frame(value)) return(value)
  data.frame(value = value)
}

write_value <- function(name, value, record) {
  if (is.null(value)) {
    record$kind <- "null"
    return(record)
  }
  if (inherits(value, "ezrsurvey_precision")) {
    record$fields <- list(n = value$n, overall_rse = value$overall_rse,
                          rating = value$rating, bullets = I(value$bullets))
    value <- value$table
    record$kind <- "precision"
  } else {
    record$kind <- if (is.data.frame(value)) "frame" else "vector"
  }
  frame <- as_frame(unclass_vector(value))
  record$columns <- lapply(frame, column_info)
  record$names <- I(names(frame))
  attrs <- setdiff(names(attributes(value)), c("names", "row.names", "class"))
  record$attrs <- lapply(stats::setNames(attrs, attrs), function(a) {
    x <- attr(value, a)
    if (is.data.frame(x)) lapply(x, function(column) I(as.character(column))) else I(x)
  })
  text <- as.data.frame(lapply(frame, column_text), stringsAsFactors = FALSE,
                        check.names = FALSE)
  names(text) <- names(frame)
  # A binary connection, so a line break inside a label stays "\n" on Windows.
  con <- file(file.path(out_dir, paste0(name, ".csv")), open = "wb")
  write.csv(enc2utf8_frame(text), con, row.names = FALSE)
  close(con)
  record
}

enc2utf8_frame <- function(frame) {
  frame[] <- lapply(frame, enc2utf8)
  frame
}

unclass_vector <- function(value) {
  if (is.data.frame(value) || is.factor(value)) return(value)
  if (is.atomic(value)) return(as.vector(value))
  value
}

run_case <- function(name, expr) {
  messages <- character(0)
  warnings <- character(0)
  error <- NULL
  value <- withCallingHandlers(
    tryCatch(eval(expr, envir = new.env(parent = globalenv())),
             error = function(e) {
               error <<- conditionMessage(e)
               NULL
             }),
    message = function(m) {
      messages <<- c(messages, sub("\n$", "", conditionMessage(m)))
      invokeRestart("muffleMessage")
    },
    warning = function(w) {
      warnings <<- c(warnings, conditionMessage(w))
      invokeRestart("muffleWarning")
    }
  )
  record <- list(messages = I(messages), warnings = I(warnings))
  if (!is.null(error)) {
    record$kind <- "error"
    record$error <- error
  } else {
    record <- write_value(name, value, record)
  }
  writeLines(toJSON(record, auto_unbox = TRUE, pretty = TRUE, null = "null",
                    digits = NA),
             file.path(out_dir, paste0(name, ".json")), useBytes = TRUE)
}

wanted <- if (length(args)) args else names(cases)
for (name in wanted) {
  cat(name, "\n")
  run_case(name, cases[[name]])
  ezrsurvey::clear_dataset()
  ezrsurvey::clear_weights()
  ezrsurvey::reset_ezrsurvey_options()
  for (o in ezrsurvey::list_orders()$name) ezrsurvey::remove_order(o)
}
