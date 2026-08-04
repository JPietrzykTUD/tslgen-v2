"""Strict JSON experiment configuration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, TypeVar

from pipcost.domain import Pattern, ScenarioSplit
from pipcost.records import digest_json

_ROOT_KEYS = {
    "schema_version",
    "name",
    "tsl_ref",
    "profile",
    "compiler",
    "simd_lanes",
    "warmups",
    "repetitions",
    "minimum_sample_ns",
    "run_seed",
    "materiality_threshold",
    "manual_threshold",
    "studies",
}
_STUDY_KEYS = {
    "name",
    "split",
    "rows",
    "first_selectivities",
    "conditional_selectivities",
    "patterns",
    "seeds",
    "batch_rows",
    "candidate_plans",
    "reference_plans",
}

T = TypeVar("T")


def _unknown(value: dict[str, Any], allowed: set[str], context: str) -> None:
    keys = sorted(set(value) - allowed)
    if keys:
        raise ValueError(f"unknown {context} keys: {', '.join(keys)}")


def _tuple_of(
    value: object,
    converter: Callable[[Any], T],
    label: str,
    *,
    allow_empty: bool = False,
) -> tuple[T, ...]:
    if not isinstance(value, list) or (not value and not allow_empty):
        qualifier = "a JSON array" if allow_empty else "a non-empty JSON array"
        raise ValueError(f"{label} must be {qualifier}")
    try:
        return tuple(converter(item) for item in value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} contains an invalid value") from exc


@dataclass(frozen=True, slots=True)
class StudyConfig:
    name: str
    split: ScenarioSplit
    rows: tuple[int, ...]
    first_selectivities: tuple[float, ...]
    conditional_selectivities: tuple[float, ...]
    patterns: tuple[Pattern, ...]
    seeds: tuple[int, ...]
    batch_rows: tuple[int | str, ...]
    candidate_plans: tuple[str, ...]
    reference_plans: tuple[str, ...]

    @property
    def requested_plans(self) -> tuple[str, ...]:
        return tuple(sorted((*self.candidate_plans, *self.reference_plans)))

    @classmethod
    def from_record(cls, value: object) -> "StudyConfig":
        if not isinstance(value, dict):
            raise ValueError("each study must be a JSON object")
        _unknown(value, _STUDY_KEYS, "study")
        missing = sorted(_STUDY_KEYS - set(value))
        if missing:
            raise ValueError(f"missing study keys: {', '.join(missing)}")
        split = str(value["split"])
        if split not in ("pilot", "training", "held_out"):
            raise ValueError(f"invalid study split {split!r}")
        patterns = _tuple_of(value["patterns"], str, "patterns")
        if any(item not in ("random", "clustered") for item in patterns):
            raise ValueError("patterns must contain only random or clustered")
        raw_batches = _tuple_of(value["batch_rows"], lambda item: item, "batch_rows")
        for item in raw_batches:
            if item != "full" and (not isinstance(item, int) or item <= 0):
                raise ValueError("batch_rows entries must be positive integers or 'full'")
        result = cls(
            name=str(value["name"]),
            split=split,  # type: ignore[arg-type]
            rows=_tuple_of(value["rows"], int, "rows"),
            first_selectivities=_tuple_of(
                value["first_selectivities"], float, "first_selectivities"
            ),
            conditional_selectivities=_tuple_of(
                value["conditional_selectivities"],
                float,
                "conditional_selectivities",
            ),
            patterns=patterns,  # type: ignore[arg-type]
            seeds=_tuple_of(value["seeds"], int, "seeds"),
            batch_rows=raw_batches,
            candidate_plans=_tuple_of(
                value["candidate_plans"], str, "candidate_plans"
            ),
            reference_plans=_tuple_of(
                value["reference_plans"],
                str,
                "reference_plans",
                allow_empty=True,
            ),
        )
        if not result.name:
            raise ValueError("study name must not be empty")
        if any(item < 0 for item in result.rows):
            raise ValueError("rows must be non-negative")
        if any(item > 0xFFFFFFFF for item in result.rows):
            raise ValueError("rows must fit the unsigned 32-bit position contract")
        if any(not 0.0 <= item <= 1.0 for item in result.first_selectivities):
            raise ValueError("first selectivities must be within [0, 1]")
        if any(
            not 0.0 <= item <= 1.0
            for item in result.conditional_selectivities
        ):
            raise ValueError("conditional selectivities must be within [0, 1]")
        if any(item < 0 for item in result.seeds):
            raise ValueError("seeds must be non-negative")
        if len(set(result.requested_plans)) != len(result.requested_plans):
            raise ValueError(
                "candidate and reference plan IDs must be unique and disjoint"
            )
        return result


@dataclass(frozen=True, slots=True)
class ExperimentConfig:
    source_path: Path
    schema_version: int
    name: str
    tsl_ref: str
    profile: str
    compiler: str
    simd_lanes: int
    warmups: int
    repetitions: int
    minimum_sample_ns: int
    run_seed: int
    materiality_threshold: float
    manual_threshold: float
    studies: tuple[StudyConfig, ...]
    raw: dict[str, Any]

    @classmethod
    def load(cls, path: Path | str) -> "ExperimentConfig":
        source = Path(path).resolve()
        try:
            value = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"could not load experiment config {source}: {exc}") from exc
        if not isinstance(value, dict):
            raise ValueError("experiment config root must be a JSON object")
        _unknown(value, _ROOT_KEYS, "config")
        missing = sorted(_ROOT_KEYS - set(value))
        if missing:
            raise ValueError(f"missing config keys: {', '.join(missing)}")
        studies_value = value["studies"]
        if not isinstance(studies_value, list) or not studies_value:
            raise ValueError("studies must be a non-empty JSON array")
        result = cls(
            source_path=source,
            schema_version=int(value["schema_version"]),
            name=str(value["name"]),
            tsl_ref=str(value["tsl_ref"]),
            profile=str(value["profile"]),
            compiler=str(value["compiler"]),
            simd_lanes=int(value["simd_lanes"]),
            warmups=int(value["warmups"]),
            repetitions=int(value["repetitions"]),
            minimum_sample_ns=int(value["minimum_sample_ns"]),
            run_seed=int(value["run_seed"]),
            materiality_threshold=float(value["materiality_threshold"]),
            manual_threshold=float(value["manual_threshold"]),
            studies=tuple(StudyConfig.from_record(item) for item in studies_value),
            raw=value,
        )
        result.validate()
        return result

    def validate(self) -> None:
        if self.schema_version != 2:
            raise ValueError(
                f"unsupported experiment schema_version {self.schema_version}"
            )
        if not self.name or not self.tsl_ref or not self.profile or not self.compiler:
            raise ValueError("name, tsl_ref, profile, and compiler must not be empty")
        if self.simd_lanes <= 0:
            raise ValueError("simd_lanes must be positive")
        if self.warmups < 0 or self.repetitions <= 0:
            raise ValueError("warmups must be non-negative and repetitions positive")
        if self.minimum_sample_ns <= 0:
            raise ValueError("minimum_sample_ns must be positive")
        if self.run_seed < 0:
            raise ValueError("run_seed must be non-negative")
        if not 0.0 <= self.materiality_threshold < 1.0:
            raise ValueError("materiality_threshold must be within [0, 1)")
        if not 0.0 <= self.manual_threshold <= 1.0:
            raise ValueError("manual_threshold must be within [0, 1]")
        names = [study.name for study in self.studies]
        if len(set(names)) != len(names):
            raise ValueError("study names must be unique")

    @property
    def digest(self) -> str:
        return digest_json(self.raw)
