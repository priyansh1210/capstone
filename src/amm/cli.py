"""Command line interface: ``python -m amm <command>``.

prepare-data   download (cached) + validate raw sources, build hourly table, write scenario manifests
download-city  download other cities' trip archives + airport weather (data/raw/<city>/)
build-city     build data/processed/<city>/hourly.parquet (+ dataset_report.json)
select-model   choose the initial model on train -> calibration (reports/model_selection.json)
calibrate      tune thresholds / periodic interval on development scenarios, freeze them
smoke          fast end-to-end experiment (configs/smoke.yaml)
benchmark      full comparison (configs/full.yaml) -> reports/<name>/
posthoc        exploratory adaptive variant (reference cap + bias trigger), dev-selected
calibrate-extra  calibrate the probe policy and Page-Hinkley/KSWIN baselines on dev scenarios
multicity      all policies x Chicago/SF/NYC/DC-2025 (+ DC 2018-24, generated) -> reports/multicity/
report         regenerate charts/tables from an existing benchmark directory
dashboard      start the Streamlit dashboard
test           run pytest
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time

from amm import paths


def cmd_prepare(a):
    from amm.config import load_config
    from amm.data import download
    from amm.data.build import build
    from amm.data.scenarios import write_manifests

    cfg = load_config(a.config)
    y0, y1 = cfg["data"]["first_year"], cfg["data"]["last_year"]
    t0 = time.time()
    if a.offline:
        print("[prepare] --offline: using cached raw files only")
        manifest = json.loads((paths.RAW / "SOURCES.json").read_text())
    else:
        manifest = download.download_all(y0, y1, timeout=a.timeout)
    trip_fail = [f for f in manifest["failures"] if f.startswith("trips") or f.startswith("weather")]
    if trip_fail:
        print(f"[prepare] {len(trip_fail)} required source files missing:")
        for f in trip_fail[:10]:
            print("   ", f)
        if not a.allow_generated_fallback:
            print("[prepare] Place the files in data/raw/manual/ and re-run, or use --allow-generated-fallback "
                  "to continue with CLEARLY LABELLED generated development data.")
            sys.exit(2)
        from amm.data.fallback import write_generated_fallback

        write_generated_fallback(y0, y1)
        print("[prepare] wrote GENERATED fallback data (not Capital Bikeshare / UCI). The UI and reports label it as generated.")
        return
    df, rep = build(y0, y1)
    print(f"[prepare] hourly rows={rep['rows']:,} range={rep['date_range_local']} trips read={rep['trip_rows_read']:,}")
    print(f"[prepare] UCI cross-check: {json.dumps(rep['uci_crosscheck'])}")
    out = write_manifests(cfg)
    print(f"[prepare] scenario manifests: {len(out)} under data/scenarios/  ({time.time() - t0:.0f}s)")


def cmd_download_city(a):
    from amm.data.download import download_city

    cities = ["chicago", "sf", "nyc", "dc"] if a.city == ["all"] else a.city
    t0 = time.time()
    failed = 0
    for c in cities:
        m = download_city(c, workers=a.workers, timeout=a.timeout)
        failed += len(m["failures"])
    print(f"[download-city] {cities}: done in {time.time() - t0:.0f}s, {failed} failed file(s)")
    if failed:
        sys.exit(3)


def cmd_build_city(a):
    from amm.data.build import build_city

    cities = ["chicago", "sf", "nyc", "dc"] if a.city == ["all"] else a.city
    for c in cities:
        t0 = time.time()
        df, rep = build_city(c, workers=a.workers)
        print(f"[build-city] {c}: rows={rep['rows']:,} trips={sum(rep['yearly_trips'].values()):,} (rows read {rep['trip_rows_read']:,}, "
              f"repeats removed {sum(rep['trips_repeated_across_members_removed'].values()):,}) unparsed={rep['trip_rows_unparsed']} "
              f"range={rep['date_range_local']} gaps={rep['archive_gap_months']} last_temp={rep['last_hour_with_observed_temperature']} "
              f"peaks={rep['workingday_peak_hours']} ({time.time() - t0:.0f}s)", flush=True)


def cmd_select(a):
    from amm.experiments import model_selection

    r = model_selection.run(a.config)
    print("[select-model] selected:", r["selected"])


def cmd_calibrate(a):
    from amm.experiments import calibrate

    t0 = time.time()
    fr = calibrate.run(workers=a.workers)
    print("[calibrate] frozen values:", json.dumps(fr["values"]))
    print(f"[calibrate] done in {time.time() - t0:.0f}s -> configs/frozen_policy.yaml")


def cmd_benchmark(a, default_cfg="configs/full.yaml"):
    from amm.experiments import benchmark

    t0 = time.time()
    out = benchmark.run(a.config or default_cfg, workers=a.workers, name=a.name)
    print(f"[benchmark] results in {out} ({time.time() - t0:.0f}s)")


def cmd_posthoc(a):
    from amm.experiments import posthoc

    t0 = time.time()
    r = posthoc.run(workers=a.workers)
    print("[posthoc] chosen on dev:", r["chosen"], f"({time.time() - t0:.0f}s) -> reports/posthoc/comparison.md")


def cmd_calibrate_extra(a):
    from amm.experiments import calibrate_extra

    t0 = time.time()
    r = calibrate_extra.run(workers=a.workers)
    print("[calibrate-extra] chosen on dev:", json.dumps(r["chosen"]), f"({time.time() - t0:.0f}s) -> configs/frozen_policy.yaml")


def cmd_multicity(a):
    from amm.experiments import multicity

    t0 = time.time()
    out = multicity.run(a.config, workers=a.workers, name=a.name, only_scenarios=a.only_scenarios)
    print(f"[multicity] results in {out} ({time.time() - t0:.0f}s)")


def cmd_multicity_report(a):
    from amm.experiments import multicity

    multicity.report(paths.REPORTS / a.name)


def cmd_report(a):
    from amm.experiments import benchmark

    benchmark.report(paths.REPORTS / a.name)


def cmd_dashboard(a):
    subprocess.call([sys.executable, "-m", "streamlit", "run", str(paths.ROOT / "app" / "dashboard.py"), "--server.port", str(a.port)])


def cmd_test(a):
    sys.exit(subprocess.call([sys.executable, "-m", "pytest", str(paths.ROOT / "tests"), "-q", *a.pytest_args]))


def main(argv=None):
    p = argparse.ArgumentParser(prog="amm", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("prepare-data")
    s.add_argument("--config")
    s.add_argument("--offline", action="store_true", help="do not touch the network; use cached files")
    s.add_argument("--timeout", type=float, default=60.0)
    s.add_argument("--allow-generated-fallback", action="store_true")
    s.set_defaults(f=cmd_prepare)
    s = sub.add_parser("download-city", help="download trip archives + airport weather for other cities")
    s.add_argument("--city", nargs="+", default=["all"], help="chicago sf nyc dc | all")
    s.add_argument("--workers", type=int, default=6)
    s.add_argument("--timeout", type=float, default=120.0)
    s.set_defaults(f=cmd_download_city)
    s = sub.add_parser("build-city", help="build data/processed/<city>/hourly.parquet from downloaded archives")
    s.add_argument("--city", nargs="+", default=["all"])
    s.add_argument("--workers", type=int, default=4)
    s.set_defaults(f=cmd_build_city)
    s = sub.add_parser("select-model")
    s.add_argument("--config")
    s.set_defaults(f=cmd_select)
    s = sub.add_parser("calibrate")
    s.add_argument("--workers", type=int, default=4)
    s.set_defaults(f=cmd_calibrate)
    for name, default in (("smoke", "configs/smoke.yaml"), ("benchmark", "configs/full.yaml")):
        s = sub.add_parser(name)
        s.add_argument("--config")
        s.add_argument("--workers", type=int, default=4)
        s.add_argument("--name", default=name)
        s.set_defaults(f=lambda a, d=default: cmd_benchmark(a, d))
    s = sub.add_parser("posthoc", help="exploratory variant designed after the frozen benchmark")
    s.add_argument("--workers", type=int, default=4)
    s.set_defaults(f=cmd_posthoc)
    s = sub.add_parser("calibrate-extra", help="calibrate probe + PH/KSWIN detectors on dev scenarios")
    s.add_argument("--workers", type=int, default=4)
    s.set_defaults(f=cmd_calibrate_extra)
    s = sub.add_parser("multicity", help="all policies x all cities (run from the frozen tag)")
    s.add_argument("--config", default="configs/multicity.yaml")
    s.add_argument("--workers", type=int, default=4)
    s.add_argument("--name", default="multicity")
    s.add_argument("--only-scenarios", nargs="*", default=None, help="re-run only these scenarios into the existing results (e.g. after a data fix)")
    s.set_defaults(f=cmd_multicity)
    s = sub.add_parser("multicity-report")
    s.add_argument("--name", default="multicity")
    s.add_argument("--workers", type=int, default=1, help="ignored (accepted for bigpc_run -Only)")
    s.set_defaults(f=cmd_multicity_report)
    s = sub.add_parser("report")
    s.add_argument("--name", default="benchmark")
    s.set_defaults(f=cmd_report)
    s = sub.add_parser("dashboard")
    s.add_argument("--port", type=int, default=8501)
    s.set_defaults(f=cmd_dashboard)
    s = sub.add_parser("test")
    s.add_argument("pytest_args", nargs="*")
    s.set_defaults(f=cmd_test)
    a = p.parse_args(argv)
    a.f(a)


if __name__ == "__main__":
    main()
