# Draw the R half of the side-by-side chart sheet: the same charts
# parity/side_by_side.py draws in Python, written to parity/charts/r/.
# Usage: Rscript parity/side_by_side.R

suppressMessages(library(ezrsurvey))

here <- dirname(sub("--file=", "", grep("--file=", commandArgs(FALSE), value = TRUE)))
out <- file.path(here, "charts", "r")
dir.create(out, showWarnings = FALSE, recursive = TRUE)

d <- podracing_survey
europe <- calc_percentage(d[d$region == "Europe", ], demo_gender)
asia <- calc_percentage(d[d$region == "Asia", ], demo_gender)
quotes <- sample_comments(d, nps_com, show_com, n = 4, seed = 1)

charts <- list(
  bars_gender = plot_bars(calc_percentage(d, demo_gender)),
  bars_driver = plot_bars(calc_percentage(d, fav_driver)),
  bars_edu_ordered = {
    register_order_presets()
    plot_bars(calc_percentage(d, demo_edu))
  },
  stacked = plot_rating_grid(d, "ratings_"),
  nps = plot_nps(d, nps_value),
  gauge = plot_nps_gauge(23),
  gauges = plot_gauges(c("Net Promoter Score" = 23, "Average quality rating" = 3.4)),
  ipm = plot_ipm(ipm_model(d, nps_value, "ratings_")),
  quotes = plot_quotes_tree(quotes),
  diff = plot_diff(compare_values(europe, asia, by = "demo_gender", value = "pct"),
                   label = demo_gender)
)

for (name in names(charts)) {
  ggplot2::ggsave(file.path(out, paste0(name, ".png")), charts[[name]],
                  width = 8, height = 4.5, dpi = 100, bg = "white")
  cat("saved", name, "\n")
}
