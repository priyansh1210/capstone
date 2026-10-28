"""Model versions and atomic activation.

Statuses: active | previous (kept as fallback during probation) | retired |
rejected (failed the validation gate) | rolled_back | failed (training or saving
failed). Promotion saves the artifact first (temp file + os.replace) and only
then swaps the in-memory (active, previous) pair in a single assignment, so a
failure at any point leaves the current model serving.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

import joblib


class ArtifactSaveError(RuntimeError):
    pass


@dataclass
class ModelVersion:
    version: str
    model_name: str
    window_days: int | None
    status: str
    train_start: str | None = None
    train_end: str | None = None
    train_end_seq: int = -1
    n_train: int = 0
    val_start: str | None = None
    val_end: str | None = None
    val_end_seq: int = -1
    n_val: int = 0
    val_mae: float | None = None
    val_rmse: float | None = None
    val_scaled: float | None = None
    current_val_mae: float | None = None
    reference_mae: float | None = None
    reference_scaled: float | None = None
    reference_signal: float | None = None  # seasonally adjusted; used by the deterioration check
    reference_source: str | None = None
    train_seconds: float = 0.0
    cycle: int | None = None
    created_step: int = 0
    activated_step: int | None = None
    retired_step: int | None = None
    params: dict = field(default_factory=dict)
    fault_injection: bool = False
    notes: str = ""
    artifact: str | None = None

    @property
    def selection_end_seq(self) -> int:
        """Rows up to here were used to fit *or select* this model; a later
        validation window must start after it."""
        return max(self.train_end_seq, self.val_end_seq)

    def record(self) -> dict:
        return asdict(self)


class Registry:
    def __init__(self, artifact_dir: Path | None, persist: bool = True):
        self.artifact_dir = Path(artifact_dir) if artifact_dir else None
        self.persist = persist and self.artifact_dir is not None
        self.versions: dict[str, ModelVersion] = {}
        self._models: dict[str, object] = {}
        self._slots: tuple[str | None, str | None] = (None, None)  # (active, previous)
        self._counter = 0

    # ------------------------------------------------------------- accessors
    @property
    def active_id(self) -> str | None:
        return self._slots[0]

    @property
    def previous_id(self) -> str | None:
        return self._slots[1]

    @property
    def active(self) -> ModelVersion:
        return self.versions[self._slots[0]]

    @property
    def previous(self) -> ModelVersion | None:
        return self.versions.get(self._slots[1]) if self._slots[1] else None

    def model(self, version: str):
        return self._models[version]

    def next_id(self) -> str:
        self._counter += 1
        return f"v{self._counter:03d}"

    # --------------------------------------------------------------- storage
    def _save_artifact(self, version: str, model) -> str | None:
        if not self.persist:
            return None
        try:
            self.artifact_dir.mkdir(parents=True, exist_ok=True)
            final = self.artifact_dir / f"{version}.joblib"
            tmp = final.with_suffix(".joblib.tmp")
            joblib.dump(model, tmp, compress=3)
            os.replace(tmp, final)
            return str(final)
        except Exception as exc:  # disk full, permissions, pickling errors ...
            raise ArtifactSaveError(f"saving {version} failed: {exc}") from exc

    def _drop_artifact(self, version: str) -> None:
        v = self.versions[version]
        if v.artifact and os.path.exists(v.artifact):
            os.remove(v.artifact)
        v.artifact = None
        self._models.pop(version, None)

    # ------------------------------------------------------------ lifecycle
    def add_record(self, v: ModelVersion) -> None:
        """Register metadata only (rejected/failed candidates)."""
        self.versions[v.version] = v

    def activate_initial(self, v: ModelVersion, model, step: int = 0) -> None:
        v.artifact = self._save_artifact(v.version, model)
        v.status, v.activated_step = "active", step
        self.versions[v.version] = v
        self._models[v.version] = model
        self._slots = (v.version, None)

    def promote(self, v: ModelVersion, model, step: int) -> None:
        """Make ``v`` active and keep the current model as ``previous``.
        Raises ArtifactSaveError without changing anything if saving fails."""
        if self.previous_id is not None:
            raise RuntimeError("cannot promote while a previous model is still under probation")
        artifact = self._save_artifact(v.version, model)  # may raise -> nothing changed
        old = self.active_id
        v.artifact, v.status, v.activated_step = artifact, "active", step
        self.versions[v.version] = v
        self._models[v.version] = model
        self.versions[old].status = "previous"
        self._slots = (v.version, old)  # single atomic swap

    def keep(self, step: int) -> None:
        """Probation passed: retire the previous model."""
        old = self.previous_id
        self._slots = (self.active_id, None)
        if old:
            self.versions[old].status = "retired"
            self.versions[old].retired_step = step
            self._drop_artifact(old)

    def rollback(self, step: int) -> None:
        """Probation failed: reactivate the previous model."""
        bad, prev = self._slots
        if prev is None:
            raise RuntimeError("no previous model to roll back to")
        self._slots = (prev, None)
        self.versions[prev].status = "active"
        self.versions[prev].activated_step = step
        self.versions[bad].status = "rolled_back"
        self.versions[bad].retired_step = step
        self._drop_artifact(bad)

    @staticmethod
    def load_artifact(path: str):
        return joblib.load(path)
