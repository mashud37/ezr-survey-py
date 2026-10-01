"""Port R's test-config.R: session options, and YAML profiles that load, save and round-trip."""

import pytest
import yaml

import ezrsurvey as ez
from ezrsurvey.config import ezrsurvey_default


def test_options_read_set_and_reset():
    options = ez.ezrsurvey_options()
    for name in ("pct_axis_unit", "pct_axis_max", "na_answers", "generation_scheme"):
        assert name in options
    assert options["pct_axis_unit"] == 25
    ez.ezrsurvey_options(pct_axis_max=100)
    assert ez.ezrsurvey_options()["pct_axis_max"] == 100
    assert ezrsurvey_default("pct_axis_max") == 100
    ez.reset_ezrsurvey_options()
    assert ez.ezrsurvey_options()["pct_axis_max"] is None


def test_options_validate_input():
    with pytest.raises(TypeError):
        ez.ezrsurvey_options(99)
    with pytest.warns(UserWarning):
        ez.ezrsurvey_options(not_a_real_option=1)


def test_na_blank_honours_na_answers():
    ez.ezrsurvey_options(na_answers=["Prefer not to answer", "Don't know"])
    assert ez.na_blank(["Yes", "Don't know", "No"]).tolist()[0] == "Yes"
    assert ez.na_blank(["Yes", "Don't know", "No"]).isna().tolist() == [False, True, False]


def test_profile_round_trips_through_yaml(tmp_path):
    path = tmp_path / ".ezrsurvey.yml"
    path.write_text(yaml.safe_dump({"pct_axis_max": 80, "generation_scheme": "pew"}), encoding="utf-8")
    assert ez.load_ezrsurvey_profile(str(path)) is True
    assert ezrsurvey_default("pct_axis_max") == 80


def test_profile_written_by_r_loads(tmp_path):
    path = tmp_path / "from-r.yml"
    path.write_text(
        "pct_axis_max: 100\nage_breaks:\n- 0\n- 18\n- .inf\nage_labels:\n- young\n- old\n"
        "orders:\n  size:\n    levels:\n    - S\n    - M\n    vars: shirt\n",
        encoding="utf-8",
    )
    assert ez.load_ezrsurvey_profile(str(path)) is True
    assert ezrsurvey_default("age_breaks") == [0, 18, float("inf")]
    assert ez.order_for("shirt") == ["S", "M"]


def test_use_profile_writes_a_template(tmp_path):
    path = str(tmp_path / "ezrsurvey.yml")
    assert ez.use_ezrsurvey_profile(path) == path
    assert (tmp_path / "ezrsurvey.yml").exists()
    with pytest.raises(ValueError):
        ez.use_ezrsurvey_profile(path)


def test_edit_profile_creates_the_file(tmp_path):
    path = str(tmp_path / "edit.yml")
    assert ez.edit_ezrsurvey_profile(path) == path
    assert (tmp_path / "edit.yml").exists()


def test_save_profile_persists_changed_options(tmp_path):
    path = str(tmp_path / "save.yml")
    ez.ezrsurvey_options(pct_axis_max=80)
    ez.save_ezrsurvey_profile(path, include_orders=False)
    ez.reset_ezrsurvey_options()
    assert ezrsurvey_default("pct_axis_max") is None
    ez.load_ezrsurvey_profile(path)
    assert ezrsurvey_default("pct_axis_max") == 80
