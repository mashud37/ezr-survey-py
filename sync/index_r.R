# List every top-level definition in an R package with the lines it spans,
# including the comment block above it, for sync/check.py to fingerprint.
# Usage: Rscript sync/index_r.R <package folder> <output csv>

args <- commandArgs(trailingOnly = TRUE)
pkg <- args[[1]]
out <- args[[2]]

ns <- readLines(file.path(pkg, "NAMESPACE"))
ns <- ns[startsWith(ns, "export(")]
exports <- gsub('"', "", substr(ns, 8, nchar(ns) - 1), fixed = TRUE)

rows <- list()
for (f in list.files(file.path(pkg, "R"), pattern = "[.]R$", full.names = TRUE)) {
  lines <- readLines(f, warn = FALSE)
  exprs <- parse(f, keep.source = TRUE)
  refs <- attr(exprs, "srcref")
  for (i in seq_along(exprs)) {
    e <- exprs[[i]]
    if (!is.call(e) || !as.character(e[[1]])[1] %in% c("<-", "=")) next
    name <- as.character(e[[2]])
    if (length(name) != 1) next
    start <- refs[[i]][1]
    top <- start
    while (top > 1 && startsWith(trimws(lines[top - 1]), "#")) top <- top - 1
    is_fun <- is.call(e[[3]]) && identical(e[[3]][[1]], as.name("function"))
    rows[[length(rows) + 1]] <- data.frame(
      name = name,
      file = basename(f),
      doc_start = top,
      end = refs[[i]][3],
      is_function = is_fun,
      exported = name %in% exports
    )
  }
}

write.csv(do.call(rbind, rows), out, row.names = FALSE)
