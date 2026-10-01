"""Port R's test-plot.R: every chart builds, and its layout decisions match R's."""

import pandas as pd
import pytest

import ezrsurvey as ez
from ezrsurvey import plot as plotting
from ezrsurvey.config import ezrsurvey_default
from ezrsurvey.decisions import build_plot


def builds(chart):
    return build_plot(chart) is not None


def layout(labels, n, orientation="auto", is_ordinal=False, sort="auto"):
    request = {"orientation": orientation, "is_ordinal": is_ordinal, "sort": sort, "wrap": None, "label_size": None}
    return plotting.auto_bar_layout(labels, n, request)


def level_order(chart, column):
    return [str(level) for level in chart.data[column].cat.categories]


def test_plot_bars_builds():
    assert builds(ez.plot_bars(ez.calc_percentage(ez.podracing_survey, "demo_gender", sort="desc")))


def test_plot_bars_flips_and_adds_an_average_line():
    assert builds(ez.plot_bars(ez.calc_percentage(ez.podracing_survey, "demo_edu"), flip=True, avg_line=True))


def test_auto_bar_layout_chooses_orientation_order_and_wrap():
    few_short = layout(["M", "F", "X"], 3)
    assert few_short["orientation"] == "cols"
    assert few_short["sort"] == "desc"
    long_label = layout(["A rather long category label"], 1)
    assert long_label["orientation"] == "bars"
    assert long_label["sort"] == "asc"
    assert layout(list("abcdefghi"), 9)["orientation"] == "bars"
    assert layout(["Low", "Mid", "High"], 3, is_ordinal=True)["sort"] == "none"
    assert layout(list("abcdefghijklmnopqrstuvwxy"), 25, orientation="bars")["size"] == ezrsurvey_default("bar_size_min")


def test_plot_bars_orders_bars_and_wraps_long_labels():
    gender = ez.calc_percentage(ez.podracing_survey, "demo_gender")
    top_gender = str(gender.loc[gender["pct"].idxmax(), "demo_gender"])
    assert level_order(ez.plot_bars(gender), "demo_gender")[0].replace("\n", " ") == top_gender
    drivers = ez.calc_percentage(ez.podracing_survey, "fav_driver")
    top_driver = str(drivers.loc[drivers["pct"].idxmax(), "fav_driver"])
    assert level_order(ez.plot_bars(drivers), "fav_driver")[-1].replace("\n", " ") == top_driver
    narrow = level_order(ez.plot_bars(drivers, orientation="cols"), "fav_driver")
    assert any("\n" in level for level in narrow)


def test_plot_bars_keeps_a_registered_order():
    ez.register_order(
        "edu_isced_t",
        [
            "Primary or less",
            "Lower secondary",
            "Upper secondary",
            "Short-cycle tertiary",
            "Bachelor or equivalent",
            "Master or equivalent",
            "Doctoral or equivalent",
        ],
        vars="demo_edu",
    )
    table = ez.calc_percentage(ez.podracing_survey, "demo_edu")
    assert table["demo_edu"].cat.ordered
    levels = level_order(ez.plot_bars(table, orientation="bars"), "demo_edu")
    assert levels[0].replace("\n", " ") == "Primary or less"


def test_plot_bars_honours_pct_axis_max():
    ez.ezrsurvey_options(pct_axis_max=100)
    built = build_plot(ez.plot_bars(ez.calc_percentage(ez.podracing_survey, "demo_gender")))
    assert tuple(built.layout.panel_scales_y[0].limits) == (0, 100)


def test_plot_nps_gauge_builds_for_both_scales():
    assert builds(ez.plot_nps_gauge(42))
    assert builds(ez.plot_nps_gauge(3.8, scale="rating"))


def test_plot_gauges_stacks_scores_and_infers_scales():
    assert builds(ez.plot_gauges({"Net Promoter Score": 23, "Average quality rating": 3.4}))
    assert builds(ez.plot_gauges({"Recommendation": 5, "Quality": 4.2}, scales=["nps", "rating"]))
    with pytest.raises(ValueError, match="named"):
        ez.plot_gauges([10, 20])


def test_each_gauge_bar_carries_its_own_breaks():
    layout_ = plotting.gauge_layout({"Net Promoter Score": 23, "Quality": 3.4}, ["nps", "rating"], 0.5)
    ticks = layout_["ticks"]
    top = ticks[ticks["y"] > 1]
    bottom = ticks[ticks["y"] < 1]
    assert top["label"].tolist() == ["-100", "0", "30", "70", "100"]
    assert bottom["label"].tolist() == ["1", "3", "4", "5"]
    assert (top["x"].min(), top["x"].max()) == (0, 1)
    assert (bottom["x"].min(), bottom["x"].max()) == (0, 1)


def test_a_band_too_narrow_for_its_name_is_left_to_its_numbers():
    assert plotting.band_fits(0.15, "EXCELLENT") is False
    assert plotting.band_fits(0.50, "NEEDS WORK") is True
    rects = plotting.gauge_layout({"Net Promoter Score": 23}, ["nps"], 0.5)["rects"]
    assert rects.loc[~rects["wide"], "label"].tolist() == ["EXCELLENT"]


def callout_x(chart, word):
    for layer in chart.layers:
        label = layer.geom.aes_params.get("label")
        if isinstance(label, str) and word in label:
            return layer._data["x"].iloc[0]
    return None


def test_each_nps_callout_is_centred_over_its_bars():
    chart = ez.plot_nps(ez.podracing_survey, "nps_value")
    assert callout_x(chart, "DETRACTOR") == 4
    assert callout_x(chart, "PASSIVE") == 8.5
    assert callout_x(chart, "PROMOTER") == 10.5


def test_plot_nps_builds_and_reports_a_score():
    chart = ez.plot_nps(ez.podracing_survey, "nps_value")
    assert builds(chart)
    assert chart.labels.title.startswith("Net Promoter Score of:")


def test_plot_nps_tolerates_worded_scores():
    assert builds(ez.plot_nps(pd.DataFrame({"v": ["10", "9 - promoter", "3 detractor", "8", "7"]}), "v"))


def test_plot_ipm_builds():
    assert builds(ez.plot_ipm(ez.ipm_model(ez.podracing_survey, "nps_value", "ratings_")))


def test_themes_and_scales_return_the_right_objects():
    from plotnine import theme
    from plotnine.scales.scale import scale

    assert isinstance(ez.theme_ezrsurvey(), theme)
    assert isinstance(ez.theme_ezrsurvey_xy(transparent=True), theme)
    assert isinstance(ez.scale_fill_rating(), scale)
    assert isinstance(ez.scale_fill_nps(), scale)


def test_plot_rating_grid_builds_a_whole_block():
    chart = ez.plot_rating_grid(ez.podracing_survey, "ratings_")
    assert not any(str(name).startswith("ratings_") for name in chart.data["variable"])
    assert builds(chart)


def test_plot_rating_grid_reports_answers_off_the_scale(capsys):
    d = ez.podracing_survey.assign(fit_a="Fits the community")
    ez.plot_rating_grid(d, "fit_", levels=["Does not fit", "Fits the commnity"])
    assert "not on the" in capsys.readouterr().err


def test_plot_rating_grid_errors_without_a_matching_column():
    with pytest.raises(ValueError, match="start with"):
        ez.plot_rating_grid(ez.podracing_survey, "nothing_")


def test_plot_stacked_rating_names_the_forgotten_argument():
    d = pd.DataFrame({"feature": ["a"], "level": ["Good"], "pct": [100]})
    with pytest.raises(ValueError, match="needs `feature` and `level`"):
        ez.plot_stacked_rating(d)
    with pytest.raises(ValueError, match="needs `feature` and `level`"):
        ez.plot_stacked_rating(d, "feature")
    assert builds(ez.plot_stacked_rating(d, "feature", "level"))


def test_plot_quotes_tree_names_the_missing_column():
    raw = pd.DataFrame({"comment": ["a quote", "another quote"]})
    with pytest.raises(ValueError, match="needs a `length` column"):
        ez.plot_quotes_tree(raw, "comment")
    with pytest.raises(ValueError, match="needs a `no_such_col`"):
        ez.plot_quotes_tree(raw, "no_such_col")
    quotes = ez.sample_comments(ez.podracing_survey, "nps_com", n=4, seed=1)
    assert builds(ez.plot_quotes_tree(quotes))


def test_plot_rating_grid_reports_two_answers_on_one_rank(capsys):
    d = pd.DataFrame(
        {
            "rate_a": ["Agree", "Disagree", "Neither agree nor disagree"],
            "rate_b": ["Strongly agree", "Agree", "Neither agree nor disagree"],
        }
    )
    ez.plot_rating_grid(d, "rate_", levels=["Strongly disagree", "Disagree", "Agree", "Strongly agree"])
    assert "both came out as" in capsys.readouterr().err
    ez.plot_rating_grid(d, "rate_", levels=["Strongly disagree", "Disagree", "Neither agree nor disagree", "Agree", "Strongly agree"])
    assert capsys.readouterr().err == ""


def test_plot_ipm_draws_on_the_scale_its_bands_describe(capsys):
    model = ez.ipm_model(ez.podracing_survey, "nps_value", "ratings_")
    wide = model.assign(performance=(model["performance"] - 1) / 4 * 100)
    built = build_plot(ez.plot_ipm(wide, bands=ez.rescale_bands(ez.bands_rating_3(), to=[0, 100])))
    panel = built.layout.panel_params[0].x.range
    assert panel[0] <= wide["performance"].min()
    assert panel[1] >= wide["performance"].max()
    ez.plot_ipm(wide)
    assert "fall outside" in capsys.readouterr().err
    plain = build_plot(ez.plot_ipm(model))
    assert tuple(plain.layout.panel_scales_x[0].limits) == (1, 5)


def test_plot_diff_builds_a_diverging_chart():
    a = pd.DataFrame({"feature": ["price", "quality", "service"], "performance": [3.1, 4.2, 3.5]})
    b = pd.DataFrame({"feature": ["price", "quality", "service"], "performance": [2.8, 4.4, 3.9]})
    assert builds(ez.compare_values(b, a).pipe(ez.plot_diff))
