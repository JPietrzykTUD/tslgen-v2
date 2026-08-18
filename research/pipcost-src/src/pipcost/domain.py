"""Typed experiment-domain values."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Literal

Pattern = Literal["random", "clustered"]
ScenarioSplit = Literal["pilot", "training", "held_out"]

def _as_int(value: object) -> int:
    if isinstance(value, (str, bytes, bytearray, int, float)):
        return int(value)
    raise ValueError(f"expected an integer-compatible value, got {value!r}")



def _stable_id(prefix: str, value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return f"{prefix}-{sha256(payload.encode('utf-8')).hexdigest()[:16]}"


@dataclass(frozen=True, slots=True)
class Scenario:
    study: str
    split: ScenarioSplit
    rows: int
    first_selectivity: float
    conditional_selectivity: float
    pattern: Pattern
    seed: int
    batch_rows: int
    simd_lanes: int
    profile: str

    def __post_init__(self) -> None:
        if not self.study:
            raise ValueError("scenario study must not be empty")
        if self.rows < 0:
            raise ValueError("scenario rows must be non-negative")
        if not 0.0 <= self.first_selectivity <= 1.0:
            raise ValueError("first_selectivity must be within [0, 1]")
        if not 0.0 <= self.conditional_selectivity <= 1.0:
            raise ValueError("conditional_selectivity must be within [0, 1]")
        if self.pattern not in ("random", "clustered"):
            raise ValueError(f"unsupported position pattern {self.pattern!r}")
        if self.seed < 0:
            raise ValueError("scenario seed must be non-negative")
        if self.batch_rows <= 0:
            raise ValueError("batch_rows must be positive")
        if self.simd_lanes <= 0:
            raise ValueError("simd_lanes must be positive")
        if not self.profile:
            raise ValueError("scenario profile must not be empty")

    @property
    def requested_combined_selectivity(self) -> float:
        return self.first_selectivity * self.conditional_selectivity

    @property
    def scenario_id(self) -> str:
        return _stable_id("scenario", self.to_record())

    def to_record(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class PlanSpec:
    plan_id: str
    representation: str
    processing_mode: str
    mask_layout: str | None
    position_width: int | None
    simd_lanes: int
    implementation: str
    vectorization: str
    materialized: bool
    scope: str
    supported: bool
    skip_reason: str | None

    @classmethod
    def from_record(cls, value: dict[str, object]) -> "PlanSpec":
        return cls(
            plan_id=str(value["plan_id"]),
            representation=str(value["representation"]),
            processing_mode=str(value["processing_mode"]),
            mask_layout=(
                None if value.get("mask_layout") is None else str(value["mask_layout"])
            ),
            position_width=(
                None
                if value.get("position_width") is None
                else _as_int(value["position_width"])
            ),
            simd_lanes=_as_int(value["simd_lanes"]),
            implementation=str(value["implementation"]),
            vectorization=str(value["vectorization"]),
            materialized=bool(value["materialized"]),
            scope=str(value["scope"]),
            supported=bool(value["supported"]),
            skip_reason=(
                None if value.get("skip_reason") is None else str(value["skip_reason"])
            ),
        )

    def to_record(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class SampleKey:
    scenario_id: str
    plan_id: str
    paired_block: int


@dataclass(frozen=True, slots=True)
class Prediction:
    plan_id: str
    predicted_ns: float
    explanation: dict[str, object]
