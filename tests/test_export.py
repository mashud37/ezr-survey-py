"""Port R's test-export.R and test-export-summary.R: savers, the output folder rule, and the summary workbook."""

import os

import openpyxl
import pandas as pd
import pytest

import ezrsurvey as ez
from ezrsurvey import export as exporting
from ezrsurvey.export import default_output_path, resolve_output_path


@pytest.fixture
def in_tmp(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    exporting.SESSION_OUTPUT["announced"] = False
    return tmp_path


def gender_table():
    return ez.calc_percentage(ez.podracing_survey, "demo_gender")


def sheet_names(path):
    return openpyxl.load_workbook(path).sheetnames


def test_the_default_output_folder(in_tmp):
    assert resolve_output_path(default_output_path("plot", "png")) == "ezrsurvey-outputs/plot.png"
    ez.save_data(gender_table())
    assert (in_tmp / "ezrsurvey-outputs" / "data.csv").exists()


def test_save_data_writes_csv_and_tsv(tmp_path):
    table = gender_table()
    csv = str(tmp_path / "t.csv")
    assert ez.save_data(table, csv) is table
    assert len(pd.read_csv(csv)) == len(table)
    tsv = str(tmp_path / "t.tsv")
    ez.save_data(table, tsv)
    assert os.path.exists(tsv)


def test_save_data_writes_xlsx_including_several_sheets(tmp_path):
    one = str(tmp_path / "one.xlsx")
    ez.save_data(gender_table(), one)
    assert os.path.exists(one)
    many = str(tmp_path / "many.xlsx")
    ez.save_data({"gender": gender_table(), "edu": ez.calc_percentage(ez.podracing_survey, "demo_edu")}, many)
    assert sheet_names(many) == ["gender", "edu"]


def test_save_data_rejects_unknown_extensions(tmp_path):
    with pytest.raises(ValueError):
        ez.save_data(ez.podracing_survey, str(tmp_path / "x.foo"))


def test_save_plot_writes_png_and_svg(tmp_path):
    chart = ez.plot_bars(gender_table())
    png = str(tmp_path / "p.png")
    assert ez.save_plot(chart, png) is chart
    assert os.path.exists(png)
    svg = str(tmp_path / "p.svg")
    ez.save_plot(chart, svg)
    assert os.path.exists(svg)


def test_save_plot_rejects_a_table(tmp_path):
    with pytest.raises(ValueError):
        ez.save_plot(ez.podracing_survey, str(tmp_path / "x.png"))


def test_save_output_dispatches_on_type(tmp_path):
    csv = str(tmp_path / "o.csv")
    ez.save_output(gender_table(), csv)
    assert os.path.exists(csv)
    png = str(tmp_path / "o.png")
    ez.save_output(ez.plot_bars(gender_table()), png)
    assert os.path.exists(png)
    with pytest.raises(ValueError):
        ez.save_output(42, csv)


def test_a_bare_name_lands_in_the_outputs_folder(in_tmp):
    assert resolve_output_path("chart.png") == "ezrsurvey-outputs/chart.png"
    assert (in_tmp / "ezrsurvey-outputs").is_dir()
    assert resolve_output_path("./chart.png") == "./chart.png"
    assert resolve_output_path("charts/chart.png") == "charts/chart.png"
    assert (in_tmp / "charts").is_dir()
    absolute = str(in_tmp / "chart.png")
    assert resolve_output_path(absolute) == absolute
    ez.ezrsurvey_options(output_dir=".")
    assert resolve_output_path("chart.png") == "chart.png"


def test_save_plot_writes_into_the_outputs_folder(in_tmp):
    ez.save_plot(ez.plot_bars(gender_table()), "chart.png", width=3, height=2)
    assert (in_tmp / "ezrsurvey-outputs" / "chart.png").exists()
    ez.save_data(gender_table(), "cars.csv")
    assert (in_tmp / "ezrsurvey-outputs" / "cars.csv").exists()


def test_the_outputs_folder_is_announced_once(in_tmp, capsys):
    resolve_output_path("a.png")
    assert "ezrsurvey-outputs" in capsys.readouterr().err
    resolve_output_path("b.png")
    assert capsys.readouterr().err == ""
    exporting.SESSION_OUTPUT["announced"] = False
    resolve_output_path("charts/c.png")
    assert capsys.readouterr().err == ""


def test_scaffold_report_writes_into_the_outputs_folder(in_tmp):
    ez.scaffold_report("html")
    assert (in_tmp / "ezrsurvey-outputs" / "survey-report-html.qmd").exists()


def test_export_summary_writes_one_sheet_per_variable(tmp_path):
    path = str(tmp_path / "s.xlsx")
    assert ez.export_summary_xlsx(ez.podracing_survey, "demo_gender", "satis_return", "nps_value", path=path) == path
    assert set(sheet_names(path)) == {"demo_gender", "satis_return", "nps_value"}


def test_export_summary_without_charts_and_with_selectors(tmp_path):
    path = str(tmp_path / "r.xlsx")
    ez.export_summary_xlsx(ez.podracing_survey, ez.starts_with("ratings_"), chart=False, path=path)
    assert len(sheet_names(path)) == 6


def test_export_summary_honours_the_default_dataset(tmp_path):
    ez.use_dataset(ez.podracing_survey)
    path = str(tmp_path / "d.xlsx")
    ez.export_summary_xlsx("demo_gender", path=path)
    assert os.path.exists(path)


def test_export_summary_writes_every_question_with_multi_select_as_one(tmp_path):
    path = str(tmp_path / "all.xlsx")
    ez.export_summary_xlsx(ez.podracing_survey, path=path)
    sheets = sheet_names(path)
    assert "motivations" in sheets
    assert not any(sheet.startswith("motivations_") for sheet in sheets)
    assert "respondent_id" not in sheets
