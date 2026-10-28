# When to Retrain? Opportunity-Aware Model Maintenance for Bike-Share Demand Forecasting under Real-World Drift

*Draft v0.3 (2026-10-28). Every number comes from executed runs: `reports/multicity/` (clean test,
git tag `clean-test-v1`; New York re-run from `clean-test-v1.1` after a data correction,
Section 6), `reports/benchmark/`, `reports/posthoc/` and `reports/calibration*/`.
Open items before submission are marked TODO.*

## Abstract

Deployed forecasting models degrade when the world changes. Retraining on a fixed schedule spends
compute whether or not anything changed, and drift-triggered retraining can fail silently. We
build a complete, leakage-safe supervisor for an hourly demand model, with delayed labels, a
validation gate, and paired post-promotion probation with rollback. On it we compare retraining
triggers using **358 million real bike-share trips from four systems** (Washington DC, Chicago,
New York, San Francisco Bay Area; 2011-2025), aggregated to hourly demand with airport weather.

Decision logs from a DC replay reveal two failure modes of deterioration triggers:
- *reference inflation*, when a model is accepted during a shock (COVID-19);
- *blindness to attainable improvement*, after a partial adaptation.

We propose **opportunity-aware retraining ("probe")**. It periodically fits one cheap challenger
on recent labels and starts a full, validated retraining cycle only if the challenger beats the
current model significantly on the newest held-out days.

All settings were calibrated on development data, and the code was frozen before a
confirmatory run on three new cities and DC 2025. New York was re-run once after a data
correction, with the same frozen code. In that run:
- **Drift-detector triggers failed.** ADWIN, Page-Hinkley and KSWIN were 25-30 % less accurate
  than a 28-day schedule on average, and worse on every system. Both diagnosed failure modes
  recurred.
- **Probe matched the schedule** (-0.1 %). The difference was not significant on any of 7 clean
  streams, and probe used **40 % fewer full retraining cycles**. It never retrained on
  stationary streams (0 vs 26 cycles).
- **No trigger beat retraining more often.** A 14-day schedule was 4-5 % more accurate at 1.7x
  compute.

## 1 Introduction

A model in production faces a maintenance decision every day: keep serving, or spend compute to
retrain. If it retrains, it must also decide whether the new model is really better.
Practitioners default to fixed schedules; the concept-drift literature offers detectors that flag
changes in distribution or error. The two are rarely compared end-to-end on long real streams,
with delayed labels, realistic validation and rollback, and judged on *quality and cost* together.

**Contributions.**
1. **A complete, inspectable supervisor.** Its state machine covers serve, investigate, wait,
   retrain, validate, promote, probation and rollback. An enforced information boundary means
   the controller only sees covariates already observed and labels already revealed; scenario
   truth never reaches it. Each boundary has a dedicated test (59 tests in total).
2. **A diagnosis of deterioration-triggered retraining**, from decision logs on 7 years of real
   data. It finds two failure modes, reference inflation under shocks and blindness to attainable
   improvement, and **both recur on held-out systems**: reference inflation in Chicago, missed
   improvement in New York, SF and DC 2025.
3. **Opportunity-aware retraining ("probe").** It replaces the self-referential question "has my
   error worsened?" with "can a better model be trained now?", answered by a cheap challenger and
   a paired test.
4. **A pre-registered evaluation on 4 bike-share systems and 358 M trips.** The policies differ
   only in their trigger: static, periodic 14-91 days, ADWIN / Page-Hinkley / KSWIN triggers, a
   bias-aware trigger, probe and a change-timed oracle. We report the error-compute trade-off,
   block-bootstrap CIs, Diebold-Mariano tests and ablations, including the negative outcomes.
5. **An open, reproducible artefact**, with download, checksums and a two-machine determinism
   check.

## 2 Related work

- **Concept-drift detection and adaptation** is surveyed by Gama et al. (2014, ACM Computing
  Surveys) and Lu et al. (2018, IEEE TKDE). We use ADWIN (Bifet & Gavalda, 2007, SDM), the
  Page-Hinkley test (Page, 1954, Biometrika) and KSWIN (Raab, Heusinger & Schleif, 2020,
  Neurocomputing) through River (Montiel et al., 2021, JMLR).
- **How this study differs:** most drift studies evaluate detectors on classification streams
  with immediate labels and per-sample adaptation. We study a regression model with delayed
  labels, validation-gated batch retraining and rollback.
- **Production ML** work stresses monitoring and deployment discipline (Sculley et al., 2015,
  NeurIPS; Breck et al., 2017, IEEE BigData). Our contribution is an empirical comparison of
  retraining *triggers* under one shared, safe update procedure.
- **Bike-share demand** forecasting commonly uses the UCI Bike Sharing data (Fanaee-T & Gama,
  2014), two years of the DC system. We extend to 2011-2025 and three more systems.

*TODO before submission: survey the cost-aware / "when to retrain" literature and position the
probe policy against it; verify all citations.*

## 3 Problem setting

**Prediction task.** Hourly system-wide trips are predicted for each day in a replay.
Predictions for hour *h* use calendar features and the airport weather observation from *h-1*.
Labels of day *d* are revealed at the start of day *d+1*. After each day's labels, a policy
decides whether to start a retraining cycle.

**A retraining cycle**:
- fits six candidates: Ridge, Random Forest and HistGradientBoosting, each on 365- and 730-day
  windows;
- validates them on a 14-day window that lies strictly after everything the current model was
  fitted or selected on, with every candidate window ending before it;
- promotes the best candidate only if its MAE is at least 5 % lower than the current model's on
  the same days;
- puts a promoted model on 14 days of probation while the previous model shadow-predicts, and
  rolls it back if it is at least 5 % worse in two consecutive 84-hour paired windows.

Cooldown is 14 days and the budget 200 cycles. Every policy shares this procedure; only the
trigger differs. The objective is low stream MAE at low compute (training + probing seconds) and
few full cycles.

## 4 Policies

- **static:** never retrain.
- **periodic-N:** attempt a cycle every N days (14/28/56/91; 28 calibrated).
- **adaptive (ADWIN):**
  - *Signal:* the detector watches a deseasonalised log-error signal (monthly difficulty index
    from calibration data), with ADWIN warm-started with the model's reference errors.
  - *Trigger:* an alarm opens an investigation. Retraining needs deterioration against the
    model's reference (14-day median of daily error), confirmed on 3 consecutive days.
  - *Safeguards:* a persistence re-check after rejections, and deferral of alarms raised during
    probation.
  - *Variants:* Page-Hinkley (threshold 20) and KSWIN (alpha 1e-4) in place of ADWIN, both
    calibrated; and **+bias**, which also triggers when total demand is mis-predicted by >= 15 %
    on 3 consecutive days.
- **probe (proposed):**
  - *When:* every 14 days (calibrated), and sooner after a detected error increase.
  - *Challenger:* fit one HGB model (80 iterations) on the last 120 days (calibrated) before the
    newest 14 eligible days.
  - *Decision:* request a full cycle if the challenger is >= 5 % better on those days and a
    one-sided paired t-test over daily MAE gives p <= 0.10. See `docs/METHOD.md`.
- **oracle:** attempts at the known injected change + 15/45/90 days (injected scenarios only).
  It is a change-timed reference, not an upper bound (Section 7.4).

## 5 Data

| System | Years | Trips | Hourly rows | Weather station |
|---|---|---|---|---|
| Washington DC (Capital Bikeshare) | 2011-2025 | 51,630,070 | 131,481 | DCA |
| Chicago (Divvy) | 2014-2024 | 46,868,464 | 96,421 | ORD |
| New York (Citi Bike) | 2014-2024 | 242,270,970 | 96,421 | LGA |
| SF Bay Area (Bay Wheels) | 2017-2024 | 17,507,791 | 65,849 | SFO |

- **Trips and timestamps:** trips are counted by local start hour, with 0 unparsed rows.
  Working-day peaks at 08:00 and 17:00 in every city-year confirm local timestamps.
- **Repeated trips:** a trip that appears in several files of one archive is counted once,
  matched on ride id or on (start, end, bike). The Citi Bike 2018 archive stores every month
  twice, and 18,855,882 repeats are removed. No other New York archive and none of the 91
  Capital Bikeshare 2011-24 archives has any.
- **Yearly check:** the build warns when a year's trips per active day exceed 1.6x its
  neighbours' mean. In all city-years checked, real growth reaches at most 1.21x.
- **Weather:** NOAA ISD-Lite, lagged 1 h, forward-filled for at most 3 h from past values only.
- **Outages:** hours inside zero-trip runs of 6 hours or more (blizzards, hurricanes) are excluded
  from fitting and from the drift signal, but scored.
- **Inputs:** exclude the target and its components (member, casual and e-bike counts).
- **Cross-check:** the DC aggregation reproduces all 17,379 hours of UCI `hour.csv` (totals
  within 1.1 %).
- **Injected scenarios:** demand in commute hours on working days is multiplied by 1.6, either
  abruptly from a hidden date or gradually over six months.
- **Generated streams:** seeded and stationary by construction (5 seeds).

## 6 Protocol

- **Development (all settings).** DC train 2011-14 / calibration 2015 / replay 2016-17 with
  injected changes used only for development, plus generated seeds 101-103.
- **Selection rule (everywhere):** lowest mean MAE ratio against static, with at most one
  retraining cycle on average on the stationary dev streams; ties within 1 % go to fewer cycles.
- **DC 2018-2024 is exploratory.** Four design decisions were informed by looking at it
  (disclosed in `docs/EVALUATION.md`).
- **Clean test.** Run once from the frozen git tag `clean-test-v1`:
  - streams: Chicago and New York (replay 2019-24), SF Bay Area (2020-24), each unmodified and
    with an injected abrupt copy (change 400 days into the replay), plus DC 2025-01..08 (238 days);
  - initial model per system: HGB on its training years, fitted with the same rule as for DC.
- **Data correction (New York).** After the run, NYC's initial model had an implausible
  calibration-year error (MAE 2,451 vs 668 on 2019). The cause was the duplicated 2018 archive
  (Section 5), and 2018 is NYC's calibration year. NYC was rebuilt and its 26 jobs re-run from
  tag `clean-test-v1.1`, whose policy, configuration, scenario and runner code is byte-identical
  to `clean-test-v1`. The first NYC results are archived. No other system was re-run.
- **Metrics:** stream MAE/RMSE on all hours, compute seconds, cycles, promotions, rejections and
  rollbacks.
- **Paired comparisons** (pre-registered in `configs/multicity.yaml`): probe vs periodic-28,
  periodic-14, ADWIN and static; ADWIN+bias vs periodic-28. Each is tested with a moving-block
  bootstrap (28-day blocks, 2,000 resamples) 95 % CI of the mean daily MAE difference, and with
  Diebold-Mariano using Newey-West variance (lag 7).

## 7 Results

### 7.1 DC 2018-2024 (exploratory) and the two failure modes

**Results.** Static 136.6, periodic-28 **81.5** (91 cycles, 361 s), ADWIN-adaptive 114.7 (22
cycles, 70 s). On the stationary generated stream, adaptive ran 0.6 cycles against 26 for
periodic, at equal MAE (34.7 vs 34.8).

**Failure 1, reference inflation.** A model promoted on 2020-03-29 passed probation inside the
COVID-19 collapse, and its reference was rebased to 0.991, about 4x the normal level. About 15
alarms over 2.5 years were then dismissed while its error grew, reaching MAE 332 by September 2022.

**Failure 2, blindness to attainable improvement.** After abrupt changes the first promotion is a
partial adaptation, and later improvement is never requested. On the synthetic abrupt streams,
adaptive recovered in 0/5 runs against 5/5 for periodic.

A bias-aware variant designed after this diagnosis reached 84.5 with 63 cycles (exploratory).

### 7.2 Clean multi-city test

**Table 1 - unmodified clean streams: MAE in trips/h (full retraining cycles).** "vs p28" is the
mean over the four systems of each policy's MAE relative to periodic-28.

| Policy | Chicago 2019-24 | New York 2019-24 | SF Bay Area 2020-24 | DC 2025 (Jan-Aug) | mean MAE vs p28 | mean compute vs p28 | full cycles (sum) |
|---|---|---|---|---|---|---|---|
| static | 211.0 (0) | 1629.1 (0) | 132.2 (0) | 339.1 (0) | +122.9% | 0.00x | 0 |
| periodic 14 d | **112.3** (140) | **578.0** (136) | **66.4** (112) | **128.3** (14) | **-4.5%** | 1.71x | 402 |
| periodic 28 d (calibrated) | 117.5 (78) | 602.1 (78) | 69.6 (65) | 134.9 (8) | +0.0% | 1.00x | 229 |
| periodic 56 d | 126.6 (39) | 656.3 (39) | 80.8 (32) | 162.5 (4) | +13.4% | 0.55x | 114 |
| periodic 91 d | 150.5 (24) | 743.2 (24) | 82.8 (20) | 207.9 (2) | +31.2% | 0.33x | 70 |
| ADWIN trigger | 194.3 (12) | 670.6 (30) | 78.1 (21) | 147.6 (4) | +24.6% | 0.38x | 67 |
| Page-Hinkley trigger | 227.6 (12) | 683.3 (36) | 75.1 (33) | 142.2 (4) | +30.2% | 0.46x | 85 |
| KSWIN trigger | 228.7 (9) | 632.9 (56) | 76.3 (26) | 147.4 (5) | +29.7% | 0.49x | 96 |
| ADWIN+bias trigger | 117.2 (60) | 614.5 (65) | 67.1 (55) | 140.0 (6) | +0.5% | 0.88x | 186 |
| **probe (proposed)** | 118.0 (35) | 607.7 (46) | 70.5 (51) | 130.7 (5) | **-0.1%** | **0.85x** | 137 |

Figure 1 (`reports/multicity/fig_pareto_clean.png`) plots error against compute.

**Detector triggers.** All three were worse than periodic-28 on every system, by 25-30 % on
average, in two patterns that match the two failure modes.
- **Missed improvement (New York, SF, DC 2025: 5-14 % worse).** The detectors kept retraining,
  but less often than the schedule (New York: 30-56 cycles vs 78; SF: 21-33 vs 65). Each update
  waited for error to rise above the model's own reference.
- **Reference inflation (Chicago: 65-95 % worse).** The ADWIN policy promoted a ridge model
  validated on the COVID-19 onset (2020-03-23 to 04-05). Its reference was rebased to 1.074, 5x
  the initial model's 0.213, so the deterioration threshold became 1.235. All 17 alarms of the
  next three years were dismissed (recent errors 0.26-1.15) while the model's daily log error
  rose from 0.47 to 0.96, until a retrain on 2023-04-29.

**Probe and ADWIN+bias.** Both were within 1 % of periodic-28 on average (-0.1 % and +0.5 %).
- **Cycles:** probe used 40 % fewer full cycles than periodic-28 across the 7 clean streams
  (271 vs 450), ADWIN+bias 19 % fewer.
- **Compute:** probe used 15-18 % less than periodic-28 (0.85x on the unmodified streams, 0.82x
  over all 7). The probes themselves cost about 8 % of a cycle each (0.41 s vs 4.9 s), which
  offsets part of the cycle saving.
- **Gate outcomes:** 96 % of probe-requested cycles were promoted, and 83 % survived probation.
  For periodic-28 the figures were 72 % and 60 %; for the ADWIN trigger, 83 % and 73 %.
- **Position on the trade-off (unmodified streams):** probe dominates periodic-28 in DC 2025 and
  ADWIN+bias in New York, is dominated by periodic-28 and ADWIN+bias in SF, and is non-dominated
  in Chicago.

**Periodic-14** was the most accurate policy on every clean stream.

### 7.3 Paired tests

**Table 2 - all 7 clean streams** (daily MAE difference A - B as % of B; 95 % block-bootstrap
CI; DM test).

| A vs B | A lower | CI excludes 0 | DM p < 0.05 | range of differences |
|---|---|---|---|---|
| probe vs periodic-28 | 2 / 7 | **0 / 7** | 0 / 7 (smallest p 0.371) | -3.1 % .. +1.3 % |
| probe vs ADWIN | **7 / 7** | 5 / 7 (SF: upper ends +0.7 %, +0.2 %) | **7 / 7** | -42.9 % .. -7.6 % |
| probe vs periodic-14 | 0 / 7 | 4 / 7, all worse | 6 / 7, all worse | +1.8 % .. +7.1 % |
| ADWIN+bias vs periodic-28 | 4 / 7 | 0 / 7 | 0 / 7 (smallest p 0.074) | -3.6 % .. +3.8 % |

Figure 2 (`fig_forest_clean.png`) shows every interval.
- **Probe vs periodic-28:** the 95 % CIs span roughly -12 % to +10 % of periodic-28's MAE, so the
  data support "no detectable difference" but not equivalence within a tight margin.
- **Probe vs periodic-14 and ADWIN:** probe is reliably worse than periodic-14 and reliably
  better than the ADWIN trigger.

### 7.4 Injected changes

**Table 3 - injected abrupt copies: MAE, and cost of the change** (MAE of the abrupt copy minus
MAE of its unmodified twin under the same policy).

| Policy | Chicago MAE | cost | New York MAE | cost | SF MAE | cost | mean vs p28 |
|---|---|---|---|---|---|---|---|
| static | 297.5 | +86.5 | 2225.3 | +596.2 | 171.7 | +39.5 | +141.3% |
| periodic 14 d | **132.1** | +19.8 | **721.5** | +143.5 | **76.4** | +10.0 | **-4.8%** |
| periodic 28 d | 140.2 | +22.7 | 744.0 | +142.0 | 80.8 | +11.2 | +0.0% |
| ADWIN trigger | 247.7 | +53.4 | 902.8 | +232.1 | 86.0 | +7.9 | +34.8% |
| Page-Hinkley trigger | 152.2 | -75.5 | 815.7 | +132.4 | 87.8 | +12.6 | +8.9% |
| KSWIN trigger | 237.7 | +9.0 | 822.6 | +189.7 | 89.0 | +12.6 | +30.1% |
| ADWIN+bias trigger | 136.0 | +18.7 | 761.2 | +146.7 | 78.0 | +11.0 | -1.4% |
| **probe (proposed)** | 141.4 | +23.4 | 745.0 | +137.4 | 79.4 | +9.0 | -0.2% |
| oracle (3 retrains timed at the change) | 411.2 | - | 2400.0 | - | 188.6 | - | +183.1% |

**Confound.** The injected change starts 400 days into each replay (fixed before the run). For
Chicago and New York that is 2020-02-05, weeks before the COVID-19 collapse, so these copies mix
the injected change with the real shock. Detection delays are therefore not interpreted for the
city streams; the paired cost of the change remains valid.
- **Cost of the change:** probe's cost was second-lowest in New York (+137, after Page-Hinkley
  at +132; periodic-28 +142) and in SF (+9.0, after ADWIN at +7.9).
- **The oracle was worse than static on all three cities.** Its three retrains (February-May 2020
  in Chicago and New York) locked in a COVID-onset model that then served until 2024. Even on the
  generated streams, with no real shock, the oracle reached only 56.5 against 50.0 for periodic-91
  (Section 7.6). Gains come from repeatedly folding in post-change data, not from reacting at
  the moment of change. This is failure mode 2 seen from the other side.

### 7.5 Ablations

**Table 4 - four unmodified clean streams**, each variant against its parent policy on the same
streams.

| Variant | vs parent | vs periodic-28 | cycles (mean) | compute vs p28 |
|---|---|---|---|---|
| probe without drift acceleration | +0.3 % | +0.2 % | 35.0 | 0.80x |
| probe without the significance test | **-1.9 %** | -2.0 % | 42.5 | 1.02x |
| probe without probation/rollback | +0.1 % | -0.1 % | 37.0 | 0.98x |
| ADWIN without the seasonal index | **+26.9 %** | +58.4 % | 14.0 | 0.25x |
| ADWIN without warm start | +3.3 % | +28.3 % | 14.8 | 0.41x |

- **Seasonal index:** essential for detector triggers (+27 % error without it, worse on all
  four systems).
- **Warm start:** +14 % error without it in New York, no difference elsewhere.
- **Probe acceleration:** no measurable effect; it can be dropped.
- **Significance test:** trades about 1.9 % accuracy for 19 % fewer cycles (34.3 vs 42.5 per
  stream). Without it, probe was more accurate than periodic-28 on all four systems, at equal
  compute (1.02x). This is a post-hoc observation that needs its own confirmatory test.
- **Probation:** no net effect on accuracy (+0.1 %; between -4 % and +4 % per system). Its
  benefit, protection against faulty candidates, appears only under fault injection (tests),
  which did not occur in these replays.

### 7.6 Generated streams (5 seeds)

| Policy | stationary MAE | stationary cycles | stationary compute s | abrupt MAE (sd) | abrupt cycles | abrupt compute s | first retrain after change (d) |
|---|---|---|---|---|---|---|---|
| static | 34.7 | 0.0 | 0.0 | 59.2 (2.7) | 0.0 | 0.0 | - |
| periodic 14 d | 34.8 | 50.6 | 309.9 | **49.1** (2.5) | 48.4 | 291.6 | 8.4 |
| periodic 28 d | 34.8 | 26.0 | 154.9 | 49.4 (2.6) | 26.0 | 157.2 | 12.0 |
| periodic 91 d | 34.8 | 8.0 | 57.4 | 50.0 (2.5) | 8.0 | 59.5 | 33.0 |
| ADWIN trigger | 34.7 | 0.6 | 4.8 | 57.5 (2.0) | 1.8 | 12.5 | 21.8 |
| Page-Hinkley trigger | 34.6 | 0.8 | 6.8 | 57.0 (2.7) | 2.4 | 17.8 | 17.6 |
| KSWIN trigger | 34.6 | 0.6 | 5.4 | 56.7 (2.5) | 1.4 | 11.5 | 37.8 |
| ADWIN+bias trigger | 34.7 | 0.6 | 4.9 | 49.2 (2.5) | 18.8 | 113.0 | 10.0 |
| **probe (proposed)** | 34.7 | **0.0** | 33.8 | 49.2 (2.4) | 18.6 | 117.6 | 26.4 |
| oracle | - | - | - | 56.5 (3.1) | 3.0 | 17.9 | 15.0 |

- **Stationary:** probe never retrained (5/5 seeds).
- **Abrupt:** probe matched the schedules with 28 % fewer cycles than periodic-28. The
  probe-vs-periodic-28 paired CIs include 0 for 4 of 5 seeds; the 5th favours probe.
- **Detector triggers:** detected the change (ADWIN in 5/5 seeds) but did not adapt beyond the
  first partial update.
- **Cost of probing:** probe's first retraining came later (26 days) than the bias trigger's
  (10 days), and its probes cost 34 s per stationary run, 5-7x what the detector triggers spent
  there (4.8-6.8 s on their 0.6-0.8 cycles).

## 8 Discussion and limitations

- **What the results support.** Drift detectors are a poor *gate* for retraining long-running
  regression models. Asking whether a better model is attainable (probe), or adding a
  demand-level check (bias trigger), recovers schedule-level accuracy and keeps the detectors'
  main virtue: no retraining under stationarity.
- **What they do not support.** Triggered retraining is not more accurate than a frequent
  schedule. When a cycle costs seconds, as here, a short schedule is the pragmatic choice. The
  triggered policies' saving (40 % fewer cycles at equal error) matters when cycles are
  expensive or each promotion needs human sign-off. We did not test such a setting.
- **One task family.** System-level hourly demand only; station-level demand and other domains
  remain open.
- **Thresholds from one city.** All thresholds were tuned on DC. Their transfer to other cities is
  what the clean test measures, but four systems are still a small sample of real histories, and
  the unmodified streams contain real, uncontrolled changes (COVID-19, e-bikes, expansion).
- **The injected-change confound.** The abrupt change coincides with COVID-19 onset in Chicago
  and New York (Section 7.4).
- **Weather is observed, not forecast.** Weather comes from airport observations rather than
  forecasts; DC 2025 ends where observations end (238 days).
- **The probe's test assumption.** Its significance test assumes approximately independent daily
  differences within 14 days. The ablation suggests the test is conservative (it costs accuracy).

## 9 Reproducibility

- **Commands:** `python -m amm download-city / build-city / calibrate / calibrate-extra /
  multicity / multicity-report`.
- **Data integrity:** raw SHA-256 checksums are in `data/raw/*/SOURCES.json`.
- **Determinism:** two machines (Python 3.11 and 3.12) produced byte-identical inputs and an
  identical replay (MAE 114.67, 22 cycles). Regenerating the clean-test report on the second
  machine reproduced all run results and CIs exactly.
- **Frozen code and thresholds:** git tag `clean-test-v1`. 230 runs took 58 min on a 24-core
  desktop CPU; no GPU was used.
- **The New York re-run:** run from `clean-test-v1.1` (data fix only), 26 runs in 12.9 min;
  recorded in `environment.json` under `reruns`.

## References (to verify before submission)

- Bifet & Gavalda (2007). Learning from time-changing data with adaptive windowing. SDM.
- Breck et al. (2017). The ML test score. IEEE BigData.
- Diebold & Mariano (1995). Comparing predictive accuracy. Journal of Business & Economic
  Statistics.
- Fanaee-T & Gama (2014). Event labeling combining ensemble detectors and background knowledge.
  Progress in Artificial Intelligence.
- Gama et al. (2014). A survey on concept drift adaptation. ACM Computing Surveys.
- Kunsch (1989). The jackknife and the bootstrap for general stationary observations. Annals of
  Statistics.
- Lu et al. (2018). Learning under concept drift: a review. IEEE TKDE.
- Montiel et al. (2021). River: machine learning for streaming data in Python. JMLR.
- Page (1954). Continuous inspection schemes. Biometrika.
- Raab, Heusinger & Schleif (2020). Reactive soft prototype computing for concept drift streams.
  Neurocomputing.
- Sculley et al. (2015). Hidden technical debt in machine learning systems. NeurIPS.
