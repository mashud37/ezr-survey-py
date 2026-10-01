"""Compare the R package with the fingerprints recorded when each definition was ported. The port stays in step with R by re-porting every definition this lists."""

import argparse
import csv
import glob
import hashlib
import importlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SYNC = Path(__file__).resolve().parent
ROOT = SYNC.parent
R_PACKAGE = ROOT.parent.parent / "ezr-research" / "ezr-survey"
PORT_INDEX = SYNC / "port-index.csv"
DATASET_INDEX = SYNC / "datasets.csv"
R_VERSION = SYNC / "r-version.txt"
INDEX_COLUMNS = [
    "r_name",
    "r_file",
    "exported",
    "py_module",
    "py_name",
    "status",
    "r_fingerprint",
]
STATUSES = ["todo", "ported", "dropped", "diverged"]
R_FILE_TO_MODULE = {
    "auto_select.R": "auto_select",
    "brand.R": "brand",
    "comments.R": "comments",
    "compare.R": "compare",
    "config.R": "config",
    "confirm.R": "confirm",
    "crosstab.R": "crosstab",
    "crosstab_banner.R": "crosstab_banner",
    "currency.R": "currency",
    "data.R": "datasets",
    "dataset.R": "dataset",
    "decisions.R": "decisions",
    "diagnostics.R": "diagnostics",
    "export.R": "export",
    "export_summary.R": "export_summary",
    "ezrsurvey-package.R": "",
    "generation.R": "generation",
    "import.R": "import_data",
    "model.R": "model",
    "orders.R": "orders",
    "palettes.R": "palettes",
    "percentage.R": "percentage",
    "plot.R": "plot",
    "progress.R": "progress",
    "recode.R": "recode",
    "region.R": "region",
    "report_deck.R": "report_deck",
    "report_officer.R": "report_builder",
    "report_quarto.R": "report_quarto",
    "scales.R": "scales",
    "theme.R": "theme",
    "utils-coerce.R": "coerce",
    "utils-pipe.R": "",
    "weights.R": "weights",
    "zzz.R": "",
}


def find_rscript():
    if os.environ.get("EZR_RSCRIPT"):
        return os.environ["EZR_RSCRIPT"]
    on_path = shutil.which("Rscript")
    if on_path:
        return on_path
    installed = sorted(glob.glob("C:/Program Files/R/R-*/bin/x64/Rscript.exe"))
    if installed:
        return installed[-1]
    raise SystemExit("Rscript not found. Put it on PATH or set EZR_RSCRIPT.")


def read_csv_rows(path):
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv_rows(path, rows, columns):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def index_r_package():
    with tempfile.TemporaryDirectory() as folder:
        out = Path(folder) / "r-index.csv"
        command = [find_rscript(), str(SYNC / "index_r.R"), str(R_PACKAGE), str(out)]
        subprocess.run(command, check=True)
        return read_csv_rows(out)


def fingerprint_definition(definition):
    path = R_PACKAGE / "R" / definition["file"]
    lines = path.read_text(encoding="utf-8").splitlines()
    first = int(definition["doc_start"]) - 1
    last = int(definition["end"])
    source = "\n".join(lines[first:last])
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def fingerprint_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def current_r_definitions():
    definitions = {}
    for row in index_r_package():
        row["fingerprint"] = fingerprint_definition(row)
        definitions[row["name"]] = row
    return definitions


def python_name_exists(module, name):
    sys.path.insert(0, str(ROOT))
    try:
        loaded = importlib.import_module("ezrsurvey." + module)
    except ImportError:
        return False
    finally:
        sys.path.pop(0)
    return hasattr(loaded, name)


def compare_definitions(port_rows, definitions):
    changed = []
    removed = []
    missing = []
    for row in port_rows:
        definition = definitions.get(row["r_name"])
        if definition is None:
            removed.append(row["r_name"])
            continue
        if row["r_fingerprint"] and row["r_fingerprint"] != definition["fingerprint"]:
            changed.append(row["r_name"])
        if row["status"] in ("ported", "diverged") and row["py_name"]:
            if not python_name_exists(row["py_module"], row["py_name"]):
                missing.append(row["py_module"] + "." + row["py_name"])
    known = {row["r_name"] for row in port_rows}
    new = [name for name in definitions if name not in known]
    return {"changed": changed, "new": new, "removed": removed, "missing": missing}


def changed_datasets():
    recorded = {row["name"]: row["fingerprint"] for row in read_csv_rows(DATASET_INDEX)}
    changed = []
    for path in sorted((R_PACKAGE / "data").glob("*.rda")):
        if recorded.get(path.stem) != fingerprint_file(path):
            changed.append(path.stem)
    return changed


def r_description_version():
    for line in (R_PACKAGE / "DESCRIPTION").read_text(encoding="utf-8").splitlines():
        if line.startswith("Version:"):
            return line.split(":", 1)[1].strip()
    return ""


def news_since(version):
    sections = []
    keep = False
    for line in (R_PACKAGE / "NEWS.md").read_text(encoding="utf-8").splitlines():
        if line.startswith("# ezrsurvey "):
            keep = line.split()[-1] != version
            if not keep:
                break
        if keep:
            sections.append(line)
    return sections


def new_index_row(definition):
    name = definition["name"]
    py_name = name if name.isidentifier() else ""
    return {
        "r_name": name,
        "r_file": definition["file"],
        "exported": definition["exported"],
        "py_module": R_FILE_TO_MODULE.get(definition["file"], ""),
        "py_name": py_name,
        "status": "todo",
        "r_fingerprint": "",
    }


def print_list(title, names):
    print(f"{title} ({len(names)})")
    for name in names:
        print(f"  {name}")


def report():
    port_rows = read_csv_rows(PORT_INDEX)
    definitions = current_r_definitions()
    result = compare_definitions(port_rows, definitions)
    print_list("changed in R since ported", result["changed"])
    print_list("new in R, not in the index", result["new"])
    print_list("removed from R", result["removed"])
    print_list("ported but missing in Python", result["missing"])
    print_list("bundled datasets changed", changed_datasets())
    counts = {status: 0 for status in STATUSES}
    for row in port_rows:
        counts[row["status"]] += 1
    print("status: " + ", ".join(f"{status} {count}" for status, count in counts.items()))
    recorded_version = R_VERSION.read_text(encoding="utf-8").strip()
    if r_description_version() != recorded_version:
        print(f"R is at {r_description_version()}; the port matches {recorded_version}. New NEWS:")
        print("\n".join(news_since(recorded_version)))


def add_new():
    port_rows = read_csv_rows(PORT_INDEX)
    known = {row["r_name"] for row in port_rows}
    added = 0
    for name, definition in current_r_definitions().items():
        if name not in known:
            port_rows.append(new_index_row(definition))
            added += 1
    write_csv_rows(PORT_INDEX, port_rows, INDEX_COLUMNS)
    print(f"added {added} definition(s) as todo")


def set_status(names, status):
    if status not in STATUSES:
        raise SystemExit(f"status must be one of {', '.join(STATUSES)}")
    port_rows = read_csv_rows(PORT_INDEX)
    definitions = current_r_definitions()
    wanted = set(names)
    for row in port_rows:
        if row["r_name"] not in wanted and row["r_file"] not in wanted:
            continue
        if status == "ported" and row["status"] in ("dropped", "diverged"):
            row["r_fingerprint"] = definitions[row["r_name"]]["fingerprint"]
            continue
        row["status"] = status
        row["r_fingerprint"] = "" if status == "todo" else definitions[row["r_name"]]["fingerprint"]
    write_csv_rows(PORT_INDEX, port_rows, INDEX_COLUMNS)


def accept_datasets():
    rows = []
    for path in sorted((R_PACKAGE / "data").glob("*.rda")):
        rows.append({"name": path.stem, "fingerprint": fingerprint_file(path)})
    write_csv_rows(DATASET_INDEX, rows, ["name", "fingerprint"])
    R_VERSION.write_text(r_description_version() + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Compare the port with the R package it ports.")
    parser.add_argument("--add-new", action="store_true", help="add R definitions missing from the index as todo")
    parser.add_argument("--accept", nargs="+", metavar="NAME", help="record the current R fingerprint for these definitions or R files, once their tests pass")
    parser.add_argument("--mark", nargs="+", metavar="ARG", help="STATUS NAME...: set todo, ported, dropped or diverged")
    parser.add_argument("--accept-datasets", action="store_true", help="record the current datasets and R version as matched")
    args = parser.parse_args()
    if args.add_new:
        add_new()
    elif args.accept:
        set_status(args.accept, "ported")
    elif args.mark:
        set_status(args.mark[1:], args.mark[0])
    elif args.accept_datasets:
        accept_datasets()
    else:
        report()


if __name__ == "__main__":
    main()
