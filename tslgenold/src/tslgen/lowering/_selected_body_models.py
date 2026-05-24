from __future__ import annotations

from dataclasses import dataclass

from tslgen.core.diagnostics import SourceLocation
import tslgen.lowering._exact_shapes as _exact_shapes


@dataclass(frozen=True, slots=True)
class OpaqueSelectedBranchBodyHandoff:
    candidate_id: str
    selected_type_tag: str
    selected_literal: int
    opaque_body_text: str
    source_location: SourceLocation
    originating_branch_chain_id: str

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise ValueError("opaque selected-body handoff candidate id must be non-empty")
        if not self.selected_type_tag:
            raise ValueError(
                "opaque selected-body handoff selected type tag must be non-empty"
            )
        if self.selected_literal not in (2, 4, 8):
            raise ValueError(
                "opaque selected-body handoff literal must be 2, 4, or 8"
            )
        if not self.opaque_body_text.strip():
            raise ValueError("opaque selected-body handoff body text must be non-empty")
        if self.source_location is None:
            raise ValueError("opaque selected-body handoff requires source location")
        if not self.originating_branch_chain_id:
            raise ValueError(
                "opaque selected-body handoff branch-chain id must be non-empty"
            )

    @property
    def key(self) -> tuple[object, ...]:
        return (
            "opaque_selected_branch_body",
            self.candidate_id,
            self.selected_type_tag,
            self.selected_literal,
            self.opaque_body_text,
            self.source_location.sort_key(),
            self.originating_branch_chain_id,
        )


@dataclass(frozen=True, slots=True)
class NoSelectedBranchBodyHandoff:
    candidate_id: str
    selected_type_tag: str
    source_location: SourceLocation
    originating_branch_chain_id: str
    attempted_literals: tuple[int, ...] = (2, 4, 8)

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise ValueError("no-selected-body handoff candidate id must be non-empty")
        if not self.selected_type_tag:
            raise ValueError(
                "no-selected-body handoff selected type tag must be non-empty"
            )
        if self.source_location is None:
            raise ValueError("no-selected-body handoff requires source location")
        if not self.originating_branch_chain_id:
            raise ValueError(
                "no-selected-body handoff branch-chain id must be non-empty"
            )
        object.__setattr__(self, "attempted_literals", tuple(self.attempted_literals))
        if self.attempted_literals != (2, 4, 8):
            raise ValueError(
                "no-selected-body handoff attempted literals must be 2, 4, 8"
            )

    @property
    def key(self) -> tuple[object, ...]:
        return (
            "no_selected_branch_body",
            self.candidate_id,
            self.selected_type_tag,
            self.source_location.sort_key(),
            self.originating_branch_chain_id,
            self.attempted_literals,
        )


@dataclass(frozen=True, slots=True)
class SelectedBranchBodyAssignmentFormRecognition:
    candidate_id: str
    selected_type_tag: str
    selected_literal: int
    originating_branch_chain_id: str
    original_opaque_body_text: str
    selected_statement_location: SourceLocation
    assignment_target_text: str
    opaque_rhs_text: str
    direct_intrinsic_token_text: str

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise ValueError(
                "selected-body assignment form candidate id must be non-empty"
            )
        if not self.selected_type_tag:
            raise ValueError(
                "selected-body assignment form type tag must be non-empty"
            )
        if self.selected_literal not in (2, 4, 8):
            raise ValueError(
                "selected-body assignment form literal must be 2, 4, or 8"
            )
        if not self.originating_branch_chain_id:
            raise ValueError(
                "selected-body assignment form branch-chain id must be non-empty"
            )
        if not self.original_opaque_body_text.strip():
            raise ValueError(
                "selected-body assignment form original body text must be non-empty"
            )
        if self.selected_statement_location is None:
            raise ValueError(
                "selected-body assignment form requires selected statement location"
            )
        if (
            self.assignment_target_text
            != _exact_shapes.EXACT_SELECTED_BODY_ASSIGNMENT_SHAPE.target_text
        ):
            raise ValueError(
                "selected-body assignment form target must be exact text 'pg'"
            )
        if not self.opaque_rhs_text:
            raise ValueError(
                "selected-body assignment form RHS text must be non-empty"
            )
        if not (
            _exact_shapes.EXACT_SELECTED_BODY_ASSIGNMENT_SHAPE
            .supports_direct_intrinsic_token(self.direct_intrinsic_token_text)
        ):
            raise ValueError(
                "selected-body assignment form direct intrinsic token is unsupported"
            )

    @property
    def key(self) -> tuple[object, ...]:
        return (
            "selected_branch_body_assignment_form",
            self.candidate_id,
            self.selected_type_tag,
            self.selected_literal,
            self.originating_branch_chain_id,
            self.original_opaque_body_text,
            self.selected_statement_location.sort_key(),
            self.assignment_target_text,
            self.opaque_rhs_text,
            self.direct_intrinsic_token_text,
        )


@dataclass(frozen=True, slots=True)
class NoSelectedBranchBodyAssignmentFormRecognition:
    candidate_id: str
    selected_type_tag: str
    source_location: SourceLocation
    originating_branch_chain_id: str
    attempted_literals: tuple[int, ...] = (2, 4, 8)

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise ValueError(
                "no-selected-body assignment form candidate id must be non-empty"
            )
        if not self.selected_type_tag:
            raise ValueError(
                "no-selected-body assignment form type tag must be non-empty"
            )
        if self.source_location is None:
            raise ValueError(
                "no-selected-body assignment form requires source location"
            )
        if not self.originating_branch_chain_id:
            raise ValueError(
                "no-selected-body assignment form branch-chain id must be non-empty"
            )
        object.__setattr__(self, "attempted_literals", tuple(self.attempted_literals))
        if self.attempted_literals != (2, 4, 8):
            raise ValueError(
                "no-selected-body assignment form attempted literals must be 2, 4, 8"
            )

    @property
    def key(self) -> tuple[object, ...]:
        return (
            "no_selected_branch_body_assignment_form",
            self.candidate_id,
            self.selected_type_tag,
            self.source_location.sort_key(),
            self.originating_branch_chain_id,
            self.attempted_literals,
        )


@dataclass(frozen=True, slots=True)
class SelectedAssignmentDirectIntrinsicBodyIr:
    candidate_id: str
    selected_type_tag: str
    selected_literal: int
    originating_branch_chain_id: str
    original_opaque_body_text: str
    source_location: SourceLocation
    assignment_target_text: str
    opaque_rhs_text: str
    direct_intrinsic_token_text: str
    direct_intrinsic_argument_texts: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise ValueError(
                "selected assignment direct-intrinsic body IR candidate id "
                "must be non-empty"
            )
        if not self.selected_type_tag:
            raise ValueError(
                "selected assignment direct-intrinsic body IR type tag "
                "must be non-empty"
            )
        if self.selected_literal not in (2, 4, 8):
            raise ValueError(
                "selected assignment direct-intrinsic body IR literal must be "
                "2, 4, or 8"
            )
        if not self.originating_branch_chain_id:
            raise ValueError(
                "selected assignment direct-intrinsic body IR branch-chain id "
                "must be non-empty"
            )
        if not self.original_opaque_body_text.strip():
            raise ValueError(
                "selected assignment direct-intrinsic body IR original body "
                "text must be non-empty"
            )
        if self.source_location is None:
            raise ValueError(
                "selected assignment direct-intrinsic body IR requires source "
                "location"
            )
        if not self.assignment_target_text:
            raise ValueError(
                "selected assignment direct-intrinsic body IR assignment "
                "target text must be non-empty"
            )
        if not self.opaque_rhs_text:
            raise ValueError(
                "selected assignment direct-intrinsic body IR RHS text must "
                "be non-empty"
            )
        if not self.direct_intrinsic_token_text:
            raise ValueError(
                "selected assignment direct-intrinsic body IR direct "
                "intrinsic token text must be non-empty"
            )
        object.__setattr__(
            self,
            "direct_intrinsic_argument_texts",
            tuple(self.direct_intrinsic_argument_texts),
        )
        if self.direct_intrinsic_argument_texts:
            raise ValueError(
                "selected assignment direct-intrinsic body IR supports only "
                "an explicit empty argument list"
            )

    @property
    def key(self) -> tuple[object, ...]:
        return (
            "selected_assignment_direct_intrinsic_body_ir",
            self.candidate_id,
            self.selected_type_tag,
            self.selected_literal,
            self.originating_branch_chain_id,
            self.original_opaque_body_text,
            self.source_location.sort_key(),
            self.assignment_target_text,
            self.opaque_rhs_text,
            self.direct_intrinsic_token_text,
            self.direct_intrinsic_argument_texts,
        )


@dataclass(frozen=True, slots=True)
class NoSelectedAssignmentDirectIntrinsicBodyIr:
    candidate_id: str
    selected_type_tag: str
    source_location: SourceLocation
    originating_branch_chain_id: str
    attempted_literals: tuple[int, ...] = (2, 4, 8)

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise ValueError("no selected body IR candidate id must be non-empty")
        if not self.selected_type_tag:
            raise ValueError("no selected body IR type tag must be non-empty")
        if self.source_location is None:
            raise ValueError("no selected body IR requires source location")
        if not self.originating_branch_chain_id:
            raise ValueError("no selected body IR branch-chain id must be non-empty")
        object.__setattr__(self, "attempted_literals", tuple(self.attempted_literals))
        if self.attempted_literals != (2, 4, 8):
            raise ValueError("no selected body IR attempted literals must be 2, 4, 8")

    @property
    def key(self) -> tuple[object, ...]:
        return (
            "no_selected_assignment_direct_intrinsic_body_ir",
            self.candidate_id,
            self.selected_type_tag,
            self.source_location.sort_key(),
            self.originating_branch_chain_id,
            self.attempted_literals,
        )


@dataclass(frozen=True, slots=True)
class SelectedBodyEnvelopeEntry:
    source_body_ir: SelectedAssignmentDirectIntrinsicBodyIr
    candidate_id: str
    selected_type_tag: str
    selected_literal: int
    originating_branch_chain_id: str
    original_opaque_body_text: str
    source_location: SourceLocation
    assignment_target_text: str
    opaque_rhs_text: str
    direct_intrinsic_token_text: str
    direct_intrinsic_argument_texts: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.source_body_ir, SelectedAssignmentDirectIntrinsicBodyIr):
            raise TypeError("selected body envelope entry requires M62 body IR")
        object.__setattr__(
            self,
            "direct_intrinsic_argument_texts",
            tuple(self.direct_intrinsic_argument_texts),
        )
        if (
            self.candidate_id != self.source_body_ir.candidate_id
            or self.selected_type_tag != self.source_body_ir.selected_type_tag
            or self.selected_literal != self.source_body_ir.selected_literal
            or self.originating_branch_chain_id
            != self.source_body_ir.originating_branch_chain_id
            or self.original_opaque_body_text
            != self.source_body_ir.original_opaque_body_text
            or self.source_location != self.source_body_ir.source_location
            or self.assignment_target_text
            != self.source_body_ir.assignment_target_text
            or self.opaque_rhs_text != self.source_body_ir.opaque_rhs_text
            or self.direct_intrinsic_token_text
            != self.source_body_ir.direct_intrinsic_token_text
            or self.direct_intrinsic_argument_texts
            != self.source_body_ir.direct_intrinsic_argument_texts
        ):
            raise ValueError(
                "selected body envelope entry facts must match source M62 body IR"
            )

    @property
    def key(self) -> tuple[object, ...]:
        return (
            "selected_body_envelope_entry",
            self.source_body_ir.key,
            self.candidate_id,
            self.selected_type_tag,
            self.selected_literal,
            self.originating_branch_chain_id,
            self.original_opaque_body_text,
            self.source_location.sort_key(),
            self.assignment_target_text,
            self.opaque_rhs_text,
            self.direct_intrinsic_token_text,
            self.direct_intrinsic_argument_texts,
        )


@dataclass(frozen=True, slots=True)
class SelectedBodyEnvelopeIr:
    candidate_id: str
    selected_type_tag: str
    source_location: SourceLocation
    originating_branch_chain_id: str
    entries: tuple[SelectedBodyEnvelopeEntry, ...]

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise ValueError("selected body envelope candidate id must be non-empty")
        if not self.selected_type_tag:
            raise ValueError("selected body envelope type tag must be non-empty")
        if self.source_location is None:
            raise ValueError("selected body envelope requires source location")
        if not self.originating_branch_chain_id:
            raise ValueError("selected body envelope branch-chain id must be non-empty")
        object.__setattr__(self, "entries", tuple(self.entries))
        if len(self.entries) != 1:
            raise ValueError("selected body envelope must contain exactly one entry")
        entry = self.entries[0]
        if (
            entry.candidate_id != self.candidate_id
            or entry.selected_type_tag != self.selected_type_tag
            or entry.source_location != self.source_location
            or entry.originating_branch_chain_id != self.originating_branch_chain_id
        ):
            raise ValueError(
                "selected body envelope entry provenance must match envelope"
            )

    @property
    def key(self) -> tuple[object, ...]:
        return (
            "selected_body_envelope_ir",
            self.candidate_id,
            self.selected_type_tag,
            self.source_location.sort_key(),
            self.originating_branch_chain_id,
            tuple(entry.key for entry in self.entries),
        )


@dataclass(frozen=True, slots=True)
class NoSelectedBodyEnvelopeIr:
    source_body_ir: NoSelectedAssignmentDirectIntrinsicBodyIr
    candidate_id: str
    selected_type_tag: str
    source_location: SourceLocation
    originating_branch_chain_id: str
    attempted_literals: tuple[int, ...] = (2, 4, 8)
    entries: tuple[SelectedBodyEnvelopeEntry, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.source_body_ir, NoSelectedAssignmentDirectIntrinsicBodyIr):
            raise TypeError("no selected body envelope requires M62 no-body IR")
        if not self.candidate_id:
            raise ValueError("no selected body envelope candidate id must be non-empty")
        if not self.selected_type_tag:
            raise ValueError("no selected body envelope type tag must be non-empty")
        if self.source_location is None:
            raise ValueError("no selected body envelope requires source location")
        if not self.originating_branch_chain_id:
            raise ValueError(
                "no selected body envelope branch-chain id must be non-empty"
            )
        object.__setattr__(self, "attempted_literals", tuple(self.attempted_literals))
        object.__setattr__(self, "entries", tuple(self.entries))
        if self.entries:
            raise ValueError("no selected body envelope must not contain entries")
        if self.attempted_literals != (2, 4, 8):
            raise ValueError(
                "no selected body envelope attempted literals must be 2, 4, 8"
            )
        if (
            self.candidate_id != self.source_body_ir.candidate_id
            or self.selected_type_tag != self.source_body_ir.selected_type_tag
            or self.source_location != self.source_body_ir.source_location
            or self.originating_branch_chain_id
            != self.source_body_ir.originating_branch_chain_id
            or self.attempted_literals != self.source_body_ir.attempted_literals
        ):
            raise ValueError(
                "no selected body envelope facts must match source M62 no-body IR"
            )

    @property
    def key(self) -> tuple[object, ...]:
        return (
            "no_selected_body_envelope_ir",
            self.source_body_ir.key,
            self.candidate_id,
            self.selected_type_tag,
            self.source_location.sort_key(),
            self.originating_branch_chain_id,
            self.attempted_literals,
            tuple(entry.key for entry in self.entries),
        )


type GenerationSelectedBranchBodyHandoff = (
    OpaqueSelectedBranchBodyHandoff | NoSelectedBranchBodyHandoff
)
type GenerationSelectedBranchBodyAssignmentRecognition = (
    SelectedBranchBodyAssignmentFormRecognition
    | NoSelectedBranchBodyAssignmentFormRecognition
)
type GenerationSelectedBranchBodyIr = (
    SelectedAssignmentDirectIntrinsicBodyIr | NoSelectedAssignmentDirectIntrinsicBodyIr
)
type GenerationSelectedBodyEnvelopeIr = (
    SelectedBodyEnvelopeIr | NoSelectedBodyEnvelopeIr
)


def is_generation_selected_body_envelope_ir(value: object) -> bool:
    return isinstance(value, (SelectedBodyEnvelopeIr, NoSelectedBodyEnvelopeIr))


def is_selected_body_envelope_ir(value: object) -> bool:
    return isinstance(value, SelectedBodyEnvelopeIr)


def is_no_selected_body_envelope_ir(value: object) -> bool:
    return isinstance(value, NoSelectedBodyEnvelopeIr)
