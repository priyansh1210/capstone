"""Bike-share systems used for the multi-city evaluation.

Each entry defines where the public trip archive lives, which archive files to
take, the local timezone of the published timestamps, the airport weather
station (NOAA ISD-Lite USAF-WBAN) and the chronological partitions. The three
new cities were never looked at while the supervisor was designed, so they
serve as the clean (confirmatory) test; ``dc`` extended to 2025 adds untouched
months for the original city.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class City:
    key: str
    label: str
    bucket: str
    include: str  # regex on archive keys
    tz: str
    station: str  # ISD-Lite "USAF-WBAN"
    station_name: str
    first_year: int
    last_year: int
    holidays: str = "federal"  # "dc" adds DC Emancipation Day + Inauguration Day
    partitions: dict = field(default_factory=dict)
    exclude: str = r"^(JC-|index\.html)"
    notes: str = ""

    def wants(self, key: str) -> bool:
        if re.search(self.exclude, key) or not re.search(self.include, key, re.I):
            return False
        m = re.search(r"(20\d{2})", key)
        return bool(m) and self.first_year <= int(m.group(1)) <= self.last_year


CITIES = {
    "dc": City(
        key="dc",
        label="Washington DC (Capital Bikeshare)",
        bucket="https://s3.amazonaws.com/capitalbikeshare-data/",
        include=r"^(\d{4}|\d{6})-capitalbikeshare-tripdata\.zip$",
        tz="America/New_York",
        station="724050-13743",
        station_name="Ronald Reagan Washington National Airport (DCA)",
        first_year=2011,
        last_year=2025,
        holidays="dc",
        # clean test: 2025 months were never used for any design decision
        partitions={"train": ["2011-01-01", "2023-12-31"], "calibration": ["2024-01-01", "2024-12-31"], "replay": ["2025-01-01", "auto"]},
        notes="2025 weather from ISD-Lite is partial; the replay ends on the last day with observed temperature",
    ),
    "chicago": City(
        key="chicago",
        label="Chicago (Divvy)",
        bucket="https://divvy-tripdata.s3.amazonaws.com/",
        include=r"^(Divvy_(Stations_)?Trips_20\d{2}.*|\d{6}-divvy-tripdata)\.zip$",
        tz="America/Chicago",
        station="725300-94846",
        station_name="Chicago O'Hare International Airport (ORD)",
        first_year=2014,
        last_year=2024,
        partitions={"train": ["2014-01-01", "2017-12-31"], "calibration": ["2018-01-01", "2018-12-31"], "replay": ["2019-01-01", "2024-12-31"]},
    ),
    "sf": City(
        key="sf",
        label="San Francisco Bay Area (Bay Wheels, formerly Ford GoBike)",
        bucket="https://s3.amazonaws.com/baywheels-data/",
        include=r"^\d{4,6}-[a-z]+-tripdata(\.csv)?\.zip$",
        tz="America/Los_Angeles",
        station="724940-23234",
        station_name="San Francisco International Airport (SFO)",
        first_year=2017,
        last_year=2024,
        partitions={"train": ["2017-07-01", "2018-12-31"], "calibration": ["2019-01-01", "2019-12-31"], "replay": ["2020-01-01", "2024-12-31"]},
        notes="system launched 2017-06-28; the archive has no file for 2020-04",
    ),
    "nyc": City(
        key="nyc",
        label="New York City (Citi Bike)",
        bucket="https://s3.amazonaws.com/tripdata/",
        include=r"^(\d{4}|\d{6})-citibike-tripdata(\.csv)?\.zip$",
        tz="America/New_York",
        station="725030-14732",
        station_name="LaGuardia Airport (LGA)",
        first_year=2014,
        last_year=2024,
        partitions={"train": ["2014-01-01", "2017-12-31"], "calibration": ["2018-01-01", "2018-12-31"], "replay": ["2019-01-01", "2024-12-31"]},
        notes="Jersey City (JC-*) files excluded; yearly archives contain nested monthly folders/zips",
    ),
}

NEW_CITIES = ("chicago", "sf", "nyc")
