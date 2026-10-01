"""Draw every chart in Python and lay it beside R's version on one HTML sheet. A person signs the visual parity off from parity/charts/index.html."""

import sys
import warnings
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import ezrsurvey as ez  # noqa: E402

OUT = HERE / "charts"
WIDTH = 8
HEIGHT = 4.5
DPI = 100


def python_charts():
    d = ez.podracing_survey
    europe = ez.calc_percentage(d[d["region"] == "Europe"], "demo_gender")
    asia = ez.calc_percentage(d[d["region"] == "Asia"], "demo_gender")
    quotes = ez.sample_comments(d, "nps_com", "show_com", n=4, seed=1)
    charts = {
        "bars_gender": ez.plot_bars(ez.calc_percentage(d, "demo_gender")),
        "bars_driver": ez.plot_bars(ez.calc_percentage(d, "fav_driver")),
    }
    ez.register_order_presets()
    charts["bars_edu_ordered"] = ez.plot_bars(ez.calc_percentage(d, "demo_edu"))
    charts["stacked"] = ez.plot_rating_grid(d, "ratings_")
    charts["nps"] = ez.plot_nps(d, "nps_value")
    charts["gauge"] = ez.plot_nps_gauge(23)
    charts["gauges"] = ez.plot_gauges({"Net Promoter Score": 23, "Average quality rating": 3.4})
    charts["ipm"] = ez.plot_ipm(ez.ipm_model(d, "nps_value", "ratings_"))
    charts["quotes"] = ez.plot_quotes_tree(quotes)
    comparison = ez.compare_values(europe, asia, by="demo_gender", value="pct")
    charts["diff"] = ez.plot_diff(comparison, label="demo_gender")
    return charts


def sheet(names):
    rows = []
    for name in names:
        rows.append(
            f"<h2>{name}</h2><div class='pair'>"
            f"<figure><img src='r/{name}.png'><figcaption>R</figcaption></figure>"
            f"<figure><img src='python/{name}.png'><figcaption>Python</figcaption></figure></div>"
        )
    style = (
        "body{font-family:sans-serif;margin:16px}.pair{display:flex;gap:12px;flex-wrap:wrap}"
        "figure{margin:0;flex:1 1 400px}img{width:100%;border:1px solid #ccc}"
    )
    return f"<!doctype html><meta charset='utf-8'><title>Chart parity</title><style>{style}</style>" + "".join(rows)


def main():
    warnings.simplefilter("ignore")
    folder = OUT / "python"
    folder.mkdir(parents=True, exist_ok=True)
    charts = python_charts()
    for name, chart in charts.items():
        ez.save_plot(chart, str(folder / f"{name}.png"), width=WIDTH, height=HEIGHT, dpi=DPI, bg="white")
        print("saved", name)
    (OUT / "index.html").write_text(sheet(list(charts)), encoding="utf-8")
    print("sheet:", OUT / "index.html")


if __name__ == "__main__":
    main()
