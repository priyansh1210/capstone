"""Calendar features for Washington DC local time (no target information)."""

from __future__ import annotations

import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar


def dc_holidays(start: str, end: str) -> set[pd.Timestamp]:
    """US federal holidays plus DC Emancipation Day (16 Apr, observed on the
    nearest weekday) and Inauguration Day (20 Jan after a presidential election),
    following the DC government holiday schedule used by UCI Bike Sharing."""
    days = set(USFederalHolidayCalendar().holidays(start=start, end=end))
    for y in range(pd.Timestamp(start).year, pd.Timestamp(end).year + 1):
        d = pd.Timestamp(year=y, month=4, day=16)
        if d.dayofweek == 5:
            d -= pd.Timedelta(days=1)
        elif d.dayofweek == 6:
            d += pd.Timedelta(days=1)
        days.add(d)
        if y % 4 == 1:
            inaug = pd.Timestamp(year=y, month=1, day=20)
            if inaug.dayofweek == 6:
                inaug += pd.Timedelta(days=1)
            days.add(inaug)
    return {d.normalize() for d in days}


def calendar_features(ts_local: pd.DatetimeIndex, base_year: int = 2011) -> pd.DataFrame:
    hol = dc_holidays(str(ts_local.min().date()), str(ts_local.max().date()))
    day = ts_local.normalize()
    out = pd.DataFrame(index=ts_local)
    out["hr"] = ts_local.hour
    out["weekday"] = ts_local.dayofweek  # 0 = Monday
    out["holiday"] = day.isin(list(hol)).astype(int)
    out["workingday"] = ((ts_local.dayofweek < 5) & (out["holiday"] == 0)).astype(int)
    out["mnth"] = ts_local.month
    # Meteorological seasons: 1 winter (DJF), 2 spring, 3 summer, 4 fall
    out["season"] = (ts_local.month % 12 // 3) + 1
    out["yr"] = ts_local.year - base_year
    return out
