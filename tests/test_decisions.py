"""Port R's test-decisions.R and test-scales.R: band presets, band lookup, rescaling, markers, axis ceilings and labels."""

import math

import pandas as pd
import pytest
from plotnine import aes, geom_point, ggplot

import ezrsurvey as ez
from ezrsurvey.decisions import band_colour, band_label, build_plot


def base_plot():
    return ggplot(ez.podracing_survey, aes("demo_age", "nps_value")) + geom_point()


def test_band_presets_have_the_required_shape():
    for bands in (ez.bands_rating_3(), ez.bands_rating_5(), ez.bands_nps()):
        assert {"from", "to", "label", "colour"} <= set(bands.columns)
        assert (bands["to"] > bands["from"]).all()


def test_annotate_bands_adds_layers():
    base = base_plot()
    chart = ez.annotate_bands(base, ez.bands_rating_3(), axis="x", at=10)
    assert len(chart.layers) > len(base.layers)
    assert build_plot(chart) is not None


def test_annotate_bands_validates_the_spec():
    with pytest.raises(ValueError):
        ez.annotate_bands(base_plot(), pd.DataFrame({"x": [1]}), at=1)


def test_mark_value_adds_a_reference_line():
    base = base_plot()
    chart = ez.mark_value(base, 5, axis="x")
    assert len(chart.layers) > len(base.layers)
    assert build_plot(chart) is not None


def test_band_lookup_colours_a_value_by_its_band():
    bands = ez.bands_rating_3()
    assert band_label([1.2, 2.4, 2.9], bands) == ["BAD"] * 3
    assert band_label([3], bands) == ["OK"]
    assert band_label([4, 5], bands) == ["GOOD", "GOOD"]
    assert band_colour([2.4], bands) == bands.loc[bands["label"] == "BAD", "colour"].tolist()
    assert band_label([0], bands) == ["BAD"]
    assert band_label([99], bands) == ["GOOD"]


def test_the_rating_palette_agrees_with_the_bands():
    bands = ez.bands_rating_3()
    bad = bands.loc[bands["label"] == "BAD", "colour"].iloc[0]
    ok = bands.loc[bands["label"] == "OK", "colour"].iloc[0]
    assert ez.pal_rating["1"] == bad
    assert ez.pal_rating["2"] == bad
    assert ez.pal_rating["3"] == ok
    assert ez.pal_rating["4"] not in (bad, ok)
    assert ez.pal_rating["5"] not in (bad, ok)


def test_presets_can_be_clipped():
    full = ez.bands_rating_3()
    assert full["from"].iloc[0] == 1
    clipped = ez.bands_rating_3(from_=2)
    assert clipped["from"].iloc[0] == 2
    assert len(clipped) == len(full)
    assert clipped["to"].tolist() == full["to"].tolist()
    assert len(ez.bands_rating_3(from_=4)) == 1
    assert len(ez.bands_rating_3(to=3)) == 1


def test_bands_nps_score_covers_the_score_axis():
    bands = ez.bands_nps_score()
    assert bands["from"].min() == -100
    assert bands["to"].max() == 100
    assert ez.bands_nps()["to"].max() == 10.5


def test_rescale_bands_moves_a_preset():
    wide = ez.rescale_bands(ez.bands_rating_3(), to=[0, 100])
    assert wide["from"].min() == 0
    assert wide["to"].max() == 100
    assert wide["to"].iloc[0] == 50
    assert wide["label"].tolist() == ez.bands_rating_3()["label"].tolist()
    assert wide["colour"].tolist() == ez.bands_rating_3()["colour"].tolist()
    seven = ez.rescale_bands(ez.bands_rating_3(), to=[1, 7])
    assert (seven["from"].min(), seven["to"].max()) == (1, 7)
    stated = ez.rescale_bands(ez.bands_rating_3(), to=[0, 10], from_=[0, 5])
    assert stated["from"].iloc[0] == 2


def test_rescale_bands_rejects_an_unusable_scale():
    with pytest.raises(ValueError, match="two numbers"):
        ez.rescale_bands(ez.bands_rating_3(), to=100)
    with pytest.raises(ValueError, match="two numbers"):
        ez.rescale_bands(ez.bands_rating_3(), to=[0, math.nan])
    with pytest.raises(ValueError, match="no range"):
        ez.rescale_bands(ez.bands_rating_3(), to=[0, 100], from_=[2, 2])


def test_nice_max_rounds_up_to_the_next_multiple():
    assert ez.nice_max(63, 25) == 75
    assert ez.nice_max(80, 25) == 100
    assert ez.nice_max(75, 25) == 100
    assert ez.nice_max([8, 17], 5) == 20
    assert ez.nice_max(40, 25, pad=10) == 60


def test_nice_max_handles_empty_input():
    assert math.isnan(ez.nice_max([]))
    assert math.isnan(ez.nice_max([None, None]))
    assert ez.nice_max([None, 30], 25) == 50


def test_nice_max_validates_arguments():
    with pytest.raises(ValueError):
        ez.nice_max("a")
    with pytest.raises(ValueError):
        ez.nice_max(10, unit=-1)


def test_label_pct_formats_percentages():
    assert ez.label_pct()([0, 33.4, 100]) == ["0%", "33%", "100%"]
    assert ez.label_pct(1)([33.45]) == ["33.5%"]


def test_scale_y_pct_returns_a_scale():
    from plotnine.scales.scale_continuous import scale_continuous

    assert isinstance(ez.scale_y_pct([10, 40]), scale_continuous)
