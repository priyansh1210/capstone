"""Trip parser: hourly counts, schema variants and trips repeated across archive members."""

import io
import zipfile

import pandas as pd

from amm.data import trips

OLD = "tripduration,starttime,stoptime,start station id,bikeid,usertype\n"


def _rows(month: int, n: int, start: int = 0) -> list[str]:
    return [f"{300 + i},2018-{month:02d}-0{1 + i % 3} {8 + i % 4:02d}:{i % 60:02d}:01.1000,2018-{month:02d}-0{1 + i % 3} {8 + i % 4:02d}:{i % 60:02d}:59.2000,"
            f"{72 + i},{30000 + start + i},{'Subscriber' if i % 2 else 'Customer'}\n" for i in range(start, start + n)]


def _quoted(lines: list[str]) -> str:
    return "".join(",".join(f'"{v}"' for v in ln.rstrip("\n").split(",")) + "\n" for ln in lines)


def _zip(path, members: dict) -> None:
    with zipfile.ZipFile(path, "w") as z:
        for name, text in members.items():
            z.writestr(name, text)


def test_trips_repeated_across_members_are_counted_once(tmp_path):
    # the layout of the Citi Bike 2018 archive: whole month quoted + the same month in unquoted
    # 1M-row parts inside a month folder + another copy of the parts + a nested zip copy
    jan, feb = _rows(1, 40), _rows(2, 30)
    inner = io.BytesIO()
    with zipfile.ZipFile(inner, "w") as z:
        z.writestr("201802-citibike-tripdata.csv", OLD + "".join(feb))
    _zip(tmp_path / "2018.zip", {
        "2018/201801-citibike-tripdata.csv": _quoted([OLD] + jan),
        "2018/201801-citibike-tripdata_1.csv": OLD + "".join(jan[:25]),
        "2018/201801-citibike-tripdata_2.csv": OLD + "".join(jan[25:]),
        "2018/1_January/201801-citibike-tripdata_1.csv": OLD + "".join(jan[:25]),
        "2018/1_January/201801-citibike-tripdata_2.csv": OLD + "".join(jan[25:]),
        "2018/201802-citibike-tripdata.csv": OLD + "".join(feb),
        "2018/201802.zip": inner.getvalue(),
        "2018/stations.csv": "station id,name\n1,a\n",
    })
    out, st = trips.aggregate_zip(tmp_path / "2018.zip")
    assert st["rows"] == 40 * 3 + 30 * 2
    assert out["cnt"].sum() == 70 and st["cross_member_duplicates_removed"] == 40 * 2 + 30
    assert out["member"].sum() == 20 + 15 and out["casual"].sum() == 20 + 15
    assert st["skipped_members"] == ["2018/stations.csv"]


def test_repeats_within_one_member_are_kept_as_published(tmp_path):
    jan = _rows(1, 10)
    _zip(tmp_path / "a.zip", {"201801.csv": OLD + "".join(jan + jan[:3])})
    out, st = trips.aggregate_zip(tmp_path / "a.zip")
    assert out["cnt"].sum() == 13 and st["cross_member_duplicates_removed"] == 0


def test_ride_id_schema_us_timestamps_and_hour_keys(tmp_path):
    new = "ride_id,rideable_type,started_at,ended_at,member_casual\n"
    rows = ["A1,electric_bike,2021-03-01 08:15:00,2021-03-01 08:30:00,member\n",
            "A2,classic_bike,2021-03-01 08:59:59,2021-03-01 09:10:00,casual\n",
            "A3,classic_bike,2021-03-01 09:00:00,2021-03-01 09:10:00,member\n"]
    dc = "Duration,Start date,End date,Start station number,Bike number,Member type\n" \
         "600,4/30/2016 23:59,5/1/2016 0:09,31000,W1,Registered\n"
    _zip(tmp_path / "b.zip", {"q1.csv": new + "".join(rows), "q2.csv": new + rows[0], "dc.csv": dc})
    out, st = trips.aggregate_zip(tmp_path / "b.zip")
    assert st["cross_member_duplicates_removed"] == 1  # A1 repeated in q2.csv
    assert out.loc["2021-03-01 08", "cnt"] == 2 and out.loc["2021-03-01 09", "cnt"] == 1
    assert out.loc["2021-03-01 08", "electric"] == 1 and out.loc["2016-04-30 23", "cnt"] == 1
    hourly, _ = trips.aggregate_all([tmp_path / "b.zip"])
    assert isinstance(hourly.index, pd.DatetimeIndex) and hourly["cnt"].sum() == 4


def test_yearly_check_flags_a_year_counted_twice():
    from amm.data.build import yearly_check

    totals = {2016: 13.8e6, 2017: 16.4e6, 2018: 36.4e6, 2019: 20.6e6, 2020: 19.6e6}  # NYC as first built
    idx = pd.date_range("2016-01-01", "2020-12-31 23:00", freq="h")
    cnt = pd.Series([totals[t.year] / (366 * 24 if t.year % 4 == 0 else 365 * 24) for t in idx], index=idx)
    yearly, jumps = yearly_check(cnt)
    assert list(jumps) == [2018] and 1.9 < jumps[2018] < 2.1
    totals[2018] = 17.5e6
    cnt = pd.Series([totals[t.year] / (366 * 24 if t.year % 4 == 0 else 365 * 24) for t in idx], index=idx)
    assert yearly_check(cnt)[1] == {}
