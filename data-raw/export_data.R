# Write the R package's bundled datasets out as CSV for the Python port, with a
# sidecar naming each column's R type and any attribute the dataset carries.
# Missing values are written as <NA>, because Namibia's ISO code is the text NA.
# Usage: Rscript data-raw/export_data.R <output folder>

suppressMessages(library(ezrsurvey))

out <- commandArgs(trailingOnly = TRUE)[[1]]
dir.create(out, showWarnings = FALSE, recursive = TRUE)

for (name in c("podracing_survey", "shopping_survey", "country_region",
               "currency_rates")) {
  d <- get(name, envir = asNamespace("ezrsurvey"))
  types <- vapply(d, function(column) class(column)[1], character(1))
  # Fifteen significant digits where they read back exactly, seventeen where
  # they do not, so every double survives the round trip bit for bit.
  written <- as.data.frame(d)
  for (column in names(d)[types == "numeric"]) {
    short <- sprintf("%.15g", d[[column]])
    exact <- ifelse(as.numeric(short) == d[[column]], short,
                    sprintf("%.17g", d[[column]]))
    written[[column]] <- ifelse(is.na(d[[column]]), NA, exact)
  }
  write.csv(written, file.path(out, paste0(name, ".csv")), row.names = FALSE,
            na = "<NA>", fileEncoding = "UTF-8")
  meta <- data.frame(kind = "column", name = names(d), value = unname(types))
  extra <- setdiff(names(attributes(d)), c("names", "row.names", "class"))
  for (a in extra) {
    meta <- rbind(meta, data.frame(kind = "attr", name = a,
                                   value = as.character(attr(d, a))))
  }
  write.csv(meta, file.path(out, paste0(name, ".meta.csv")), row.names = FALSE,
            fileEncoding = "UTF-8")
  cat(name, nrow(d), "rows,", ncol(d), "columns,",
      sum(is.na(d)), "missing values\n")
}

# The English stop-word list R users get from the stopwords package (Snowball,
# BSD licence), which sample_comments_diverse() removes before scoring.
writeLines(stopwords::stopwords("en"), file.path(out, "stopwords-en.txt"),
           useBytes = TRUE)
cat("stopwords-en", length(stopwords::stopwords("en")), "words\n")
