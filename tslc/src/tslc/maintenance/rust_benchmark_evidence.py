"""Exact Rust benchmark-report and policy evidence for the coverage ratchet."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import cast

from tslc.backend.rust_policy_consumption import RustPolicyCoveragePlan
from tslc.backend.rust_policy_selection import RustPolicySelectionStatus
from tslc.benchmark.identity import (
    benchmark_slot_identity_hash,
    is_sha256_digest,
    specialization_identity_hash,
)
from tslc.benchmark.model import BenchmarkProjectPlan


@dataclass(frozen=True, slots=True)
class RustBenchmarkProfileEvidence:
    """One exact generated-profile manifest, including empty report profiles."""

    profile_name: str
    manifest_hash: str

    def __post_init__(self) -> None:
        if not self.profile_name or not is_sha256_digest(self.manifest_hash):
            raise ValueError("Rust benchmark profile evidence must be complete")

    def sort_key(self) -> tuple[str, str]:
        return (self.profile_name, self.manifest_hash)

    def record(self) -> list[str]:
        return [self.profile_name, self.manifest_hash]

    @classmethod
    def from_record(cls, record: object) -> RustBenchmarkProfileEvidence:
        values = _string_record(record, 2, "Rust benchmark profile")
        return cls(*values)


@dataclass(frozen=True, slots=True)
class RustBenchmarkCandidateEvidence:
    """One report candidate set with canonical and lowered-body identities."""

    profile_name: str
    slot_hash: str
    key_hash: str
    stable_id: str
    candidates: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        if (
            not self.profile_name
            or not is_sha256_digest(self.slot_hash)
            or not is_sha256_digest(self.key_hash)
            or not self.stable_id
        ):
            raise ValueError("Rust benchmark candidate evidence must be complete")
        _validate_candidates(self.candidates)

    def sort_key(self) -> tuple[str, str, str, str]:
        return (self.profile_name, self.stable_id, self.slot_hash, self.key_hash)

    def record(self) -> list[object]:
        return [
            self.profile_name,
            self.slot_hash,
            self.key_hash,
            self.stable_id,
            [list(candidate) for candidate in self.candidates],
        ]

    @classmethod
    def from_record(cls, record: object) -> RustBenchmarkCandidateEvidence:
        if not isinstance(record, list) or len(record) != 5:
            raise ValueError("Rust benchmark candidate record must contain five fields")
        profile_name, slot_hash, key_hash, stable_id = _string_values(
            record[:4], "Rust benchmark candidate"
        )
        return cls(
            profile_name,
            slot_hash,
            key_hash,
            stable_id,
            _candidate_pairs(record[4], "Rust benchmark candidate"),
        )


@dataclass(frozen=True, slots=True)
class RustBenchmarkPolicyEvidence:
    """One report's independent policy status and compiler mapping hashes."""

    profile_name: str
    slot_hash: str
    key_hash: str
    stable_id: str
    status: RustPolicySelectionStatus
    candidates: tuple[tuple[str, str], ...]
    mappings: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        if (
            not self.profile_name
            or not is_sha256_digest(self.slot_hash)
            or not is_sha256_digest(self.key_hash)
            or not self.stable_id
        ):
            raise ValueError("Rust benchmark policy evidence must be complete")
        _validate_candidates(self.candidates)
        _validate_hash_pairs(self.mappings, "Rust benchmark policy mapping")
        mapping_ids = tuple(candidate_id for candidate_id, _digest in self.mappings)
        candidate_ids = tuple(candidate_id for candidate_id, _digest in self.candidates)
        if self.status == "supported":
            if mapping_ids != candidate_ids:
                raise ValueError(
                    "supported Rust policy evidence requires every mapping hash"
                )
        elif self.status == "report_only":
            if self.mappings:
                raise ValueError("report-only Rust policy evidence cannot have mappings")
        else:
            raise ValueError(f"unknown Rust policy evidence status {self.status!r}")

    def sort_key(self) -> tuple[str, str, str, str]:
        return (self.profile_name, self.stable_id, self.slot_hash, self.key_hash)

    def record(self) -> list[object]:
        return [
            self.profile_name,
            self.slot_hash,
            self.key_hash,
            self.stable_id,
            self.status,
            [list(candidate) for candidate in self.candidates],
            [list(mapping) for mapping in self.mappings],
        ]

    @classmethod
    def from_record(cls, record: object) -> RustBenchmarkPolicyEvidence:
        if not isinstance(record, list) or len(record) != 7:
            raise ValueError("Rust benchmark policy record must contain seven fields")
        profile_name, slot_hash, key_hash, stable_id = _string_values(
            record[:4], "Rust benchmark policy"
        )
        status = record[4]
        if status not in ("supported", "report_only"):
            raise ValueError(f"unknown Rust benchmark policy status {status!r}")
        return cls(
            profile_name,
            slot_hash,
            key_hash,
            stable_id,
            cast(RustPolicySelectionStatus, status),
            _candidate_pairs(record[5], "Rust benchmark policy candidate"),
            _candidate_pairs(record[6], "Rust benchmark policy mapping"),
        )


@dataclass(frozen=True, slots=True)
class RustBenchmarkEvidence:
    """Frozen exact evidence kept separate from aggregate inventory counts."""

    profiles: tuple[RustBenchmarkProfileEvidence, ...]
    candidates: tuple[RustBenchmarkCandidateEvidence, ...]
    policies: tuple[RustBenchmarkPolicyEvidence, ...]

    def __post_init__(self) -> None:
        profile_names = tuple(profile.profile_name for profile in self.profiles)
        candidate_ids = tuple(item.stable_id for item in self.candidates)
        policy_ids = tuple(item.stable_id for item in self.policies)
        if len(set(profile_names)) != len(profile_names):
            raise ValueError("Rust benchmark evidence profile names must be unique")
        if len(set(candidate_ids)) != len(candidate_ids):
            raise ValueError("Rust benchmark evidence candidate IDs must be unique")
        if len(set(policy_ids)) != len(policy_ids):
            raise ValueError("Rust benchmark evidence policy IDs must be unique")
        known_profiles = set(profile_names)
        if any(
            item.profile_name not in known_profiles for item in self.candidates
        ) or any(
            item.profile_name not in known_profiles for item in self.policies
        ):
            raise ValueError(
                "Rust benchmark candidate and policy profiles must be declared"
            )
        candidate_keys = {
            (
                item.profile_name,
                item.slot_hash,
                item.key_hash,
                item.stable_id,
                item.candidates,
            )
            for item in self.candidates
        }
        policy_keys = {
            (
                item.profile_name,
                item.slot_hash,
                item.key_hash,
                item.stable_id,
                item.candidates,
            )
            for item in self.policies
        }
        if candidate_keys != policy_keys:
            raise ValueError(
                "Rust report candidates and policy coverage must match exactly"
            )


def build_rust_benchmark_evidence(
    benchmarks: BenchmarkProjectPlan,
    policy_coverage: RustPolicyCoveragePlan,
) -> RustBenchmarkEvidence:
    """Project canonical report and policy owners into exact ratchet facts."""

    benchmark_profiles = benchmarks.profiles_for("rust")
    profile_names = {profile.profile_name for profile in benchmark_profiles}
    if any(
        profile.profile_name not in profile_names
        for profile in policy_coverage.profiles
    ):
        raise ValueError("Rust policy coverage contains a foreign benchmark profile")

    profiles = tuple(
        sorted(
            (
                RustBenchmarkProfileEvidence(
                    profile_name=profile.profile_name,
                    manifest_hash=profile.manifest_hash,
                )
                for profile in benchmark_profiles
            ),
            key=RustBenchmarkProfileEvidence.sort_key,
        )
    )
    candidates = tuple(
        sorted(
            (
                RustBenchmarkCandidateEvidence(
                    profile_name=profile.profile_name,
                    slot_hash=benchmark_slot_identity_hash(
                        profile.profile_name,
                        candidate_set.specialization,
                    ),
                    key_hash=specialization_identity_hash(candidate_set.key),
                    stable_id=candidate_set.stable_id,
                    candidates=tuple(
                        (candidate.variant_id, candidate.body_hash)
                        for candidate in candidate_set.candidates
                    ),
                )
                for profile in benchmark_profiles
                for candidate_set in profile.candidate_sets
            ),
            key=RustBenchmarkCandidateEvidence.sort_key,
        )
    )
    candidate_slot_hashes = {
        candidate_set.key: benchmark_slot_identity_hash(
            profile.profile_name,
            candidate_set.specialization,
        )
        for profile in benchmark_profiles
        for candidate_set in profile.candidate_sets
    }
    policies = tuple(
        sorted(
            (
                RustBenchmarkPolicyEvidence(
                    profile_name=profile.profile_name,
                    slot_hash=candidate_slot_hashes[decision.key],
                    key_hash=specialization_identity_hash(decision.key),
                    stable_id=decision.stable_id,
                    status=decision.status,
                    candidates=tuple(
                        (candidate.candidate_id, candidate.body_hash)
                        for candidate in decision.candidates
                    ),
                    mappings=tuple(
                        (
                            mapping.candidate_id,
                            sha256(mapping.source.encode("utf-8")).hexdigest(),
                        )
                        for mapping in decision.mapping_choices
                    ),
                )
                for profile in policy_coverage.profiles
                for decision in profile.decisions
            ),
            key=RustBenchmarkPolicyEvidence.sort_key,
        )
    )
    return RustBenchmarkEvidence(profiles, candidates, policies)


def deserialize_rust_benchmark_evidence(
    profiles: object,
    candidates: object,
    policies: object,
) -> RustBenchmarkEvidence:
    if not isinstance(profiles, list):
        raise ValueError("Rust benchmark baseline profiles must be a list")
    if not isinstance(candidates, list):
        raise ValueError("Rust benchmark baseline candidates must be a list")
    if not isinstance(policies, list):
        raise ValueError("Rust benchmark baseline policies must be a list")
    return RustBenchmarkEvidence(
        profiles=tuple(
            sorted(
                (RustBenchmarkProfileEvidence.from_record(item) for item in profiles),
                key=RustBenchmarkProfileEvidence.sort_key,
            )
        ),
        candidates=tuple(
            sorted(
                (RustBenchmarkCandidateEvidence.from_record(item) for item in candidates),
                key=RustBenchmarkCandidateEvidence.sort_key,
            )
        ),
        policies=tuple(
            sorted(
                (RustBenchmarkPolicyEvidence.from_record(item) for item in policies),
                key=RustBenchmarkPolicyEvidence.sort_key,
            )
        ),
    )


def _string_record(record: object, size: int, label: str) -> tuple[str, ...]:
    if not isinstance(record, list) or len(record) != size:
        raise ValueError(f"{label} record must contain {size} fields")
    return _string_values(record, label)


def _string_values(values: list[object], label: str) -> tuple[str, ...]:
    if not all(isinstance(value, str) and value for value in values):
        raise ValueError(f"{label} record fields must be non-empty strings")
    return tuple(cast(list[str], values))


def _candidate_pairs(value: object, label: str) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, list):
        raise ValueError(f"{label} identities must be a list")
    pairs: list[tuple[str, str]] = []
    for pair in value:
        if not isinstance(pair, list) or len(pair) != 2:
            raise ValueError(f"{label} identity must contain ID and hash")
        candidate_id, digest = _string_values(pair, label)
        pairs.append((candidate_id, digest))
    return tuple(pairs)


def _validate_candidates(candidates: tuple[tuple[str, str], ...]) -> None:
    if not candidates or candidates[0][0] != "default":
        raise ValueError("Rust benchmark evidence must begin with the default")
    candidate_ids = tuple(candidate_id for candidate_id, _digest in candidates)
    if len(set(candidate_ids)) != len(candidate_ids):
        raise ValueError("Rust benchmark evidence candidate IDs must be unique")
    if any(
        not candidate_id or not is_sha256_digest(digest)
        for candidate_id, digest in candidates
    ):
        raise ValueError("Rust benchmark evidence candidates must be complete")


def _validate_hash_pairs(
    values: tuple[tuple[str, str], ...],
    label: str,
) -> None:
    if any(
        not identity or not is_sha256_digest(digest)
        for identity, digest in values
    ):
        raise ValueError(f"{label} must contain canonical SHA-256 hashes")


__all__ = (
    "RustBenchmarkCandidateEvidence",
    "RustBenchmarkEvidence",
    "RustBenchmarkPolicyEvidence",
    "RustBenchmarkProfileEvidence",
    "build_rust_benchmark_evidence",
    "deserialize_rust_benchmark_evidence",
)
