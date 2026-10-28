# Data sources, attribution, transformations and feature availability

## Why this dataset (change from the original specification)

The specification named the UCI Bike Sharing dataset (Fanaee-T 2013: 17,379 hourly rows,
2011-2012). At the project owner's request the project instead uses a **bigger, real-drift
version of the same data**: the raw Capital Bikeshare trip archive that UCI Bike Sharing was
built from (its Readme points to `capitalbikeshare.com/system-data`), extended to
**2011-2024**, with hourly weather *observations* from NOAA.

| | UCI Bike Sharing | This project |
|---|---|---|
| Span | 2011-2012 | 2011-2024 (14 years) |
| Hourly rows | 17,379 | **122,722** (aggregated from **44,967,423** trips) |
| Real drift | little (2 years) | system growth, COVID-19 (Mar 2020), e-bike era (2020+), 2023-24 surge |
| Weather | daily-normalised, source not observation-timed | NOAA ISD-Lite hourly observations at DCA, lagged 1 h |

UCI Gas Sensor Array Drift was considered and rejected: 13,910 samples, no recorded order
within its 10 batches (files are sorted by gas class), and a classification task that would
have replaced the spec's demand-regression design.

## Sources and licences

1. **Capital Bikeshare system data** - one zip per year 2011-2017, per month 2018-2024
   (91 files, 1.28 GB) from `https://s3.amazonaws.com/capitalbikeshare-data/`. Provided by
   Lyft Bikes and Scooters, LLC under the *Capital Bikeshare Data License Agreement*
   (https://capitalbikeshare.com/data-license-agreement). Raw files are kept locally and not
   redistributed by this project. Attribution: "Data provided by Capital Bikeshare".
2. **NOAA NCEI Integrated Surface Database, ISD-Lite**, station 724050-13743 (Ronald Reagan
   Washington National Airport, DCA), 2011-2024 (14 files), via the NOAA Open Data
   Dissemination bucket `noaa-isd-pds`. U.S. Government data, no copyright restrictions;
   cite "NOAA National Centers for Environmental Information, Integrated Surface Database (ISD)".
3. **UCI Bike Sharing** (only for a cross-check of our aggregation):
   Fanaee-T, H. (2013). Bike Sharing [Dataset]. UCI Machine Learning Repository.
   https://doi.org/10.24432/C5W894 - CC BY 4.0. Its `Readme.txt` is preserved unchanged inside
   `data/raw/uci_bike_sharing/bike_sharing_dataset.zip`. `day.csv` is not used.

Every file's URL, size, origin (downloaded / cache / manual) and **SHA-256** is recorded in
`data/raw/SOURCES.json`; sizes and (single-part) MD5 ETags are checked against the S3 bucket
listing. Examples: `2011-capitalbikeshare-tripdata.zip` 25,334,200 B,
sha256 `1bd6f458...cfadd8`; `bike_sharing_dataset.zip` 279,992 B, sha256 `b70182d0...845401`.

Raw files are never modified: they are read in place (zip members streamed) and all derived
data is written to `data/processed/` and `data/scenarios/`.

## Download behaviour

`python -m amm prepare-data` streams each file with a 60 s socket timeout and 3 retries to
`<file>.part`, validates it (non-empty, zip/gzip magic bytes, size and MD5 where known) and
renames it atomically. A valid local copy is reused (cache), so the second run and all later
work are offline (`--offline` skips the network entirely). If a download fails, the error
names the URL and the exact path for a manual copy: `data/raw/manual/<filename>`.

*Observed in this build:* Python's TLS stack reported "certificate has expired" for
`archive.ics.uci.edu` (curl from the same machine succeeded), so the UCI zip was placed via the
manual fallback. If trip or weather files cannot be obtained at all, `--allow-generated-fallback`
writes **clearly labelled generated data** (`GENERATED_FALLBACK`), and the dashboard shows a red
banner; it is never presented as Capital Bikeshare or UCI data.

## Transformations (source -> `data/processed/hourly.parquet`)

1. **Trips -> hourly counts.** Each published trip is counted in the local (US Eastern)
   wall-clock hour of its start timestamp. Two schemas are handled: legacy (`Start date`,
   `Member type`) to Mar 2020 and current (`started_at`, `member_casual`, `rideable_type`).
   All 44,967,423 rows parsed (0 unparsed). `cnt` = all trips; `member`, `casual`, `electric`
   are kept for analysis only. The operator already removed staff/test trips and trips < 60 s.
2. **Hourly grid.** Every existing local wall-clock hour 2011-01-01 00:00 to 2024-12-31 23:00:
   122,722 rows. The 14 spring-forward hours do not exist (no trips recorded in them); each
   fall-back hour appears once and contains both physical hours (documented DST limitation).
   Hours without trips are real zeros (519 hours).
3. **Suspected outages.** Runs of >= 6 consecutive zero-trip hours (232 hours on 16 days) are
   flagged - they coincide with the Jan-2011 snowstorm, Hurricane Irene (Aug 2011), Hurricane
   Sandy (Oct 2012), Feb-2014 snow and the Jan-2016 blizzard. The flag is derived from the
   target, so it is **not** an input. At stream time the same rule is recomputed only on
   *revealed* labels to exclude such hours from fitting and from the drift signal; they are
   still predicted and scored.
4. **Weather (forecasting interpretation).** ISD-Lite is UTC; it is put on a complete hourly
   UTC grid (51 UTC hours had no observation), continuous fields are carried *forward* from
   earlier observations for at most 3 hours (never backward), precipitation is never carried.
   The value used for target hour *H* is the observation from *H - 1 h* (an observation
   reported before the hour starts), then mapped to local time. Derived: relative humidity
   (Magnus), apparent temperature (Steadman), cloud fraction from the sky-cover code and a
   `weathersit`-like class (1 clear/partly, 2 cloudy, 3 precipitation, 4 >= 2.5 mm/h).
   Remaining missing values (7 temperature, 916 precipitation, 743 cloud hours) are imputed
   inside each model pipeline from that model's own training rows only.
5. **Calendar.** `hr`, `weekday` (0 = Monday), `holiday` (US federal holidays + DC Emancipation
   Day + Inauguration Day), `workingday`, `mnth`, `season` (meteorological), `yr` (year - 2011).

**UCI cross-check (2011-2012):** all 17,379 UCI hours align with our hours; our total is
1.1 % lower, 67 % of hours agree within +/-2 trips, mean absolute difference 2.1 trips/hour.
Exact agreement is not expected: the operator has re-published and cleaned the archive since 2013.

## Model inputs and excluded columns

Inputs (`amm.data.features.FEATURES`): `hr, weekday, workingday, holiday, mnth, season, yr,
temp_c, atemp_c, humidity, windspeed_ms, pressure_hpa, cloud_cover, precip_1h_mm, weathersit`.

Never inputs (enforced by `assert_no_leakage` and tested): `cnt` (target), `member` and
`casual` (sum to `cnt`), `electric` (subset of the target), `instant` (identifier, kept for
traceability), `ts_local`, `suspected_outage` (target-derived), any scenario identifier. No
demand lags are used (no label-availability-dependent features).

## Chronological partitions

| Partition | Range | Rows | Use |
|---|---|---|---|
| train | 2011-01-01 - 2016-12-31 | 52,602 | initial model fit |
| calibration | 2017 | 8,759 | initial model selection and reference error, seasonal index |
| replay | 2018-01-01 - 2024-12-31 | 61,361 | reported evaluation (2,557 daily batches) |
| dev replay | train 2011-14 / cal 2015 / replay 2016-17 | - | threshold and interval calibration only |

## Derived scenarios (`data/scenarios/<name>/manifest.json`)

| Name | Kind | Definition (hidden from the controller) |
|---|---|---|
| `bike_unmodified` | source observations | replay as observed ("unmodified", not "stationary") |
| `bike_abrupt` | modified observations | from 2019-04-01: demand x1.6 in hours 7-9 and 16-19 on working days, rounded, non-negative |
| `bike_gradual` | modified observations | same hours: factor ramps linearly 1.0 -> 1.6 from 2019-03-01 to 2019-09-01, then stays |
| `synthetic_stationary` | generated | seeded AR(1) weather, fixed hour profiles, fixed NB(r=25) noise, no trend; seeds 1-5 (dev: 101-103) |
| `synthetic_abrupt` | generated | same generator, x1.6 commute-hour demand from replay day 240 |
| test fixtures | generated | tiny streams + deliberately weak models (`tests/conftest.py`) |

Manifests store seeds, the transformation, the number of modified rows and target totals
before/after. Only the evaluator and the UI read them.

## Other systems (multi-city study)

Built with the same pipeline: `amm download-city`, then `amm build-city`. Every trip is counted
in the local hour it started, with weather from the nearest NOAA ISD-Lite airport station,
lagged 1 h.

| System | Source (public S3 bucket) | Years | Weather station | Partitions (train / calibration / replay) |
|---|---|---|---|---|
| Chicago (Divvy) | `divvy-tripdata.s3.amazonaws.com` | 2014-2024 | 725300-94846 ORD | 2014-17 / 2018 / 2019-24 |
| New York (Citi Bike) | `s3.amazonaws.com/tripdata` (Jersey City `JC-*` files excluded) | 2014-2024 | 725030-14732 LGA | 2014-17 / 2018 / 2019-24 |
| SF Bay Area (Bay Wheels, formerly Ford GoBike) | `s3.amazonaws.com/baywheels-data` | 2017-07..2024 | 724940-23234 SFO | 2017-07..2018 / 2019 / 2020-24 |
| Washington DC (Capital Bikeshare) | `s3.amazonaws.com/capitalbikeshare-data` | 2011-2025 | 724050-13743 DCA | 2011-23 / 2024 / 2025-01..last day with weather |

**Checks.**
- 0 unparsed rows in every system.
- Working-day peaks at 08:00 and 17:00 in every city-year.
- Months without any trip inside the archive's range (Bay Wheels 2020-04) are dropped as
  archive gaps, not treated as zero demand.

**Replay-year totals are in line with commonly reported annual ridership** (figures recalled,
not re-checked against operator reports):
- New York: 20.55 M (2019) ... 44.30 M (2024);
- Chicago: 3.82 M (2019) ... 5.86 M (2024).

### Trips repeated across files of one archive (found 2026-10-28)

The Citi Bike archive `2018-citibike-tripdata.zip` holds the year three times over:
- every month as a whole-month CSV, with quoted fields;
- the same months as 1,000,000-row parts in folders such as `4_April/`, unquoted;
- a second copy of April's two parts at the top level.

The first build counted **36,404,221 rows; the whole-month files alone contain 17,548,339**.
Two copies plus the extra April copy give 2 x 17,548,339 + 1,307,543 = 36,404,221, exactly the
count built. Because the copies are quoted differently, comparing files
byte for byte cannot find them (`scripts/inspect_archive.py`, log in
`memory/logs/inspect_nyc_2018.txt`).

**The parser fix (`src/amm/data/trips.py`):**
- A trip seen in an earlier CSV of the same archive is dropped from later CSVs.
- Trips are matched on the ride id where the schema has one, otherwise on (start time, end time,
  bike id), after the CSV parser removes the quoting.
- Repeats within a single file are kept as published.

**Verification:**
- On all 91 Capital Bikeshare archives the fixed parser gives a byte-identical hourly table
  (44,967,423 trips, 0 hours different, 0 rows removed).
- Tests: `tests/test_trips.py`.

**New build check.** `build-city` now reports yearly totals and the rows it removed, and warns
when a year's trips per active day exceed 1.6x the mean of the neighbouring years. Real growth
in all checked city-years is at most 1.21x (Chicago 2021); the double-counted NYC 2018 gave
1.97x.

**Effect on results.** 2018 is New York's calibration year, so the first clean-test NYC results
are superseded (BUILD_STATUS D20). Chicago, SF and DC are unaffected.
