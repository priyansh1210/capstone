"""SQLite persistence for runs, predictions, decisions and model versions.

Primary keys make every write idempotency-checked: a prediction is unique per
(run, seq, role), a step per (run, step), so a replayed or duplicated step
raises instead of silently creating duplicates. All writes of one replay step
happen in one transaction.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs(
  run_id TEXT PRIMARY KEY, policy TEXT, scenario TEXT, data_kind TEXT, seed INTEGER,
  config TEXT, created_at TEXT, status TEXT, last_step INTEGER, total_steps INTEGER, notes TEXT);
CREATE TABLE IF NOT EXISTS steps(
  run_id TEXT, step INTEGER, batch_start TEXT, state TEXT, active_version TEXT,
  n_revealed INTEGER, rolling_mae REAL, rolling_rmse REAL, rolling_scaled REAL, adwin_width INTEGER,
  cycles INTEGER, fits INTEGER, train_seconds REAL,
  PRIMARY KEY(run_id, step));
CREATE TABLE IF NOT EXISTS predictions(
  run_id TEXT, seq INTEGER, role TEXT, ts TEXT, batch INTEGER, model_version TEXT, y_pred REAL,
  prediction_step INTEGER, label_reveal_step INTEGER, y_true REAL, abs_err REAL, scaled_err REAL,
  PRIMARY KEY(run_id, seq, role));
CREATE TABLE IF NOT EXISTS decisions(
  run_id TEXT, event_id INTEGER, step INTEGER, ts TEXT, state_from TEXT, state_to TEXT,
  action TEXT, reason TEXT, measurements TEXT, thresholds TEXT, fault_injection INTEGER,
  PRIMARY KEY(run_id, event_id));
CREATE TABLE IF NOT EXISTS model_versions(
  run_id TEXT, version TEXT, record TEXT, status TEXT, created_step INTEGER,
  PRIMARY KEY(run_id, version));
CREATE TABLE IF NOT EXISTS candidates(
  run_id TEXT, cycle INTEGER, model TEXT, window_days INTEGER, step INTEGER, n_train INTEGER,
  train_start TEXT, train_end TEXT, val_mae REAL, val_rmse REAL, val_scaled REAL, current_val_mae REAL,
  rel_improvement REAL, passed INTEGER, promoted INTEGER, seconds REAL, error TEXT,
  PRIMARY KEY(run_id, cycle, model, window_days));
CREATE TABLE IF NOT EXISTS cycles(
  run_id TEXT, cycle INTEGER, step INTEGER, trigger TEXT, outcome TEXT, n_fits INTEGER, seconds REAL,
  val_start TEXT, val_end TEXT, n_val INTEGER, current_val_mae REAL, best_val_mae REAL,
  PRIMARY KEY(run_id, cycle));
CREATE INDEX IF NOT EXISTS ix_pred_reveal ON predictions(run_id, label_reveal_step);
CREATE INDEX IF NOT EXISTS ix_pred_step ON predictions(run_id, prediction_step);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, path: str | Path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path, timeout=30, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.executescript(SCHEMA)
        self.conn.commit()
        self._in_tx = False

    def close(self) -> None:
        self.conn.close()

    @contextmanager
    def tx(self):
        if self._in_tx:
            yield
            return
        self._in_tx = True
        try:
            yield
            self.conn.commit()
        except BaseException:
            self.conn.rollback()
            raise
        finally:
            self._in_tx = False

    def _commit_if_idle(self):
        if not self._in_tx:
            self.conn.commit()

    # ------------------------------------------------------------------ runs
    def create_run(self, run_id, policy, scenario, data_kind, seed, config: dict, total_steps: int, notes=""):
        self.conn.execute(
            "INSERT INTO runs VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (run_id, policy, scenario, data_kind, seed, json.dumps(config), _now(), "running", -1, total_steps, notes),
        )
        self._commit_if_idle()

    def set_run(self, run_id, **fields):
        cols = ", ".join(f"{k}=?" for k in fields)
        self.conn.execute(f"UPDATE runs SET {cols} WHERE run_id=?", (*fields.values(), run_id))
        self._commit_if_idle()

    def last_step(self, run_id) -> int:
        r = self.conn.execute("SELECT MAX(step) FROM steps WHERE run_id=?", (run_id,)).fetchone()
        return -1 if r[0] is None else int(r[0])

    # ------------------------------------------------------------ predictions
    def add_predictions(self, rows: list[tuple]):
        self.conn.executemany(
            "INSERT INTO predictions(run_id,seq,role,ts,batch,model_version,y_pred,prediction_step,label_reveal_step)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            rows,
        )

    def score_predictions(self, rows: list[tuple]):
        """rows: (y_true, abs_err, scaled_err, run_id, seq, role) - only fills rows not yet scored."""
        cur = self.conn.executemany(
            "UPDATE predictions SET y_true=?, abs_err=?, scaled_err=? WHERE run_id=? AND seq=? AND role=? AND y_true IS NULL",
            rows,
        )
        if cur.rowcount != len(rows):
            raise RuntimeError(f"expected to score {len(rows)} predictions, scored {cur.rowcount} (duplicate reveal?)")

    # ------------------------------------------------------------- decisions
    def add_decision(self, run_id, event_id, step, ts, s_from, s_to, action, reason, meas, thr, fault=False):
        self.conn.execute(
            "INSERT INTO decisions VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (run_id, event_id, step, ts, s_from, s_to, action, reason, json.dumps(meas, default=float), json.dumps(thr, default=float), int(fault)),
        )

    def upsert_version(self, run_id, rec: dict):
        self.conn.execute(
            "INSERT INTO model_versions VALUES (?,?,?,?,?) ON CONFLICT(run_id, version) DO UPDATE SET record=excluded.record, status=excluded.status",
            (run_id, rec["version"], json.dumps(rec, default=str), rec["status"], rec["created_step"]),
        )

    def add_candidate(self, row: tuple):
        self.conn.execute("INSERT INTO candidates VALUES (" + ",".join("?" * 17) + ")", row)

    def add_cycle(self, row: tuple):
        self.conn.execute("INSERT INTO cycles VALUES (" + ",".join("?" * 12) + ")", row)

    def add_step(self, row: tuple):
        self.conn.execute("INSERT INTO steps VALUES (" + ",".join("?" * 13) + ")", row)

    # ----------------------------------------------------------------- rewind
    def rewind(self, run_id: str, step: int) -> None:
        """Delete everything recorded at or after ``step`` (resume from a checkpoint)."""
        with self.tx():
            c = self.conn
            c.execute("DELETE FROM steps WHERE run_id=? AND step>=?", (run_id, step))
            c.execute("DELETE FROM decisions WHERE run_id=? AND step>=?", (run_id, step))
            c.execute("DELETE FROM predictions WHERE run_id=? AND prediction_step>=?", (run_id, step))
            c.execute(
                "UPDATE predictions SET y_true=NULL, abs_err=NULL, scaled_err=NULL WHERE run_id=? AND label_reveal_step>=?",
                (run_id, step),
            )
            c.execute("DELETE FROM candidates WHERE run_id=? AND step>=?", (run_id, step))
            c.execute("DELETE FROM cycles WHERE run_id=? AND step>=?", (run_id, step))
            c.execute("DELETE FROM model_versions WHERE run_id=? AND created_step>=?", (run_id, step))

    # ------------------------------------------------------------------ reads
    def query(self, sql: str, params=()):
        import pandas as pd

        return pd.read_sql_query(sql, self.conn, params=params)
