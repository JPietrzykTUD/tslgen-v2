from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from tslgen.core.diagnostics import SourceLocation
import tslgen.lowering._exact_shapes as _exact_shapes
import tslgen.lowering._selected_body_models as _selected_body_models


class _KeyedProtocol(Protocol):
    @property
    def key(self) -> tuple[object, ...]: ...


class GenerationTypeRefLike(_KeyedProtocol, Protocol):
    @property
    def kind(self) -> str: ...

    @property
    def type_tag(self) -> str: ...

    @property
    def source_type_tag(self) -> str | None: ...


type GenerationTypeRef = GenerationTypeRefLike


type GenerationSelectedBodyEnvelopeIr = (
    _selected_body_models.GenerationSelectedBodyEnvelopeIr
)


def _is_generation_selected_body_envelope(value: object) -> bool:
    return _selected_body_models.is_generation_selected_body_envelope_ir(value)


def _is_selected_body_envelope(value: object) -> bool:
    return _selected_body_models.is_selected_body_envelope_ir(value)


def _is_no_selected_body_envelope(value: object) -> bool:
    return _selected_body_models.is_no_selected_body_envelope_ir(value)


type ExactArrayInitializationHelperLeafKind = Literal[
    "type_generation_base_in",
    "value_generation_vector_length",
    "value_generation_vector_alignment",
    "value_backend_uninit_array",
]
type ExactArrayInitializationHelperRequestKind = Literal[
    "generation_type",
    "generation_value",
    "backend_value",
]
type ExactArrayInitializationHelperLeafFieldName = Literal[
    "base_type_leaf",
    "vector_length_leaf",
    "vector_alignment_leaf",
    "backend_uninit_leaf",
]

class SourceLocated(Protocol):
    @property
    def source_location(self) -> SourceLocation | None: ...


class ExactArrayInitializationHelperLeafSpecLike(Protocol):
    @property
    def field_name(self) -> ExactArrayInitializationHelperLeafFieldName: ...

    @property
    def expected_leaf_kind(self) -> ExactArrayInitializationHelperLeafKind: ...


class ExactArrayInitializationSlotFormLike(SourceLocated, Protocol):
    @property
    def variable_token(self) -> str: ...


class ExactArrayInitializationHelperLeafLike(SourceLocated, Protocol):
    @property
    def kind(self) -> ExactArrayInitializationHelperLeafKind: ...

    @property
    def source_text(self) -> str: ...


class ArrayBodyEnvelopeSkeletonKeyLike(Protocol):
    @property
    def candidate_id(self) -> str: ...

    @property
    def selected_type_tag(self) -> str: ...

    @property
    def originating_branch_chain_id(self) -> str: ...


class ArrayBodyEnvelopeSkeletonLike(SourceLocated, Protocol):
    pass


class ArrayBodyEnvelopeSkeletonRequirementLike(Protocol):
    @property
    def source_location(self) -> SourceLocation | None: ...


class ArrayBodyEnvelopeLike(SourceLocated, Protocol):
    @property
    def candidate_id(self) -> str: ...

    @property
    def selected_type_tag(self) -> str: ...

    @property
    def originating_branch_chain_id(self) -> str: ...



_TSIL_IDENTIFIER = r"[A-Za-z_][A-Za-z0-9_]*"

_EXACT_ARRAY_INITIALIZATION_HELPER_TEXT_BY_KIND: dict[
    ExactArrayInitializationHelperLeafKind, str
] = {
    "type_generation_base_in": "type<generation>(base::in)",
    "value_generation_vector_length": "value<generation>(vector::length)",
    "value_generation_vector_alignment": "value<generation>(vector::alignment)",
    "value_backend_uninit_array": "value<backend>(uninit::array)",
}


@dataclass(frozen=True, slots=True)
class _ExactArrayInitializationHelperLeafSpec:
    field_name: ExactArrayInitializationHelperLeafFieldName
    expected_leaf_kind: ExactArrayInitializationHelperLeafKind
    request_kind: ExactArrayInitializationHelperRequestKind
    request_ordinal: int


_EXACT_ARRAY_INITIALIZATION_HELPER_LEAF_SPECS: tuple[
    _ExactArrayInitializationHelperLeafSpec, ...
] = (
    _ExactArrayInitializationHelperLeafSpec(
        field_name="base_type_leaf",
        expected_leaf_kind="type_generation_base_in",
        request_kind="generation_type",
        request_ordinal=0,
    ),
    _ExactArrayInitializationHelperLeafSpec(
        field_name="vector_length_leaf",
        expected_leaf_kind="value_generation_vector_length",
        request_kind="generation_value",
        request_ordinal=1,
    ),
    _ExactArrayInitializationHelperLeafSpec(
        field_name="vector_alignment_leaf",
        expected_leaf_kind="value_generation_vector_alignment",
        request_kind="generation_value",
        request_ordinal=2,
    ),
    _ExactArrayInitializationHelperLeafSpec(
        field_name="backend_uninit_leaf",
        expected_leaf_kind="value_backend_uninit_array",
        request_kind="backend_value",
        request_ordinal=3,
    ),
)


@dataclass(frozen=True, slots=True)
class _ExactArrayInitializationBaseTypeRequestRule:
    request_ordinal: int
    request_kind: Literal["generation_type"]
    helper_leaf_kind: Literal["type_generation_base_in"]
    expected_leaf_source_text: str
    result_kind: Literal["base.in"]


_EXACT_ARRAY_INITIALIZATION_BASE_TYPE_REQUEST_RULE = (
    _ExactArrayInitializationBaseTypeRequestRule(
        request_ordinal=0,
        request_kind="generation_type",
        helper_leaf_kind="type_generation_base_in",
        expected_leaf_source_text=_EXACT_ARRAY_INITIALIZATION_HELPER_TEXT_BY_KIND[
            "type_generation_base_in"
        ],
        result_kind="base.in",
    )
)


@dataclass(frozen=True, slots=True)
class _ExactArrayInitializationVectorLengthRequestRule:
    request_ordinal: int
    request_kind: Literal["generation_value"]
    helper_leaf_kind: Literal["value_generation_vector_length"]
    expected_leaf_source_text: str


_EXACT_ARRAY_INITIALIZATION_VECTOR_LENGTH_REQUEST_RULE = (
    _ExactArrayInitializationVectorLengthRequestRule(
        request_ordinal=1,
        request_kind="generation_value",
        helper_leaf_kind="value_generation_vector_length",
        expected_leaf_source_text=_EXACT_ARRAY_INITIALIZATION_HELPER_TEXT_BY_KIND[
            "value_generation_vector_length"
        ],
    )
)


@dataclass(frozen=True, slots=True)
class _ExactArrayInitializationVectorAlignmentRequestRule:
    request_ordinal: int
    request_kind: Literal["generation_value"]
    helper_leaf_kind: Literal["value_generation_vector_alignment"]
    expected_leaf_source_text: str


_EXACT_ARRAY_INITIALIZATION_VECTOR_ALIGNMENT_REQUEST_RULE = (
    _ExactArrayInitializationVectorAlignmentRequestRule(
        request_ordinal=2,
        request_kind="generation_value",
        helper_leaf_kind="value_generation_vector_alignment",
        expected_leaf_source_text=_EXACT_ARRAY_INITIALIZATION_HELPER_TEXT_BY_KIND[
            "value_generation_vector_alignment"
        ],
    )
)


@dataclass(frozen=True, slots=True)
class _ExactArrayInitializationBackendUninitRequestRule:
    request_ordinal: int
    request_kind: Literal["backend_value"]
    helper_leaf_kind: Literal["value_backend_uninit_array"]
    expected_leaf_source_text: str


_EXACT_ARRAY_INITIALIZATION_BACKEND_UNINIT_REQUEST_RULE = (
    _ExactArrayInitializationBackendUninitRequestRule(
        request_ordinal=3,
        request_kind="backend_value",
        helper_leaf_kind="value_backend_uninit_array",
        expected_leaf_source_text=_EXACT_ARRAY_INITIALIZATION_HELPER_TEXT_BY_KIND[
            "value_backend_uninit_array"
        ],
    )
)

type ExactPredicatePathSelectedUpdateState = Literal[
    "accepted_selected_update",
    "accepted_no_update",
]
type ExactArrayInitializationVectorLengthKind = Literal[
    "fixed_lanes",
    "runtime_lanes",
    "scalable_lanes",
]
type ExactArrayInitializationVectorAlignmentKind = Literal[
    "fixed_bytes",
    "unsupported",
]

type ExactArrayBodyEnvelopeSlotLabel = Literal[
    "opaque_pre_branch_array_initialization",
    "opaque_pre_branch_predicate_initialization",
    "selected_body_envelope",
    "opaque_post_branch_store_call",
    "opaque_post_branch_return_emission",
]
type ExactArrayBodyEnvelopeSlot = (
    ExactArrayBodyEnvelopeOpaqueSlot | ExactArrayBodyEnvelopeSelectedSlot
)
type ExactArrayBodyStructuralRoleLabel = Literal[
    "first_slot_declaration_shell",
    "opaque_predicate_init_shaped_slot",
    "selected_body_envelope_slot",
    "opaque_post_branch_store_call_shaped_slot",
    "opaque_return_emission_shaped_slot",
]

_EXACT_ARRAY_BODY_ENVELOPE_SLOT_LABELS: tuple[
    ExactArrayBodyEnvelopeSlotLabel, ...
] = (
    "opaque_pre_branch_array_initialization",
    "opaque_pre_branch_predicate_initialization",
    "selected_body_envelope",
    "opaque_post_branch_store_call",
    "opaque_post_branch_return_emission",
)
_EXACT_ARRAY_BODY_ENVELOPE_SLOT_ORDINALS = tuple(
    range(len(_EXACT_ARRAY_BODY_ENVELOPE_SLOT_LABELS))
)
_EXACT_ARRAY_BODY_ENVELOPE_OPAQUE_SLOT_LABELS = (
    "opaque_pre_branch_array_initialization",
    "opaque_pre_branch_predicate_initialization",
    "opaque_post_branch_store_call",
    "opaque_post_branch_return_emission",
)
_EXACT_ARRAY_BODY_STRUCTURAL_ROLE_LABELS: tuple[
    ExactArrayBodyStructuralRoleLabel, ...
] = (
    "first_slot_declaration_shell",
    "opaque_predicate_init_shaped_slot",
    "selected_body_envelope_slot",
    "opaque_post_branch_store_call_shaped_slot",
    "opaque_return_emission_shaped_slot",
)


@dataclass(frozen=True, slots=True)
class ExactArrayInitializationVectorLengthValue:
    kind: ExactArrayInitializationVectorLengthKind
    lanes: int | None = None

    def __post_init__(self) -> None:
        if self.kind not in ("fixed_lanes", "runtime_lanes", "scalable_lanes"):
            raise ValueError("array-initialization vector-length kind is unsupported")
        if self.kind == "fixed_lanes":
            if isinstance(self.lanes, bool) or not isinstance(self.lanes, int):
                raise ValueError(
                    "fixed array-initialization vector length requires integer lanes"
                )
            if self.lanes <= 0:
                raise ValueError(
                    "fixed array-initialization vector length must be positive"
                )
        elif self.lanes is not None:
            raise ValueError(
                "runtime/scalable array-initialization vector length must not "
                "pretend to have fixed integer lanes"
            )

    @property
    def key(self) -> tuple[str, int | None]:
        return (self.kind, self.lanes)


@dataclass(frozen=True, slots=True)
class ExactArrayInitializationVectorLengthMetadata:
    candidate_id: str
    target_extension: str
    source_extension: str
    selected_type_tag: str
    vector_length: ExactArrayInitializationVectorLengthValue
    source_location: SourceLocation | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "candidate_id",
            "target_extension",
            "source_extension",
            "selected_type_tag",
        ):
            if not getattr(self, field_name):
                raise ValueError(
                    "array-initialization vector-length metadata "
                    f"{field_name} must be non-empty"
                )
        if not isinstance(
            self.vector_length,
            ExactArrayInitializationVectorLengthValue,
        ):
            raise TypeError(
                "array-initialization vector-length metadata requires a typed "
                "vector-length value"
            )

    @property
    def lookup_key(self) -> tuple[str, str, str, str]:
        return (
            self.candidate_id,
            self.target_extension,
            self.source_extension,
            self.selected_type_tag,
        )

    @property
    def key(self) -> tuple[object, ...]:
        location_key = (
            self.source_location.sort_key()
            if self.source_location is not None
            else ()
        )
        return (*self.lookup_key, self.vector_length.key, location_key)


@dataclass(frozen=True, slots=True)
class ExactArrayInitializationVectorAlignmentValue:
    kind: ExactArrayInitializationVectorAlignmentKind
    bytes: int | None = None
    unsupported_policy: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in ("fixed_bytes", "unsupported"):
            raise ValueError("array-initialization vector-alignment kind is unsupported")
        if self.kind == "fixed_bytes":
            if isinstance(self.bytes, bool) or not isinstance(self.bytes, int):
                raise ValueError(
                    "fixed array-initialization vector alignment requires "
                    "integer bytes"
                )
            if self.bytes <= 0:
                raise ValueError(
                    "fixed array-initialization vector alignment must be positive"
                )
            if self.unsupported_policy is not None:
                raise ValueError(
                    "fixed array-initialization vector alignment must not carry "
                    "an unsupported policy"
                )
        else:
            if self.bytes is not None:
                raise ValueError(
                    "unsupported array-initialization vector alignment must not "
                    "pretend to have fixed integer bytes"
                )
            if not self.unsupported_policy:
                raise ValueError(
                    "unsupported array-initialization vector alignment requires "
                    "an explicit policy"
                )

    @property
    def key(self) -> tuple[str, int | None, str | None]:
        return (self.kind, self.bytes, self.unsupported_policy)


@dataclass(frozen=True, slots=True)
class ExactArrayInitializationVectorAlignmentMetadata:
    candidate_id: str
    target_extension: str
    source_extension: str
    selected_type_tag: str
    vector_alignment: ExactArrayInitializationVectorAlignmentValue
    source_location: SourceLocation | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "candidate_id",
            "target_extension",
            "source_extension",
            "selected_type_tag",
        ):
            if not getattr(self, field_name):
                raise ValueError(
                    "array-initialization vector-alignment metadata "
                    f"{field_name} must be non-empty"
                )
        if not isinstance(
            self.vector_alignment,
            ExactArrayInitializationVectorAlignmentValue,
        ):
            raise TypeError(
                "array-initialization vector-alignment metadata requires a typed "
                "vector-alignment value"
            )

    @property
    def lookup_key(self) -> tuple[str, str, str, str]:
        return (
            self.candidate_id,
            self.target_extension,
            self.source_extension,
            self.selected_type_tag,
        )

    @property
    def key(self) -> tuple[object, ...]:
        location_key = (
            self.source_location.sort_key()
            if self.source_location is not None
            else ()
        )
        return (*self.lookup_key, self.vector_alignment.key, location_key)


@dataclass(frozen=True, slots=True)
class ExactArrayBodyEnvelopeSkeletonKey:
    candidate_id: str
    selected_type_tag: str
    originating_branch_chain_id: str

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise ValueError("array-body envelope skeleton key candidate id must be non-empty")
        if not self.selected_type_tag:
            raise ValueError("array-body envelope skeleton key type tag must be non-empty")
        if not self.originating_branch_chain_id:
            raise ValueError(
                "array-body envelope skeleton key branch-chain id must be non-empty"
            )

    @property
    def key(self) -> tuple[str, str, str]:
        return (
            self.candidate_id,
            self.selected_type_tag,
            self.originating_branch_chain_id,
        )


@dataclass(frozen=True, slots=True)
class ExactArrayBodyEnvelopeSkeletonRequirement:
    candidate_id: str
    selected_type_tag: str
    originating_branch_chain_id: str
    source_location: SourceLocation | None = None

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise ValueError(
                "array-body envelope skeleton requirement candidate id must be non-empty"
            )
        if not self.selected_type_tag:
            raise ValueError(
                "array-body envelope skeleton requirement type tag must be non-empty"
            )
        if not self.originating_branch_chain_id:
            raise ValueError(
                "array-body envelope skeleton requirement branch-chain id must be non-empty"
            )

    @property
    def lookup_key(self) -> ExactArrayBodyEnvelopeSkeletonKey:
        return ExactArrayBodyEnvelopeSkeletonKey(
            candidate_id=self.candidate_id,
            selected_type_tag=self.selected_type_tag,
            originating_branch_chain_id=self.originating_branch_chain_id,
        )

    @property
    def key(self) -> tuple[object, ...]:
        location_key = (
            self.source_location.sort_key()
            if self.source_location is not None
            else ()
        )
        return (*self.lookup_key.key, location_key)


@dataclass(frozen=True, slots=True)
class ExactArrayBodyEnvelopeSkeletonSlot:
    label: ExactArrayBodyEnvelopeSlotLabel
    ordinal: int
    source_location: SourceLocation
    candidate_id: str
    selected_type_tag: str
    originating_branch_chain_id: str
    opaque_source_text: str | None = None

    def __post_init__(self) -> None:
        if self.label not in _EXACT_ARRAY_BODY_ENVELOPE_SLOT_LABELS:
            raise ValueError("array-body envelope skeleton slot label is unsupported")
        if isinstance(self.ordinal, bool) or not isinstance(self.ordinal, int):
            raise ValueError("array-body envelope skeleton slot ordinal must be an int")
        if self.source_location is None:
            raise ValueError("array-body envelope skeleton slot requires source location")
        if not self.candidate_id:
            raise ValueError("array-body envelope skeleton slot candidate id must be non-empty")
        if not self.selected_type_tag:
            raise ValueError("array-body envelope skeleton slot type tag must be non-empty")
        if not self.originating_branch_chain_id:
            raise ValueError(
                "array-body envelope skeleton slot branch-chain id must be non-empty"
            )
        if (
            self.label in _EXACT_ARRAY_BODY_ENVELOPE_OPAQUE_SLOT_LABELS
            and not (self.opaque_source_text or "").strip()
        ):
            raise ValueError(
                "array-body envelope opaque skeleton slots require source text"
            )
        if self.label == "selected_body_envelope" and self.opaque_source_text is not None:
            raise ValueError(
                "array-body envelope selected skeleton slot must not carry body text"
            )

    @property
    def key(self) -> tuple[object, ...]:
        return (
            "exact_array_body_envelope_skeleton_slot",
            self.label,
            self.ordinal,
            self.source_location.sort_key(),
            self.candidate_id,
            self.selected_type_tag,
            self.originating_branch_chain_id,
            self.opaque_source_text or "",
        )


@dataclass(frozen=True, slots=True)
class ExactArrayBodyEnvelopeSkeleton:
    candidate_id: str
    selected_type_tag: str
    source_location: SourceLocation
    originating_branch_chain_id: str
    slots: tuple[ExactArrayBodyEnvelopeSkeletonSlot, ...]
    is_exact_array_body_shape: bool = True

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise ValueError("array-body envelope skeleton candidate id must be non-empty")
        if not self.selected_type_tag:
            raise ValueError("array-body envelope skeleton type tag must be non-empty")
        if self.source_location is None:
            raise ValueError("array-body envelope skeleton requires source location")
        if not self.originating_branch_chain_id:
            raise ValueError(
                "array-body envelope skeleton branch-chain id must be non-empty"
            )
        object.__setattr__(self, "slots", tuple(self.slots))

    @property
    def key(self) -> tuple[object, ...]:
        return (
            "exact_array_body_envelope_skeleton",
            self.candidate_id,
            self.selected_type_tag,
            self.source_location.sort_key(),
            self.originating_branch_chain_id,
            tuple(slot.key for slot in self.slots),
            self.is_exact_array_body_shape,
        )


@dataclass(frozen=True, slots=True)
class ExactArrayBodyEnvelopeOpaqueSlot:
    label: ExactArrayBodyEnvelopeSlotLabel
    ordinal: int
    opaque_source_text: str
    source_location: SourceLocation
    candidate_id: str
    selected_type_tag: str
    originating_branch_chain_id: str

    def __post_init__(self) -> None:
        if self.label not in _EXACT_ARRAY_BODY_ENVELOPE_OPAQUE_SLOT_LABELS:
            raise ValueError("array-body envelope opaque slot label is unsupported")
        if self.ordinal not in _EXACT_ARRAY_BODY_ENVELOPE_SLOT_ORDINALS:
            raise ValueError("array-body envelope slot ordinal is unsupported")
        if not self.opaque_source_text.strip():
            raise ValueError("array-body envelope opaque slot text must be non-empty")
        if self.source_location is None:
            raise ValueError("array-body envelope opaque slot requires source location")
        if not self.candidate_id:
            raise ValueError("array-body envelope opaque slot candidate id must be non-empty")
        if not self.selected_type_tag:
            raise ValueError("array-body envelope opaque slot type tag must be non-empty")
        if not self.originating_branch_chain_id:
            raise ValueError(
                "array-body envelope opaque slot branch-chain id must be non-empty"
            )

    @property
    def key(self) -> tuple[object, ...]:
        return (
            "exact_array_body_envelope_opaque_slot",
            self.label,
            self.ordinal,
            self.opaque_source_text,
            self.source_location.sort_key(),
            self.candidate_id,
            self.selected_type_tag,
            self.originating_branch_chain_id,
        )


@dataclass(frozen=True, slots=True)
class ExactArrayBodyEnvelopeSelectedSlot:
    label: Literal["selected_body_envelope"]
    ordinal: int
    selected_body_envelope: GenerationSelectedBodyEnvelopeIr
    source_location: SourceLocation
    candidate_id: str
    selected_type_tag: str
    originating_branch_chain_id: str

    def __post_init__(self) -> None:
        if self.label != "selected_body_envelope":
            raise ValueError(
                "array-body envelope selected slot label must be selected_body_envelope"
            )
        if self.ordinal not in _EXACT_ARRAY_BODY_ENVELOPE_SLOT_ORDINALS:
            raise ValueError("array-body envelope selected slot ordinal is unsupported")
        if not _is_generation_selected_body_envelope(
            self.selected_body_envelope,
        ):
            raise TypeError("array-body envelope selected slot requires M63 envelope")
        if self.source_location is None:
            raise ValueError("array-body envelope selected slot requires source location")
        if (
            self.candidate_id != self.selected_body_envelope.candidate_id
            or self.selected_type_tag
            != self.selected_body_envelope.selected_type_tag
            or self.originating_branch_chain_id
            != self.selected_body_envelope.originating_branch_chain_id
        ):
            raise ValueError(
                "array-body envelope selected slot provenance must match M63 envelope"
            )

    @property
    def key(self) -> tuple[object, ...]:
        return (
            "exact_array_body_envelope_selected_slot",
            self.label,
            self.ordinal,
            self.selected_body_envelope.key,
            self.source_location.sort_key(),
            self.candidate_id,
            self.selected_type_tag,
            self.originating_branch_chain_id,
        )


@dataclass(frozen=True, slots=True)
class ExactArrayBodyEnvelopeIr:
    candidate_id: str
    selected_type_tag: str
    source_location: SourceLocation
    originating_branch_chain_id: str
    slots: tuple[ExactArrayBodyEnvelopeSlot, ...]

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise ValueError("array-body envelope candidate id must be non-empty")
        if not self.selected_type_tag:
            raise ValueError("array-body envelope type tag must be non-empty")
        if self.source_location is None:
            raise ValueError("array-body envelope requires source location")
        if not self.originating_branch_chain_id:
            raise ValueError("array-body envelope branch-chain id must be non-empty")
        object.__setattr__(self, "slots", tuple(self.slots))
        if tuple(slot.label for slot in self.slots) != _EXACT_ARRAY_BODY_ENVELOPE_SLOT_LABELS:
            raise ValueError("array-body envelope slots must use the exact M64 order")
        if tuple(slot.ordinal for slot in self.slots) != _EXACT_ARRAY_BODY_ENVELOPE_SLOT_ORDINALS:
            raise ValueError("array-body envelope slot ordinals must be exact")
        for slot in self.slots:
            if (
                slot.candidate_id != self.candidate_id
                or slot.selected_type_tag != self.selected_type_tag
                or slot.originating_branch_chain_id
                != self.originating_branch_chain_id
            ):
                raise ValueError(
                    "array-body envelope slot provenance must match envelope"
                )

    @property
    def selected_body_slot(self) -> ExactArrayBodyEnvelopeSelectedSlot:
        slot = self.slots[2]
        if not isinstance(slot, ExactArrayBodyEnvelopeSelectedSlot):
            raise AssertionError("M64 selected-body slot invariant was violated")
        return slot

    @property
    def key(self) -> tuple[object, ...]:
        return (
            "exact_array_body_envelope_ir",
            self.candidate_id,
            self.selected_type_tag,
            self.source_location.sort_key(),
            self.originating_branch_chain_id,
            tuple(slot.key for slot in self.slots),
        )


@dataclass(frozen=True, slots=True)
class ExactArrayInitializationUnresolvedLeaf:
    kind: ExactArrayInitializationHelperLeafKind
    source_text: str
    source_location: SourceLocation

    def __post_init__(self) -> None:
        expected_text = _EXACT_ARRAY_INITIALIZATION_HELPER_TEXT_BY_KIND.get(self.kind)
        if expected_text is None:
            raise ValueError("array-initialization helper leaf kind is unsupported")
        if self.source_text != expected_text:
            raise ValueError(
                "array-initialization helper leaf text must match its exact kind"
            )
        if self.source_location is None:
            raise ValueError(
                "array-initialization helper leaf requires source location"
            )

    @property
    def key(self) -> tuple[object, ...]:
        return (
            "exact_array_initialization_unresolved_leaf",
            self.kind,
            self.source_text,
            self.source_location.sort_key(),
        )


@dataclass(frozen=True, slots=True)
class ExactArrayInitializationSlotFormIr:
    source_envelope: ExactArrayBodyEnvelopeIr
    slot_label: Literal["opaque_pre_branch_array_initialization"]
    slot_ordinal: int
    source_location: SourceLocation
    candidate_id: str
    selected_type_tag: str
    originating_branch_chain_id: str
    original_slot_text: str
    variable_token: str
    variable_token_location: SourceLocation
    base_type_leaf: ExactArrayInitializationUnresolvedLeaf
    vector_length_leaf: ExactArrayInitializationUnresolvedLeaf
    vector_alignment_leaf: ExactArrayInitializationUnresolvedLeaf
    backend_uninit_leaf: ExactArrayInitializationUnresolvedLeaf

    def __post_init__(self) -> None:
        if not isinstance(self.source_envelope, ExactArrayBodyEnvelopeIr):
            raise TypeError(
                "array-initialization slot form requires an M65 array-body envelope"
            )
        if self.slot_label != "opaque_pre_branch_array_initialization":
            raise ValueError(
                "array-initialization slot form label must be "
                "opaque_pre_branch_array_initialization"
            )
        if self.slot_ordinal != 0:
            raise ValueError("array-initialization slot form ordinal must be 0")
        if self.source_location is None:
            raise ValueError("array-initialization slot form requires source location")
        if not self.candidate_id:
            raise ValueError(
                "array-initialization slot form candidate id must be non-empty"
            )
        if not self.selected_type_tag:
            raise ValueError(
                "array-initialization slot form type tag must be non-empty"
            )
        if not self.originating_branch_chain_id:
            raise ValueError(
                "array-initialization slot form branch-chain id must be non-empty"
            )
        if (
            self.candidate_id != self.source_envelope.candidate_id
            or self.selected_type_tag != self.source_envelope.selected_type_tag
            or self.originating_branch_chain_id
            != self.source_envelope.originating_branch_chain_id
        ):
            raise ValueError(
                "array-initialization slot form provenance must match its M65 envelope"
            )
        if not self.original_slot_text.strip():
            raise ValueError("array-initialization slot form text must be non-empty")
        if self.variable_token != "tmp":
            raise ValueError("array-initialization slot form variable token must be tmp")
        if self.variable_token_location is None:
            raise ValueError(
                "array-initialization slot form variable token requires source location"
            )

    @property
    def key(self) -> tuple[object, ...]:
        return (
            "exact_array_initialization_slot_form_ir",
            self.source_envelope.key,
            self.slot_label,
            self.slot_ordinal,
            self.source_location.sort_key(),
            self.candidate_id,
            self.selected_type_tag,
            self.originating_branch_chain_id,
            self.original_slot_text,
            self.variable_token,
            self.variable_token_location.sort_key(),
            self.base_type_leaf.key,
            self.vector_length_leaf.key,
            self.vector_alignment_leaf.key,
            self.backend_uninit_leaf.key,
        )


@dataclass(frozen=True, slots=True)
class ExactArrayInitializationHelperRequestRecord:
    source_form: ExactArrayInitializationSlotFormIr
    source_envelope: ExactArrayBodyEnvelopeIr
    request_ordinal: int
    request_kind: ExactArrayInitializationHelperRequestKind
    helper_leaf_kind: ExactArrayInitializationHelperLeafKind
    leaf_source_text: str
    leaf_source_location: SourceLocation
    candidate_id: str
    selected_type_tag: str
    originating_branch_chain_id: str
    slot_label: Literal["opaque_pre_branch_array_initialization"]
    slot_ordinal: int
    variable_token: str

    def __post_init__(self) -> None:
        if not isinstance(self.source_form, ExactArrayInitializationSlotFormIr):
            raise TypeError(
                "array-initialization helper request requires an M66 slot form"
            )
        if not isinstance(self.source_envelope, ExactArrayBodyEnvelopeIr):
            raise TypeError(
                "array-initialization helper request requires an M65 envelope"
            )
        if self.source_envelope != self.source_form.source_envelope:
            raise ValueError(
                "array-initialization helper request envelope must match "
                "the M66 slot form envelope"
            )
        if self.request_ordinal not in range(
            len(_EXACT_ARRAY_INITIALIZATION_HELPER_LEAF_SPECS)
        ):
            raise ValueError(
                "array-initialization helper request ordinal is unsupported"
            )
        if self.request_kind not in (
            "generation_type",
            "generation_value",
            "backend_value",
        ):
            raise ValueError("array-initialization helper request kind is unsupported")
        expected_text = _EXACT_ARRAY_INITIALIZATION_HELPER_TEXT_BY_KIND.get(
            self.helper_leaf_kind,
        )
        if expected_text is None or self.leaf_source_text != expected_text:
            raise ValueError(
                "array-initialization helper request source text must match "
                "its unresolved M66 leaf kind"
            )
        if self.leaf_source_location is None:
            raise ValueError(
                "array-initialization helper request requires leaf source location"
            )
        if (
            self.candidate_id != self.source_form.candidate_id
            or self.selected_type_tag != self.source_form.selected_type_tag
            or self.originating_branch_chain_id
            != self.source_form.originating_branch_chain_id
        ):
            raise ValueError(
                "array-initialization helper request provenance must match "
                "the M66 slot form"
            )
        if self.slot_label != self.source_form.slot_label:
            raise ValueError(
                "array-initialization helper request slot label must match "
                "the M66 slot form"
            )
        if self.slot_ordinal != self.source_form.slot_ordinal:
            raise ValueError(
                "array-initialization helper request slot ordinal must match "
                "the M66 slot form"
            )
        if self.variable_token != self.source_form.variable_token:
            raise ValueError(
                "array-initialization helper request variable token must match "
                "the M66 slot form"
            )

    @property
    def key(self) -> tuple[object, ...]:
        return (
            "exact_array_initialization_helper_request_record",
            self.source_form.key,
            self.source_envelope.key,
            self.request_ordinal,
            self.request_kind,
            self.helper_leaf_kind,
            self.leaf_source_text,
            self.leaf_source_location.sort_key(),
            self.candidate_id,
            self.selected_type_tag,
            self.originating_branch_chain_id,
            self.slot_label,
            self.slot_ordinal,
            self.variable_token,
        )


@dataclass(frozen=True, slots=True)
class ExactArrayInitializationHelperRequestIr:
    source_form: ExactArrayInitializationSlotFormIr
    source_envelope: ExactArrayBodyEnvelopeIr
    source_location: SourceLocation
    candidate_id: str
    selected_type_tag: str
    originating_branch_chain_id: str
    slot_label: Literal["opaque_pre_branch_array_initialization"]
    slot_ordinal: int
    variable_token: str
    requests: tuple[ExactArrayInitializationHelperRequestRecord, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.source_form, ExactArrayInitializationSlotFormIr):
            raise TypeError(
                "array-initialization helper request IR requires an M66 slot form"
            )
        if not isinstance(self.source_envelope, ExactArrayBodyEnvelopeIr):
            raise TypeError(
                "array-initialization helper request IR requires an M65 envelope"
            )
        if self.source_envelope != self.source_form.source_envelope:
            raise ValueError(
                "array-initialization helper request IR envelope must match "
                "the M66 slot form envelope"
            )
        if self.source_location != self.source_form.source_location:
            raise ValueError(
                "array-initialization helper request IR source location must "
                "match the M66 slot form"
            )
        if (
            self.candidate_id != self.source_form.candidate_id
            or self.selected_type_tag != self.source_form.selected_type_tag
            or self.originating_branch_chain_id
            != self.source_form.originating_branch_chain_id
        ):
            raise ValueError(
                "array-initialization helper request IR provenance must match "
                "the M66 slot form"
            )
        if self.slot_label != self.source_form.slot_label:
            raise ValueError(
                "array-initialization helper request IR slot label must match "
                "the M66 slot form"
            )
        if self.slot_ordinal != self.source_form.slot_ordinal:
            raise ValueError(
                "array-initialization helper request IR slot ordinal must "
                "match the M66 slot form"
            )
        if self.variable_token != self.source_form.variable_token:
            raise ValueError(
                "array-initialization helper request IR variable token must "
                "match the M66 slot form"
            )
        object.__setattr__(self, "requests", tuple(self.requests))
        expected = tuple(
            (spec.request_ordinal, spec.expected_leaf_kind)
            for spec in _EXACT_ARRAY_INITIALIZATION_HELPER_LEAF_SPECS
        )
        actual = tuple(
            (request.request_ordinal, request.helper_leaf_kind)
            for request in self.requests
        )
        if actual != expected:
            raise ValueError(
                "array-initialization helper request IR must contain exactly "
                "the four M66 helper leaves in deterministic order"
            )
        for request in self.requests:
            if request.source_form != self.source_form:
                raise ValueError(
                    "array-initialization helper request record must match "
                    "the M66 source form"
                )

    @property
    def key(self) -> tuple[object, ...]:
        return (
            "exact_array_initialization_helper_request_ir",
            self.source_form.key,
            self.source_envelope.key,
            self.source_location.sort_key(),
            self.candidate_id,
            self.selected_type_tag,
            self.originating_branch_chain_id,
            self.slot_label,
            self.slot_ordinal,
            self.variable_token,
            tuple(request.key for request in self.requests),
        )


@dataclass(frozen=True, slots=True)
class ExactArrayInitializationBaseTypeResolutionIr:
    source_request_ir: ExactArrayInitializationHelperRequestIr
    source_base_type_request: ExactArrayInitializationHelperRequestRecord
    resolved_type_ref: GenerationTypeRef
    unresolved_requests: tuple[ExactArrayInitializationHelperRequestRecord, ...]
    source_location: SourceLocation
    candidate_id: str
    selected_type_tag: str
    originating_branch_chain_id: str
    slot_label: Literal["opaque_pre_branch_array_initialization"]
    slot_ordinal: int
    variable_token: str

    def __post_init__(self) -> None:
        if not isinstance(self.source_request_ir, ExactArrayInitializationHelperRequestIr):
            raise TypeError(
                "array-initialization base-type resolution requires an M67 "
                "helper-request IR"
            )
        if not isinstance(
            self.source_base_type_request,
            ExactArrayInitializationHelperRequestRecord,
        ):
            raise TypeError(
                "array-initialization base-type resolution requires an M67 "
                "base-type request record"
            )
        if self.source_base_type_request not in self.source_request_ir.requests:
            raise ValueError(
                "array-initialization base-type source request must come from "
                "the M67 helper-request IR"
            )
        if self.resolved_type_ref.kind != "base.in":
            raise ValueError(
                "array-initialization base-type resolution must resolve "
                "GenerationTypeRef(kind='base.in')"
            )
        if self.resolved_type_ref.type_tag != self.selected_type_tag:
            raise ValueError(
                "array-initialization base-type resolution type tag must match "
                "the M67 selected type tag"
            )
        if self.source_location != self.source_request_ir.source_location:
            raise ValueError(
                "array-initialization base-type resolution source location "
                "must match the M67 helper-request IR"
            )
        if (
            self.candidate_id != self.source_request_ir.candidate_id
            or self.selected_type_tag != self.source_request_ir.selected_type_tag
            or self.originating_branch_chain_id
            != self.source_request_ir.originating_branch_chain_id
        ):
            raise ValueError(
                "array-initialization base-type resolution provenance must "
                "match the M67 helper-request IR"
            )
        if self.slot_label != self.source_request_ir.slot_label:
            raise ValueError(
                "array-initialization base-type resolution slot label must "
                "match the M67 helper-request IR"
            )
        if self.slot_ordinal != self.source_request_ir.slot_ordinal:
            raise ValueError(
                "array-initialization base-type resolution slot ordinal must "
                "match the M67 helper-request IR"
            )
        if self.variable_token != self.source_request_ir.variable_token:
            raise ValueError(
                "array-initialization base-type resolution variable token must "
                "match the M67 helper-request IR"
            )
        object.__setattr__(self, "unresolved_requests", tuple(self.unresolved_requests))
        expected_unresolved = tuple(
            request
            for request in self.source_request_ir.requests
            if request is not self.source_base_type_request
        )
        if self.unresolved_requests != expected_unresolved:
            raise ValueError(
                "array-initialization base-type resolution must preserve all "
                "non-base M67 requests as unresolved records in deterministic order"
            )
        for request in self.unresolved_requests:
            if request.helper_leaf_kind == "type_generation_base_in":
                raise ValueError(
                    "array-initialization base-type resolution unresolved "
                    "requests must not include the resolved base-type request"
                )

    @property
    def key(self) -> tuple[object, ...]:
        return (
            "exact_array_initialization_base_type_resolution_ir",
            self.source_request_ir.key,
            self.source_base_type_request.key,
            self.resolved_type_ref.key,
            tuple(request.key for request in self.unresolved_requests),
            self.source_location.sort_key(),
            self.candidate_id,
            self.selected_type_tag,
            self.originating_branch_chain_id,
            self.slot_label,
            self.slot_ordinal,
            self.variable_token,
        )


@dataclass(frozen=True, slots=True)
class ExactArrayInitializationVectorLengthResolutionIr:
    source_base_type_resolution: ExactArrayInitializationBaseTypeResolutionIr
    source_vector_length_request: ExactArrayInitializationHelperRequestRecord
    resolved_vector_length: ExactArrayInitializationVectorLengthValue
    unresolved_requests: tuple[ExactArrayInitializationHelperRequestRecord, ...]
    source_location: SourceLocation
    candidate_id: str
    target_extension: str
    source_extension: str
    selected_type_tag: str
    originating_branch_chain_id: str
    slot_label: Literal["opaque_pre_branch_array_initialization"]
    slot_ordinal: int
    variable_token: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.source_base_type_resolution,
            ExactArrayInitializationBaseTypeResolutionIr,
        ):
            raise TypeError(
                "array-initialization vector-length resolution requires an M68 "
                "base-type resolution"
            )
        if not isinstance(
            self.source_vector_length_request,
            ExactArrayInitializationHelperRequestRecord,
        ):
            raise TypeError(
                "array-initialization vector-length resolution requires an M67 "
                "vector-length request record"
            )
        if self.source_vector_length_request not in (
            self.source_base_type_resolution.unresolved_requests
        ):
            raise ValueError(
                "array-initialization vector-length source request must come "
                "from the M68 unresolved request records"
            )
        if self.source_vector_length_request.helper_leaf_kind != (
            "value_generation_vector_length"
        ):
            raise ValueError(
                "array-initialization vector-length resolution must resolve "
                "the M67 value<generation>(vector::length) request"
            )
        if not isinstance(
            self.resolved_vector_length,
            ExactArrayInitializationVectorLengthValue,
        ):
            raise TypeError(
                "array-initialization vector-length resolution requires a "
                "typed vector-length value"
            )
        if self.source_location != self.source_base_type_resolution.source_location:
            raise ValueError(
                "array-initialization vector-length resolution source location "
                "must match the M68 base-type resolution"
            )
        if (
            self.candidate_id != self.source_base_type_resolution.candidate_id
            or self.selected_type_tag
            != self.source_base_type_resolution.selected_type_tag
            or self.originating_branch_chain_id
            != self.source_base_type_resolution.originating_branch_chain_id
        ):
            raise ValueError(
                "array-initialization vector-length resolution provenance must "
                "match the M68 base-type resolution"
            )
        if not self.target_extension or not self.source_extension:
            raise ValueError(
                "array-initialization vector-length resolution requires typed "
                "target/source extension context"
            )
        if self.slot_label != self.source_base_type_resolution.slot_label:
            raise ValueError(
                "array-initialization vector-length resolution slot label must "
                "match the M68 base-type resolution"
            )
        if self.slot_ordinal != self.source_base_type_resolution.slot_ordinal:
            raise ValueError(
                "array-initialization vector-length resolution slot ordinal "
                "must match the M68 base-type resolution"
            )
        if self.variable_token != self.source_base_type_resolution.variable_token:
            raise ValueError(
                "array-initialization vector-length resolution variable token "
                "must match the M68 base-type resolution"
            )
        object.__setattr__(self, "unresolved_requests", tuple(self.unresolved_requests))
        expected_unresolved = tuple(
            request
            for request in self.source_base_type_resolution.unresolved_requests
            if request is not self.source_vector_length_request
        )
        if self.unresolved_requests != expected_unresolved:
            raise ValueError(
                "array-initialization vector-length resolution must preserve "
                "only vector-alignment and backend-uninit requests as "
                "unresolved records in deterministic order"
            )
        for request in self.unresolved_requests:
            if request.helper_leaf_kind == "value_generation_vector_length":
                raise ValueError(
                    "array-initialization vector-length resolution unresolved "
                    "requests must not include the resolved vector-length request"
                )

    @property
    def key(self) -> tuple[object, ...]:
        return (
            "exact_array_initialization_vector_length_resolution_ir",
            self.source_base_type_resolution.key,
            self.source_vector_length_request.key,
            self.resolved_vector_length.key,
            tuple(request.key for request in self.unresolved_requests),
            self.source_location.sort_key(),
            self.candidate_id,
            self.target_extension,
            self.source_extension,
            self.selected_type_tag,
            self.originating_branch_chain_id,
            self.slot_label,
            self.slot_ordinal,
            self.variable_token,
        )


@dataclass(frozen=True, slots=True)
class ExactArrayInitializationVectorAlignmentResolutionIr:
    source_vector_length_resolution: ExactArrayInitializationVectorLengthResolutionIr
    source_vector_alignment_request: ExactArrayInitializationHelperRequestRecord
    resolved_vector_alignment: ExactArrayInitializationVectorAlignmentValue
    unresolved_requests: tuple[ExactArrayInitializationHelperRequestRecord, ...]
    source_location: SourceLocation
    candidate_id: str
    target_extension: str
    source_extension: str
    selected_type_tag: str
    originating_branch_chain_id: str
    slot_label: Literal["opaque_pre_branch_array_initialization"]
    slot_ordinal: int
    variable_token: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.source_vector_length_resolution,
            ExactArrayInitializationVectorLengthResolutionIr,
        ):
            raise TypeError(
                "array-initialization vector-alignment resolution requires an "
                "M70 vector-length resolution"
            )
        if not isinstance(
            self.source_vector_alignment_request,
            ExactArrayInitializationHelperRequestRecord,
        ):
            raise TypeError(
                "array-initialization vector-alignment resolution requires an "
                "M67 vector-alignment request record"
            )
        if self.source_vector_alignment_request not in (
            self.source_vector_length_resolution.unresolved_requests
        ):
            raise ValueError(
                "array-initialization vector-alignment source request must come "
                "from the M70 unresolved request records"
            )
        if self.source_vector_alignment_request.helper_leaf_kind != (
            "value_generation_vector_alignment"
        ):
            raise ValueError(
                "array-initialization vector-alignment resolution must resolve "
                "the M67 value<generation>(vector::alignment) request"
            )
        if not isinstance(
            self.resolved_vector_alignment,
            ExactArrayInitializationVectorAlignmentValue,
        ):
            raise TypeError(
                "array-initialization vector-alignment resolution requires a "
                "typed vector-alignment value"
            )
        if self.resolved_vector_alignment.kind == "unsupported":
            raise ValueError(
                "array-initialization vector-alignment resolution must not turn "
                "unsupported alignment metadata into a resolved alignment value"
            )
        if self.source_location != self.source_vector_length_resolution.source_location:
            raise ValueError(
                "array-initialization vector-alignment resolution source "
                "location must match the M70 vector-length resolution"
            )
        if (
            self.candidate_id != self.source_vector_length_resolution.candidate_id
            or self.selected_type_tag
            != self.source_vector_length_resolution.selected_type_tag
            or self.originating_branch_chain_id
            != self.source_vector_length_resolution.originating_branch_chain_id
        ):
            raise ValueError(
                "array-initialization vector-alignment resolution provenance "
                "must match the M70 vector-length resolution"
            )
        if (
            self.target_extension
            != self.source_vector_length_resolution.target_extension
            or self.source_extension
            != self.source_vector_length_resolution.source_extension
        ):
            raise ValueError(
                "array-initialization vector-alignment resolution extension "
                "context must match the M70 vector-length resolution"
            )
        if self.slot_label != self.source_vector_length_resolution.slot_label:
            raise ValueError(
                "array-initialization vector-alignment resolution slot label "
                "must match the M70 vector-length resolution"
            )
        if self.slot_ordinal != self.source_vector_length_resolution.slot_ordinal:
            raise ValueError(
                "array-initialization vector-alignment resolution slot ordinal "
                "must match the M70 vector-length resolution"
            )
        if self.variable_token != self.source_vector_length_resolution.variable_token:
            raise ValueError(
                "array-initialization vector-alignment resolution variable "
                "token must match the M70 vector-length resolution"
            )
        object.__setattr__(self, "unresolved_requests", tuple(self.unresolved_requests))
        expected_unresolved = tuple(
            request
            for request in self.source_vector_length_resolution.unresolved_requests
            if request is not self.source_vector_alignment_request
        )
        if self.unresolved_requests != expected_unresolved:
            raise ValueError(
                "array-initialization vector-alignment resolution must preserve "
                "only backend-uninit requests as unresolved records in "
                "deterministic order"
            )
        for request in self.unresolved_requests:
            if request.helper_leaf_kind == "value_generation_vector_alignment":
                raise ValueError(
                    "array-initialization vector-alignment resolution unresolved "
                    "requests must not include the resolved vector-alignment "
                    "request"
                )

    @property
    def key(self) -> tuple[object, ...]:
        return (
            "exact_array_initialization_vector_alignment_resolution_ir",
            self.source_vector_length_resolution.key,
            self.source_vector_alignment_request.key,
            self.resolved_vector_alignment.key,
            tuple(request.key for request in self.unresolved_requests),
            self.source_location.sort_key(),
            self.candidate_id,
            self.target_extension,
            self.source_extension,
            self.selected_type_tag,
            self.originating_branch_chain_id,
            self.slot_label,
            self.slot_ordinal,
            self.variable_token,
        )


@dataclass(frozen=True, slots=True)
class ExactArrayInitializationDeferredBackendUninitValue:
    source_backend_uninit_request: ExactArrayInitializationHelperRequestRecord
    policy: Literal["deferred_backend_value"]
    source_location: SourceLocation
    candidate_id: str
    target_extension: str
    source_extension: str
    selected_type_tag: str
    originating_branch_chain_id: str
    slot_label: Literal["opaque_pre_branch_array_initialization"]
    slot_ordinal: int
    variable_token: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.source_backend_uninit_request,
            ExactArrayInitializationHelperRequestRecord,
        ):
            raise TypeError(
                "array-initialization backend-uninit boundary requires an "
                "M67 helper-request record"
            )
        if self.policy != "deferred_backend_value":
            raise ValueError(
                "array-initialization backend-uninit boundary must remain a "
                "deferred backend-value policy"
            )
        request = self.source_backend_uninit_request
        if (
            request.request_ordinal != 3
            or request.request_kind != "backend_value"
            or request.helper_leaf_kind != "value_backend_uninit_array"
        ):
            raise ValueError(
                "array-initialization backend-uninit boundary requires the "
                "M67 request with ordinal 3, kind 'backend_value', and leaf "
                "kind 'value_backend_uninit_array'"
            )
        if (
            request.leaf_source_text
            != _EXACT_ARRAY_INITIALIZATION_HELPER_TEXT_BY_KIND[
                "value_backend_uninit_array"
            ]
        ):
            raise ValueError(
                "array-initialization backend-uninit boundary preserves only "
                "the exact M67 source text as provenance"
            )
        if self.source_location != request.leaf_source_location:
            raise ValueError(
                "array-initialization backend-uninit boundary source location "
                "must match the source M67 request"
            )
        if (
            self.candidate_id != request.candidate_id
            or self.selected_type_tag != request.selected_type_tag
            or self.originating_branch_chain_id
            != request.originating_branch_chain_id
            or self.slot_label != request.slot_label
            or self.slot_ordinal != request.slot_ordinal
            or self.variable_token != request.variable_token
        ):
            raise ValueError(
                "array-initialization backend-uninit boundary provenance must "
                "match the source M67 request"
            )
        if not self.target_extension or not self.source_extension:
            raise ValueError(
                "array-initialization backend-uninit boundary requires typed "
                "target/source extension provenance"
            )

    @property
    def key(self) -> tuple[object, ...]:
        return (
            "exact_array_initialization_deferred_backend_uninit_value",
            self.source_backend_uninit_request.key,
            self.policy,
            self.source_location.sort_key(),
            self.candidate_id,
            self.target_extension,
            self.source_extension,
            self.selected_type_tag,
            self.originating_branch_chain_id,
            self.slot_label,
            self.slot_ordinal,
            self.variable_token,
        )


@dataclass(frozen=True, slots=True)
class ExactArrayInitializationHelperSetCompletionIr:
    source_vector_alignment_resolution: ExactArrayInitializationVectorAlignmentResolutionIr
    source_vector_length_resolution: ExactArrayInitializationVectorLengthResolutionIr
    source_base_type_resolution: ExactArrayInitializationBaseTypeResolutionIr
    source_backend_uninit_request: ExactArrayInitializationHelperRequestRecord
    unresolved_backend_uninit: ExactArrayInitializationDeferredBackendUninitValue
    source_location: SourceLocation
    candidate_id: str
    target_extension: str
    source_extension: str
    selected_type_tag: str
    originating_branch_chain_id: str
    slot_label: Literal["opaque_pre_branch_array_initialization"]
    slot_ordinal: int
    variable_token: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.source_vector_alignment_resolution,
            ExactArrayInitializationVectorAlignmentResolutionIr,
        ):
            raise TypeError(
                "array-initialization helper-set completion requires an M71 "
                "vector-alignment resolution"
            )
        if (
            self.source_vector_length_resolution
            is not self.source_vector_alignment_resolution.source_vector_length_resolution
        ):
            raise ValueError(
                "array-initialization helper-set completion must carry the "
                "accepted M70 vector-length resolution from M71"
            )
        if (
            self.source_base_type_resolution
            is not self.source_vector_length_resolution.source_base_type_resolution
        ):
            raise ValueError(
                "array-initialization helper-set completion must carry the "
                "accepted M68 base-type resolution from M70"
            )
        if self.source_backend_uninit_request not in (
            self.source_vector_alignment_resolution.unresolved_requests
        ):
            raise ValueError(
                "array-initialization helper-set completion source "
                "backend-uninit request must come from the M71 unresolved "
                "request records"
            )
        if (
            self.unresolved_backend_uninit.source_backend_uninit_request
            is not self.source_backend_uninit_request
        ):
            raise ValueError(
                "array-initialization helper-set completion backend-uninit "
                "boundary must reference the selected M67 backend-uninit request"
            )
        if (
            self.source_location
            != self.source_vector_alignment_resolution.source_location
        ):
            raise ValueError(
                "array-initialization helper-set completion source location "
                "must match the M71 vector-alignment resolution"
            )
        if (
            self.candidate_id
            != self.source_vector_alignment_resolution.candidate_id
            or self.target_extension
            != self.source_vector_alignment_resolution.target_extension
            or self.source_extension
            != self.source_vector_alignment_resolution.source_extension
            or self.selected_type_tag
            != self.source_vector_alignment_resolution.selected_type_tag
            or self.originating_branch_chain_id
            != self.source_vector_alignment_resolution.originating_branch_chain_id
            or self.slot_label
            != self.source_vector_alignment_resolution.slot_label
            or self.slot_ordinal
            != self.source_vector_alignment_resolution.slot_ordinal
            or self.variable_token
            != self.source_vector_alignment_resolution.variable_token
        ):
            raise ValueError(
                "array-initialization helper-set completion provenance must "
                "match the M71 vector-alignment resolution"
            )
        if (
            self.unresolved_backend_uninit.candidate_id != self.candidate_id
            or self.unresolved_backend_uninit.target_extension
            != self.target_extension
            or self.unresolved_backend_uninit.source_extension
            != self.source_extension
            or self.unresolved_backend_uninit.selected_type_tag
            != self.selected_type_tag
            or self.unresolved_backend_uninit.originating_branch_chain_id
            != self.originating_branch_chain_id
            or self.unresolved_backend_uninit.slot_label != self.slot_label
            or self.unresolved_backend_uninit.slot_ordinal != self.slot_ordinal
            or self.unresolved_backend_uninit.variable_token != self.variable_token
        ):
            raise ValueError(
                "array-initialization helper-set completion backend-uninit "
                "boundary provenance must match the completed helper set"
            )

    @property
    def key(self) -> tuple[object, ...]:
        return (
            "exact_array_initialization_helper_set_completion_ir",
            self.source_vector_alignment_resolution.key,
            self.source_vector_length_resolution.key,
            self.source_base_type_resolution.key,
            self.source_backend_uninit_request.key,
            self.unresolved_backend_uninit.key,
            self.source_location.sort_key(),
            self.candidate_id,
            self.target_extension,
            self.source_extension,
            self.selected_type_tag,
            self.originating_branch_chain_id,
            self.slot_label,
            self.slot_ordinal,
            self.variable_token,
        )


@dataclass(frozen=True, slots=True)
class ExactArrayInitializationDeclarationShellIr:
    source_helper_set_completion: ExactArrayInitializationHelperSetCompletionIr
    source_slot_form: ExactArrayInitializationSlotFormIr
    source_envelope: ExactArrayBodyEnvelopeIr
    declaration_kind: Literal["var<typed>"]
    array_type_kind: Literal["array_type"]
    base_type_ref: GenerationTypeRef
    vector_length: ExactArrayInitializationVectorLengthValue
    vector_alignment: ExactArrayInitializationVectorAlignmentValue
    unresolved_backend_uninit: ExactArrayInitializationDeferredBackendUninitValue
    source_location: SourceLocation
    candidate_id: str
    target_extension: str
    source_extension: str
    selected_type_tag: str
    originating_branch_chain_id: str
    slot_label: Literal["opaque_pre_branch_array_initialization"]
    slot_ordinal: int
    variable_token: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.source_helper_set_completion,
            ExactArrayInitializationHelperSetCompletionIr,
        ):
            raise TypeError(
                "array-initialization declaration-shell IR requires an M72 "
                "helper-set completion"
            )
        if not isinstance(self.source_slot_form, ExactArrayInitializationSlotFormIr):
            raise TypeError(
                "array-initialization declaration-shell IR requires the "
                "reachable M66 slot form"
            )
        if not isinstance(self.source_envelope, ExactArrayBodyEnvelopeIr):
            raise TypeError(
                "array-initialization declaration-shell IR requires the "
                "reachable M65 array-body envelope"
            )
        completion = self.source_helper_set_completion
        source_request_ir = completion.source_base_type_resolution.source_request_ir
        if self.source_slot_form is not source_request_ir.source_form:
            raise ValueError(
                "array-initialization declaration-shell IR source slot form "
                "must be the M66 form reachable through the M72 helper set"
            )
        if self.source_envelope is not self.source_slot_form.source_envelope:
            raise ValueError(
                "array-initialization declaration-shell IR source envelope "
                "must be the M65 envelope reachable through the M66 slot form"
            )
        if self.declaration_kind != "var<typed>":
            raise ValueError(
                "array-initialization declaration-shell IR supports only the "
                "exact var<typed> declaration shell"
            )
        if self.array_type_kind != "array_type":
            raise ValueError(
                "array-initialization declaration-shell IR supports only the "
                "exact array_type shell"
            )
        if self.base_type_ref is not completion.source_base_type_resolution.resolved_type_ref:
            raise ValueError(
                "array-initialization declaration-shell IR must carry the "
                "accepted M68 base-type fact"
            )
        if self.base_type_ref.kind != "base.in":
            raise ValueError(
                "array-initialization declaration-shell IR base type must be "
                "the accepted M68 base.in type ref"
            )
        if (
            self.vector_length
            is not completion.source_vector_length_resolution.resolved_vector_length
        ):
            raise ValueError(
                "array-initialization declaration-shell IR must carry the "
                "accepted M70 vector-length fact"
            )
        if (
            self.vector_alignment
            is not completion.source_vector_alignment_resolution.resolved_vector_alignment
        ):
            raise ValueError(
                "array-initialization declaration-shell IR must carry the "
                "accepted M71 vector-alignment fact"
            )
        if (
            self.unresolved_backend_uninit
            is not completion.unresolved_backend_uninit
        ):
            raise ValueError(
                "array-initialization declaration-shell IR must preserve the "
                "accepted M72 deferred backend-uninit boundary"
            )
        if self.unresolved_backend_uninit.policy != "deferred_backend_value":
            raise ValueError(
                "array-initialization declaration-shell IR backend uninit "
                "must remain a deferred backend-value policy"
            )
        if self.source_location != completion.source_location:
            raise ValueError(
                "array-initialization declaration-shell IR source location "
                "must match the M72 helper-set completion"
            )
        if (
            self.candidate_id != completion.candidate_id
            or self.target_extension != completion.target_extension
            or self.source_extension != completion.source_extension
            or self.selected_type_tag != completion.selected_type_tag
            or self.originating_branch_chain_id
            != completion.originating_branch_chain_id
            or self.slot_label != completion.slot_label
            or self.slot_ordinal != completion.slot_ordinal
            or self.variable_token != completion.variable_token
        ):
            raise ValueError(
                "array-initialization declaration-shell IR provenance must "
                "match the M72 helper-set completion"
            )
        if (
            self.slot_label != "opaque_pre_branch_array_initialization"
            or self.slot_ordinal != 0
            or self.variable_token != "tmp"
        ):
            raise ValueError(
                "array-initialization declaration-shell IR supports only the "
                "exact first-slot tmp declaration shell"
            )

    @property
    def key(self) -> tuple[object, ...]:
        return (
            "exact_array_initialization_declaration_shell_ir",
            self.source_helper_set_completion.key,
            self.source_slot_form.key,
            self.source_envelope.key,
            self.declaration_kind,
            self.array_type_kind,
            self.base_type_ref.key,
            self.vector_length.key,
            self.vector_alignment.key,
            self.unresolved_backend_uninit.key,
            self.source_location.sort_key(),
            self.candidate_id,
            self.target_extension,
            self.source_extension,
            self.selected_type_tag,
            self.originating_branch_chain_id,
            self.slot_label,
            self.slot_ordinal,
            self.variable_token,
        )


@dataclass(frozen=True, slots=True)
class _ExactArrayBodyStructuralRole:
    role_label: ExactArrayBodyStructuralRoleLabel
    role_ordinal: int
    envelope_slot: ExactArrayBodyEnvelopeSlot
    source_location: SourceLocation
    candidate_id: str
    target_extension: str | None
    source_extension: str | None
    selected_type_tag: str
    originating_branch_chain_id: str
    declaration_shell: ExactArrayInitializationDeclarationShellIr | None = None
    selected_body_envelope: GenerationSelectedBodyEnvelopeIr | None = None
    opaque_source_text: str | None = None

    def __post_init__(self) -> None:
        if self.role_label not in _EXACT_ARRAY_BODY_STRUCTURAL_ROLE_LABELS:
            raise ValueError("array-body structural role label is unsupported")
        if self.role_ordinal not in _EXACT_ARRAY_BODY_ENVELOPE_SLOT_ORDINALS:
            raise ValueError("array-body structural role ordinal is unsupported")
        if self.source_location is None:
            raise ValueError("array-body structural role requires source location")
        if not self.candidate_id:
            raise ValueError("array-body structural role candidate id must be non-empty")
        if not self.selected_type_tag:
            raise ValueError("array-body structural role type tag must be non-empty")
        if not self.originating_branch_chain_id:
            raise ValueError(
                "array-body structural role branch-chain id must be non-empty"
            )
        if (
            self.envelope_slot.ordinal != self.role_ordinal
            or self.envelope_slot.candidate_id != self.candidate_id
            or self.envelope_slot.selected_type_tag != self.selected_type_tag
            or self.envelope_slot.originating_branch_chain_id
            != self.originating_branch_chain_id
        ):
            raise ValueError(
                "array-body structural role provenance must match its M65 slot"
            )
        if self.role_ordinal == 0:
            if not isinstance(self.declaration_shell, ExactArrayInitializationDeclarationShellIr):
                raise ValueError(
                    "first structural role requires the accepted M73 declaration shell"
                )
            if self.declaration_shell.slot_ordinal != 0:
                raise ValueError(
                    "first structural role may attach the M73 declaration shell "
                    "only to slot ordinal 0"
                )
            if self.selected_body_envelope is not None or self.opaque_source_text is not None:
                raise ValueError(
                    "first structural role must not carry selected-body or opaque "
                    "non-first evidence"
                )
        elif self.role_ordinal == 2:
            if not isinstance(self.envelope_slot, ExactArrayBodyEnvelopeSelectedSlot):
                raise ValueError(
                    "selected-body structural role requires the M65 selected-body slot"
                )
            if self.selected_body_envelope is not self.envelope_slot.selected_body_envelope:
                raise ValueError(
                    "selected-body structural role must preserve the nested M63 envelope"
                )
            if self.declaration_shell is not None or self.opaque_source_text is not None:
                raise ValueError(
                    "selected-body structural role must not carry declaration or "
                    "opaque source text"
                )
        else:
            if not isinstance(self.envelope_slot, ExactArrayBodyEnvelopeOpaqueSlot):
                raise ValueError(
                    "opaque structural roles require opaque M65 envelope slots"
                )
            if self.opaque_source_text != self.envelope_slot.opaque_source_text:
                raise ValueError(
                    "opaque structural roles must preserve M65 opaque source text"
                )
            if self.declaration_shell is not None or self.selected_body_envelope is not None:
                raise ValueError(
                    "opaque structural roles must not carry declaration-shell or "
                    "selected-body envelope links"
                )

    @property
    def key(self) -> tuple[object, ...]:
        location_key = self.source_location.sort_key()
        declaration_key = (
            self.declaration_shell.key if self.declaration_shell is not None else ()
        )
        selected_key = (
            self.selected_body_envelope.key
            if self.selected_body_envelope is not None
            else ()
        )
        return (
            "exact_array_body_structural_role",
            self.role_label,
            self.role_ordinal,
            self.envelope_slot.key,
            location_key,
            self.candidate_id,
            self.target_extension or "",
            self.source_extension or "",
            self.selected_type_tag,
            self.originating_branch_chain_id,
            declaration_key,
            selected_key,
            self.opaque_source_text or "",
        )


@dataclass(frozen=True, slots=True)
class ExactArrayBodyStructuralSequenceIr:
    source_envelope: ExactArrayBodyEnvelopeIr
    declaration_shell: ExactArrayInitializationDeclarationShellIr
    roles: tuple[_ExactArrayBodyStructuralRole, ...]
    source_location: SourceLocation
    candidate_id: str
    target_extension: str
    source_extension: str
    selected_type_tag: str
    originating_branch_chain_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.source_envelope, ExactArrayBodyEnvelopeIr):
            raise TypeError(
                "array-body structural sequence requires an M65 array-body envelope"
            )
        if not isinstance(
            self.declaration_shell,
            ExactArrayInitializationDeclarationShellIr,
        ):
            raise TypeError(
                "array-body structural sequence requires an M73 declaration shell"
            )
        object.__setattr__(self, "roles", tuple(self.roles))
        if self.source_location is None:
            raise ValueError("array-body structural sequence requires source location")
        if (
            self.candidate_id != self.source_envelope.candidate_id
            or self.candidate_id != self.declaration_shell.candidate_id
            or self.selected_type_tag != self.source_envelope.selected_type_tag
            or self.selected_type_tag != self.declaration_shell.selected_type_tag
            or self.originating_branch_chain_id
            != self.source_envelope.originating_branch_chain_id
            or self.originating_branch_chain_id
            != self.declaration_shell.originating_branch_chain_id
        ):
            raise ValueError(
                "array-body structural sequence provenance must match the "
                "accepted M65 envelope and M73 declaration shell"
            )
        if (
            self.target_extension != self.declaration_shell.target_extension
            or self.source_extension != self.declaration_shell.source_extension
        ):
            raise ValueError(
                "array-body structural sequence extension provenance must "
                "match the accepted M73 declaration shell"
            )
        if self.declaration_shell.source_envelope is not self.source_envelope:
            raise ValueError(
                "array-body structural sequence declaration shell must reference "
                "the same accepted M65 envelope"
            )
        if tuple(role.role_label for role in self.roles) != (
            _EXACT_ARRAY_BODY_STRUCTURAL_ROLE_LABELS
        ):
            raise ValueError(
                "array-body structural sequence roles must use the exact M74 order"
            )
        if tuple(role.role_ordinal for role in self.roles) != (
            _EXACT_ARRAY_BODY_ENVELOPE_SLOT_ORDINALS
        ):
            raise ValueError(
                "array-body structural sequence role ordinals must be exact"
            )
        if tuple(role.envelope_slot for role in self.roles) != self.source_envelope.slots:
            raise ValueError(
                "array-body structural sequence roles must preserve source slot order"
            )
        if self.roles[0].declaration_shell is not self.declaration_shell:
            raise ValueError(
                "array-body structural sequence must attach the M73 declaration "
                "shell only to role ordinal 0"
            )
        for role in self.roles[1:]:
            if role.declaration_shell is not None:
                raise ValueError(
                    "array-body structural sequence must not attach the M73 "
                    "declaration shell to nonzero slots"
                )
        if (
            self.roles[2].selected_body_envelope
            is not self.source_envelope.selected_body_slot.selected_body_envelope
        ):
            raise ValueError(
                "array-body structural sequence must preserve the M63 selected/no-body "
                "envelope only in the selected-body slot"
            )

    @property
    def key(self) -> tuple[object, ...]:
        return (
            "exact_array_body_structural_sequence_ir",
            self.source_envelope.key,
            self.declaration_shell.key,
            tuple(role.key for role in self.roles),
            self.source_location.sort_key(),
            self.candidate_id,
            self.target_extension,
            self.source_extension,
            self.selected_type_tag,
            self.originating_branch_chain_id,
        )


@dataclass(frozen=True, slots=True)
class ExactPredicatePathStructuralRequestIr:
    source_sequence: ExactArrayBodyStructuralSequenceIr
    predicate_init_role_label: Literal["opaque_predicate_init_shaped_slot"]
    predicate_init_slot_ordinal: Literal[1]
    predicate_init_source_location: SourceLocation
    predicate_type_token_text: str
    predicate_token_text: str
    predicate_init_direct_intrinsic_token_text: str
    selected_update_state: ExactPredicatePathSelectedUpdateState
    selected_body_envelope: GenerationSelectedBodyEnvelopeIr
    selected_update_slot_ordinal: Literal[2]
    selected_update_source_location: SourceLocation
    selected_update_assignment_target_text: str | None = None
    selected_update_direct_intrinsic_token_text: str | None = None
    store_call_role_label: Literal["opaque_post_branch_store_call_shaped_slot"] = (
        "opaque_post_branch_store_call_shaped_slot"
    )
    store_call_slot_ordinal: Literal[3] = 3
    store_call_source_location: SourceLocation | None = None
    store_call_predicate_argument_text: str = ""
    candidate_id: str = ""
    target_extension: str = ""
    source_extension: str = ""
    selected_type_tag: str = ""
    originating_branch_chain_id: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.source_sequence, ExactArrayBodyStructuralSequenceIr):
            raise TypeError(
                "predicate-path structural request requires an M74 sequence"
            )
        if self.predicate_init_role_label != "opaque_predicate_init_shaped_slot":
            raise ValueError(
                "predicate-path structural request requires the M74 predicate-init role"
            )
        if self.predicate_init_slot_ordinal != 1:
            raise ValueError(
                "predicate-path structural request predicate-init ordinal must be 1"
            )
        if self.predicate_init_source_location is None:
            raise ValueError(
                "predicate-path structural request requires predicate-init location"
            )
        for field_name in (
            "predicate_type_token_text",
            "predicate_token_text",
            "predicate_init_direct_intrinsic_token_text",
        ):
            if not getattr(self, field_name):
                raise ValueError(
                    f"predicate-path structural request {field_name} must be non-empty"
                )
        if self.selected_update_state not in (
            "accepted_selected_update",
            "accepted_no_update",
        ):
            raise ValueError(
                "predicate-path structural request selected update state is unsupported"
            )
        if not _is_generation_selected_body_envelope(
            self.selected_body_envelope,
        ):
            raise TypeError(
                "predicate-path structural request requires the accepted M63 envelope"
            )
        if self.selected_update_slot_ordinal != 2:
            raise ValueError(
                "predicate-path structural request selected update ordinal must be 2"
            )
        if self.selected_update_source_location is None:
            raise ValueError(
                "predicate-path structural request requires selected-update location"
            )
        if self.selected_update_state == "accepted_selected_update":
            if not _is_selected_body_envelope(self.selected_body_envelope):
                raise ValueError(
                    "selected predicate update state requires a selected-body envelope"
                )
            if not self.selected_update_assignment_target_text:
                raise ValueError(
                    "selected predicate update state requires an assignment target"
                )
            if not self.selected_update_direct_intrinsic_token_text:
                raise ValueError(
                    "selected predicate update state requires a direct-intrinsic token"
                )
        else:
            if not _is_no_selected_body_envelope(self.selected_body_envelope):
                raise ValueError(
                    "no-update predicate state requires a no-selected-body envelope"
                )
            if (
                self.selected_update_assignment_target_text is not None
                or self.selected_update_direct_intrinsic_token_text is not None
            ):
                raise ValueError(
                    "no-update predicate state must not synthesize update tokens"
                )
        if self.store_call_role_label != "opaque_post_branch_store_call_shaped_slot":
            raise ValueError(
                "predicate-path structural request requires the M74 store-call role"
            )
        if self.store_call_slot_ordinal != 3:
            raise ValueError(
                "predicate-path structural request store-call ordinal must be 3"
            )
        if self.store_call_source_location is None:
            raise ValueError(
                "predicate-path structural request requires store-call location"
            )
        if not self.store_call_predicate_argument_text:
            raise ValueError(
                "predicate-path structural request requires a store predicate token"
            )
        for field_name in (
            "candidate_id",
            "target_extension",
            "source_extension",
            "selected_type_tag",
            "originating_branch_chain_id",
        ):
            if not getattr(self, field_name):
                raise ValueError(
                    f"predicate-path structural request {field_name} must be non-empty"
                )
        if (
            self.candidate_id != self.source_sequence.candidate_id
            or self.target_extension != self.source_sequence.target_extension
            or self.source_extension != self.source_sequence.source_extension
            or self.selected_type_tag != self.source_sequence.selected_type_tag
            or self.originating_branch_chain_id
            != self.source_sequence.originating_branch_chain_id
        ):
            raise ValueError(
                "predicate-path structural request provenance must match M74 sequence"
            )
        if self.selected_body_envelope is not self.source_sequence.roles[
            2
        ].selected_body_envelope:
            raise ValueError(
                "predicate-path structural request must preserve the M74 selected-body "
                "envelope identity"
            )
        if (
            self.selected_body_envelope.candidate_id != self.candidate_id
            or self.selected_body_envelope.selected_type_tag != self.selected_type_tag
            or self.selected_body_envelope.originating_branch_chain_id
            != self.originating_branch_chain_id
        ):
            raise ValueError(
                "predicate-path structural request selected-body provenance "
                "must match M74"
            )

    @property
    def key(self) -> tuple[object, ...]:
        store_call_source_location = self.store_call_source_location
        if store_call_source_location is None:
            raise AssertionError(
                "predicate-path structural request store-call location "
                "was not validated"
            )
        return (
            "exact_predicate_path_structural_request_ir",
            self.source_sequence.key,
            self.predicate_init_role_label,
            self.predicate_init_slot_ordinal,
            self.predicate_init_source_location.sort_key(),
            self.predicate_type_token_text,
            self.predicate_token_text,
            self.predicate_init_direct_intrinsic_token_text,
            self.selected_update_state,
            self.selected_body_envelope.key,
            self.selected_update_slot_ordinal,
            self.selected_update_source_location.sort_key(),
            self.selected_update_assignment_target_text or "",
            self.selected_update_direct_intrinsic_token_text or "",
            self.store_call_role_label,
            self.store_call_slot_ordinal,
            store_call_source_location.sort_key(),
            self.store_call_predicate_argument_text,
            self.candidate_id,
            self.target_extension,
            self.source_extension,
            self.selected_type_tag,
            self.originating_branch_chain_id,
        )

    @property
    def source_location(self) -> SourceLocation:
        return self.source_sequence.source_location


@dataclass(frozen=True, slots=True)
class ExactPostBranchIntrinsicCallSiteStructuralRequestIr:
    source_predicate_path: ExactPredicatePathStructuralRequestIr
    source_sequence: ExactArrayBodyStructuralSequenceIr
    post_branch_role_label: Literal["opaque_post_branch_store_call_shaped_slot"]
    post_branch_slot_ordinal: Literal[3]
    post_branch_source_location: SourceLocation
    original_call_source_text: str
    call_head_token_text: str
    unresolved_intrinsic_token_text: str
    predicate_argument_ordinal: Literal[0]
    predicate_argument_token_text: str
    predicate_argument_source_slot_ordinal: Literal[3]
    predicate_argument_source_token_text: str
    member_access_argument_ordinal: Literal[1]
    member_access_argument_text: str
    member_access_base_token_text: str
    member_access_member_token_text: str
    member_access_source_variable_token_text: str
    source_operand_argument_ordinal: Literal[2]
    source_operand_argument_token_text: str
    candidate_id: str
    target_extension: str
    source_extension: str
    selected_type_tag: str
    originating_branch_chain_id: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.source_predicate_path,
            ExactPredicatePathStructuralRequestIr,
        ):
            raise TypeError(
                "post-branch intrinsic call-site request requires an M75 "
                "predicate-path request"
            )
        if self.source_sequence is not self.source_predicate_path.source_sequence:
            raise ValueError(
                "post-branch intrinsic call-site request must preserve the M74 "
                "sequence carried by M75"
            )
        if self.post_branch_role_label != "opaque_post_branch_store_call_shaped_slot":
            raise ValueError(
                "post-branch intrinsic call-site request requires the M74 "
                "post-branch store-call-shaped role"
            )
        if self.post_branch_slot_ordinal != 3:
            raise ValueError(
                "post-branch intrinsic call-site request slot ordinal must be 3"
            )
        if self.post_branch_source_location is None:
            raise ValueError(
                "post-branch intrinsic call-site request requires a source location"
            )
        if not self.original_call_source_text.strip():
            raise ValueError(
                "post-branch intrinsic call-site request requires source text"
            )
        if (
            self.call_head_token_text
            != _exact_shapes.EXACT_POST_BRANCH_CALL_HEAD_TOKEN
        ):
            raise ValueError(
                "post-branch intrinsic call-site request records only the exact "
                "structural call-head token intrin"
            )
        if (
            self.unresolved_intrinsic_token_text
            != _exact_shapes.EXACT_POST_BRANCH_INTRINSIC_TOKEN
        ):
            raise ValueError(
                "post-branch intrinsic call-site request records only the exact "
                "unresolved intrinsic token svst1"
            )
        if self.predicate_argument_ordinal != 0:
            raise ValueError(
                "post-branch intrinsic call-site predicate argument ordinal must be 0"
            )
        if self.predicate_argument_source_slot_ordinal != (
            self.source_predicate_path.store_call_slot_ordinal
        ):
            raise ValueError(
                "post-branch intrinsic call-site predicate argument source slot "
                "must be the M75 slot-3 predicate-token use"
            )
        if (
            self.predicate_argument_token_text
            != self.source_predicate_path.store_call_predicate_argument_text
            or self.predicate_argument_source_token_text
            != self.source_predicate_path.store_call_predicate_argument_text
        ):
            raise ValueError(
                "post-branch intrinsic call-site predicate argument must link "
                "to the accepted M75 slot-3 predicate-token use"
            )
        if self.member_access_argument_ordinal != 1:
            raise ValueError(
                "post-branch intrinsic call-site member-access argument ordinal "
                "must be 1"
            )
        if (
            self.member_access_argument_text
            != _exact_shapes.EXACT_POST_BRANCH_MEMBER_ACCESS_TEXT
            or self.member_access_base_token_text
            != _exact_shapes.EXACT_POST_BRANCH_MEMBER_ACCESS_BASE_TOKEN
            or self.member_access_member_token_text
            != _exact_shapes.EXACT_POST_BRANCH_MEMBER_ACCESS_MEMBER_TOKEN
        ):
            raise ValueError(
                "post-branch intrinsic call-site member-access-shaped argument "
                "must remain the exact structural token/path tmp.data()"
            )
        if (
            self.member_access_source_variable_token_text
            != self.source_sequence.declaration_shell.variable_token
            or self.member_access_base_token_text
            != self.source_sequence.declaration_shell.variable_token
        ):
            raise ValueError(
                "post-branch intrinsic call-site tmp.data() argument must link "
                "only to the structural tmp provenance carried through M73/M74/M75"
            )
        if self.source_operand_argument_ordinal != 2:
            raise ValueError(
                "post-branch intrinsic call-site source-operand argument ordinal "
                "must be 2"
            )
        if (
            self.source_operand_argument_token_text
            != _exact_shapes.EXACT_POST_BRANCH_SOURCE_OPERAND_TOKEN
        ):
            raise ValueError(
                "post-branch intrinsic call-site records only the exact structural "
                "source operand token a"
            )
        store_location = self.source_predicate_path.store_call_source_location
        if store_location is None:
            raise ValueError(
                "post-branch intrinsic call-site request requires the M75 "
                "store-call source location"
            )
        if (
            self.post_branch_slot_ordinal
            != self.source_predicate_path.store_call_slot_ordinal
            or self.post_branch_role_label
            != self.source_predicate_path.store_call_role_label
            or self.post_branch_source_location != store_location
        ):
            raise ValueError(
                "post-branch intrinsic call-site slot identity must match the "
                "accepted M75 store-call predicate-token use"
            )
        if len(self.source_sequence.roles) <= 3:
            raise ValueError(
                "post-branch intrinsic call-site request requires M74 role "
                "ordinal 3 provenance"
            )
        post_branch_role = self.source_sequence.roles[3]
        if (
            post_branch_role.role_label != self.post_branch_role_label
            or post_branch_role.role_ordinal != self.post_branch_slot_ordinal
            or post_branch_role.source_location != self.post_branch_source_location
            or post_branch_role.opaque_source_text != self.original_call_source_text
        ):
            raise ValueError(
                "post-branch intrinsic call-site source text and slot provenance "
                "must match the accepted M74 role carried by M75"
            )
        for field_name in (
            "candidate_id",
            "target_extension",
            "source_extension",
            "selected_type_tag",
            "originating_branch_chain_id",
        ):
            if not getattr(self, field_name):
                raise ValueError(
                    f"post-branch intrinsic call-site request {field_name} "
                    "must be non-empty"
                )
        if (
            self.candidate_id != self.source_predicate_path.candidate_id
            or self.target_extension != self.source_predicate_path.target_extension
            or self.source_extension != self.source_predicate_path.source_extension
            or self.selected_type_tag != self.source_predicate_path.selected_type_tag
            or self.originating_branch_chain_id
            != self.source_predicate_path.originating_branch_chain_id
        ):
            raise ValueError(
                "post-branch intrinsic call-site request provenance must match M75"
            )
        if (
            self.candidate_id != self.source_sequence.candidate_id
            or self.target_extension != self.source_sequence.target_extension
            or self.source_extension != self.source_sequence.source_extension
            or self.selected_type_tag != self.source_sequence.selected_type_tag
            or self.originating_branch_chain_id
            != self.source_sequence.originating_branch_chain_id
        ):
            raise ValueError(
                "post-branch intrinsic call-site request provenance must match M74"
            )

    @property
    def key(self) -> tuple[object, ...]:
        return (
            "exact_post_branch_intrinsic_call_site_structural_request_ir",
            self.source_predicate_path.key,
            self.source_sequence.key,
            self.post_branch_role_label,
            self.post_branch_slot_ordinal,
            self.post_branch_source_location.sort_key(),
            self.original_call_source_text,
            self.call_head_token_text,
            self.unresolved_intrinsic_token_text,
            self.predicate_argument_ordinal,
            self.predicate_argument_token_text,
            self.predicate_argument_source_slot_ordinal,
            self.predicate_argument_source_token_text,
            self.member_access_argument_ordinal,
            self.member_access_argument_text,
            self.member_access_base_token_text,
            self.member_access_member_token_text,
            self.member_access_source_variable_token_text,
            self.source_operand_argument_ordinal,
            self.source_operand_argument_token_text,
            self.candidate_id,
            self.target_extension,
            self.source_extension,
            self.selected_type_tag,
            self.originating_branch_chain_id,
        )

    @property
    def source_location(self) -> SourceLocation:
        return self.post_branch_source_location
