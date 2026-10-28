"""Download caching/validation/manual fallback, outage rule, seasonal index, scenarios."""

import zipfile

import numpy as np
import pandas as pd
import pytest

from amm import paths
from amm.data import download, synthetic
from amm.data.quality import outage_mask
from amm.metrics import SeasonalIndex, daily_median, scaled_error


@pytest.fixture
def tmp_layout(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "ROOT", tmp_path)
    monkeypatch.setattr(paths, "MANUAL", tmp_path / "manual")
    (tmp_path / "manual").mkdir()
    src = tmp_path / "remote" / "a.zip"
    src.parent.mkdir()
    with zipfile.ZipFile(src, "w") as z:
        z.writestr("a.csv", "x\n1\n")
    return tmp_path, src


def _src(tmp, url, size=None):
    return download.SourceFile("trips", "a.zip", url, tmp / "raw" / "a.zip", size, None)


def test_download_cache_and_checksum(tmp_layout):
    tmp, src = tmp_layout
    r1 = download.obtain(_src(tmp, src.as_uri(), src.stat().st_size), backoff=0)
    assert r1.origin == "downloaded" and "size" in r1.validated_against
    r2 = download.obtain(_src(tmp, src.as_uri(), src.stat().st_size), backoff=0)
    assert r2.origin == "cache" and r2.sha256 == r1.sha256
    assert (tmp / "raw" / "a.zip").read_bytes() == src.read_bytes()  # raw file unchanged


def test_manual_fallback_and_useful_error(tmp_layout):
    tmp, src = tmp_layout
    missing = (tmp / "remote" / "missing.zip").as_uri()
    with pytest.raises(download.DownloadError, match="place it at"):
        download.obtain(_src(tmp, missing), retries=1, backoff=0)
    (tmp / "manual" / "a.zip").write_bytes(src.read_bytes())
    r = download.obtain(_src(tmp, missing), retries=1, backoff=0)
    assert r.origin == "manual"


def test_corrupt_files_are_rejected(tmp_layout):
    tmp, src = tmp_layout
    bad = tmp / "remote" / "bad.zip"
    bad.write_bytes(b"<html>not a zip</html>")
    with pytest.raises(download.DownloadError):
        download.obtain(download.SourceFile("trips", "a.zip", bad.as_uri(), tmp / "raw" / "a.zip"), retries=1, backoff=0)
    with pytest.raises(download.DownloadError):  # size mismatch vs bucket listing
        download.obtain(_src(tmp, src.as_uri(), size=1), retries=1, backoff=0)


def test_outage_mask_marks_only_long_zero_runs():
    y = np.array([5, 0, 0, 3] + [0] * 7 + [4, 0])
    m = outage_mask(y, min_run=6)
    assert m.sum() == 7 and m[4:11].all() and not m[1:3].any() and not m[-1]


def test_seasonal_index_normalises_and_scales():
    months = np.repeat(np.arange(1, 13), 100)
    err = np.where(np.isin(months, [12, 1, 2]), 0.4, 0.2)
    idx = SeasonalIndex.fit(err, months)
    f = idx.factors[1:]
    assert abs(f.mean() - 1) < 1e-9 and f[0] > f[6]  # January harder than July
    sig = idx.signal(err, months)
    assert sig.std() < err.std()  # seasonal swing reduced
    ts = pd.date_range("2020-01-01", periods=48, freq="h").to_numpy()
    assert daily_median(np.r_[np.zeros(24), np.ones(24)], ts) == 0.5


def test_scaled_error_is_capped_and_symmetric_in_log():
    e = scaled_error([0, 100, 10], [5000, 100, 0])
    assert e[0] == 3.0 and e[1] == 0 and np.isclose(e[2], np.log(11))


def test_synthetic_stream_is_seeded_and_stationary():
    a = synthetic.generate(1, 30)
    b = synthetic.generate(1, 30)
    pd.testing.assert_frame_equal(a, b)
    assert (a["cnt"] >= 0).all() and a["yr"].nunique() == 1
    ch = {"start": "2001-01-10", "factor": 2.0, "hours": [8], "workingday_only": False}
    f = synthetic.change_factor(a, ch)
    assert set(np.unique(f)) == {1.0, 2.0} and (f[a["ts_local"] < "2001-01-10"] == 1).all()
