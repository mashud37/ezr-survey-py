# A full management read-out of the bundled podracing_survey, the way an agency
# would present it back to a client: a cover, chaptered sections, and every
# question block in the questionnaire worked through in turn.
#
#   python podracing-deck.py      # writes ezrsurvey-outputs/podracing-deck.pptx
#
# The point of this example is two things at once:
#
#   1. The SHAPE of a deck script: one line per slide. Each report_slide()
#      call does the whole job (calculate, plot, place), so reordering the
#      read-out is reordering the lines, and every content title is the survey
#      question the slide answers. report_section() drops a single-word divider
#      between chapters.
#
#   2. A REAL read-out, not an illustration. It covers recommendation, the six
#      experience ratings and their drivers, motivations, the three sponsor
#      brands, the full respondent profile, favourite drivers, open-text
#      comments and a methods appendix: the whole questionnaire, not a token
#      chart or two.
#
# Swap in an organisation template with ez.use_brand("org-template.pptx")
# before building; otherwise the deck uses the bundled styled 16:9 template.
# For plain white slides, pass style="plain" to ez.report_new().


import ezrsurvey as ez

# One brand call so single-series bars carry the deck's navy identity. In real
# use this points at your PowerPoint template, ez.use_brand("brand/org.pptx"),
# and reads the palette straight out of it.
ez.use_brand(colors=["#12314E", "#3E6E8E", "#C9A227"])

# Derive the one profile column that is not in the raw export: age bands.
survey = ez.podracing_survey
survey["age_band"] = ez.recode_age(survey["demo_age"])
ez.use_dataset(survey)

# The importance/performance model feeds the summary gauge and the driver
# matrix, so it is built once; everything else is calculated on its slide.
ipm = ez.ipm_model("nps_value", "ratings_")
quality = ipm["performance"].mean()
LIKE_LEVELS = ["Very unlikeable", "Unlikeable", "Likeable", "Very likeable"]


def level_mix(prefix, name, levels=None):
    """One row per question and answer level, with its percentage: what a stacked chart reads."""
    long = survey.filter(regex="^" + prefix).melt(var_name=name, value_name="level")
    long = long[long["level"] != ""]
    long[name] = long[name].str.replace(prefix, "", regex=False)
    ranks = ez.recode_likert(long["level"], levels=levels).astype(str)
    long["level"] = ranks.to_numpy() + " - " + long["level"]
    counts = long.groupby([name, "level"]).size().reset_index(name="n")
    counts["pct"] = counts["n"] / counts.groupby(name)["n"].transform("sum") * 100
    return counts


def sponsor_recall():
    long = survey.filter(regex="^partner_recall_").melt(var_name="brand", value_name="answer")
    long = long[long["answer"] != ""]
    long["brand"] = long["brand"].str.replace("partner_recall_", "", regex=False)
    long["sponsor"] = (long["answer"] == "Sponsor") * 100
    shares = long.groupby("brand")["sponsor"].mean().round()
    return shares.reset_index(name="pct")


# ---- the deck: one line per slide ----

doc = ez.report_new("pptx")
doc = ez.report_title_slide(doc, "Pod-Racing Fan Survey 2026", subtitle="1,000 fans surveyed after the Boonta Eve meeting  |  Fieldwork 2026")

doc = ez.report_section(doc, "SUMMARY")
doc = ez.report_slide(doc, "Executive summary", [
    "Fans are strong advocates: the Net Promoter Score sits firmly positive.",
    "Atmosphere and speed are the standout strengths and the biggest draw.",
    "Commentary and value for money lag, and are the clearest places to improve.",
    "Sponsor recognition is uneven, leaving room to strengthen partner visibility.",
])
doc = ez.report_slide(doc, "Overall, how do fans rate pod racing and how likely are they to recommend it?", ez.plot_gauges({"Net Promoter Score": ez.calc_nps("nps_value")["nps"].iloc[0], "Average quality rating": quality}, scales=["nps", "rating"]))

doc = ez.report_section(doc, "RECOMMENDATION")
doc = ez.report_slide(doc, "How likely are you to recommend pod racing to a friend?", ez.plot_nps("nps_value"))
doc = ez.report_slide(doc, "Does advocacy hold up across the fan base?", ez.calc_nps("nps_value", by="region"))
doc = ez.report_slide(doc, "How likely are you to attend another meeting?", ez.plot_bars(ez.calc_percentage("satis_return", sort="desc")))

doc = ez.report_section(doc, "RATINGS")
doc = ez.report_slide(doc, "How would you rate each aspect of the pod-racing experience?", ez.plot_stacked_rating(level_mix("ratings_", "feature"), "feature", "level"))
doc = ez.report_slide(doc, "Which aspects matter most for recommendation, and which fall short?", ez.plot_ipm(ipm))

doc = ez.report_section(doc, "MOTIVATIONS")
doc = ez.report_slide(doc, "What draws you to pod racing?", ez.plot_bars(ez.calc_percentage_multi("motivations_", id="respondent_id", sort="desc"), label="option"))

doc = ez.report_section(doc, "SPONSORS")
doc = ez.report_slide(doc, "Which race sponsors do fans correctly recognise?", ez.plot_bars(sponsor_recall(), label="brand", sort="desc"))
doc = ez.report_slide(doc, "How likeable are the race sponsors?", ez.plot_stacked_rating(level_mix("partner_likeability_", "brand", LIKE_LEVELS), "brand", "level"))

doc = ez.report_section(doc, "DEMOGRAPHICS")
doc = ez.report_slide(doc, "What is your gender?", ez.plot_bars(ez.calc_percentage("demo_gender", sort="desc")))
doc = ez.report_slide(doc, "How old are you?", ez.plot_bars(ez.calc_percentage("age_band"), sort="none"))
doc = ez.report_slide(doc, "What is your highest level of education?", ez.plot_bars(ez.calc_percentage("demo_edu", sort="desc")))
doc = ez.report_slide(doc, "What is your employment status?", ez.plot_bars(ez.calc_percentage("demo_job", sort="desc")))
doc = ez.report_slide(doc, "Which sector do you work in?", ez.plot_bars(ez.calc_percentage("demo_sector", sort="desc")))
doc = ez.report_slide(doc, "Where in the world do you follow pod racing from?", ez.plot_bars(ez.calc_percentage("region", sort="desc")))

doc = ez.report_section(doc, "FANDOM")
doc = ez.report_slide(doc, "Which race meeting did you attend?", ez.plot_bars(ez.calc_percentage("race_attended", sort="desc")))
doc = ez.report_slide(doc, "Who is your favourite pod-racing driver?", ez.plot_bars(ez.calc_percentage("fav_driver", sort="desc")))

doc = ez.report_section(doc, "COMMENTS")
doc = ez.report_slide(doc, "In your own words, what do you think of pod racing?", ez.plot_quotes_tree(ez.sample_comments_diverse("nps_com", "show_com", n=9, seed=42)))

doc = ez.report_section(doc, "APPENDIX")
doc = ez.report_slide(doc, "How was the survey run?", ez.plot_bars(ez.calc_percentage("collector", sort="desc")))
doc = ez.report_slide(doc, "How to read this report", ez.precision_summary("demo_gender", ez.starts_with("ratings_"))["bullets"])

ez.report_save(doc, "ezrsurvey-outputs/podracing-deck.pptx")

ez.clear_dataset()
ez.clear_brand()

# ---- the one-call route ----
# When the deck is just "these charts, one per slide", report_deck() does the
# whole thing in one call.
#
#   ez.report_deck(
#       {"How likely to recommend?": ez.plot_nps(ez.podracing_survey, "nps_value"),
#        "Which aspects fall short?": ez.plot_ipm(ipm)},
#       path="ezrsurvey-outputs/quick-deck.pptx",
#       title="Pod-Racing Fan Survey",
#   )
