from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


type ExactArrayBodyPipelineArtifactKind = Literal[
    "array_body_envelope",
    "array_initialization_slot_form",
    "array_initialization_helper_request",
    "array_initialization_base_type_resolution",
    "array_initialization_vector_length_resolution",
    "array_initialization_vector_alignment_resolution",
    "array_initialization_helper_set_completion",
    "array_initialization_declaration_shell",
    "array_body_structural_sequence",
    "predicate_path_structural_request",
    "post_branch_intrinsic_call_site_structural_request",
    "return_emission_structural_request",
    "array_body_structural_package",
]
type ExactArrayBodyPipelineStageName = Literal[
    "array_body_envelope_slot_assembly",
    "array_initialization_slot_form_lowering",
    "array_initialization_helper_request_lowering",
    "array_initialization_base_type_request_resolution",
    "array_initialization_vector_length_request_resolution",
    "array_initialization_vector_alignment_request_resolution",
    "array_initialization_helper_set_completion",
    "array_initialization_declaration_shell_lowering",
    "array_body_structural_sequence_classification",
    "predicate_path_structural_request_lowering",
    "post_branch_intrinsic_call_site_structural_request_lowering",
    "return_emission_structural_request_lowering",
    "array_body_structural_package_assembly",
]
type ExactArrayBodyPipelineBackfeedPolicy = Literal[
    "none",
    "typed_request_only",
]


@dataclass(frozen=True, slots=True)
class ExactArrayBodyPipelineFact:
    kind: ExactArrayBodyPipelineArtifactKind
    key: tuple[object, ...]
    value: object

    def __post_init__(self) -> None:
        object.__setattr__(self, "key", tuple(self.key))


@dataclass(frozen=True, slots=True)
class ExactArrayBodyPipelineBackfeedRequest:
    """Typed placeholder for future backfeed needs; M77 records none."""

    source_stage_name: ExactArrayBodyPipelineStageName
    requested_artifact_kind: ExactArrayBodyPipelineArtifactKind
    key: tuple[object, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "key", tuple(self.key))


@dataclass(frozen=True, slots=True)
class ExactArrayBodyPipelineStageStep:
    stage_name: ExactArrayBodyPipelineStageName
    stage: object
    produced_fact: ExactArrayBodyPipelineFact
    depends_on: tuple[ExactArrayBodyPipelineArtifactKind, ...] = ()
    backfeed_policy: ExactArrayBodyPipelineBackfeedPolicy = "none"

    def __post_init__(self) -> None:
        object.__setattr__(self, "depends_on", tuple(self.depends_on))

    @property
    def key(self) -> tuple[object, ...]:
        return (
            self.stage_name,
            self.produced_fact.kind,
            self.produced_fact.key,
            self.depends_on,
            self.backfeed_policy,
        )


@dataclass(frozen=True, slots=True)
class ExactArrayBodyPipelineSnapshot:
    steps: tuple[ExactArrayBodyPipelineStageStep, ...] = ()
    pending_backfeed_requests: tuple[ExactArrayBodyPipelineBackfeedRequest, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "steps", tuple(self.steps))
        object.__setattr__(
            self,
            "pending_backfeed_requests",
            tuple(self.pending_backfeed_requests),
        )

    @classmethod
    def empty(cls) -> ExactArrayBodyPipelineSnapshot:
        return cls()

    @property
    def stages(self) -> tuple[object, ...]:
        return tuple(step.stage for step in self.steps)

    @property
    def key(self) -> tuple[object, ...]:
        return (
            tuple(step.key for step in self.steps),
            tuple(request.key for request in self.pending_backfeed_requests),
        )

    def facts_for(
        self,
        kind: ExactArrayBodyPipelineArtifactKind,
    ) -> tuple[ExactArrayBodyPipelineFact, ...]:
        return tuple(
            step.produced_fact
            for step in self.steps
            if step.produced_fact.kind == kind
        )


def exact_array_body_pipeline_step(
    *,
    stage_name: ExactArrayBodyPipelineStageName,
    stage: object,
    artifact_kind: ExactArrayBodyPipelineArtifactKind,
    artifact_key: tuple[object, ...],
    artifact_value: object,
    depends_on: tuple[ExactArrayBodyPipelineArtifactKind, ...] = (),
    backfeed_policy: ExactArrayBodyPipelineBackfeedPolicy = "none",
) -> ExactArrayBodyPipelineStageStep:
    return ExactArrayBodyPipelineStageStep(
        stage_name=stage_name,
        stage=stage,
        produced_fact=ExactArrayBodyPipelineFact(
            kind=artifact_kind,
            key=artifact_key,
            value=artifact_value,
        ),
        depends_on=depends_on,
        backfeed_policy=backfeed_policy,
    )
