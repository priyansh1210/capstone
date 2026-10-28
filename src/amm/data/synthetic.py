"""Seeded, fully generated hourly demand streams.

Stationary by construction: the input process (calendar cycles plus weather
AR(1) processes with fixed parameters and no seasonal or yearly trend), the
demand function and the noise process (gamma-Poisson / negative binomial with
fixed dispersion) never change unless a change is explicitly injected via
``change``. Timestamps start in 2001 so generated rows can never be confused
with the 2011-2024 source observations.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from amm.data.calendar import calendar_features

START = "2001-01-01"
COMMUTE_PEAKS = np.array([0.03, 0.02, 0.01, 0.01, 0.02, 0.1, 0.35, 0.85, 1.0, 0.55, 0.35, 0.4, 0.45, 0.42, 0.4, 0.5, 0.8, 1.0, 0.75, 0.5, 0.35, 0.25, 0.15, 0.08])
WEEKEND = np.array([0.08, 0.06, 0.04, 0.02, 0.02, 0.03, 0.06, 0.12, 0.25, 0.45, 0.65, 0.8, 0.9, 0.95, 0.95, 0.9, 0.85, 0.75, 0.6, 0.45, 0.35, 0.28, 0.2, 0.12])


def _ar1(rng, n, mean, sd, phi):
    e = rng.normal(0, sd * np.sqrt(1 - phi**2), n)
    x = np.empty(n)
    x[0] = rng.normal(mean, sd)
    for i in range(1, n):
        x[i] = mean + phi * (x[i - 1] - mean) + e[i]
    return x


def generate(seed: int, n_days: int, change: dict | None = None, start: str = START) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    ts = pd.date_range(start, periods=n_days * 24, freq="h")
    n = len(ts)
    cal = calendar_features(ts, base_year=ts[0].year)
    cal["holiday"] = 0
    cal["workingday"] = (ts.dayofweek < 5).astype(int)
    cal["yr"] = 0  # no year trend in the generated world
    temp = _ar1(rng, n, 15.0, 7.0, 0.985)
    hum = np.clip(_ar1(rng, n, 62.0, 15.0, 0.95), 5, 100)
    wind = np.clip(_ar1(rng, n, 4.0, 2.0, 0.9), 0, None)
    pres = _ar1(rng, n, 1015.0, 7.0, 0.99)
    cloud = np.clip(_ar1(rng, n, 0.5, 0.3, 0.95), 0, 1)
    raining = np.zeros(n, bool)
    for i in range(1, n):
        raining[i] = rng.random() < (0.75 if raining[i - 1] else 0.02)
    precip = np.where(raining, rng.exponential(1.0, n), 0.0)
    e = hum / 100 * 6.105 * np.exp(17.27 * temp / (237.7 + temp))
    atemp = temp + 0.33 * e - 0.70 * wind - 4.0
    sit = np.where(cloud > 0.5, 2, 1)
    sit = np.where(precip > 0, 3, sit)
    sit = np.where(precip >= 2.5, 4, sit)
    df = cal.reset_index().rename(columns={"index": "ts_local"})
    df["ts_local"] = ts
    df["temp_c"], df["atemp_c"], df["humidity"] = temp, atemp, hum
    df["windspeed_ms"], df["pressure_hpa"], df["cloud_cover"] = wind, pres, cloud
    df["precip_1h_mm"], df["weathersit"] = precip, sit.astype(float)

    hr = df["hr"].to_numpy()
    profile = np.where(df["workingday"].to_numpy() == 1, COMMUTE_PEAKS[hr], WEEKEND[hr])
    log_mu = (
        np.log(600.0)
        + np.log(profile + 0.02)
        + 0.045 * (temp - 15)
        - 0.0015 * (temp - 22) ** 2
        - 0.008 * (hum - 62)
        - 0.6 * (precip > 0)
        - 0.04 * wind
    )
    mu = np.exp(log_mu)
    if change:
        mu = mu * change_factor(df, change)
    r = 25.0  # fixed negative-binomial dispersion
    lam = rng.gamma(shape=r, scale=mu / r)
    df["cnt"] = rng.poisson(lam).astype("int64")
    df["instant"] = np.arange(n)
    df["seq"] = df["instant"]
    df["suspected_outage"] = 0
    return df


def change_factor(df: pd.DataFrame, ch: dict) -> np.ndarray:
    """Multiplicative demand change for the selected hours (abrupt or gradual)."""
    ts = pd.to_datetime(df["ts_local"]).to_numpy()
    start = np.datetime64(pd.Timestamp(ch["start"]))
    if ch.get("end"):
        end = np.datetime64(pd.Timestamp(ch["end"]))
        frac = np.clip((ts - start) / (end - start), 0.0, 1.0)
    else:
        frac = (ts >= start).astype(float)
    sel = np.isin(df["hr"].to_numpy(), ch["hours"])
    if ch.get("workingday_only", False):
        sel &= df["workingday"].to_numpy() == 1
    return np.where(sel, 1.0 + (ch["factor"] - 1.0) * frac, 1.0)
