"""Port R's test-brand.R: reading OOXML themes, adopting a brand, and brand colours reaching the charts."""

import os
import zipfile
from pathlib import Path

import pytest

import ezrsurvey as ez
from ezrsurvey.brand import extract_ooxml_theme, is_hex, parse_ooxml_theme
from ezrsurvey.config import ezrsurvey_default
from ezrsurvey.decisions import build_plot
from ezrsurvey.theme import FALLBACK_FAMILY

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def minimal_pptx(path):
    theme = (FIXTURES / "theme-srgb.xml").read_text(encoding="utf-8")
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("ppt/theme/theme1.xml", theme)
    return path


def bar_fills():
    chart = ez.plot_bars(ez.calc_percentage(ez.podracing_survey, "demo_gender"))
    return set(build_plot(chart).layers[0].data["fill"])


def test_parse_reads_srgb_colours_and_fonts():
    theme = parse_ooxml_theme(str(FIXTURES / "theme-srgb.xml"))
    assert theme["accents"][:3] == ["#0B5394", "#E69138", "#6AA84F"]
    assert len(theme["accents"]) == 6
    assert theme["dark"] == "#1A1A2E"
    assert theme["light"] == "#FDFDFD"
    assert theme["font_major"] == "Georgia"
    assert theme["font_minor"] == "Verdana"


def test_parse_falls_back_to_system_colours_and_skips_theme_fonts():
    theme = parse_ooxml_theme(str(FIXTURES / "theme-sysclr.xml"))
    assert theme["dark"] == "#000000"
    assert theme["light"] == "#FFFFFF"
    assert theme["accents"][0] == "#4472C4"
    assert theme["font_major"] is None
    assert theme["font_minor"] == "Calibri"


def test_use_brand_extracts_a_template_end_to_end(tmp_path):
    path = minimal_pptx(str(tmp_path / "brand.pptx"))
    info = ez.use_brand(path, quiet=True)
    assert len(info["colors"]) == 6
    assert all(is_hex(colour) for colour in info["colors"])
    assert ezrsurvey_default("brand_color_primary") == info["colors"][0]
    assert ezrsurvey_default("brand_template_pptx") == os.path.abspath(path).replace("\\", "/")


def test_use_brand_accepts_colours_and_fonts_without_a_template():
    with pytest.warns(UserWarning, match="invalid hex"):
        ez.use_brand(colors=["#112233", "oops", "#445566"], quiet=True)
    assert ezrsurvey_default("brand_color_primary") == "#112233"
    assert ezrsurvey_default("brand_colors") == ["#112233", "#445566"]
    ez.use_brand(fonts={"major": "Georgia", "minor": "Verdana"}, quiet=True)
    assert ezrsurvey_default("brand_font_major") == "Georgia"
    assert ezrsurvey_default("brand_font_minor") == "Verdana"


def test_use_brand_validates_its_input():
    with pytest.raises(ValueError, match="Provide a"):
        ez.use_brand()
    with pytest.raises(ValueError, match="pptx or"):
        ez.use_brand("nope.txt")
    with pytest.raises(ValueError, match="does not exist"):
        extract_ooxml_theme("missing-file.pptx")


def test_brand_colours_flow_into_bars_and_pal_brand():
    ez.ezrsurvey_options(brand_colors=["#112233", "#445566"], brand_color_primary="#112233")
    assert bar_fills() == {"#112233"}
    assert ez.pal_brand() == ["#112233", "#445566"]
    assert ez.pal_brand(1) == ["#112233"]
    assert len(ez.pal_brand(5)) == 5


def test_defaults_are_unchanged_without_a_brand():
    assert bar_fills() == {ez.pal_neutral}
    assert ez.pal_brand() == ez.pal_sequential_blue
    assert ez.theme_ezrsurvey().themeables["text"].properties["family"] == FALLBACK_FAMILY


def test_brand_fonts_are_ignored_when_not_installed():
    ez.ezrsurvey_options(brand_font_minor="No Such Corporate Font 123")
    assert ez.theme_ezrsurvey().themeables["text"].properties["family"] == FALLBACK_FAMILY


def test_clear_brand_resets_everything_and_brand_info_prints():
    ez.use_brand(colors="#112233", quiet=True)
    ez.clear_brand()
    info = ez.brand_info()
    assert all(value is None for value in info.values())
    assert "No brand set" in repr(info)
