# Parity cases: one named R expression each. tests/parity_cases.py holds the
# same calls in Python under the same names. Session state (dataset, weights,
# options, orders) is reset after every case.

# Two questions named after the columns crosstab() used to count under, and two
# factors whose level order is not alphabetical.
named_cells <- data.frame(
  value = c("Low", "High", "High", "Low", "High", "Low"),
  n = c("A", "A", "B", "B", "B", "A")
)
agree_levels <- c("Strongly disagree", "Disagree", "Agree", "Strongly agree")
agree_factors <- data.frame(
  agree = factor(c("Disagree", "Agree", "Strongly agree", "Agree"), levels = agree_levels),
  group = factor(c("Old", "Young", "Old", "Young"), levels = c("Young", "Old"))
)

cases <- list(
  # ---- Coerce and recode ----
  ensure_numeric_messy = quote(ensure_numeric(c("25 years", "31", "forty"), name = "age")),
  ensure_numeric_scale = quote(ensure_numeric(c("8 - very likely", "10", "3.5/5"), quiet = TRUE)),
  na_blank_default = quote(na_blank(c("Yes", "", "Prefer not to answer", "No", NA, "  No  "))),
  na_blank_also = quote(na_blank(c("a", "n/a", "N/A"), also = c("n/a", "N/A"))),
  drop_items_basic = quote(drop_items(c("Yes", "No", "Other", " don't know "), items = c("Other", "Don't know"))),
  bin_numeric_basic = quote(bin_numeric(c(15, 19, 27, 41, NA), breaks = c(0, 18, 25, 35, Inf),
                                        labels = c("<18", "18-24", "25-34", "35+"))),
  bin_numeric_outside = quote(bin_numeric(c(10, 50, 60), breaks = c(18, 25, 40.5),
                                          labels = c("18 to 24", "25 to 40+"))),
  recode_age_messy = quote(recode_age(c("17", "22 years", "31", "47", "young", ""))),
  recode_likert_basic = quote(recode_likert(c("Very bad", "Ok", "Good", "Very good", "4 - Good", "nope", NA))),
  recode_likert_nested = quote(recode_likert(c("\U0001F642 Very good", "\U0001F610 Good"))),
  recode_likert_synonyms = quote(recode_likert(c("Dissatisfied", "Satisfied", "Very dissatisfied"),
                                               synonyms = list(Bad = "Dissatisfied", Good = "Satisfied",
                                                               "Very bad" = "Very dissatisfied"))),
  recode_likert_bad_synonym = quote(recode_likert("x", synonyms = list(Great = "x"))),
  nps_group_codes = quote(nps_group(c(0, 6, 7, 8, 9, 10, 11, NA, "9 - likely"))),
  nps_group_labels = quote(nps_group(c(3, 8, 10), labels = TRUE)),
  split_multi_packed = quote(split_multi(
    data.frame(respondent = 1:4, motivations = c("Speed; Drivers", "Speed", "", "Betting; Speed")),
    motivations)),
  split_multi_empty = quote(split_multi(data.frame(a = c("", NA)), a)),
  clean_label_basic = quote(clean_label(c("Broadcast.quality...audio", "ratings_Camera.work",
                                          "ratings_Talent...analysis"), prefix = "ratings_")),

  # ---- Generation, region, currency ----
  generation_scheme_pew = quote(generation_scheme("pew")),
  recode_generation_year = quote(recode_generation(c(1990, 2001, 1968, 1900, 2020), input = "year")),
  recode_generation_age = quote(recode_generation(c(36, 25, "40 years"), input = "age", year = 2026)),
  recode_region_spellings = quote(recode_region(c("USA", "U.S.", "England", "Deutschland", "Holland",
                                                  "NO", "no", "Timor-Leste", "Cote d'Ivoire",
                                                  "the Netherlands", "España", "", NA))),
  recode_region_codes = quote(recode_region(c("US", "GBR", "DE", "JPN", "Korea, North"))),
  recode_region_unmatched = quote(recode_region(c("Germany", "Atlantis", "Narnia", "Mordor",
                                                  "Oz", "Gondor", "Atlantis"))),
  recode_subregion_basic = quote(recode_subregion(c("Germany", "Japan", "Brazil"))),
  add_region_basic = quote(add_region(tibble::tibble(demo_country = c("Germany", "Japan", "Brazil")),
                                      demo_country, subregion = TRUE)),
  convert_currency_basic = quote(convert_currency(c(100, 50), from = c("EUR", "GBP"), to = "USD")),
  convert_currency_cross = quote(convert_currency(100, "EUR", "RMB")),
  convert_currency_unknown = quote(convert_currency(c(100, 10), c("EUR", "XYZ"), "USD")),
  convert_currency_rates = quote(convert_currency("$1,200", "EUR", "GBP", rates = c(EUR = 0.9, GBP = 0.8))),
  add_currency_column = quote(add_currency(tibble::tibble(spend = c(100, 200, 50),
                                                          currency = c("EUR", "GBP", "JPY")),
                                           spend, from = currency, to = "USD")),
  add_currency_constant = quote(add_currency(tibble::tibble(spend = c(100, 200)), spend,
                                             from = "EUR", into = "spend_usd")),
  list_currencies_default = quote(list_currencies()),

  # ---- Orders ----
  order_presets_list = quote({
    register_order_presets()
    list_orders()
  }),
  order_for_prefix = quote({
    register_order("edu", c("low", "mid", "high"), prefixes = "edu_")
    order_for("edu_level")
  }),
  apply_order_basic = quote({
    register_order("size", c("S", "M", "L"))
    apply_order(c("L", "S", "M", "XL"), name = "size")
  }),

  # ---- Summaries ----
  calc_percentage_gender = quote(calc_percentage(podracing_survey, demo_gender)),
  calc_percentage_desc = quote(calc_percentage(podracing_survey, demo_gender, sort = "desc")),
  calc_percentage_asc_digits = quote(calc_percentage(podracing_survey, demo_job, sort = "asc", digits = 1)),
  calc_percentage_by = quote(calc_percentage(podracing_survey, satis_return, by = region)),
  calc_percentage_by_two = quote(calc_percentage(podracing_survey, demo_gender, by = c(region, collector))),
  calc_percentage_wide = quote(calc_percentage(podracing_survey, satis_return, by = region, wide = TRUE)),
  calc_percentage_levels = quote(calc_percentage(podracing_survey, satis_return,
                                                 levels = c("Very unlikely", "Unlikely", "Not sure",
                                                            "Likely", "Very likely"))),
  calc_percentage_levels_missing = quote(calc_percentage(podracing_survey, satis_return,
                                                         levels = c("Likely", "Very likely"))),
  calc_percentage_registered_by = quote({
    register_order_presets()
    calc_percentage(podracing_survey, satis_return, by = demo_gender)
  }),
  calc_percentage_keep_na = quote(calc_percentage(podracing_survey, demo_gender, na_rm = FALSE)),
  calc_percentage_drop = quote(calc_percentage(podracing_survey, demo_job, drop = c("Unemployed", "student"))),
  calc_percentage_weighted = quote(calc_percentage(podracing_survey, satis_return,
                                                   weights = c(variable = "demo_gender", Male = 0.49,
                                                               Female = 0.5, "Non-binary" = 0.01))),
  calc_percentage_weighted_wide = quote(calc_percentage(podracing_survey, satis_return, by = region,
                                                        wide = TRUE,
                                                        weights = list(region = c(Europe = 0.3,
                                                          "North America" = 0.3, Asia = 0.2,
                                                          "Latin America" = 0.1, Oceania = 0.1)))),
  calc_percentage_default_dataset = quote({
    use_dataset(podracing_survey)
    calc_percentage(demo_edu, sort = "desc")
  }),
  calc_percentage_default_by = quote({
    ezrsurvey_options(default_by = "collector")
    calc_percentage(podracing_survey, demo_gender)
  }),
  calc_percentage_bad_column = quote(calc_percentage(podracing_survey, demo_gendr)),
  calc_percentage_no_data = quote(calc_percentage(demo_gender)),
  calc_percentage_bad_sort = quote(calc_percentage(podracing_survey, demo_gender, sort = "up")),
  calc_percentage_multi_block = quote(calc_percentage_multi(podracing_survey, "motivations_",
                                                            id = respondent_id, sort = "desc")),
  calc_percentage_multi_by = quote(calc_percentage_multi(podracing_survey, "motivations_", by = region)),
  calc_percentage_multi_raw_names = quote(calc_percentage_multi(shopping_survey, "reasons_",
                                                                clean_names = FALSE, drop = "Fair prices")),
  calc_percentage_multi_packed = quote(calc_percentage_multi(
    data.frame(respondent = 1:4, motivations = c("Speed; Drivers", "Speed", "", "Betting; Speed")),
    "motivations", id = respondent, sort = "desc")),
  calc_percentage_multi_no_prefix = quote(calc_percentage_multi(podracing_survey, "nothing_")),
  calc_summary_age = quote(calc_summary(podracing_survey, demo_age)),
  calc_summary_by = quote(calc_summary(podracing_survey, demo_age, by = region)),
  calc_summary_text = quote(calc_summary(data.frame(a = c("25 years", "31", "forty", NA)), a)),
  calc_summary_weighted = quote(calc_summary(shopping_survey, weekly_spend, by = payment,
                                             weights = c(variable = "demo_gender", Female = 0.5,
                                                         Male = 0.5))),
  calc_percentage_batch_named = quote(calc_percentage_batch(podracing_survey, demo_gender, demo_job)),
  calc_percentage_batch_prefix = quote(calc_percentage_batch(podracing_survey, starts_with("ratings_"),
                                                             prefix = "ratings_")),
  calc_percentage_batch_by = quote(calc_percentage_batch(podracing_survey, starts_with("partner_recall"),
                                                         by = demo_gender, sort = "desc")),
  calc_percentage_factor_order = quote(calc_percentage(
    data.frame(agree = factor(c("Agree", "Strongly disagree", "Disagree", "Agree", "Strongly agree", ""),
                              levels = c(agree_levels, ""))),
    agree)),
  calc_percentage_bands = quote(calc_percentage(
    data.frame(band = bin_numeric(c(45, 120, 60), breaks = c(40, 70, 100, 150),
                                  labels = c("40-70k", "70-100k", "100-150k"))),
    band)),

  # ---- Weights ----
  weight_vector_gender = quote(weight_vector(podracing_survey, c(variable = "demo_gender", Male = 0.49,
                                                                 Female = 0.5, "Non-binary" = 0.01))),
  weight_vector_raked = quote(weight_vector(podracing_survey,
                                            list(demo_gender = c(Male = 0.49, Female = 0.5,
                                                                 "Non-binary" = 0.01),
                                                 collector = c(email = 0.25, panel = 0.25,
                                                               socials = 0.25, in_app = 0.25)))),
  set_weights_message = quote({
    use_dataset(podracing_survey)
    set_weights(c(variable = "demo_gender", Male = 0.49, Female = 0.5, "Non-binary" = 0.01))
  }),
  set_weights_missing_category = quote({
    use_dataset(podracing_survey)
    set_weights(c(variable = "demo_gender", Male = 0.5, Female = 0.5))
  }),

  # ---- Crosstab and compare ----
  crosstab_counts = quote(crosstab(podracing_survey, demo_gender, region)),
  crosstab_row_pct = quote(crosstab(podracing_survey, region, demo_gender, cell = "row_pct")),
  crosstab_col_pct_long = quote(crosstab(podracing_survey, region, demo_gender, cell = "col_pct", wide = FALSE)),
  crosstab_total_pct = quote(crosstab(podracing_survey, collector, demo_gender, cell = "total_pct", digits = 1)),
  crosstab_value = quote(crosstab(podracing_survey, region, demo_gender, value = nps_value)),
  crosstab_registered = quote({
    register_order_presets()
    crosstab(podracing_survey, satis_return, demo_edu)
  }),
  crosstab_weighted = quote(crosstab(podracing_survey, region, demo_gender, cell = "col_pct",
                                     weights = c(variable = "collector", email = 1, panel = 1,
                                                 socials = 1, in_app = 1))),
  crosstab_named_value = quote(crosstab(named_cells, value, n)),
  crosstab_named_n_row_pct = quote(crosstab(named_cells, n, value, cell = "row_pct")),
  crosstab_named_value_long = quote(crosstab(named_cells, value, n, wide = FALSE)),
  crosstab_factor_order = quote(crosstab(agree_factors, agree, group)),
  crosstab_registered_columns = quote({
    register_order("size", c("S", "M", "L"), vars = "size")
    crosstab(data.frame(shop = c("x", "x", "y", "y"), size = c("M", "L", "S", "M")), shop, size)
  }),
  compare_values_basic = quote(compare_values(
    current = data.frame(feature = c("price", "quality", "new"), performance = c(2.8, 4.4, 1)),
    previous = data.frame(feature = c("price", "quality", "gone"), performance = c(3.1, 4.2, 2)))),

  # ---- Diagnostics ----
  se_mean_basic = quote(se_mean(c(4, 5, 3, 4, 5, 2, 4))),
  se_prop_basic = quote(se_prop(c(0.33, 33), 1184, pctp = TRUE)),
  rse_rating_bands = quote(rse_rating(c(3, 8, 12, 20, 40, NA))),
  diagnose_mixed = quote(diagnose(podracing_survey, demo_gender, nps_value, starts_with("ratings_"))),
  diagnose_by = quote(diagnose(podracing_survey, nps_value, demo_gender, by = region)),
  precision_summary_podracing = quote(precision_summary(podracing_survey)),

  # ---- NPS ----
  calc_nps_basic = quote(calc_nps(podracing_survey, nps_value)),
  calc_nps_by = quote(calc_nps(podracing_survey, nps_value, by = region)),
  calc_nps_weighted = quote(calc_nps(shopping_survey, recommend,
                                     weights = c(variable = "demo_gender", Female = 0.5, Male = 0.5))),

  # ---- Import ----
  select_prefix_basic = quote(select_prefix(podracing_survey, c("ratings_", "partner_"), keep = "respondent_id")),
  select_suffix_basic = quote(select_suffix(podracing_survey, "_com", keep = "respondent_id")),
  parse_filename_basic = quote(parse_filename(tibble::tibble(file = c("podracing_wave1_NA_2026.csv",
                                                                      "short_name.csv")),
                                              into = c("survey", "wave", "locale", "year")))
,

  # ---- Banner ----
  banner_two_by_two = quote(crosstab_banner(podracing_survey, rows = c(satis_return, demo_edu),
                                            cols = c(demo_gender, region))),
  banner_numeric = quote(crosstab_banner(podracing_survey, rows = c(nps_value, demo_age), cols = demo_gender)),
  banner_diff = quote(crosstab_banner(podracing_survey, rows = satis_return, cols = region, cell = "diff")),
  banner_long = quote(crosstab_banner(podracing_survey, rows = c(satis_return, starts_with("motivations_")),
                                      cols = collector, long = TRUE, total = FALSE)),
  banner_counts_weighted = quote(crosstab_banner(podracing_survey, rows = c(demo_job, demo_age),
                                                 cols = region, cell = "count", stats = c("mean", "p25", "p75"),
                                                 weights = c(variable = "demo_gender", Male = 0.49,
                                                             Female = 0.5, "Non-binary" = 0.01))),
  banner_registered = quote({
    register_order_presets()
    crosstab_banner(podracing_survey, rows = c(satis_return, ratings_speed), cols = c(demo_edu, satis_return))
  }),
  banner_auto = quote(crosstab_banner(podracing_survey)),
  banner_auto_shopping = quote(crosstab_banner(shopping_survey, max_levels = 8)),
  banner_mean_error = quote(crosstab_banner(podracing_survey, rows = demo_gender, cols = region, cell = "mean")),
  banner_empty = quote(crosstab_banner(podracing_survey[0, ], rows = demo_gender, cols = region)),
  banner_named_value = quote(crosstab_banner(named_cells, rows = value, cols = n, cell = "count")),
  banner_factor_order = quote(crosstab_banner(agree_factors, rows = agree, cols = group)),

  # ---- Drivers ----
  importance_rwa = quote(calc_importance(podracing_survey, nps_value, starts_with("ratings_"))),
  importance_rwa_shopping = quote(calc_importance(shopping_survey, recommend, starts_with("ratings_"))),
  importance_correlation = quote(calc_importance(podracing_survey, nps_value, starts_with("ratings_"),
                                                 method = "correlation")),
  ipm_podracing = quote(ipm_model(podracing_survey, nps_value, "ratings_")),
  ipm_shopping_correlation = quote(ipm_model(shopping_survey, recommend, "ratings_", method = "correlation")),
  ipm_no_prefix = quote(ipm_model(podracing_survey, nps_value, "nothing_"))
,

  # ---- Comments ----
  prep_comments_both = quote(ezrsurvey:::prep_comments(podracing_survey, c("nps_com", "show_com"),
                                                       30, 60, "production")),
  tfidf_matrix = quote({
    long <- ezrsurvey:::prep_comments(podracing_survey, c("nps_com", "show_com"), 30, 400, NULL)
    m <- ezrsurvey:::build_tfidf(long$comment[1:60], ezrsurvey:::resolve_stopwords(NULL))
    as.data.frame(m$tfidf)
  }),
  comment_info = quote({
    long <- ezrsurvey:::prep_comments(podracing_survey, c("nps_com", "show_com"), 30, 400, NULL)
    m <- ezrsurvey:::build_tfidf(long$comment, ezrsurvey:::resolve_stopwords(NULL))
    tibble::tibble(entropy = apply(m$tf, 1, ezrsurvey:::shannon_bits), tfidf = rowSums(m$tfidf))
  })
)

bar_decision <- function(table, ...) {
  p <- plot_bars(table, ...)
  label <- names(p$data)[1]
  built <- ggplot2::ggplot_build(p)
  tibble::tibble(
    levels = paste(levels(p$data[[label]]), collapse = " | "),
    width = built$data[[1]]$xmax[[1]] - built$data[[1]]$xmin[[1]],
    ymax = ggplot2::layer_scales(p)$y$get_limits()[[2]],
    flipped = inherits(p$coordinates, "CoordFlip"),
    text_size = built$data[[3]]$size[[1]]
  )
}

cases$bar_decisions <- quote({
  register_order_presets()
  dplyr::bind_rows(
    bar_decision(calc_percentage(podracing_survey, demo_gender)),
    bar_decision(calc_percentage(podracing_survey, fav_driver)),
    bar_decision(calc_percentage(podracing_survey, fav_driver), orientation = "cols"),
    bar_decision(calc_percentage(podracing_survey, demo_edu)),
    bar_decision(calc_percentage(podracing_survey, demo_job, sort = "desc"), sort = "none"),
    bar_decision(calc_percentage(podracing_survey, race_attended), wrap = 15),
    bar_decision(calc_percentage_multi(podracing_survey, "motivations_"), max = 100)
  )
})
