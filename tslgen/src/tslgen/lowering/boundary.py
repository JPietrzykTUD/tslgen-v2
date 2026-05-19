from __future__ import annotations

from dataclasses import dataclass, field, replace
import re
from typing import Literal

from tslgen.analysis.candidates import CandidateSelection, ImplementationCandidate
from tslgen.core.diagnostics import Diagnostic, SourceLocation, has_errors, sort_diagnostics
from tslgen.core.frozen_map import FrozenMap
from tslgen.core.result import Result
from tslgen.domain.catalog import Catalog
from tslgen.domain.generation_rules import (
    ConcreteIntegerGenerationRuleSet,
    ScalarSizeBytesGenerationRuleSet,
    build_concrete_integer_generation_rule_set_from_catalog,
    build_scalar_size_bytes_generation_rule_set_from_catalog,
    classify_concrete_integer_generation_type_tag,
    classify_scalar_size_bytes_generation_type_tag,
    default_concrete_integer_generation_rule_set,
    default_scalar_size_bytes_generation_rule_set,
    is_non_integer_generation_type_tag,
)
from tslgen.domain.values import CatalogValue


type LoweringStrategy = Literal["mini_tsil", "typed_opaque"]
type PayloadClassification = Literal[
    "tsil",
    "intrinsic",
    "backend_specific",
    "opaque",
]
type LoweringStatus = Literal["lowered", "unsupported"]
type GenerationBranchChoice = Literal["true", "false"]
type GenerationElseSyntax = Literal["else<generation>", "else"]
type GenerationTypeRefKind = Literal[
    "base.in",
    "base.signed_of",
    "base.unsigned_of",
]
type GenerationValueKind = Literal["type.size_bytes", "type.size_bits"]
type GenerationPredicateKind = Literal["type.size_bytes.equals"]
type GenerationRecognitionKind = Literal[
    "generation.value",
    "generation.predicate",
    "generation.control_flow",
]
type GenerationLoweringStageName = Literal[
    "helper_expression_recognition",
    "typed_generation_value",
    "typed_generation_predicate",
    "generation_control_flow_pruning",
    "selected_body_lowering",
    "selected_body_form_recognition",
    "selected_body_ir_lowering",
    "selected_body_envelope_lowering",
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
]
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
type TsilBinaryOperator = Literal["+"]
type TsilExpression = (
    TsilParameterReference | TsilBinaryExpression | TsilIntrinsicComposeExpression
)
type TsilStatement = TsilReturnStatement
type GenerationLoweringStageOutput = (
    GenerationExpressionRecognition
    | GenerationValue
    | GenerationPredicate
    | PrunedGenerationBranch
    | GenerationSizeByteBranchChainPruning
    | OpaqueSelectedBranchBodyHandoff
    | NoSelectedBranchBodyHandoff
    | SelectedBranchBodyAssignmentFormRecognition
    | NoSelectedBranchBodyAssignmentFormRecognition
    | SelectedAssignmentDirectIntrinsicBodyIr
    | NoSelectedAssignmentDirectIntrinsicBodyIr
    | SelectedBodyEnvelopeIr
    | NoSelectedBodyEnvelopeIr
    | ExactArrayBodyEnvelopeIr
    | ExactArrayInitializationSlotFormIr
    | ExactArrayInitializationHelperRequestIr
    | ExactArrayInitializationBaseTypeResolutionIr
    | ExactArrayInitializationVectorLengthResolutionIr
    | ExactArrayInitializationVectorAlignmentResolutionIr
    | ExactArrayInitializationHelperSetCompletionIr
    | ExactArrayInitializationDeclarationShellIr
    | ExactArrayBodyStructuralSequenceIr
    | ExactPredicatePathStructuralRequestIr
    | TsilStatement
)

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

_GENERATION_CONDITION_MARKER = "if<generation>"
_GENERATION_HELPER_MARKERS = (
    "if<generation>",
    "type<generation>",
    "value<generation>",
)
_GENERATION_TYPE_MARKER = "type<generation>"
_GENERATION_VALUE_MARKER = "value<generation>"
_TSIL_IDENTIFIER = r"[A-Za-z_][A-Za-z0-9_]*"
_TSIL_IDENTIFIER_RE = re.compile(rf"\A{_TSIL_IDENTIFIER}\Z")
_PRIMITIVE_ATTRIBUTE_CONDITION_RE = re.compile(
    rf"\A\s*value<generation>\(\s*primitive::attribute\(\s*"
    rf"({_TSIL_IDENTIFIER})\s*\)\s*\)\s*\Z"
)
_DIRECT_PARAMETER_ADD_RETURN_RE = re.compile(
    rf"\A\s*emit_return\(\s*({_TSIL_IDENTIFIER})\s*\+\s*"
    rf"({_TSIL_IDENTIFIER})\s*\)\s*;\s*\Z"
)
_INTRIN_COMPOSE_RETURN_RE = re.compile(
    rf"\A\s*emit_return\(\s*intrin_compose\s*<\s*({_TSIL_IDENTIFIER})\s*>\s*"
    r"\(([^()]*)\)\s*\)\s*;\s*\Z"
)
_INTRIN_COMPOSE_MARKER_RE = re.compile(r"\bintrin_compose\s*<")
_EMIT_RETURN_HEAD_RE = re.compile(r"\A\s*emit_return\s*\(")
_SELECTED_BODY_ASSIGNMENT_TARGET = "pg"
_SELECTED_BODY_ASSIGNMENT_DIRECT_INTRINSIC_TOKENS = (
    "svptrue_b16",
    "svptrue_b32",
    "svptrue_b64",
)
_SELECTED_BODY_ASSIGNMENT_RHS_RE = re.compile(
    rf"\Aintrin\s*<\s*({_TSIL_IDENTIFIER})\s*>\s*\(\s*\)\Z"
)
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
_ARRAY_INITIALIZATION_HELPER_TARGET = rf"{_TSIL_IDENTIFIER}::{_TSIL_IDENTIFIER}"
_ARRAY_INITIALIZATION_HELPER_SHAPE = (
    rf"(?:type|value)<(?:generation|backend)>\("
    rf"{_ARRAY_INITIALIZATION_HELPER_TARGET}\)"
)
_EXACT_ARRAY_INITIALIZATION_SLOT_RE = re.compile(
    r"\A[ \t]*var<typed>\("
    r"array_type<"
    r"(?P<base_type>type<generation>\(base::in\))"
    r",[ \t]*"
    r"(?P<vector_length>value<generation>\(vector::length\))"
    r",[ \t]*"
    r"(?P<vector_alignment>value<generation>\(vector::alignment\))"
    r">,[ \t]*(?P<variable>tmp),[ \t]*"
    r"(?P<backend_uninit>value<backend>\(uninit::array\))"
    r"\)[ \t]*\Z"
)
_EXACT_PREDICATE_INIT_SLOT_RE = re.compile(
    rf"\A\s*(?P<predicate_type>{_TSIL_IDENTIFIER})\s+"
    rf"(?P<predicate_token>{_TSIL_IDENTIFIER})\s*=\s*"
    rf"intrin\s*<\s*(?P<direct_intrinsic_token>{_TSIL_IDENTIFIER})\s*>\s*"
    r"\(\s*\)\s*;\s*\Z"
)
_EXACT_POST_BRANCH_STORE_PREDICATE_SLOT_RE = re.compile(
    rf"\A\s*intrin\s*<\s*(?P<call_token>{_TSIL_IDENTIFIER})\s*>\s*"
    rf"\(\s*(?P<predicate_token>{_TSIL_IDENTIFIER})\s*,\s*"
    r"tmp\.data\(\)\s*,\s*a\s*\)\s*;\s*\Z"
)
_ARRAY_INITIALIZATION_SLOT_HELPER_SHAPE_RE = re.compile(
    r"\A[ \t]*var<typed>\("
    rf"array_type<(?P<base_type>{_ARRAY_INITIALIZATION_HELPER_SHAPE})"
    r",[ \t]*"
    rf"(?P<vector_length>{_ARRAY_INITIALIZATION_HELPER_SHAPE})"
    r",[ \t]*"
    rf"(?P<vector_alignment>{_ARRAY_INITIALIZATION_HELPER_SHAPE})"
    r">,[ \t]*tmp,[ \t]*"
    rf"(?P<backend_uninit>{_ARRAY_INITIALIZATION_HELPER_SHAPE})"
    r"\)[ \t]*\Z"
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
class GenerationContext:
    values: FrozenMap[str, CatalogValue] = field(default_factory=FrozenMap.empty)
    primitive_attributes: FrozenMap[str, CatalogValue] | None = None
    use_candidate_attributes: bool = True
    selected_primitive_name: str | None = None
    emitted_primitive_name: str | None = None
    selected_candidate_id: str | None = None
    normalized_signature: str | None = None
    parameters: tuple[str, ...] = ()
    selected_type_tag: str | None = None
    type_tag_override: str | None = None
    use_candidate_type_tag: bool = True
    concrete_integer_generation_rules: ConcreteIntegerGenerationRuleSet = field(
        default_factory=default_concrete_integer_generation_rule_set
    )
    scalar_size_bytes_generation_rules: ScalarSizeBytesGenerationRuleSet = field(
        default_factory=default_scalar_size_bytes_generation_rule_set
    )
    array_initialization_vector_length_metadata: tuple[
        ExactArrayInitializationVectorLengthMetadata, ...
    ] = ()
    array_initialization_vector_alignment_metadata: tuple[
        ExactArrayInitializationVectorAlignmentMetadata, ...
    ] = ()
    implementation_source_location: SourceLocation | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", FrozenMap(self.values.items()))
        if self.primitive_attributes is not None:
            object.__setattr__(
                self,
                "primitive_attributes",
                FrozenMap(self.primitive_attributes.items()),
            )
        object.__setattr__(self, "parameters", tuple(self.parameters))
        object.__setattr__(
            self,
            "array_initialization_vector_length_metadata",
            tuple(
                sorted(
                    self.array_initialization_vector_length_metadata,
                    key=lambda metadata: metadata.key,
                )
            ),
        )
        object.__setattr__(
            self,
            "array_initialization_vector_alignment_metadata",
            tuple(
                sorted(
                    self.array_initialization_vector_alignment_metadata,
                    key=lambda metadata: metadata.key,
                )
            ),
        )
        for field_name in (
            "selected_primitive_name",
            "emitted_primitive_name",
            "selected_candidate_id",
            "normalized_signature",
            "selected_type_tag",
            "type_tag_override",
        ):
            value = getattr(self, field_name)
            if value == "":
                raise ValueError(f"generation context {field_name} must be non-empty")
        for parameter in self.parameters:
            if not parameter:
                raise ValueError("generation context parameters must be non-empty")


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
class LoweringRequest:
    strategy: LoweringStrategy = "mini_tsil"
    backend_id: str | None = None
    generation_context: GenerationContext = field(default_factory=GenerationContext)
    array_body_envelope_skeletons: tuple[ExactArrayBodyEnvelopeSkeleton, ...] = ()
    required_array_body_envelope_skeletons: tuple[
        ExactArrayBodyEnvelopeSkeletonRequirement, ...
    ] = ()

    def __post_init__(self) -> None:
        if self.strategy not in ("mini_tsil", "typed_opaque"):
            raise ValueError(f"unknown lowering strategy: {self.strategy!r}")
        if self.backend_id is not None and not self.backend_id:
            raise ValueError("lowering backend id must be non-empty when provided")
        object.__setattr__(
            self,
            "array_body_envelope_skeletons",
            tuple(
                sorted(
                    self.array_body_envelope_skeletons,
                    key=lambda skeleton: (
                        _array_body_envelope_skeleton_lookup_key(skeleton).key,
                        skeleton.key,
                    ),
                )
            ),
        )
        object.__setattr__(
            self,
            "required_array_body_envelope_skeletons",
            tuple(
                sorted(
                    self.required_array_body_envelope_skeletons,
                    key=lambda requirement: requirement.key,
                )
            ),
        )


@dataclass(frozen=True, slots=True)
class ClassifiedPayload:
    body_kind: str
    classification: PayloadClassification
    raw_payload: CatalogValue
    text: str | None = None
    has_generation_condition: bool = False

    def __post_init__(self) -> None:
        if not self.body_kind:
            raise ValueError("classified payload body kind must be non-empty")

    @property
    def key(self) -> tuple[object, ...]:
        return (
            self.classification,
            self.body_kind,
            self.text or "",
            self.has_generation_condition,
        )


@dataclass(frozen=True, slots=True)
class LoweringInput:
    candidate: ImplementationCandidate
    payload: ClassifiedPayload

    @property
    def candidate_id(self) -> str:
        return self.candidate.candidate_id

    @property
    def source_location(self) -> SourceLocation:
        return self.candidate.variant.source.declaration.source_span.location

    @property
    def key(self) -> tuple[object, ...]:
        return (
            self.candidate.candidate_id,
            self.payload.key,
        )


@dataclass(frozen=True, slots=True)
class LoweringInputSet:
    request: LoweringRequest
    inputs: tuple[LoweringInput, ...]
    inputs_by_candidate_id: FrozenMap[str, LoweringInput] = field(init=False)

    def __post_init__(self) -> None:
        inputs = tuple(sorted(self.inputs, key=lambda item: item.key))
        object.__setattr__(self, "inputs", inputs)
        object.__setattr__(
            self,
            "inputs_by_candidate_id",
            FrozenMap((item.candidate_id, item) for item in inputs),
        )


def build_catalog_lowering_request(
    catalog: Catalog,
    *,
    strategy: LoweringStrategy = "mini_tsil",
    backend_id: str | None = None,
    generation_context: GenerationContext | None = None,
) -> Result[LoweringRequest]:
    """Build a lowering request with generation rules derived before evaluation."""

    concrete_rules = build_concrete_integer_generation_rule_set_from_catalog(catalog)
    scalar_size_rules = build_scalar_size_bytes_generation_rule_set_from_catalog(catalog)
    diagnostics = (*concrete_rules.diagnostics, *scalar_size_rules.diagnostics)
    if has_errors(diagnostics):
        return Result.failure(sort_diagnostics(diagnostics))

    concrete_rule_set = concrete_rules.unwrap()
    scalar_size_rule_set = scalar_size_rules.unwrap()
    context = (
        GenerationContext(
            concrete_integer_generation_rules=concrete_rule_set,
            scalar_size_bytes_generation_rules=scalar_size_rule_set,
        )
        if generation_context is None
        else replace(
            generation_context,
            concrete_integer_generation_rules=concrete_rule_set,
            scalar_size_bytes_generation_rules=scalar_size_rule_set,
        )
    )
    return Result.ok(
        LoweringRequest(
            strategy=strategy,
            backend_id=backend_id,
            generation_context=context,
        )
    )


@dataclass(frozen=True, slots=True)
class TsilParameterReference:
    name: str

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("TSIL parameter reference name must be non-empty")

    @property
    def key(self) -> tuple[str, str]:
        return ("parameter", self.name)


@dataclass(frozen=True, slots=True)
class TsilBinaryExpression:
    operator: TsilBinaryOperator
    left: TsilParameterReference
    right: TsilParameterReference

    @property
    def key(self) -> tuple[object, ...]:
        return (
            "binary",
            self.operator,
            self.left.key,
            self.right.key,
        )


@dataclass(frozen=True, slots=True)
class TsilIntrinsicComposeExpression:
    intrinsic: str
    arguments: tuple[TsilParameterReference, ...]

    def __post_init__(self) -> None:
        if not self.intrinsic:
            raise ValueError("TSIL intrinsic-compose intrinsic must be non-empty")
        object.__setattr__(self, "arguments", tuple(self.arguments))

    @property
    def key(self) -> tuple[object, ...]:
        return (
            "intrin_compose",
            self.intrinsic,
            tuple(argument.key for argument in self.arguments),
        )


@dataclass(frozen=True, slots=True)
class TsilReturnStatement:
    expression: TsilExpression

    @property
    def key(self) -> tuple[object, ...]:
        return ("return", self.expression.key)


@dataclass(frozen=True, slots=True)
class TsilPrimitiveAttributeCondition:
    attribute_name: str

    def __post_init__(self) -> None:
        if not self.attribute_name:
            raise ValueError("primitive attribute condition name must be non-empty")

    @property
    def key(self) -> tuple[str, str]:
        return ("primitive_attribute", self.attribute_name)


@dataclass(frozen=True, slots=True)
class TsilTypeSignednessCondition:
    type_ref: GenerationTypeRef

    @property
    def key(self) -> tuple[object, ...]:
        return ("type_is_signed", self.type_ref.key)


type TsilGenerationCondition = (
    TsilPrimitiveAttributeCondition | TsilTypeSignednessCondition
)


@dataclass(frozen=True, slots=True)
class GenerationSizeByteBranchChainArm:
    literal: int
    predicate: GenerationPredicate
    statement_text: str

    def __post_init__(self) -> None:
        if self.literal not in (2, 4, 8):
            raise ValueError("size-byte branch-chain arm literal must be 2, 4, or 8")
        if self.predicate.kind != "type.size_bytes.equals":
            raise ValueError("size-byte branch-chain arm requires a size-byte predicate")
        if self.predicate.literal != self.literal:
            raise ValueError("size-byte branch-chain arm literal must match predicate")
        if not self.statement_text.strip():
            raise ValueError("size-byte branch-chain arm body must be non-empty")

    @property
    def key(self) -> tuple[object, ...]:
        return (self.literal, self.predicate.key, self.statement_text)


@dataclass(frozen=True, slots=True)
class GenerationSizeByteBranchChainPruning:
    arms: tuple[GenerationSizeByteBranchChainArm, ...]
    type_tag: str
    selected_literal: int | None
    selected_statement_text: str | None = None
    condition_location: SourceLocation | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "arms", tuple(self.arms))
        if tuple(arm.literal for arm in self.arms) != (2, 4, 8):
            raise ValueError("size-byte branch chain must have == 2, == 4, == 8 arms")
        if not self.type_tag:
            raise ValueError("size-byte branch-chain type tag must be non-empty")
        if self.selected_literal is not None and self.selected_literal not in (2, 4, 8):
            raise ValueError("selected size-byte branch literal must be 2, 4, 8, or None")
        if self.selected_literal is None:
            if self.selected_statement_text is not None:
                raise ValueError("no-match branch chain must not have selected body text")
        elif not (self.selected_statement_text or "").strip():
            raise ValueError("matched branch chain must record selected body text")

    @property
    def key(self) -> tuple[object, ...]:
        location_key = (
            self.condition_location.sort_key()
            if self.condition_location is not None
            else ()
        )
        return (
            tuple(arm.key for arm in self.arms),
            self.type_tag,
            self.selected_literal or 0,
            self.selected_statement_text or "",
            location_key,
        )


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
            raise ValueError("no-selected-body handoff attempted literals must be 2, 4, 8")

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
        if self.assignment_target_text != _SELECTED_BODY_ASSIGNMENT_TARGET:
            raise ValueError(
                "selected-body assignment form target must be exact text 'pg'"
            )
        if not self.opaque_rhs_text:
            raise ValueError(
                "selected-body assignment form RHS text must be non-empty"
            )
        if self.direct_intrinsic_token_text not in (
            _SELECTED_BODY_ASSIGNMENT_DIRECT_INTRINSIC_TOKENS
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
        if not isinstance(
            self.selected_body_envelope,
            (SelectedBodyEnvelopeIr, NoSelectedBodyEnvelopeIr),
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
class PrunedGenerationBranch:
    condition: TsilGenerationCondition
    selected_branch: GenerationBranchChoice
    statement_text: str
    else_syntax: GenerationElseSyntax = "else<generation>"
    condition_location: SourceLocation | None = None

    def __post_init__(self) -> None:
        if not self.statement_text.strip():
            raise ValueError("pruned generation branch statement text must be non-empty")

    @property
    def key(self) -> tuple[object, ...]:
        location_key = (
            self.condition_location.sort_key()
            if self.condition_location is not None
            else ()
        )
        return (
            self.condition.key,
            self.selected_branch,
            self.statement_text,
            self.else_syntax,
            location_key,
        )


@dataclass(frozen=True, slots=True)
class GenerationTypeRef:
    kind: GenerationTypeRefKind
    type_tag: str
    source_type_tag: str | None = None

    def __post_init__(self) -> None:
        if not self.type_tag:
            raise ValueError("generation type ref type tag must be non-empty")
        if self.source_type_tag == "":
            raise ValueError("generation type ref source type tag must be non-empty")

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.kind, self.type_tag, self.source_type_tag or "")


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
        if not isinstance(
            self.selected_body_envelope,
            (SelectedBodyEnvelopeIr, NoSelectedBodyEnvelopeIr),
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
            if not isinstance(self.selected_body_envelope, SelectedBodyEnvelopeIr):
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
            if not isinstance(self.selected_body_envelope, NoSelectedBodyEnvelopeIr):
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
class GenerationValue:
    kind: GenerationValueKind
    value: int
    type_tag: str

    def __post_init__(self) -> None:
        if isinstance(self.value, bool) or not isinstance(self.value, int):
            raise ValueError("generation value payload must be an integer")
        if not self.type_tag:
            raise ValueError("generation value type tag must be non-empty")

    @property
    def key(self) -> tuple[str, int, str]:
        return (self.kind, self.value, self.type_tag)


@dataclass(frozen=True, slots=True)
class GenerationPredicate:
    kind: GenerationPredicateKind
    literal: int
    value: bool
    type_tag: str

    def __post_init__(self) -> None:
        if isinstance(self.literal, bool) or not isinstance(self.literal, int):
            raise ValueError("generation predicate literal must be an integer")
        if self.literal not in (2, 4, 8):
            raise ValueError("generation predicate literal must be 2, 4, or 8")
        if not isinstance(self.value, bool):
            raise ValueError("generation predicate payload must be boolean")
        if not self.type_tag:
            raise ValueError("generation predicate type tag must be non-empty")

    @property
    def key(self) -> tuple[str, int, bool, str]:
        return (self.kind, self.literal, self.value, self.type_tag)


@dataclass(frozen=True, slots=True)
class GenerationExpressionRecognition:
    kind: GenerationRecognitionKind
    source_text: str

    def __post_init__(self) -> None:
        if not self.source_text.strip():
            raise ValueError("generation recognition source text must be non-empty")

    @property
    def key(self) -> tuple[str, str]:
        return (self.kind, self.source_text)


@dataclass(frozen=True, slots=True)
class GenerationLoweringStage:
    stage: GenerationLoweringStageName
    output: GenerationLoweringStageOutput

    def __post_init__(self) -> None:
        expected: tuple[type[object], ...]
        if self.stage == "helper_expression_recognition":
            expected = (GenerationExpressionRecognition,)
        elif self.stage == "typed_generation_value":
            expected = (GenerationValue,)
        elif self.stage == "typed_generation_predicate":
            expected = (GenerationPredicate,)
        elif self.stage == "generation_control_flow_pruning":
            expected = (PrunedGenerationBranch, GenerationSizeByteBranchChainPruning)
        elif self.stage == "selected_body_lowering":
            expected = (
                TsilReturnStatement,
                OpaqueSelectedBranchBodyHandoff,
                NoSelectedBranchBodyHandoff,
            )
        elif self.stage == "selected_body_form_recognition":
            expected = (
                SelectedBranchBodyAssignmentFormRecognition,
                NoSelectedBranchBodyAssignmentFormRecognition,
            )
        elif self.stage == "selected_body_ir_lowering":
            expected = (
                SelectedAssignmentDirectIntrinsicBodyIr,
                NoSelectedAssignmentDirectIntrinsicBodyIr,
            )
        elif self.stage == "selected_body_envelope_lowering":
            expected = (
                SelectedBodyEnvelopeIr,
                NoSelectedBodyEnvelopeIr,
            )
        elif self.stage == "array_body_envelope_slot_assembly":
            expected = (ExactArrayBodyEnvelopeIr,)
        elif self.stage == "array_initialization_slot_form_lowering":
            expected = (ExactArrayInitializationSlotFormIr,)
        elif self.stage == "array_initialization_helper_request_lowering":
            expected = (ExactArrayInitializationHelperRequestIr,)
        elif self.stage == "array_initialization_base_type_request_resolution":
            expected = (ExactArrayInitializationBaseTypeResolutionIr,)
        elif self.stage == "array_initialization_vector_length_request_resolution":
            expected = (ExactArrayInitializationVectorLengthResolutionIr,)
        elif self.stage == "array_initialization_vector_alignment_request_resolution":
            expected = (ExactArrayInitializationVectorAlignmentResolutionIr,)
        elif self.stage == "array_initialization_helper_set_completion":
            expected = (ExactArrayInitializationHelperSetCompletionIr,)
        elif self.stage == "array_initialization_declaration_shell_lowering":
            expected = (ExactArrayInitializationDeclarationShellIr,)
        elif self.stage == "array_body_structural_sequence_classification":
            expected = (ExactArrayBodyStructuralSequenceIr,)
        elif self.stage == "predicate_path_structural_request_lowering":
            expected = (ExactPredicatePathStructuralRequestIr,)
        else:
            raise ValueError(f"unknown generation lowering stage: {self.stage!r}")
        if not isinstance(self.output, expected):
            raise TypeError(
                f"{self.stage} stage requires output type "
                f"{', '.join(item.__name__ for item in expected)}"
            )

    @property
    def key(self) -> tuple[object, ...]:
        return (self.stage, self.output.key)


@dataclass(frozen=True, slots=True)
class LoweredImplementation:
    candidate_id: str
    status: LoweringStatus
    statements: tuple[TsilStatement, ...] = ()
    generation_branches: tuple[PrunedGenerationBranch, ...] = ()
    generation_type_refs: tuple[GenerationTypeRef, ...] = ()
    generation_values: tuple[GenerationValue, ...] = ()
    generation_predicates: tuple[GenerationPredicate, ...] = ()
    generation_branch_chains: tuple[GenerationSizeByteBranchChainPruning, ...] = ()
    selected_branch_body_handoffs: tuple[GenerationSelectedBranchBodyHandoff, ...] = ()
    selected_branch_body_assignment_forms: tuple[
        GenerationSelectedBranchBodyAssignmentRecognition, ...
    ] = ()
    selected_branch_body_irs: tuple[GenerationSelectedBranchBodyIr, ...] = ()
    selected_body_envelopes: tuple[GenerationSelectedBodyEnvelopeIr, ...] = ()
    array_body_envelopes: tuple[ExactArrayBodyEnvelopeIr, ...] = ()
    array_initialization_slot_forms: tuple[
        ExactArrayInitializationSlotFormIr, ...
    ] = ()
    array_initialization_helper_requests: tuple[
        ExactArrayInitializationHelperRequestIr, ...
    ] = ()
    array_initialization_base_type_resolutions: tuple[
        ExactArrayInitializationBaseTypeResolutionIr, ...
    ] = ()
    array_initialization_vector_length_resolutions: tuple[
        ExactArrayInitializationVectorLengthResolutionIr, ...
    ] = ()
    array_initialization_vector_alignment_resolutions: tuple[
        ExactArrayInitializationVectorAlignmentResolutionIr, ...
    ] = ()
    array_initialization_helper_set_completions: tuple[
        ExactArrayInitializationHelperSetCompletionIr, ...
    ] = ()
    array_initialization_declaration_shells: tuple[
        ExactArrayInitializationDeclarationShellIr, ...
    ] = ()
    array_body_structural_sequences: tuple[
        ExactArrayBodyStructuralSequenceIr, ...
    ] = ()
    predicate_path_structural_requests: tuple[
        ExactPredicatePathStructuralRequestIr, ...
    ] = ()
    generation_stages: tuple[GenerationLoweringStage, ...] = ()

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise ValueError("lowered implementation candidate id must be non-empty")
        object.__setattr__(self, "statements", tuple(self.statements))
        object.__setattr__(
            self,
            "generation_branches",
            tuple(self.generation_branches),
        )
        object.__setattr__(
            self,
            "generation_type_refs",
            tuple(self.generation_type_refs),
        )
        object.__setattr__(
            self,
            "generation_values",
            tuple(self.generation_values),
        )
        object.__setattr__(
            self,
            "generation_predicates",
            tuple(self.generation_predicates),
        )
        object.__setattr__(
            self,
            "generation_branch_chains",
            tuple(self.generation_branch_chains),
        )
        object.__setattr__(
            self,
            "selected_branch_body_handoffs",
            tuple(self.selected_branch_body_handoffs),
        )
        object.__setattr__(
            self,
            "selected_branch_body_assignment_forms",
            tuple(self.selected_branch_body_assignment_forms),
        )
        object.__setattr__(
            self,
            "selected_branch_body_irs",
            tuple(self.selected_branch_body_irs),
        )
        object.__setattr__(
            self,
            "selected_body_envelopes",
            tuple(self.selected_body_envelopes),
        )
        object.__setattr__(
            self,
            "array_body_envelopes",
            tuple(self.array_body_envelopes),
        )
        object.__setattr__(
            self,
            "array_initialization_slot_forms",
            tuple(self.array_initialization_slot_forms),
        )
        object.__setattr__(
            self,
            "array_initialization_helper_requests",
            tuple(self.array_initialization_helper_requests),
        )
        object.__setattr__(
            self,
            "array_initialization_base_type_resolutions",
            tuple(self.array_initialization_base_type_resolutions),
        )
        object.__setattr__(
            self,
            "array_initialization_vector_length_resolutions",
            tuple(self.array_initialization_vector_length_resolutions),
        )
        object.__setattr__(
            self,
            "array_initialization_vector_alignment_resolutions",
            tuple(self.array_initialization_vector_alignment_resolutions),
        )
        object.__setattr__(
            self,
            "array_initialization_helper_set_completions",
            tuple(self.array_initialization_helper_set_completions),
        )
        object.__setattr__(
            self,
            "array_initialization_declaration_shells",
            tuple(self.array_initialization_declaration_shells),
        )
        object.__setattr__(
            self,
            "array_body_structural_sequences",
            tuple(self.array_body_structural_sequences),
        )
        object.__setattr__(
            self,
            "predicate_path_structural_requests",
            tuple(self.predicate_path_structural_requests),
        )
        object.__setattr__(
            self,
            "generation_stages",
            tuple(self.generation_stages),
        )

    @property
    def key(self) -> tuple[object, ...]:
        return (
            self.candidate_id,
            self.status,
            tuple(statement.key for statement in self.statements),
            tuple(branch.key for branch in self.generation_branches),
            tuple(type_ref.key for type_ref in self.generation_type_refs),
            tuple(value.key for value in self.generation_values),
            tuple(predicate.key for predicate in self.generation_predicates),
            tuple(chain.key for chain in self.generation_branch_chains),
            tuple(handoff.key for handoff in self.selected_branch_body_handoffs),
            tuple(
                form.key for form in self.selected_branch_body_assignment_forms
            ),
            tuple(body_ir.key for body_ir in self.selected_branch_body_irs),
            tuple(envelope.key for envelope in self.selected_body_envelopes),
            tuple(envelope.key for envelope in self.array_body_envelopes),
            tuple(form.key for form in self.array_initialization_slot_forms),
            tuple(
                helper_request.key
                for helper_request in self.array_initialization_helper_requests
            ),
            tuple(
                resolution.key
                for resolution in self.array_initialization_base_type_resolutions
            ),
            tuple(
                resolution.key
                for resolution in (
                    self.array_initialization_vector_length_resolutions
                )
            ),
            tuple(
                resolution.key
                for resolution in (
                    self.array_initialization_vector_alignment_resolutions
                )
            ),
            tuple(
                completion.key
                for completion in self.array_initialization_helper_set_completions
            ),
            tuple(
                shell.key
                for shell in self.array_initialization_declaration_shells
            ),
            tuple(
                sequence.key
                for sequence in self.array_body_structural_sequences
            ),
            tuple(
                request.key
                for request in self.predicate_path_structural_requests
            ),
            tuple(stage.key for stage in self.generation_stages),
        )


@dataclass(frozen=True, slots=True)
class LoweringPlan:
    request: LoweringRequest
    input_set: LoweringInputSet
    implementations: tuple[LoweredImplementation, ...]
    implementations_by_candidate_id: FrozenMap[str, LoweredImplementation] = field(
        init=False
    )

    def __post_init__(self) -> None:
        implementations = tuple(sorted(self.implementations, key=lambda item: item.key))
        object.__setattr__(self, "implementations", implementations)
        object.__setattr__(
            self,
            "implementations_by_candidate_id",
            FrozenMap((item.candidate_id, item) for item in implementations),
        )


@dataclass(frozen=True, slots=True)
class _ArrayBodyEnvelopeSkeletonLookup:
    skeletons: tuple[
        tuple[ExactArrayBodyEnvelopeSkeletonKey, ExactArrayBodyEnvelopeSkeleton],
        ...
    ]
    requirements: tuple[
        tuple[
            ExactArrayBodyEnvelopeSkeletonKey,
            ExactArrayBodyEnvelopeSkeletonRequirement,
        ],
        ...
    ]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "skeletons",
            tuple(sorted(self.skeletons, key=lambda item: item[0].key)),
        )
        object.__setattr__(
            self,
            "requirements",
            tuple(sorted(self.requirements, key=lambda item: item[0].key)),
        )

    @property
    def skeleton_keys(self) -> tuple[ExactArrayBodyEnvelopeSkeletonKey, ...]:
        return tuple(key for key, _skeleton in self.skeletons)

    def skeleton_for(
        self,
        lookup_key: ExactArrayBodyEnvelopeSkeletonKey,
    ) -> ExactArrayBodyEnvelopeSkeleton | None:
        for key, skeleton in self.skeletons:
            if key == lookup_key:
                return skeleton
        return None

    def requirement_for(
        self,
        lookup_key: ExactArrayBodyEnvelopeSkeletonKey,
    ) -> ExactArrayBodyEnvelopeSkeletonRequirement | None:
        for key, requirement in self.requirements:
            if key == lookup_key:
                return requirement
        return None


def prepare_lowering_inputs(
    selection: CandidateSelection,
    request: LoweringRequest | None = None,
) -> Result[LoweringInputSet]:
    lowering_request = request or LoweringRequest()
    diagnostics: list[Diagnostic] = []
    inputs: list[LoweringInput] = []
    for candidate in selection.candidates:
        classified = _classify_payload(candidate)
        diagnostics.extend(classified.diagnostics)
        if classified.is_ok:
            inputs.append(
                LoweringInput(
                    candidate=candidate,
                    payload=classified.unwrap(),
                )
            )

    ordered = sort_diagnostics(diagnostics)
    if has_errors(ordered):
        return Result.failure(ordered)
    return Result.ok(
        LoweringInputSet(request=lowering_request, inputs=tuple(inputs)),
        diagnostics=ordered,
    )


def lower_candidates(
    selection: CandidateSelection,
    request: LoweringRequest | None = None,
) -> Result[LoweringPlan]:
    input_set = prepare_lowering_inputs(selection, request)
    if not input_set.is_ok:
        return Result.failure(input_set.diagnostics)

    lowering_inputs = input_set.unwrap()
    if lowering_inputs.request.strategy == "typed_opaque":
        unsupported_diagnostics = tuple(
            _unsupported_payload_diagnostic(item, strategy="typed_opaque")
            for item in lowering_inputs.inputs
        )
        ordered = sort_diagnostics(unsupported_diagnostics)
        if has_errors(ordered):
            return Result.failure(ordered)
        return Result.ok(
            LoweringPlan(
                request=lowering_inputs.request,
                input_set=lowering_inputs,
                implementations=(),
            ),
            diagnostics=ordered,
        )

    diagnostics: list[Diagnostic] = []
    skeleton_lookup_result = _build_array_body_envelope_skeleton_lookup(
        lowering_inputs.request,
    )
    diagnostics.extend(skeleton_lookup_result.diagnostics)
    if not skeleton_lookup_result.is_ok:
        ordered = sort_diagnostics(diagnostics)
        return Result.failure(ordered)
    skeleton_lookup = skeleton_lookup_result.unwrap()
    implementations: list[LoweredImplementation] = []
    for item in lowering_inputs.inputs:
        lowered = _lower_input(item, lowering_inputs.request, skeleton_lookup)
        diagnostics.extend(lowered.diagnostics)
        if lowered.is_ok:
            implementations.append(lowered.unwrap())

    if not has_errors(tuple(diagnostics)):
        diagnostics.extend(
            _unused_array_body_envelope_skeleton_diagnostics(
                skeleton_lookup,
                tuple(implementations),
            )
        )
    ordered = sort_diagnostics(diagnostics)
    if has_errors(ordered):
        return Result.failure(ordered)
    return Result.ok(
        LoweringPlan(
            request=lowering_inputs.request,
            input_set=lowering_inputs,
            implementations=tuple(implementations),
        ),
        diagnostics=ordered,
    )


def handoff_opaque_selected_branch_body(
    candidate_id: str,
    stage: GenerationLoweringStage,
) -> Result[GenerationSelectedBranchBodyHandoff]:
    if not candidate_id:
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-LOWER-HANDOFF-CANDIDATE-MISSING",
                    "opaque selected-body handoff requires a candidate id",
                ),
            )
        )
    if (
        stage.stage != "generation_control_flow_pruning"
        or not isinstance(stage.output, GenerationSizeByteBranchChainPruning)
    ):
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-LOWER-HANDOFF-SOURCE-UNSUPPORTED",
                    "opaque selected-body handoff consumes only typed "
                    "GenerationSizeByteBranchChainPruning output from the "
                    "generation_control_flow_pruning stage",
                    location=_stage_output_location(stage.output),
                ),
            )
        )

    pruning = stage.output
    if pruning.condition_location is None:
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-LOWER-HANDOFF-PROVENANCE-MISSING",
                    "opaque selected-body handoff requires branch-chain "
                    "source provenance",
                ),
            )
        )

    originating_branch_chain_id = _originating_branch_chain_id(
        candidate_id,
        pruning,
    )
    if pruning.selected_literal is None:
        return Result.ok(
            NoSelectedBranchBodyHandoff(
                candidate_id=candidate_id,
                selected_type_tag=pruning.type_tag,
                source_location=pruning.condition_location,
                originating_branch_chain_id=originating_branch_chain_id,
                attempted_literals=tuple(arm.literal for arm in pruning.arms),
            )
        )

    if not (pruning.selected_statement_text or "").strip():
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-LOWER-HANDOFF-BODY-MISSING",
                    "opaque selected-body handoff requires selected branch "
                    "body text for matched branch-chain pruning",
                    location=pruning.condition_location,
                ),
            )
        )

    selected_literal = pruning.selected_literal
    body_text = pruning.selected_statement_text
    if selected_literal is None or body_text is None:
        raise AssertionError("selected branch handoff state was checked above")
    return Result.ok(
        OpaqueSelectedBranchBodyHandoff(
            candidate_id=candidate_id,
            selected_type_tag=pruning.type_tag,
            selected_literal=selected_literal,
            opaque_body_text=body_text,
            source_location=pruning.condition_location,
            originating_branch_chain_id=originating_branch_chain_id,
        )
    )


def recognize_selected_branch_body_assignment_form(
    source: GenerationSelectedBranchBodyHandoff | GenerationLoweringStage,
) -> Result[GenerationSelectedBranchBodyAssignmentRecognition]:
    handoff = _selected_body_assignment_handoff_source(source)
    if not handoff.is_ok:
        return Result.failure(handoff.diagnostics)

    selected_body_handoff = handoff.unwrap()
    if isinstance(selected_body_handoff, NoSelectedBranchBodyHandoff):
        return Result.ok(
            NoSelectedBranchBodyAssignmentFormRecognition(
                candidate_id=selected_body_handoff.candidate_id,
                selected_type_tag=selected_body_handoff.selected_type_tag,
                source_location=selected_body_handoff.source_location,
                originating_branch_chain_id=(
                    selected_body_handoff.originating_branch_chain_id
                ),
                attempted_literals=selected_body_handoff.attempted_literals,
            )
        )

    recognized = _recognize_opaque_selected_branch_body_assignment_form(
        selected_body_handoff,
    )
    if not recognized.is_ok:
        return Result.failure(recognized.diagnostics)
    return Result.ok(recognized.unwrap())


def lower_selected_branch_body_ir(
    source: GenerationSelectedBranchBodyAssignmentRecognition | GenerationLoweringStage,
) -> Result[GenerationSelectedBranchBodyIr]:
    recognition = _selected_body_ir_recognition_source(source)
    if not recognition.is_ok:
        return Result.failure(recognition.diagnostics)

    form = recognition.unwrap()
    if isinstance(form, NoSelectedBranchBodyAssignmentFormRecognition):
        return Result.ok(
            NoSelectedAssignmentDirectIntrinsicBodyIr(
                candidate_id=form.candidate_id,
                selected_type_tag=form.selected_type_tag,
                source_location=form.source_location,
                originating_branch_chain_id=form.originating_branch_chain_id,
                attempted_literals=form.attempted_literals,
            )
        )

    return Result.ok(
        SelectedAssignmentDirectIntrinsicBodyIr(
            candidate_id=form.candidate_id,
            selected_type_tag=form.selected_type_tag,
            selected_literal=form.selected_literal,
            originating_branch_chain_id=form.originating_branch_chain_id,
            original_opaque_body_text=form.original_opaque_body_text,
            source_location=form.selected_statement_location,
            assignment_target_text=form.assignment_target_text,
            opaque_rhs_text=form.opaque_rhs_text,
            direct_intrinsic_token_text=form.direct_intrinsic_token_text,
            direct_intrinsic_argument_texts=(),
        )
    )


def lower_selected_body_envelope(
    source: GenerationSelectedBranchBodyIr | GenerationLoweringStage,
) -> Result[GenerationSelectedBodyEnvelopeIr]:
    body_ir_result = _selected_body_envelope_source(source)
    if not body_ir_result.is_ok:
        return Result.failure(body_ir_result.diagnostics)

    body_ir = body_ir_result.unwrap()
    if isinstance(body_ir, NoSelectedAssignmentDirectIntrinsicBodyIr):
        diagnostic = _validate_no_selected_body_envelope_source(body_ir)
        if diagnostic is not None:
            return Result.failure((diagnostic,))
        try:
            return Result.ok(
                NoSelectedBodyEnvelopeIr(
                    source_body_ir=body_ir,
                    candidate_id=body_ir.candidate_id,
                    selected_type_tag=body_ir.selected_type_tag,
                    source_location=body_ir.source_location,
                    originating_branch_chain_id=body_ir.originating_branch_chain_id,
                    attempted_literals=body_ir.attempted_literals,
                    entries=(),
                )
            )
        except (TypeError, ValueError) as exc:
            return Result.failure(
                (
                    _inconsistent_selected_body_envelope_diagnostic(
                        str(exc),
                        body_ir.source_location,
                    ),
                )
            )

    diagnostic = _validate_selected_body_envelope_source(body_ir)
    if diagnostic is not None:
        return Result.failure((diagnostic,))
    try:
        entry = SelectedBodyEnvelopeEntry(
            source_body_ir=body_ir,
            candidate_id=body_ir.candidate_id,
            selected_type_tag=body_ir.selected_type_tag,
            selected_literal=body_ir.selected_literal,
            originating_branch_chain_id=body_ir.originating_branch_chain_id,
            original_opaque_body_text=body_ir.original_opaque_body_text,
            source_location=body_ir.source_location,
            assignment_target_text=body_ir.assignment_target_text,
            opaque_rhs_text=body_ir.opaque_rhs_text,
            direct_intrinsic_token_text=body_ir.direct_intrinsic_token_text,
            direct_intrinsic_argument_texts=body_ir.direct_intrinsic_argument_texts,
        )
        return Result.ok(
            SelectedBodyEnvelopeIr(
                candidate_id=body_ir.candidate_id,
                selected_type_tag=body_ir.selected_type_tag,
                source_location=body_ir.source_location,
                originating_branch_chain_id=body_ir.originating_branch_chain_id,
                entries=(entry,),
            )
        )
    except (TypeError, ValueError) as exc:
        return Result.failure(
            (
                _inconsistent_selected_body_envelope_diagnostic(
                    str(exc),
                    body_ir.source_location,
                ),
            )
        )


def assemble_exact_array_body_envelope(
    source: GenerationSelectedBodyEnvelopeIr | GenerationLoweringStage,
    skeleton: ExactArrayBodyEnvelopeSkeleton,
) -> Result[ExactArrayBodyEnvelopeIr]:
    envelope_result = _array_body_envelope_m63_source(source)
    if not envelope_result.is_ok:
        return Result.failure(envelope_result.diagnostics)

    envelope = envelope_result.unwrap()
    skeleton_diagnostic = _validate_exact_array_body_envelope_skeleton(
        skeleton,
        envelope,
    )
    if skeleton_diagnostic is not None:
        return Result.failure((skeleton_diagnostic,))

    slots: list[ExactArrayBodyEnvelopeSlot] = []
    for skeleton_slot in skeleton.slots:
        if skeleton_slot.label == "selected_body_envelope":
            slots.append(
                ExactArrayBodyEnvelopeSelectedSlot(
                    label="selected_body_envelope",
                    ordinal=skeleton_slot.ordinal,
                    selected_body_envelope=envelope,
                    source_location=skeleton_slot.source_location,
                    candidate_id=skeleton_slot.candidate_id,
                    selected_type_tag=skeleton_slot.selected_type_tag,
                    originating_branch_chain_id=(
                        skeleton_slot.originating_branch_chain_id
                    ),
                )
            )
            continue

        opaque_source_text = skeleton_slot.opaque_source_text
        if opaque_source_text is None:
            raise AssertionError("M64 opaque slot text was validated above")
        slots.append(
            ExactArrayBodyEnvelopeOpaqueSlot(
                label=skeleton_slot.label,
                ordinal=skeleton_slot.ordinal,
                opaque_source_text=opaque_source_text,
                source_location=skeleton_slot.source_location,
                candidate_id=skeleton_slot.candidate_id,
                selected_type_tag=skeleton_slot.selected_type_tag,
                originating_branch_chain_id=(
                    skeleton_slot.originating_branch_chain_id
                ),
            )
        )

    try:
        return Result.ok(
            ExactArrayBodyEnvelopeIr(
                candidate_id=skeleton.candidate_id,
                selected_type_tag=skeleton.selected_type_tag,
                source_location=skeleton.source_location,
                originating_branch_chain_id=skeleton.originating_branch_chain_id,
                slots=tuple(slots),
            )
        )
    except (TypeError, ValueError) as exc:
        return Result.failure(
            (
                _array_body_envelope_shape_unsupported_diagnostic(
                    str(exc),
                    skeleton.source_location,
                ),
            )
        )


def lower_exact_array_initialization_slot_form(
    source: object,
) -> Result[ExactArrayInitializationSlotFormIr]:
    envelope_result = _array_initialization_slot_form_source(source)
    if not envelope_result.is_ok:
        return Result.failure(envelope_result.diagnostics)

    envelope = envelope_result.unwrap()
    selected_slot = _array_initialization_envelope_slot(envelope)
    if selected_slot is None:
        return Result.failure(
            (
                _array_initialization_slot_missing_diagnostic(
                    "array-initialization slot form lowering requires the M65 "
                    "opaque_pre_branch_array_initialization slot at ordinal 0",
                    envelope.source_location,
                ),
            )
        )
    if not isinstance(selected_slot, ExactArrayBodyEnvelopeOpaqueSlot):
        return Result.failure(
            (
                _array_initialization_slot_wrong_position_diagnostic(
                    "array-initialization slot form lowering requires an opaque "
                    "M65 slot, but the selected slot is not opaque",
                    selected_slot.source_location,
                ),
            )
        )

    slot_diagnostic = _validate_array_initialization_slot_position(
        envelope,
        selected_slot,
    )
    if slot_diagnostic is not None:
        return Result.failure((slot_diagnostic,))

    exact_match = _EXACT_ARRAY_INITIALIZATION_SLOT_RE.match(
        selected_slot.opaque_source_text,
    )
    if exact_match is None:
        shape_match = _ARRAY_INITIALIZATION_SLOT_HELPER_SHAPE_RE.match(
            selected_slot.opaque_source_text,
        )
        if shape_match is not None:
            return Result.failure(
                (
                    _array_initialization_slot_helper_unsupported_diagnostic(
                        selected_slot,
                    ),
                )
            )
        return Result.failure(
            (
                _array_initialization_slot_malformed_diagnostic(
                    "array-initialization slot form lowering recognizes only "
                    "the exact array.tsl:105 var<typed>(array_type<...>, tmp, "
                    "value<backend>(uninit::array)) form",
                    selected_slot.source_location,
                ),
            )
        )

    try:
        return Result.ok(
            ExactArrayInitializationSlotFormIr(
                source_envelope=envelope,
                slot_label="opaque_pre_branch_array_initialization",
                slot_ordinal=selected_slot.ordinal,
                source_location=selected_slot.source_location,
                candidate_id=selected_slot.candidate_id,
                selected_type_tag=selected_slot.selected_type_tag,
                originating_branch_chain_id=(
                    selected_slot.originating_branch_chain_id
                ),
                original_slot_text=selected_slot.opaque_source_text,
                variable_token=exact_match.group("variable"),
                variable_token_location=_source_span_for_match_group(
                    selected_slot.source_location,
                    exact_match,
                    "variable",
                ),
                base_type_leaf=_array_initialization_leaf(
                    "type_generation_base_in",
                    selected_slot.source_location,
                    exact_match,
                    "base_type",
                ),
                vector_length_leaf=_array_initialization_leaf(
                    "value_generation_vector_length",
                    selected_slot.source_location,
                    exact_match,
                    "vector_length",
                ),
                vector_alignment_leaf=_array_initialization_leaf(
                    "value_generation_vector_alignment",
                    selected_slot.source_location,
                    exact_match,
                    "vector_alignment",
                ),
                backend_uninit_leaf=_array_initialization_leaf(
                    "value_backend_uninit_array",
                    selected_slot.source_location,
                    exact_match,
                    "backend_uninit",
                ),
            )
        )
    except (TypeError, ValueError) as exc:
        return Result.failure(
            (
                _array_initialization_slot_provenance_mismatch_diagnostic(
                    str(exc),
                    selected_slot.source_location,
                ),
            )
        )


def lower_exact_array_initialization_helper_requests(
    source: object,
) -> Result[ExactArrayInitializationHelperRequestIr]:
    form_result = _array_initialization_helper_request_source(source)
    if not form_result.is_ok:
        return Result.failure(form_result.diagnostics)

    form = form_result.unwrap()
    provenance_diagnostic = _validate_array_initialization_helper_form_provenance(
        form,
    )
    if provenance_diagnostic is not None:
        return Result.failure((provenance_diagnostic,))

    diagnostics: list[Diagnostic] = []
    requests: list[ExactArrayInitializationHelperRequestRecord] = []
    seen_leaf_kinds: set[ExactArrayInitializationHelperLeafKind] = set()
    for spec in _EXACT_ARRAY_INITIALIZATION_HELPER_LEAF_SPECS:
        leaf = getattr(form, spec.field_name, None)
        if not isinstance(leaf, ExactArrayInitializationUnresolvedLeaf):
            diagnostics.append(
                _array_initialization_helper_request_missing_leaf_diagnostic(
                    spec,
                    form,
                )
            )
            continue
        if leaf.kind in seen_leaf_kinds:
            diagnostics.append(
                _array_initialization_helper_request_duplicate_leaf_diagnostic(
                    leaf,
                    form,
                )
            )
            continue
        seen_leaf_kinds.add(leaf.kind)
        if leaf.kind != spec.expected_leaf_kind:
            diagnostics.append(
                _array_initialization_helper_request_mismatched_leaf_diagnostic(
                    spec,
                    leaf,
                )
            )
            continue
        expected_text = _EXACT_ARRAY_INITIALIZATION_HELPER_TEXT_BY_KIND.get(leaf.kind)
        if expected_text is None or leaf.source_text != expected_text:
            diagnostics.append(
                _array_initialization_helper_request_unsupported_leaf_diagnostic(
                    spec,
                    leaf,
                )
            )
            continue
        if leaf.source_location is None:
            diagnostics.append(
                _array_initialization_helper_request_missing_leaf_diagnostic(
                    spec,
                    form,
                )
            )
            continue
        try:
            requests.append(
                ExactArrayInitializationHelperRequestRecord(
                    source_form=form,
                    source_envelope=form.source_envelope,
                    request_ordinal=spec.request_ordinal,
                    request_kind=spec.request_kind,
                    helper_leaf_kind=leaf.kind,
                    leaf_source_text=leaf.source_text,
                    leaf_source_location=leaf.source_location,
                    candidate_id=form.candidate_id,
                    selected_type_tag=form.selected_type_tag,
                    originating_branch_chain_id=form.originating_branch_chain_id,
                    slot_label=form.slot_label,
                    slot_ordinal=form.slot_ordinal,
                    variable_token=form.variable_token,
                )
            )
        except (TypeError, ValueError) as exc:
            diagnostics.append(
                _array_initialization_helper_request_provenance_mismatch_diagnostic(
                    str(exc),
                    leaf.source_location,
                )
            )

    if diagnostics:
        ordered = sort_diagnostics(tuple(diagnostics))
        return Result.failure(ordered)

    try:
        return Result.ok(
            ExactArrayInitializationHelperRequestIr(
                source_form=form,
                source_envelope=form.source_envelope,
                source_location=form.source_location,
                candidate_id=form.candidate_id,
                selected_type_tag=form.selected_type_tag,
                originating_branch_chain_id=form.originating_branch_chain_id,
                slot_label=form.slot_label,
                slot_ordinal=form.slot_ordinal,
                variable_token=form.variable_token,
                requests=tuple(requests),
            )
        )
    except (TypeError, ValueError) as exc:
        return Result.failure(
            (
                _array_initialization_helper_request_provenance_mismatch_diagnostic(
                    str(exc),
                    form.source_location,
                ),
            )
        )


def lower_exact_array_initialization_base_type_request(
    source: object,
    context: GenerationContext | None = None,
    *,
    selected_candidate_type_tag: str | None = None,
) -> Result[ExactArrayInitializationBaseTypeResolutionIr]:
    request_ir_result = _array_initialization_base_type_resolution_source(source)
    if not request_ir_result.is_ok:
        return Result.failure(request_ir_result.diagnostics)

    request_ir = request_ir_result.unwrap()
    diagnostics = _validate_array_initialization_base_type_request_ir_provenance(
        request_ir,
    )
    base_request = _array_initialization_base_type_request_record(
        request_ir,
        diagnostics,
    )
    if diagnostics:
        return Result.failure(sort_diagnostics(tuple(diagnostics)))
    if base_request is None:
        raise AssertionError("base request diagnostics must be present when missing")

    generation_context = context or GenerationContext()
    candidate_type_tag = selected_candidate_type_tag
    if candidate_type_tag is None and generation_context.use_candidate_type_tag:
        candidate_type_tag = request_ir.selected_type_tag
    semantic_label = "array-initialization base-type request"
    effective_type_tag = _effective_generation_type_tag(
        generation_context,
        selected_candidate_type_tag=candidate_type_tag,
        query_text=semantic_label,
        location=base_request.leaf_source_location,
    )
    if not effective_type_tag.is_ok:
        return Result.failure(effective_type_tag.diagnostics)

    resolved_type_ref = _base_in_type_ref(
        effective_type_tag.unwrap(),
        generation_context.concrete_integer_generation_rules,
        semantic_label,
        base_request.leaf_source_location,
    )
    if not resolved_type_ref.is_ok:
        return Result.failure(resolved_type_ref.diagnostics)
    type_ref = resolved_type_ref.unwrap()
    if type_ref.type_tag != request_ir.selected_type_tag:
        return Result.failure(
            (
                _array_initialization_base_type_resolution_provenance_mismatch_diagnostic(
                    "array-initialization base-type request resolved selected "
                    f"type tag {type_ref.type_tag!r}, but the M67 "
                    "helper-request IR records selected type tag "
                    f"{request_ir.selected_type_tag!r}",
                    base_request.leaf_source_location,
                ),
            )
        )

    unresolved_requests = tuple(
        request
        for request in request_ir.requests
        if request is not base_request
    )
    try:
        return Result.ok(
            ExactArrayInitializationBaseTypeResolutionIr(
                source_request_ir=request_ir,
                source_base_type_request=base_request,
                resolved_type_ref=type_ref,
                unresolved_requests=unresolved_requests,
                source_location=request_ir.source_location,
                candidate_id=request_ir.candidate_id,
                selected_type_tag=request_ir.selected_type_tag,
                originating_branch_chain_id=request_ir.originating_branch_chain_id,
                slot_label=request_ir.slot_label,
                slot_ordinal=request_ir.slot_ordinal,
                variable_token=request_ir.variable_token,
            )
        )
    except (TypeError, ValueError) as exc:
        return Result.failure(
            (
                _array_initialization_base_type_resolution_provenance_mismatch_diagnostic(
                    str(exc),
                    request_ir.source_location,
                ),
            )
        )


def lower_exact_array_initialization_vector_length_request(
    source: object,
    context: GenerationContext | None = None,
    *,
    selected_candidate_id: str | None = None,
    target_extension: str | None = None,
    source_extension: str | None = None,
    selected_type_tag: str | None = None,
    require_fixed_lanes: bool = False,
) -> Result[ExactArrayInitializationVectorLengthResolutionIr]:
    base_resolution_result = _array_initialization_vector_length_resolution_source(
        source,
    )
    if not base_resolution_result.is_ok:
        return Result.failure(base_resolution_result.diagnostics)

    base_resolution = base_resolution_result.unwrap()
    diagnostics = _validate_array_initialization_vector_length_resolution_provenance(
        base_resolution,
    )
    vector_length_request = _array_initialization_vector_length_request_record(
        base_resolution,
        diagnostics,
    )
    if diagnostics:
        return Result.failure(sort_diagnostics(tuple(diagnostics)))
    if vector_length_request is None:
        raise AssertionError(
            "vector-length request diagnostics must be present when missing"
        )

    generation_context = context or GenerationContext()
    effective_candidate_id = (
        selected_candidate_id
        or generation_context.selected_candidate_id
        or base_resolution.candidate_id
    )
    effective_type_tag = (
        selected_type_tag
        or generation_context.selected_type_tag
        or base_resolution.selected_type_tag
    )
    if (
        effective_candidate_id != base_resolution.candidate_id
        or effective_type_tag != base_resolution.selected_type_tag
    ):
        return Result.failure(
            (
                _array_initialization_vector_length_context_mismatch_diagnostic(
                    "array-initialization vector-length request resolution "
                    "requires the typed selected candidate context to match "
                    "the M68 base-type resolution candidate id and selected "
                    "type tag",
                    vector_length_request.leaf_source_location,
                ),
            )
        )
    if target_extension is None or source_extension is None:
        return Result.failure(
            (
                _array_initialization_vector_length_metadata_missing_diagnostic(
                    "array-initialization vector-length request resolution "
                    "requires typed target/source extension context before "
                    "lowering evaluation",
                    vector_length_request.leaf_source_location,
                ),
            )
        )

    metadata_result = _array_initialization_vector_length_metadata_for_context(
        generation_context,
        candidate_id=base_resolution.candidate_id,
        target_extension=target_extension,
        source_extension=source_extension,
        selected_type_tag=base_resolution.selected_type_tag,
        location=vector_length_request.leaf_source_location,
    )
    if not metadata_result.is_ok:
        return Result.failure(metadata_result.diagnostics)
    metadata = metadata_result.unwrap()
    if require_fixed_lanes and metadata.vector_length.kind != "fixed_lanes":
        return Result.failure(
            (
                _array_initialization_vector_length_metadata_unsupported_diagnostic(
                    "array-initialization vector-length request resolution was "
                    "asked for fixed numeric lanes, but the supplied typed "
                    f"metadata is {metadata.vector_length.kind!r}",
                    metadata.source_location or vector_length_request.leaf_source_location,
                ),
            )
        )

    unresolved_requests = tuple(
        request
        for request in base_resolution.unresolved_requests
        if request is not vector_length_request
    )
    try:
        return Result.ok(
            ExactArrayInitializationVectorLengthResolutionIr(
                source_base_type_resolution=base_resolution,
                source_vector_length_request=vector_length_request,
                resolved_vector_length=metadata.vector_length,
                unresolved_requests=unresolved_requests,
                source_location=base_resolution.source_location,
                candidate_id=base_resolution.candidate_id,
                target_extension=metadata.target_extension,
                source_extension=metadata.source_extension,
                selected_type_tag=base_resolution.selected_type_tag,
                originating_branch_chain_id=(
                    base_resolution.originating_branch_chain_id
                ),
                slot_label=base_resolution.slot_label,
                slot_ordinal=base_resolution.slot_ordinal,
                variable_token=base_resolution.variable_token,
            )
        )
    except (TypeError, ValueError) as exc:
        return Result.failure(
            (
                _array_initialization_vector_length_provenance_mismatch_diagnostic(
                    str(exc),
                    base_resolution.source_location,
                ),
            )
        )


def lower_exact_array_initialization_vector_alignment_request(
    source: object,
    context: GenerationContext | None = None,
    *,
    selected_candidate_id: str | None = None,
    target_extension: str | None = None,
    source_extension: str | None = None,
    selected_type_tag: str | None = None,
) -> Result[ExactArrayInitializationVectorAlignmentResolutionIr]:
    vector_length_result = _array_initialization_vector_alignment_resolution_source(
        source,
    )
    if not vector_length_result.is_ok:
        return Result.failure(vector_length_result.diagnostics)

    vector_length_resolution = vector_length_result.unwrap()
    diagnostics = _validate_array_initialization_vector_alignment_resolution_provenance(
        vector_length_resolution,
    )
    vector_alignment_request = _array_initialization_vector_alignment_request_record(
        vector_length_resolution,
        diagnostics,
    )
    if diagnostics:
        return Result.failure(sort_diagnostics(tuple(diagnostics)))
    if vector_alignment_request is None:
        raise AssertionError(
            "vector-alignment request diagnostics must be present when missing"
        )

    generation_context = context or GenerationContext()
    effective_candidate_id = (
        selected_candidate_id
        or generation_context.selected_candidate_id
        or vector_length_resolution.candidate_id
    )
    effective_target_extension = target_extension or vector_length_resolution.target_extension
    effective_source_extension = source_extension or vector_length_resolution.source_extension
    effective_type_tag = (
        selected_type_tag
        or generation_context.selected_type_tag
        or vector_length_resolution.selected_type_tag
    )
    if (
        effective_candidate_id != vector_length_resolution.candidate_id
        or effective_target_extension != vector_length_resolution.target_extension
        or effective_source_extension != vector_length_resolution.source_extension
        or effective_type_tag != vector_length_resolution.selected_type_tag
    ):
        return Result.failure(
            (
                _array_initialization_vector_alignment_context_mismatch_diagnostic(
                    "array-initialization vector-alignment request resolution "
                    "requires the typed selected candidate context to match "
                    "the M70 vector-length resolution candidate id, target "
                    "extension, source extension, and selected type tag",
                    vector_alignment_request.leaf_source_location,
                ),
            )
        )

    metadata_result = _array_initialization_vector_alignment_metadata_for_context(
        generation_context,
        candidate_id=vector_length_resolution.candidate_id,
        target_extension=vector_length_resolution.target_extension,
        source_extension=vector_length_resolution.source_extension,
        selected_type_tag=vector_length_resolution.selected_type_tag,
        location=vector_alignment_request.leaf_source_location,
    )
    if not metadata_result.is_ok:
        return Result.failure(metadata_result.diagnostics)
    metadata = metadata_result.unwrap()
    if metadata.vector_alignment.kind == "unsupported":
        return Result.failure(
            (
                _array_initialization_vector_alignment_metadata_unsupported_diagnostic(
                    "array-initialization vector-alignment request resolution "
                    "received explicit unsupported vector-alignment metadata "
                    f"policy {metadata.vector_alignment.unsupported_policy!r}",
                    metadata.source_location
                    or vector_alignment_request.leaf_source_location,
                ),
            )
        )

    unresolved_requests = tuple(
        request
        for request in vector_length_resolution.unresolved_requests
        if request is not vector_alignment_request
    )
    try:
        return Result.ok(
            ExactArrayInitializationVectorAlignmentResolutionIr(
                source_vector_length_resolution=vector_length_resolution,
                source_vector_alignment_request=vector_alignment_request,
                resolved_vector_alignment=metadata.vector_alignment,
                unresolved_requests=unresolved_requests,
                source_location=vector_length_resolution.source_location,
                candidate_id=vector_length_resolution.candidate_id,
                target_extension=vector_length_resolution.target_extension,
                source_extension=vector_length_resolution.source_extension,
                selected_type_tag=vector_length_resolution.selected_type_tag,
                originating_branch_chain_id=(
                    vector_length_resolution.originating_branch_chain_id
                ),
                slot_label=vector_length_resolution.slot_label,
                slot_ordinal=vector_length_resolution.slot_ordinal,
                variable_token=vector_length_resolution.variable_token,
            )
        )
    except (TypeError, ValueError) as exc:
        return Result.failure(
            (
                _array_initialization_vector_alignment_provenance_mismatch_diagnostic(
                    str(exc),
                    vector_length_resolution.source_location,
                ),
            )
        )


def lower_exact_array_initialization_helper_set_completion(
    source: object,
    context: GenerationContext | None = None,
    *,
    selected_candidate_id: str | None = None,
    target_extension: str | None = None,
    source_extension: str | None = None,
    selected_type_tag: str | None = None,
) -> Result[ExactArrayInitializationHelperSetCompletionIr]:
    vector_alignment_result = _array_initialization_helper_set_completion_source(
        source,
    )
    if not vector_alignment_result.is_ok:
        return Result.failure(vector_alignment_result.diagnostics)

    vector_alignment_resolution = vector_alignment_result.unwrap()
    diagnostics = _validate_array_initialization_helper_set_completion_provenance(
        vector_alignment_resolution,
    )
    backend_uninit_request = _array_initialization_backend_uninit_request_record(
        vector_alignment_resolution,
        diagnostics,
    )
    if diagnostics:
        return Result.failure(sort_diagnostics(tuple(diagnostics)))
    if backend_uninit_request is None:
        raise AssertionError(
            "backend-uninit request diagnostics must be present when missing"
        )

    generation_context = context or GenerationContext()
    effective_candidate_id = (
        selected_candidate_id
        or generation_context.selected_candidate_id
        or vector_alignment_resolution.candidate_id
    )
    effective_target_extension = (
        target_extension or vector_alignment_resolution.target_extension
    )
    effective_source_extension = (
        source_extension or vector_alignment_resolution.source_extension
    )
    effective_type_tag = (
        selected_type_tag
        or generation_context.selected_type_tag
        or vector_alignment_resolution.selected_type_tag
    )
    if (
        effective_candidate_id != vector_alignment_resolution.candidate_id
        or effective_target_extension != vector_alignment_resolution.target_extension
        or effective_source_extension != vector_alignment_resolution.source_extension
        or effective_type_tag != vector_alignment_resolution.selected_type_tag
    ):
        return Result.failure(
            (
                _array_initialization_helper_set_context_mismatch_diagnostic(
                    "array-initialization helper-set completion requires the "
                    "typed selected candidate context to match the M71 "
                    "vector-alignment resolution candidate id, target "
                    "extension, source extension, and selected type tag",
                    backend_uninit_request.leaf_source_location,
                ),
            )
        )

    try:
        deferred_backend_uninit = ExactArrayInitializationDeferredBackendUninitValue(
            source_backend_uninit_request=backend_uninit_request,
            policy="deferred_backend_value",
            source_location=backend_uninit_request.leaf_source_location,
            candidate_id=vector_alignment_resolution.candidate_id,
            target_extension=vector_alignment_resolution.target_extension,
            source_extension=vector_alignment_resolution.source_extension,
            selected_type_tag=vector_alignment_resolution.selected_type_tag,
            originating_branch_chain_id=(
                vector_alignment_resolution.originating_branch_chain_id
            ),
            slot_label=vector_alignment_resolution.slot_label,
            slot_ordinal=vector_alignment_resolution.slot_ordinal,
            variable_token=vector_alignment_resolution.variable_token,
        )
        return Result.ok(
            ExactArrayInitializationHelperSetCompletionIr(
                source_vector_alignment_resolution=vector_alignment_resolution,
                source_vector_length_resolution=(
                    vector_alignment_resolution.source_vector_length_resolution
                ),
                source_base_type_resolution=(
                    vector_alignment_resolution.source_vector_length_resolution
                    .source_base_type_resolution
                ),
                source_backend_uninit_request=backend_uninit_request,
                unresolved_backend_uninit=deferred_backend_uninit,
                source_location=vector_alignment_resolution.source_location,
                candidate_id=vector_alignment_resolution.candidate_id,
                target_extension=vector_alignment_resolution.target_extension,
                source_extension=vector_alignment_resolution.source_extension,
                selected_type_tag=vector_alignment_resolution.selected_type_tag,
                originating_branch_chain_id=(
                    vector_alignment_resolution.originating_branch_chain_id
                ),
                slot_label=vector_alignment_resolution.slot_label,
                slot_ordinal=vector_alignment_resolution.slot_ordinal,
                variable_token=vector_alignment_resolution.variable_token,
            )
        )
    except (TypeError, ValueError) as exc:
        return Result.failure(
            (
                _array_initialization_helper_set_provenance_mismatch_diagnostic(
                    str(exc),
                    vector_alignment_resolution.source_location,
                ),
            )
        )


def lower_exact_array_initialization_declaration_shell(
    source: object,
    context: GenerationContext | None = None,
    *,
    selected_candidate_id: str | None = None,
    target_extension: str | None = None,
    source_extension: str | None = None,
    selected_type_tag: str | None = None,
) -> Result[ExactArrayInitializationDeclarationShellIr]:
    completion_result = _array_initialization_declaration_shell_source(source)
    if not completion_result.is_ok:
        return Result.failure(completion_result.diagnostics)

    completion = completion_result.unwrap()
    diagnostics = _validate_array_initialization_declaration_shell(completion)
    if diagnostics:
        return Result.failure(sort_diagnostics(tuple(diagnostics)))

    generation_context = context or GenerationContext()
    effective_candidate_id = (
        selected_candidate_id
        or generation_context.selected_candidate_id
        or completion.candidate_id
    )
    effective_target_extension = target_extension or completion.target_extension
    effective_source_extension = source_extension or completion.source_extension
    effective_type_tag = (
        selected_type_tag
        or generation_context.selected_type_tag
        or completion.selected_type_tag
    )
    if (
        effective_candidate_id != completion.candidate_id
        or effective_target_extension != completion.target_extension
        or effective_source_extension != completion.source_extension
        or effective_type_tag != completion.selected_type_tag
    ):
        return Result.failure(
            (
                _array_initialization_declaration_shell_context_mismatch_diagnostic(
                    "array-initialization declaration-shell lowering requires "
                    "the typed selected candidate context to match the M72 "
                    "helper-set completion candidate id, target extension, "
                    "source extension, and selected type tag",
                    completion.source_location,
                ),
            )
        )

    source_slot_form = completion.source_base_type_resolution.source_request_ir.source_form
    source_envelope = source_slot_form.source_envelope
    try:
        return Result.ok(
            ExactArrayInitializationDeclarationShellIr(
                source_helper_set_completion=completion,
                source_slot_form=source_slot_form,
                source_envelope=source_envelope,
                declaration_kind="var<typed>",
                array_type_kind="array_type",
                base_type_ref=completion.source_base_type_resolution.resolved_type_ref,
                vector_length=(
                    completion.source_vector_length_resolution.resolved_vector_length
                ),
                vector_alignment=(
                    completion.source_vector_alignment_resolution
                    .resolved_vector_alignment
                ),
                unresolved_backend_uninit=completion.unresolved_backend_uninit,
                source_location=completion.source_location,
                candidate_id=completion.candidate_id,
                target_extension=completion.target_extension,
                source_extension=completion.source_extension,
                selected_type_tag=completion.selected_type_tag,
                originating_branch_chain_id=completion.originating_branch_chain_id,
                slot_label=completion.slot_label,
                slot_ordinal=completion.slot_ordinal,
                variable_token=completion.variable_token,
            )
        )
    except (TypeError, ValueError) as exc:
        return Result.failure(
            (
                _array_initialization_declaration_shell_provenance_mismatch_diagnostic(
                    str(exc),
                    completion.source_location,
                ),
            )
        )


def lower_exact_array_body_structural_sequence(
    source: object,
    declaration_shell: object | None = None,
    context: GenerationContext | None = None,
    *,
    selected_candidate_id: str | None = None,
    target_extension: str | None = None,
    source_extension: str | None = None,
    selected_type_tag: str | None = None,
) -> Result[ExactArrayBodyStructuralSequenceIr]:
    source_result = _array_body_structural_sequence_source(source, declaration_shell)
    if not source_result.is_ok:
        return Result.failure(source_result.diagnostics)
    envelope, shell = source_result.unwrap()

    diagnostics = _validate_array_body_structural_sequence_inputs(envelope, shell)
    if diagnostics:
        return Result.failure(sort_diagnostics(tuple(diagnostics)))

    generation_context = context or GenerationContext()
    effective_candidate_id = (
        selected_candidate_id
        or generation_context.selected_candidate_id
        or shell.candidate_id
    )
    effective_target_extension = target_extension or shell.target_extension
    effective_source_extension = source_extension or shell.source_extension
    effective_type_tag = (
        selected_type_tag
        or generation_context.selected_type_tag
        or shell.selected_type_tag
    )
    if (
        effective_candidate_id != shell.candidate_id
        or effective_target_extension != shell.target_extension
        or effective_source_extension != shell.source_extension
        or effective_type_tag != shell.selected_type_tag
    ):
        return Result.failure(
            (
                _array_body_structural_sequence_context_mismatch_diagnostic(
                    "array-body structural sequence classification requires "
                    "the typed selected candidate context to match the M73 "
                    "declaration shell candidate id, target extension, source "
                    "extension, and selected type tag",
                    shell.source_location,
                ),
            )
        )

    roles: list[_ExactArrayBodyStructuralRole] = []
    for role_label, slot in zip(
        _EXACT_ARRAY_BODY_STRUCTURAL_ROLE_LABELS,
        envelope.slots,
        strict=True,
    ):
        try:
            roles.append(
                _structural_role_from_slot(
                    role_label,
                    slot,
                    shell,
                    target_extension=shell.target_extension,
                    source_extension=shell.source_extension,
                )
            )
        except (TypeError, ValueError) as exc:
            return Result.failure(
                (
                    _array_body_structural_sequence_malformed_diagnostic(
                        str(exc),
                        slot.source_location,
                    ),
                )
            )

    try:
        return Result.ok(
            ExactArrayBodyStructuralSequenceIr(
                source_envelope=envelope,
                declaration_shell=shell,
                roles=tuple(roles),
                source_location=envelope.source_location,
                candidate_id=envelope.candidate_id,
                target_extension=shell.target_extension,
                source_extension=shell.source_extension,
                selected_type_tag=envelope.selected_type_tag,
                originating_branch_chain_id=envelope.originating_branch_chain_id,
            )
        )
    except (TypeError, ValueError) as exc:
        return Result.failure(
            (
                _array_body_structural_sequence_malformed_diagnostic(
                    str(exc),
                    envelope.source_location,
                ),
            )
        )


def resolve_generation_type_query(
    query_text: str,
    context: GenerationContext | None = None,
    *,
    selected_candidate_type_tag: str | None = None,
    location: SourceLocation | None = None,
) -> Result[GenerationTypeRef]:
    generation_context = context or GenerationContext()
    diagnostic_location = (
        location
        if location is not None
        else generation_context.implementation_source_location
    )
    query = query_text.strip()
    inner = _generation_type_query_inner(query, diagnostic_location)
    if not inner.is_ok:
        return Result.failure(inner.diagnostics)
    return _generation_type_ref_from_inner(
        inner.unwrap(),
        query,
        generation_context,
        selected_candidate_type_tag=selected_candidate_type_tag,
        location=diagnostic_location,
    )


def resolve_generation_value_query(
    query_text: str,
    context: GenerationContext | None = None,
    *,
    selected_candidate_type_tag: str | None = None,
    location: SourceLocation | None = None,
) -> Result[GenerationValue]:
    generation_context = context or GenerationContext()
    diagnostic_location = (
        location
        if location is not None
        else generation_context.implementation_source_location
    )
    query = query_text.strip()
    size_bits = _generation_size_bits_value_expression(
        query,
        generation_context,
        selected_candidate_type_tag=selected_candidate_type_tag,
        location=diagnostic_location,
    )
    if size_bits is not None:
        return size_bits
    inner = _generation_value_query_inner(query, diagnostic_location)
    if not inner.is_ok:
        return Result.failure(inner.diagnostics)
    return _generation_value_from_inner(
        inner.unwrap(),
        query,
        generation_context,
        selected_candidate_type_tag=selected_candidate_type_tag,
        location=diagnostic_location,
    )


def resolve_generation_predicate_query(
    query_text: str,
    context: GenerationContext | None = None,
    *,
    selected_candidate_type_tag: str | None = None,
    location: SourceLocation | None = None,
) -> Result[GenerationPredicate]:
    generation_context = context or GenerationContext()
    diagnostic_location = (
        location
        if location is not None
        else generation_context.implementation_source_location
    )
    staged = _resolve_generation_predicate_query_staged(
        query_text,
        generation_context,
        selected_candidate_type_tag=selected_candidate_type_tag,
        location=diagnostic_location,
    )
    if not staged.is_ok:
        return Result.failure(staged.diagnostics)
    return Result.ok(staged.unwrap().predicate)


@dataclass(frozen=True, slots=True)
class _StagedGenerationPredicate:
    predicate: GenerationPredicate
    generation_values: tuple[GenerationValue, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "generation_values", tuple(self.generation_values))


@dataclass(frozen=True, slots=True)
class _StagedGenerationSizeByteBranchChain:
    pruning: GenerationSizeByteBranchChainPruning
    generation_values: tuple[GenerationValue, ...] = ()
    generation_predicates: tuple[GenerationPredicate, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "generation_values", tuple(self.generation_values))
        object.__setattr__(
            self,
            "generation_predicates",
            tuple(self.generation_predicates),
        )


@dataclass(frozen=True, slots=True)
class _ExactArrayInitializationStagePipelineResult:
    array_body_envelopes: tuple[ExactArrayBodyEnvelopeIr, ...] = ()
    array_initialization_slot_forms: tuple[
        ExactArrayInitializationSlotFormIr, ...
    ] = ()
    array_initialization_helper_requests: tuple[
        ExactArrayInitializationHelperRequestIr, ...
    ] = ()
    array_initialization_base_type_resolutions: tuple[
        ExactArrayInitializationBaseTypeResolutionIr, ...
    ] = ()
    array_initialization_vector_length_resolutions: tuple[
        ExactArrayInitializationVectorLengthResolutionIr, ...
    ] = ()
    array_initialization_vector_alignment_resolutions: tuple[
        ExactArrayInitializationVectorAlignmentResolutionIr, ...
    ] = ()
    array_initialization_helper_set_completions: tuple[
        ExactArrayInitializationHelperSetCompletionIr, ...
    ] = ()
    array_initialization_declaration_shells: tuple[
        ExactArrayInitializationDeclarationShellIr, ...
    ] = ()
    array_body_structural_sequences: tuple[
        ExactArrayBodyStructuralSequenceIr, ...
    ] = ()
    predicate_path_structural_requests: tuple[
        ExactPredicatePathStructuralRequestIr, ...
    ] = ()
    stages: tuple[GenerationLoweringStage, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "array_body_envelopes",
            tuple(self.array_body_envelopes),
        )
        object.__setattr__(
            self,
            "array_initialization_slot_forms",
            tuple(self.array_initialization_slot_forms),
        )
        object.__setattr__(
            self,
            "array_initialization_helper_requests",
            tuple(self.array_initialization_helper_requests),
        )
        object.__setattr__(
            self,
            "array_initialization_base_type_resolutions",
            tuple(self.array_initialization_base_type_resolutions),
        )
        object.__setattr__(
            self,
            "array_initialization_vector_length_resolutions",
            tuple(self.array_initialization_vector_length_resolutions),
        )
        object.__setattr__(
            self,
            "array_initialization_vector_alignment_resolutions",
            tuple(self.array_initialization_vector_alignment_resolutions),
        )
        object.__setattr__(
            self,
            "array_initialization_helper_set_completions",
            tuple(self.array_initialization_helper_set_completions),
        )
        object.__setattr__(
            self,
            "array_initialization_declaration_shells",
            tuple(self.array_initialization_declaration_shells),
        )
        object.__setattr__(
            self,
            "array_body_structural_sequences",
            tuple(self.array_body_structural_sequences),
        )
        object.__setattr__(
            self,
            "predicate_path_structural_requests",
            tuple(self.predicate_path_structural_requests),
        )
        object.__setattr__(self, "stages", tuple(self.stages))

    @property
    def key(self) -> tuple[object, ...]:
        return (
            tuple(envelope.key for envelope in self.array_body_envelopes),
            tuple(form.key for form in self.array_initialization_slot_forms),
            tuple(
                request.key
                for request in self.array_initialization_helper_requests
            ),
            tuple(
                resolution.key
                for resolution in self.array_initialization_base_type_resolutions
            ),
            tuple(
                resolution.key
                for resolution in (
                    self.array_initialization_vector_length_resolutions
                )
            ),
            tuple(
                resolution.key
                for resolution in (
                    self.array_initialization_vector_alignment_resolutions
                )
            ),
            tuple(
                completion.key
                for completion in self.array_initialization_helper_set_completions
            ),
            tuple(
                shell.key
                for shell in self.array_initialization_declaration_shells
            ),
            tuple(
                sequence.key
                for sequence in self.array_body_structural_sequences
            ),
            tuple(
                request.key
                for request in self.predicate_path_structural_requests
            ),
            tuple(stage.key for stage in self.stages),
        )


def _recognition_stage(
    kind: GenerationRecognitionKind,
    source_text: str,
) -> GenerationLoweringStage:
    return GenerationLoweringStage(
        stage="helper_expression_recognition",
        output=GenerationExpressionRecognition(
            kind=kind,
            source_text=source_text.strip(),
        ),
    )


def _generation_value_stage(value: GenerationValue) -> GenerationLoweringStage:
    return GenerationLoweringStage(stage="typed_generation_value", output=value)


def _generation_predicate_stage(
    predicate: GenerationPredicate,
) -> GenerationLoweringStage:
    return GenerationLoweringStage(
        stage="typed_generation_predicate",
        output=predicate,
    )


def _generation_control_flow_stage(
    branch: PrunedGenerationBranch | GenerationSizeByteBranchChainPruning,
) -> GenerationLoweringStage:
    return GenerationLoweringStage(
        stage="generation_control_flow_pruning",
        output=branch,
    )


def _selected_body_stage(
    output: TsilStatement | GenerationSelectedBranchBodyHandoff,
) -> GenerationLoweringStage:
    return GenerationLoweringStage(stage="selected_body_lowering", output=output)


def _selected_body_form_recognition_stage(
    output: GenerationSelectedBranchBodyAssignmentRecognition,
) -> GenerationLoweringStage:
    return GenerationLoweringStage(
        stage="selected_body_form_recognition",
        output=output,
    )


def _selected_body_ir_stage(
    output: GenerationSelectedBranchBodyIr,
) -> GenerationLoweringStage:
    return GenerationLoweringStage(
        stage="selected_body_ir_lowering",
        output=output,
    )


def _selected_body_envelope_stage(
    output: GenerationSelectedBodyEnvelopeIr,
) -> GenerationLoweringStage:
    return GenerationLoweringStage(
        stage="selected_body_envelope_lowering",
        output=output,
    )


def _array_body_envelope_slot_assembly_stage(
    output: ExactArrayBodyEnvelopeIr,
) -> GenerationLoweringStage:
    return GenerationLoweringStage(
        stage="array_body_envelope_slot_assembly",
        output=output,
    )


def _array_initialization_slot_form_stage(
    output: ExactArrayInitializationSlotFormIr,
) -> GenerationLoweringStage:
    return GenerationLoweringStage(
        stage="array_initialization_slot_form_lowering",
        output=output,
    )


def _array_initialization_helper_request_stage(
    output: ExactArrayInitializationHelperRequestIr,
) -> GenerationLoweringStage:
    return GenerationLoweringStage(
        stage="array_initialization_helper_request_lowering",
        output=output,
    )


def _array_initialization_base_type_resolution_stage(
    output: ExactArrayInitializationBaseTypeResolutionIr,
) -> GenerationLoweringStage:
    return GenerationLoweringStage(
        stage="array_initialization_base_type_request_resolution",
        output=output,
    )


def _array_initialization_vector_length_resolution_stage(
    output: ExactArrayInitializationVectorLengthResolutionIr,
) -> GenerationLoweringStage:
    return GenerationLoweringStage(
        stage="array_initialization_vector_length_request_resolution",
        output=output,
    )


def _array_initialization_vector_alignment_resolution_stage(
    output: ExactArrayInitializationVectorAlignmentResolutionIr,
) -> GenerationLoweringStage:
    return GenerationLoweringStage(
        stage="array_initialization_vector_alignment_request_resolution",
        output=output,
    )


def _array_initialization_helper_set_completion_stage(
    output: ExactArrayInitializationHelperSetCompletionIr,
) -> GenerationLoweringStage:
    return GenerationLoweringStage(
        stage="array_initialization_helper_set_completion",
        output=output,
    )


def _array_initialization_declaration_shell_stage(
    output: ExactArrayInitializationDeclarationShellIr,
) -> GenerationLoweringStage:
    return GenerationLoweringStage(
        stage="array_initialization_declaration_shell_lowering",
        output=output,
    )


def _array_body_structural_sequence_stage(
    output: ExactArrayBodyStructuralSequenceIr,
) -> GenerationLoweringStage:
    return GenerationLoweringStage(
        stage="array_body_structural_sequence_classification",
        output=output,
    )


def _predicate_path_structural_request_stage(
    output: ExactPredicatePathStructuralRequestIr,
) -> GenerationLoweringStage:
    return GenerationLoweringStage(
        stage="predicate_path_structural_request_lowering",
        output=output,
    )


def _stage_output_location(
    output: GenerationLoweringStageOutput,
) -> SourceLocation | None:
    if isinstance(
        output,
        (
            PrunedGenerationBranch,
            GenerationSizeByteBranchChainPruning,
        ),
    ):
        return output.condition_location
    if isinstance(output, SelectedBranchBodyAssignmentFormRecognition):
        return output.selected_statement_location
    if isinstance(
        output,
        (
            OpaqueSelectedBranchBodyHandoff,
            NoSelectedBranchBodyHandoff,
            NoSelectedBranchBodyAssignmentFormRecognition,
            SelectedAssignmentDirectIntrinsicBodyIr,
            NoSelectedAssignmentDirectIntrinsicBodyIr,
            SelectedBodyEnvelopeIr,
            NoSelectedBodyEnvelopeIr,
            ExactArrayBodyEnvelopeIr,
            ExactArrayInitializationSlotFormIr,
            ExactArrayInitializationHelperRequestIr,
            ExactArrayInitializationBaseTypeResolutionIr,
            ExactArrayInitializationVectorLengthResolutionIr,
            ExactArrayInitializationVectorAlignmentResolutionIr,
            ExactArrayInitializationHelperSetCompletionIr,
            ExactArrayInitializationDeclarationShellIr,
            ExactArrayBodyStructuralSequenceIr,
            ExactPredicatePathStructuralRequestIr,
        ),
    ):
        return output.source_location
    return None


def _originating_branch_chain_id(
    candidate_id: str,
    pruning: GenerationSizeByteBranchChainPruning,
) -> str:
    location_key = (
        pruning.condition_location.sort_key()
        if pruning.condition_location is not None
        else ("", 0, 0, 0, 0)
    )
    literal_key = ",".join(str(arm.literal) for arm in pruning.arms)
    return (
        f"{candidate_id}:generation-size-byte-branch-chain:"
        f"{pruning.type_tag}:{literal_key}:{location_key}"
    )


def _array_body_envelope_skeleton_lookup_key(
    skeleton: ExactArrayBodyEnvelopeSkeleton,
) -> ExactArrayBodyEnvelopeSkeletonKey:
    return ExactArrayBodyEnvelopeSkeletonKey(
        candidate_id=skeleton.candidate_id,
        selected_type_tag=skeleton.selected_type_tag,
        originating_branch_chain_id=skeleton.originating_branch_chain_id,
    )


def _array_body_envelope_m63_lookup_key(
    envelope: GenerationSelectedBodyEnvelopeIr,
) -> ExactArrayBodyEnvelopeSkeletonKey:
    return ExactArrayBodyEnvelopeSkeletonKey(
        candidate_id=envelope.candidate_id,
        selected_type_tag=envelope.selected_type_tag,
        originating_branch_chain_id=envelope.originating_branch_chain_id,
    )


def _build_array_body_envelope_skeleton_lookup(
    request: LoweringRequest,
) -> Result[_ArrayBodyEnvelopeSkeletonLookup]:
    diagnostics: list[Diagnostic] = []
    skeletons_by_key: dict[
        ExactArrayBodyEnvelopeSkeletonKey,
        ExactArrayBodyEnvelopeSkeleton,
    ] = {}
    for skeleton in request.array_body_envelope_skeletons:
        lookup_key = _array_body_envelope_skeleton_lookup_key(skeleton)
        existing = skeletons_by_key.get(lookup_key)
        if existing is None:
            skeletons_by_key[lookup_key] = skeleton
            continue
        diagnostics.append(
            _duplicate_array_body_envelope_skeleton_diagnostic(
                lookup_key,
                skeleton,
                conflicting=existing != skeleton,
            )
        )

    requirements_by_key: dict[
        ExactArrayBodyEnvelopeSkeletonKey,
        ExactArrayBodyEnvelopeSkeletonRequirement,
    ] = {}
    for requirement in request.required_array_body_envelope_skeletons:
        requirements_by_key.setdefault(requirement.lookup_key, requirement)

    ordered = sort_diagnostics(diagnostics)
    if has_errors(ordered):
        return Result.failure(ordered)
    return Result.ok(
        _ArrayBodyEnvelopeSkeletonLookup(
            skeletons=tuple(
                sorted(
                    skeletons_by_key.items(),
                    key=lambda item: item[0].key,
                )
            ),
            requirements=tuple(
                sorted(
                    requirements_by_key.items(),
                    key=lambda item: item[0].key,
                )
            ),
        ),
        diagnostics=ordered,
    )


def _assemble_matching_array_body_envelope(
    envelope_stage: GenerationLoweringStage,
    skeleton_lookup: _ArrayBodyEnvelopeSkeletonLookup,
) -> Result[ExactArrayBodyEnvelopeIr | None]:
    if not isinstance(
        envelope_stage.output,
        (SelectedBodyEnvelopeIr, NoSelectedBodyEnvelopeIr),
    ):
        raise TypeError("array-body envelope integration requires an M63 stage")

    lookup_key = _array_body_envelope_m63_lookup_key(envelope_stage.output)
    skeleton = skeleton_lookup.skeleton_for(lookup_key)
    if skeleton is None:
        requirement = skeleton_lookup.requirement_for(lookup_key)
        if requirement is None:
            return Result.ok(None)
        return Result.failure(
            (
                _missing_array_body_envelope_skeleton_diagnostic(
                    requirement,
                    envelope_stage.output,
                ),
            )
        )

    assembled = assemble_exact_array_body_envelope(envelope_stage, skeleton)
    if not assembled.is_ok:
        return Result.failure(assembled.diagnostics)
    return Result.ok(assembled.unwrap())


def _lower_exact_array_initialization_stage_pipeline(
    item: LoweringInput,
    request: LoweringRequest,
    envelope_stage: GenerationLoweringStage,
    skeleton_lookup: _ArrayBodyEnvelopeSkeletonLookup,
) -> Result[_ExactArrayInitializationStagePipelineResult]:
    array_envelope_result = _assemble_matching_array_body_envelope(
        envelope_stage,
        skeleton_lookup,
    )
    if not array_envelope_result.is_ok:
        return Result.failure(array_envelope_result.diagnostics)
    array_envelope = array_envelope_result.unwrap()
    if array_envelope is None:
        return Result.ok(_ExactArrayInitializationStagePipelineResult())

    array_body_stage = _array_body_envelope_slot_assembly_stage(array_envelope)
    array_initialization_slot_form_result = (
        lower_exact_array_initialization_slot_form(array_envelope)
    )
    if not array_initialization_slot_form_result.is_ok:
        return Result.failure(array_initialization_slot_form_result.diagnostics)
    array_initialization_slot_form = array_initialization_slot_form_result.unwrap()
    array_initialization_slot_form_stage = _array_initialization_slot_form_stage(
        array_initialization_slot_form,
    )

    array_initialization_helper_request_result = (
        lower_exact_array_initialization_helper_requests(
            array_initialization_slot_form,
        )
    )
    if not array_initialization_helper_request_result.is_ok:
        return Result.failure(array_initialization_helper_request_result.diagnostics)
    array_initialization_helper_request = (
        array_initialization_helper_request_result.unwrap()
    )
    array_initialization_helper_request_stage = (
        _array_initialization_helper_request_stage(
            array_initialization_helper_request,
        )
    )

    base_type_resolution_result = lower_exact_array_initialization_base_type_request(
        array_initialization_helper_request,
        _context_for_candidate(item, request),
        selected_candidate_type_tag=(
            item.candidate.type_tag
            if request.generation_context.use_candidate_type_tag
            else None
        ),
    )
    if not base_type_resolution_result.is_ok:
        return Result.failure(base_type_resolution_result.diagnostics)
    base_type_resolution = base_type_resolution_result.unwrap()
    base_type_resolution_stage = _array_initialization_base_type_resolution_stage(
        base_type_resolution,
    )
    vector_length_resolution_result = (
        lower_exact_array_initialization_vector_length_request(
            base_type_resolution,
            _context_for_candidate(item, request),
            selected_candidate_id=item.candidate_id,
            target_extension=item.candidate.target_extension,
            source_extension=item.candidate.source_extension,
            selected_type_tag=(
                item.candidate.type_tag
                if request.generation_context.use_candidate_type_tag
                else None
            ),
        )
    )
    if not vector_length_resolution_result.is_ok:
        return Result.failure(vector_length_resolution_result.diagnostics)
    vector_length_resolution = vector_length_resolution_result.unwrap()
    vector_length_resolution_stage = (
        _array_initialization_vector_length_resolution_stage(
            vector_length_resolution,
        )
    )
    vector_alignment_resolution_result = (
        lower_exact_array_initialization_vector_alignment_request(
            vector_length_resolution,
            _context_for_candidate(item, request),
            selected_candidate_id=item.candidate_id,
            target_extension=item.candidate.target_extension,
            source_extension=item.candidate.source_extension,
            selected_type_tag=(
                item.candidate.type_tag
                if request.generation_context.use_candidate_type_tag
                else None
            ),
        )
    )
    if not vector_alignment_resolution_result.is_ok:
        return Result.failure(vector_alignment_resolution_result.diagnostics)
    vector_alignment_resolution = vector_alignment_resolution_result.unwrap()
    vector_alignment_resolution_stage = (
        _array_initialization_vector_alignment_resolution_stage(
            vector_alignment_resolution,
        )
    )
    helper_set_completion_result = lower_exact_array_initialization_helper_set_completion(
        vector_alignment_resolution,
        _context_for_candidate(item, request),
        selected_candidate_id=item.candidate_id,
        target_extension=item.candidate.target_extension,
        source_extension=item.candidate.source_extension,
        selected_type_tag=(
            item.candidate.type_tag
            if request.generation_context.use_candidate_type_tag
            else None
        ),
    )
    if not helper_set_completion_result.is_ok:
        return Result.failure(helper_set_completion_result.diagnostics)
    helper_set_completion = helper_set_completion_result.unwrap()
    helper_set_completion_stage = _array_initialization_helper_set_completion_stage(
        helper_set_completion,
    )
    declaration_shell_result = lower_exact_array_initialization_declaration_shell(
        helper_set_completion,
        _context_for_candidate(item, request),
        selected_candidate_id=item.candidate_id,
        target_extension=item.candidate.target_extension,
        source_extension=item.candidate.source_extension,
        selected_type_tag=(
            item.candidate.type_tag
            if request.generation_context.use_candidate_type_tag
            else None
        ),
    )
    if not declaration_shell_result.is_ok:
        return Result.failure(declaration_shell_result.diagnostics)
    declaration_shell = declaration_shell_result.unwrap()
    declaration_shell_stage = _array_initialization_declaration_shell_stage(
        declaration_shell,
    )
    structural_sequence_result = lower_exact_array_body_structural_sequence(
        array_envelope,
        declaration_shell,
        _context_for_candidate(item, request),
        selected_candidate_id=item.candidate_id,
        target_extension=item.candidate.target_extension,
        source_extension=item.candidate.source_extension,
        selected_type_tag=(
            item.candidate.type_tag
            if request.generation_context.use_candidate_type_tag
            else None
        ),
    )
    if not structural_sequence_result.is_ok:
        return Result.failure(structural_sequence_result.diagnostics)
    structural_sequence = structural_sequence_result.unwrap()
    structural_sequence_stage = _array_body_structural_sequence_stage(
        structural_sequence,
    )
    predicate_path_result = lower_exact_predicate_path_structural_request(
        structural_sequence_stage,
        _context_for_candidate(item, request),
        selected_candidate_id=item.candidate_id,
        target_extension=item.candidate.target_extension,
        source_extension=item.candidate.source_extension,
        selected_type_tag=(
            item.candidate.type_tag
            if request.generation_context.use_candidate_type_tag
            else None
        ),
    )
    if not predicate_path_result.is_ok:
        return Result.failure(predicate_path_result.diagnostics)
    predicate_path = predicate_path_result.unwrap()
    predicate_path_stage = _predicate_path_structural_request_stage(predicate_path)

    return Result.ok(
        _ExactArrayInitializationStagePipelineResult(
            array_body_envelopes=(array_envelope,),
            array_initialization_slot_forms=(array_initialization_slot_form,),
            array_initialization_helper_requests=(
                array_initialization_helper_request,
            ),
            array_initialization_base_type_resolutions=(base_type_resolution,),
            array_initialization_vector_length_resolutions=(
                vector_length_resolution,
            ),
            array_initialization_vector_alignment_resolutions=(
                vector_alignment_resolution,
            ),
            array_initialization_helper_set_completions=(
                helper_set_completion,
            ),
            array_initialization_declaration_shells=(
                declaration_shell,
            ),
            array_body_structural_sequences=(
                structural_sequence,
            ),
            predicate_path_structural_requests=(
                predicate_path,
            ),
            stages=(
                array_body_stage,
                array_initialization_slot_form_stage,
                array_initialization_helper_request_stage,
                base_type_resolution_stage,
                vector_length_resolution_stage,
                vector_alignment_resolution_stage,
                helper_set_completion_stage,
                declaration_shell_stage,
                structural_sequence_stage,
                predicate_path_stage,
            ),
        )
    )


def _unused_array_body_envelope_skeleton_diagnostics(
    skeleton_lookup: _ArrayBodyEnvelopeSkeletonLookup,
    implementations: tuple[LoweredImplementation, ...],
) -> tuple[Diagnostic, ...]:
    if not skeleton_lookup.skeleton_keys:
        return ()

    envelope_keys = tuple(
        _array_body_envelope_m63_lookup_key(envelope)
        for implementation in implementations
        for envelope in implementation.selected_body_envelopes
    )
    used_keys = {
        ExactArrayBodyEnvelopeSkeletonKey(
            candidate_id=envelope.candidate_id,
            selected_type_tag=envelope.selected_type_tag,
            originating_branch_chain_id=envelope.originating_branch_chain_id,
        )
        for implementation in implementations
        for envelope in implementation.array_body_envelopes
    }
    diagnostics: list[Diagnostic] = []
    for skeleton_key in skeleton_lookup.skeleton_keys:
        if skeleton_key in used_keys:
            continue
        skeleton = skeleton_lookup.skeleton_for(skeleton_key)
        if skeleton is None:
            raise AssertionError("array-body skeleton lookup key disappeared")
        if any(
            envelope_key.candidate_id == skeleton_key.candidate_id
            for envelope_key in envelope_keys
        ):
            diagnostics.append(
                _mismatched_array_body_envelope_skeleton_diagnostic(
                    skeleton_key,
                    skeleton,
                    envelope_keys,
                )
            )
            continue
        diagnostics.append(
            _orphan_array_body_envelope_skeleton_diagnostic(skeleton_key, skeleton)
        )
    return tuple(diagnostics)


def _selected_body_assignment_handoff_source(
    source: GenerationSelectedBranchBodyHandoff | GenerationLoweringStage,
) -> Result[GenerationSelectedBranchBodyHandoff]:
    if isinstance(source, (OpaqueSelectedBranchBodyHandoff, NoSelectedBranchBodyHandoff)):
        return Result.ok(source)
    if (
        source.stage == "selected_body_lowering"
        and isinstance(
            source.output,
            (OpaqueSelectedBranchBodyHandoff, NoSelectedBranchBodyHandoff),
        )
    ):
        return Result.ok(source.output)
    return Result.failure(
        (
            Diagnostic.error(
                "TSL-LOWER-SELECTED-BODY-FORM-SOURCE-UNSUPPORTED",
                "selected-body assignment-form recognition consumes only typed "
                "OpaqueSelectedBranchBodyHandoff or NoSelectedBranchBodyHandoff "
                "values, or the selected_body_lowering stage output containing "
                "one of those values",
                location=_stage_output_location(source.output),
            ),
        )
    )


def _selected_body_ir_recognition_source(
    source: GenerationSelectedBranchBodyAssignmentRecognition | GenerationLoweringStage,
) -> Result[GenerationSelectedBranchBodyAssignmentRecognition]:
    if isinstance(
        source,
        (
            SelectedBranchBodyAssignmentFormRecognition,
            NoSelectedBranchBodyAssignmentFormRecognition,
        ),
    ):
        return Result.ok(source)
    if (
        source.stage == "selected_body_form_recognition"
        and isinstance(
            source.output,
            (
                SelectedBranchBodyAssignmentFormRecognition,
                NoSelectedBranchBodyAssignmentFormRecognition,
            ),
        )
    ):
        return Result.ok(source.output)
    return Result.failure(
        (
            Diagnostic.error(
                "TSL-LOWER-SELECTED-BODY-IR-SOURCE-UNSUPPORTED",
                "selected-body IR lowering consumes only typed "
                "SelectedBranchBodyAssignmentFormRecognition or "
                "NoSelectedBranchBodyAssignmentFormRecognition values, or the "
                "selected_body_form_recognition stage output containing one "
                "of those values",
                location=_stage_output_location(source.output),
            ),
        )
    )


def _selected_body_envelope_source(
    source: GenerationSelectedBranchBodyIr | GenerationLoweringStage,
) -> Result[GenerationSelectedBranchBodyIr]:
    if isinstance(
        source,
        (
            SelectedAssignmentDirectIntrinsicBodyIr,
            NoSelectedAssignmentDirectIntrinsicBodyIr,
        ),
    ):
        return Result.ok(source)
    if isinstance(source, GenerationLoweringStage):
        if (
            source.stage == "selected_body_ir_lowering"
            and isinstance(
                source.output,
                (
                    SelectedAssignmentDirectIntrinsicBodyIr,
                    NoSelectedAssignmentDirectIntrinsicBodyIr,
                ),
            )
        ):
            return Result.ok(source.output)
        location = _stage_output_location(source.output)
    else:
        location = None
    return Result.failure(
        (
            Diagnostic.error(
                "TSL-LOWER-SELECTED-BODY-ENVELOPE-SOURCE-UNSUPPORTED",
                "selected-body envelope lowering consumes only typed "
                "SelectedAssignmentDirectIntrinsicBodyIr or "
                "NoSelectedAssignmentDirectIntrinsicBodyIr values, or the "
                "selected_body_ir_lowering stage output containing one of "
                "those M62 values",
                location=location,
            ),
        )
    )


def _array_body_envelope_m63_source(
    source: GenerationSelectedBodyEnvelopeIr | GenerationLoweringStage,
) -> Result[GenerationSelectedBodyEnvelopeIr]:
    if isinstance(source, (SelectedBodyEnvelopeIr, NoSelectedBodyEnvelopeIr)):
        return Result.ok(source)
    if isinstance(source, GenerationLoweringStage):
        if (
            source.stage == "selected_body_envelope_lowering"
            and isinstance(source.output, (SelectedBodyEnvelopeIr, NoSelectedBodyEnvelopeIr))
        ):
            return Result.ok(source.output)
        location = _stage_output_location(source.output)
    else:
        location = None
    return Result.failure(
        (
            Diagnostic.error(
                "TSL-LOWER-ARRAY-BODY-ENVELOPE-SOURCE-UNSUPPORTED",
                "array-body envelope slot assembly consumes only typed M63 "
                "SelectedBodyEnvelopeIr or NoSelectedBodyEnvelopeIr values, "
                "or the selected_body_envelope_lowering stage output "
                "containing one of those M63 values",
                location=location,
            ),
        )
    )


def _array_initialization_slot_form_source(
    source: object,
) -> Result[ExactArrayBodyEnvelopeIr]:
    if isinstance(source, ExactArrayBodyEnvelopeIr):
        return Result.ok(source)
    if isinstance(source, GenerationLoweringStage):
        if (
            source.stage == "array_body_envelope_slot_assembly"
            and isinstance(source.output, ExactArrayBodyEnvelopeIr)
        ):
            return Result.ok(source.output)
        location = _stage_output_location(source.output)
        return Result.failure(
            (
                _array_initialization_slot_source_unsupported_diagnostic(
                    "array-initialization slot form lowering consumes only "
                    "typed M65 ExactArrayBodyEnvelopeIr values, the "
                    "array_body_envelope_slot_assembly stage output, or a "
                    "LoweredImplementation with a matching M65 envelope",
                    location,
                ),
            )
        )
    if isinstance(source, LoweredImplementation):
        if len(source.array_body_envelopes) == 1:
            return Result.ok(source.array_body_envelopes[0])
        if len(source.array_body_envelopes) == 0:
            return Result.failure(
                (
                    _array_initialization_slot_missing_diagnostic(
                        "array-initialization slot form lowering requires a "
                        "LoweredImplementation carrying an accepted M65 "
                        "array_body_envelopes entry",
                        _lowered_implementation_location(source),
                    ),
                )
            )
        return Result.failure(
            (
                _array_initialization_slot_source_unsupported_diagnostic(
                    "array-initialization slot form lowering consumes exactly "
                    "one M65 array-body envelope at this boundary",
                    _lowered_implementation_location(source),
                ),
            )
        )
    return Result.failure(
        (
            _array_initialization_slot_source_unsupported_diagnostic(
                "array-initialization slot form lowering consumes only typed "
                "M65 ExactArrayBodyEnvelopeIr values or "
                "array_body_envelope_slot_assembly stage output",
                None,
            ),
        )
    )


def _array_initialization_helper_request_source(
    source: object,
) -> Result[ExactArrayInitializationSlotFormIr]:
    if isinstance(source, ExactArrayInitializationSlotFormIr):
        return Result.ok(source)
    if isinstance(source, GenerationLoweringStage):
        if (
            source.stage == "array_initialization_slot_form_lowering"
            and isinstance(source.output, ExactArrayInitializationSlotFormIr)
        ):
            return Result.ok(source.output)
        return Result.failure(
            (
                _array_initialization_helper_request_source_unsupported_diagnostic(
                    "array-initialization helper request lowering consumes only "
                    "typed M66 ExactArrayInitializationSlotFormIr values, the "
                    "array_initialization_slot_form_lowering stage output, or "
                    "a LoweredImplementation with a matching M66 form",
                    _stage_output_location(source.output),
                ),
            )
        )
    if isinstance(source, LoweredImplementation):
        if len(source.array_initialization_slot_forms) == 1:
            return Result.ok(source.array_initialization_slot_forms[0])
        if len(source.array_initialization_slot_forms) == 0:
            return Result.failure(
                (
                    _array_initialization_helper_request_missing_form_diagnostic(
                        "array-initialization helper request lowering requires "
                        "a LoweredImplementation carrying an accepted M66 "
                        "array_initialization_slot_forms entry",
                        _lowered_implementation_location(source),
                    ),
                )
            )
        return Result.failure(
            (
                _array_initialization_helper_request_source_unsupported_diagnostic(
                    "array-initialization helper request lowering consumes "
                    "exactly one M66 array-initialization slot form at this "
                    "boundary",
                    _lowered_implementation_location(source),
                ),
            )
        )
    return Result.failure(
        (
            _array_initialization_helper_request_source_unsupported_diagnostic(
                "array-initialization helper request lowering consumes only "
                "typed M66 ExactArrayInitializationSlotFormIr values or "
                "array_initialization_slot_form_lowering stage output",
                None,
            ),
        )
    )


def _array_initialization_base_type_resolution_source(
    source: object,
) -> Result[ExactArrayInitializationHelperRequestIr]:
    if isinstance(source, ExactArrayInitializationHelperRequestIr):
        return Result.ok(source)
    if isinstance(source, GenerationLoweringStage):
        if (
            source.stage == "array_initialization_helper_request_lowering"
            and isinstance(source.output, ExactArrayInitializationHelperRequestIr)
        ):
            return Result.ok(source.output)
        return Result.failure(
            (
                _array_initialization_base_type_resolution_source_unsupported_diagnostic(
                    "array-initialization base-type request resolution consumes "
                    "typed M67 ExactArrayInitializationHelperRequestIr values, "
                    "the array_initialization_helper_request_lowering stage "
                    "output, or a LoweredImplementation with a matching M67 "
                    "helper-request IR",
                    _stage_output_location(source.output),
                ),
            )
        )
    if isinstance(source, LoweredImplementation):
        if len(source.array_initialization_helper_requests) == 1:
            return Result.ok(source.array_initialization_helper_requests[0])
        if len(source.array_initialization_helper_requests) == 0:
            return Result.failure(
                (
                    _array_initialization_base_type_resolution_missing_ir_diagnostic(
                        "array-initialization base-type request resolution "
                        "requires a LoweredImplementation carrying an accepted "
                        "M67 array_initialization_helper_requests entry",
                        _lowered_implementation_location(source),
                    ),
                )
            )
        return Result.failure(
            (
                _array_initialization_base_type_resolution_multiple_ir_diagnostic(
                    "array-initialization base-type request resolution requires "
                    "exactly one M67 array_initialization_helper_requests "
                    f"entry; got {len(source.array_initialization_helper_requests)}",
                    _lowered_implementation_location(source),
                ),
            )
        )
    return Result.failure(
        (
            _array_initialization_base_type_resolution_source_unsupported_diagnostic(
                "array-initialization base-type request resolution consumes "
                "typed M67 ExactArrayInitializationHelperRequestIr values or "
                "array_initialization_helper_request_lowering stage output",
                None,
            ),
        )
    )


def _array_initialization_vector_length_resolution_source(
    source: object,
) -> Result[ExactArrayInitializationBaseTypeResolutionIr]:
    if isinstance(source, ExactArrayInitializationBaseTypeResolutionIr):
        return Result.ok(source)
    if isinstance(source, GenerationLoweringStage):
        if (
            source.stage == "array_initialization_base_type_request_resolution"
            and isinstance(source.output, ExactArrayInitializationBaseTypeResolutionIr)
        ):
            return Result.ok(source.output)
        return Result.failure(
            (
                _array_initialization_vector_length_source_unsupported_diagnostic(
                    "array-initialization vector-length request resolution "
                    "consumes typed M68 "
                    "ExactArrayInitializationBaseTypeResolutionIr values, the "
                    "array_initialization_base_type_request_resolution stage "
                    "output, or a LoweredImplementation with a matching M68 "
                    "base-type resolution",
                    _stage_output_location(source.output),
                ),
            )
        )
    if isinstance(source, LoweredImplementation):
        if len(source.array_initialization_base_type_resolutions) == 1:
            return Result.ok(source.array_initialization_base_type_resolutions[0])
        if len(source.array_initialization_base_type_resolutions) == 0:
            return Result.failure(
                (
                    _array_initialization_vector_length_missing_ir_diagnostic(
                        "array-initialization vector-length request resolution "
                        "requires a LoweredImplementation carrying an accepted "
                        "M68 array_initialization_base_type_resolutions entry",
                        _lowered_implementation_location(source),
                    ),
                )
            )
        return Result.failure(
            (
                _array_initialization_vector_length_multiple_ir_diagnostic(
                    "array-initialization vector-length request resolution "
                    "requires exactly one M68 "
                    "array_initialization_base_type_resolutions entry; got "
                    f"{len(source.array_initialization_base_type_resolutions)}",
                    _lowered_implementation_location(source),
                ),
            )
        )
    return Result.failure(
        (
            _array_initialization_vector_length_source_unsupported_diagnostic(
                "array-initialization vector-length request resolution "
                "consumes only typed M68 "
                "ExactArrayInitializationBaseTypeResolutionIr values or "
                "array_initialization_base_type_request_resolution stage output",
                None,
            ),
        )
    )


def _array_initialization_vector_alignment_resolution_source(
    source: object,
) -> Result[ExactArrayInitializationVectorLengthResolutionIr]:
    if isinstance(source, ExactArrayInitializationVectorLengthResolutionIr):
        return Result.ok(source)
    if isinstance(source, GenerationLoweringStage):
        if (
            source.stage == "array_initialization_vector_length_request_resolution"
            and isinstance(source.output, ExactArrayInitializationVectorLengthResolutionIr)
        ):
            return Result.ok(source.output)
        return Result.failure(
            (
                _array_initialization_vector_alignment_source_unsupported_diagnostic(
                    "array-initialization vector-alignment request resolution "
                    "consumes typed M70 "
                    "ExactArrayInitializationVectorLengthResolutionIr values, "
                    "the array_initialization_vector_length_request_resolution "
                    "stage output, or a LoweredImplementation with a matching "
                    "M70 vector-length resolution",
                    _stage_output_location(source.output),
                ),
            )
        )
    if isinstance(source, LoweredImplementation):
        if len(source.array_initialization_vector_length_resolutions) == 1:
            return Result.ok(source.array_initialization_vector_length_resolutions[0])
        if len(source.array_initialization_vector_length_resolutions) == 0:
            return Result.failure(
                (
                    _array_initialization_vector_alignment_missing_ir_diagnostic(
                        "array-initialization vector-alignment request "
                        "resolution requires a LoweredImplementation carrying "
                        "an accepted M70 "
                        "array_initialization_vector_length_resolutions entry",
                        _lowered_implementation_location(source),
                    ),
                )
            )
        return Result.failure(
            (
                _array_initialization_vector_alignment_multiple_ir_diagnostic(
                    "array-initialization vector-alignment request resolution "
                    "requires exactly one M70 "
                    "array_initialization_vector_length_resolutions entry; "
                    f"got {len(source.array_initialization_vector_length_resolutions)}",
                    _lowered_implementation_location(source),
                ),
            )
        )
    return Result.failure(
        (
            _array_initialization_vector_alignment_source_unsupported_diagnostic(
                "array-initialization vector-alignment request resolution "
                "consumes only typed M70 "
                "ExactArrayInitializationVectorLengthResolutionIr values or "
                "array_initialization_vector_length_request_resolution stage "
                "output",
                None,
            ),
        )
    )


def _array_initialization_helper_set_completion_source(
    source: object,
) -> Result[ExactArrayInitializationVectorAlignmentResolutionIr]:
    if isinstance(source, ExactArrayInitializationVectorAlignmentResolutionIr):
        return Result.ok(source)
    if isinstance(source, GenerationLoweringStage):
        if (
            source.stage == "array_initialization_vector_alignment_request_resolution"
            and isinstance(source.output, ExactArrayInitializationVectorAlignmentResolutionIr)
        ):
            return Result.ok(source.output)
        return Result.failure(
            (
                _array_initialization_helper_set_source_unsupported_diagnostic(
                    "array-initialization helper-set completion consumes typed "
                    "M71 ExactArrayInitializationVectorAlignmentResolutionIr "
                    "values, the "
                    "array_initialization_vector_alignment_request_resolution "
                    "stage output, or a LoweredImplementation with a matching "
                    "M71 vector-alignment resolution",
                    _stage_output_location(source.output),
                ),
            )
        )
    if isinstance(source, LoweredImplementation):
        if len(source.array_initialization_vector_alignment_resolutions) == 1:
            return Result.ok(
                source.array_initialization_vector_alignment_resolutions[0]
            )
        if len(source.array_initialization_vector_alignment_resolutions) == 0:
            return Result.failure(
                (
                    _array_initialization_helper_set_missing_ir_diagnostic(
                        "array-initialization helper-set completion requires "
                        "a LoweredImplementation carrying an accepted M71 "
                        "array_initialization_vector_alignment_resolutions "
                        "entry",
                        _lowered_implementation_location(source),
                    ),
                )
            )
        return Result.failure(
            (
                _array_initialization_helper_set_multiple_ir_diagnostic(
                    "array-initialization helper-set completion requires "
                    "exactly one M71 "
                    "array_initialization_vector_alignment_resolutions entry; "
                    f"got {len(source.array_initialization_vector_alignment_resolutions)}",
                    _lowered_implementation_location(source),
                ),
            )
        )
    return Result.failure(
        (
            _array_initialization_helper_set_source_unsupported_diagnostic(
                "array-initialization helper-set completion consumes only "
                "typed M71 ExactArrayInitializationVectorAlignmentResolutionIr "
                "values or "
                "array_initialization_vector_alignment_request_resolution "
                "stage output",
                None,
            ),
        )
    )


def _array_initialization_declaration_shell_source(
    source: object,
) -> Result[ExactArrayInitializationHelperSetCompletionIr]:
    if isinstance(source, ExactArrayInitializationHelperSetCompletionIr):
        return Result.ok(source)
    if isinstance(source, GenerationLoweringStage):
        if (
            source.stage == "array_initialization_helper_set_completion"
            and isinstance(source.output, ExactArrayInitializationHelperSetCompletionIr)
        ):
            return Result.ok(source.output)
        return Result.failure(
            (
                _array_initialization_declaration_shell_source_unsupported_diagnostic(
                    "array-initialization declaration-shell lowering consumes "
                    "typed M72 ExactArrayInitializationHelperSetCompletionIr "
                    "values, the array_initialization_helper_set_completion "
                    "stage output, or a LoweredImplementation with a matching "
                    "M72 helper-set completion",
                    _stage_output_location(source.output),
                ),
            )
        )
    if isinstance(source, LoweredImplementation):
        if len(source.array_initialization_helper_set_completions) == 1:
            return Result.ok(source.array_initialization_helper_set_completions[0])
        if len(source.array_initialization_helper_set_completions) == 0:
            return Result.failure(
                (
                    _array_initialization_declaration_shell_missing_ir_diagnostic(
                        "array-initialization declaration-shell lowering "
                        "requires a LoweredImplementation carrying an accepted "
                        "M72 array_initialization_helper_set_completions entry",
                        _lowered_implementation_location(source),
                    ),
                )
            )
        return Result.failure(
            (
                _array_initialization_declaration_shell_multiple_ir_diagnostic(
                    "array-initialization declaration-shell lowering requires "
                    "exactly one M72 "
                    "array_initialization_helper_set_completions entry; got "
                    f"{len(source.array_initialization_helper_set_completions)}",
                    _lowered_implementation_location(source),
                ),
            )
        )
    return Result.failure(
        (
            _array_initialization_declaration_shell_source_unsupported_diagnostic(
                "array-initialization declaration-shell lowering consumes "
                "only typed M72 "
                "ExactArrayInitializationHelperSetCompletionIr values or "
                "array_initialization_helper_set_completion stage output",
                None,
            ),
        )
        )


def lower_exact_predicate_path_structural_request(
    source: object,
    context: GenerationContext | None = None,
    *,
    selected_candidate_id: str | None = None,
    target_extension: str | None = None,
    source_extension: str | None = None,
    selected_type_tag: str | None = None,
) -> Result[ExactPredicatePathStructuralRequestIr]:
    source_result = _predicate_path_structural_request_source(source)
    if not source_result.is_ok:
        return Result.failure(source_result.diagnostics)
    sequence = source_result.unwrap()

    generation_context = context or GenerationContext()
    effective_candidate_id = (
        selected_candidate_id
        or generation_context.selected_candidate_id
        or sequence.candidate_id
    )
    effective_target_extension = target_extension or sequence.target_extension
    effective_source_extension = source_extension or sequence.source_extension
    effective_type_tag = (
        selected_type_tag
        or generation_context.selected_type_tag
        or sequence.selected_type_tag
    )
    if (
        effective_candidate_id != sequence.candidate_id
        or effective_target_extension != sequence.target_extension
        or effective_source_extension != sequence.source_extension
        or effective_type_tag != sequence.selected_type_tag
    ):
        return Result.failure(
            (
                _predicate_path_context_mismatch_diagnostic(
                    "predicate-path structural request lowering requires the "
                    "typed selected candidate context to match the M74 sequence "
                    "candidate id, target extension, source extension, and "
                    "selected type tag",
                    sequence.source_location,
                ),
            )
        )

    validation_diagnostics = _validate_predicate_path_structural_request_input(
        sequence,
    )
    if validation_diagnostics:
        return Result.failure(sort_diagnostics(tuple(validation_diagnostics)))

    init_role = sequence.roles[1]
    selected_role = sequence.roles[2]
    store_role = sequence.roles[3]
    assert init_role.opaque_source_text is not None
    assert store_role.opaque_source_text is not None
    init_match = _EXACT_PREDICATE_INIT_SLOT_RE.match(init_role.opaque_source_text)
    store_match = _EXACT_POST_BRANCH_STORE_PREDICATE_SLOT_RE.match(
        store_role.opaque_source_text,
    )
    if init_match is None or store_match is None:
        raise AssertionError("predicate-path validation did not enforce exact shapes")
    selected_body_envelope = selected_role.selected_body_envelope
    assert isinstance(
        selected_body_envelope,
        (SelectedBodyEnvelopeIr, NoSelectedBodyEnvelopeIr),
    )
    if isinstance(selected_body_envelope, SelectedBodyEnvelopeIr):
        entry = selected_body_envelope.entries[0]
        selected_update_state: ExactPredicatePathSelectedUpdateState = (
            "accepted_selected_update"
        )
        selected_update_assignment_target_text = entry.assignment_target_text
        selected_update_direct_intrinsic_token_text = entry.direct_intrinsic_token_text
        selected_update_source_location = entry.source_location
    else:
        selected_update_state = "accepted_no_update"
        selected_update_assignment_target_text = None
        selected_update_direct_intrinsic_token_text = None
        selected_update_source_location = selected_body_envelope.source_location

    try:
        return Result.ok(
            ExactPredicatePathStructuralRequestIr(
                source_sequence=sequence,
                predicate_init_role_label="opaque_predicate_init_shaped_slot",
                predicate_init_slot_ordinal=1,
                predicate_init_source_location=init_role.source_location,
                predicate_type_token_text=init_match.group("predicate_type"),
                predicate_token_text=init_match.group("predicate_token"),
                predicate_init_direct_intrinsic_token_text=init_match.group(
                    "direct_intrinsic_token",
                ),
                selected_update_state=selected_update_state,
                selected_body_envelope=selected_body_envelope,
                selected_update_slot_ordinal=2,
                selected_update_source_location=selected_update_source_location,
                selected_update_assignment_target_text=(
                    selected_update_assignment_target_text
                ),
                selected_update_direct_intrinsic_token_text=(
                    selected_update_direct_intrinsic_token_text
                ),
                store_call_role_label="opaque_post_branch_store_call_shaped_slot",
                store_call_slot_ordinal=3,
                store_call_source_location=store_role.source_location,
                store_call_predicate_argument_text=store_match.group(
                    "predicate_token",
                ),
                candidate_id=sequence.candidate_id,
                target_extension=sequence.target_extension,
                source_extension=sequence.source_extension,
                selected_type_tag=sequence.selected_type_tag,
                originating_branch_chain_id=sequence.originating_branch_chain_id,
            )
        )
    except (TypeError, ValueError) as exc:
        return Result.failure(
            (
                _predicate_path_provenance_mismatch_diagnostic(
                    str(exc),
                    sequence.source_location,
                ),
            )
        )


def _array_body_structural_sequence_source(
    source: object,
    declaration_shell: object | None,
) -> Result[tuple[ExactArrayBodyEnvelopeIr, ExactArrayInitializationDeclarationShellIr]]:
    if isinstance(source, ExactArrayInitializationDeclarationShellIr):
        if declaration_shell is not None:
            return Result.failure(
                (
                    _array_body_structural_sequence_source_unsupported_diagnostic(
                        "array-body structural sequence classification accepts "
                        "a separate declaration-shell argument only when the "
                        "primary source is an M65 envelope source",
                        source.source_location,
                    ),
                )
            )
        return Result.ok((source.source_envelope, source))

    if isinstance(source, ExactArrayBodyEnvelopeIr):
        shell_result = _array_body_structural_sequence_shell_source(
            declaration_shell,
        )
        if not shell_result.is_ok:
            return Result.failure(shell_result.diagnostics)
        return Result.ok((source, shell_result.unwrap()))

    if isinstance(source, GenerationLoweringStage):
        if (
            source.stage == "array_initialization_declaration_shell_lowering"
            and isinstance(source.output, ExactArrayInitializationDeclarationShellIr)
        ):
            if declaration_shell is not None:
                return Result.failure(
                    (
                        _array_body_structural_sequence_source_unsupported_diagnostic(
                            "array-body structural sequence classification "
                            "accepts a separate declaration-shell argument only "
                            "when the primary source is an M65 envelope source",
                            source.output.source_location,
                        ),
                    )
                )
            return Result.ok((source.output.source_envelope, source.output))
        if (
            source.stage == "array_body_envelope_slot_assembly"
            and isinstance(source.output, ExactArrayBodyEnvelopeIr)
        ):
            shell_result = _array_body_structural_sequence_shell_source(
                declaration_shell,
            )
            if not shell_result.is_ok:
                return Result.failure(shell_result.diagnostics)
            return Result.ok((source.output, shell_result.unwrap()))
        return Result.failure(
            (
                _array_body_structural_sequence_source_unsupported_diagnostic(
                    "array-body structural sequence classification consumes "
                    "accepted M65 ExactArrayBodyEnvelopeIr values with an M73 "
                    "declaration shell, accepted M73 declaration-shell values "
                    "or stage output, or a LoweredImplementation carrying "
                    "exactly one matching M65 envelope and M73 shell",
                    _stage_output_location(source.output),
                ),
            )
        )

    if isinstance(source, LoweredImplementation):
        if declaration_shell is not None:
            return Result.failure(
                (
                    _array_body_structural_sequence_source_unsupported_diagnostic(
                        "array-body structural sequence classification does "
                        "not accept a separate declaration-shell argument when "
                        "the primary source is a LoweredImplementation",
                        _lowered_implementation_location(source),
                    ),
                )
            )
        diagnostics: list[Diagnostic] = []
        if len(source.array_body_envelopes) == 0:
            diagnostics.append(
                _array_body_structural_sequence_missing_ir_diagnostic(
                    "array-body structural sequence classification requires "
                    "a LoweredImplementation carrying one accepted M65 "
                    "array_body_envelopes entry",
                    _lowered_implementation_location(source),
                )
            )
        elif len(source.array_body_envelopes) > 1:
            diagnostics.append(
                _array_body_structural_sequence_multiple_ir_diagnostic(
                    "array-body structural sequence classification requires "
                    "exactly one M65 array_body_envelopes entry",
                    _lowered_implementation_location(source),
                )
            )
        if len(source.array_initialization_declaration_shells) == 0:
            diagnostics.append(
                _array_body_structural_sequence_missing_ir_diagnostic(
                    "array-body structural sequence classification requires "
                    "a LoweredImplementation carrying one accepted M73 "
                    "array_initialization_declaration_shells entry",
                    _lowered_implementation_location(source),
                )
            )
        elif len(source.array_initialization_declaration_shells) > 1:
            diagnostics.append(
                _array_body_structural_sequence_multiple_ir_diagnostic(
                    "array-body structural sequence classification requires "
                    "exactly one M73 array_initialization_declaration_shells "
                    "entry",
                    _lowered_implementation_location(source),
                )
            )
        if diagnostics:
            return Result.failure(sort_diagnostics(tuple(diagnostics)))
        return Result.ok(
            (
                source.array_body_envelopes[0],
                source.array_initialization_declaration_shells[0],
            )
        )

    return Result.failure(
        (
            _array_body_structural_sequence_source_unsupported_diagnostic(
                "array-body structural sequence classification consumes only "
                "accepted M65 envelope/M73 declaration-shell typed sources or "
                "a matching LoweredImplementation",
                None,
            ),
        )
    )


def _array_body_structural_sequence_shell_source(
    source: object | None,
) -> Result[ExactArrayInitializationDeclarationShellIr]:
    if isinstance(source, ExactArrayInitializationDeclarationShellIr):
        return Result.ok(source)
    if isinstance(source, GenerationLoweringStage):
        if (
            source.stage == "array_initialization_declaration_shell_lowering"
            and isinstance(source.output, ExactArrayInitializationDeclarationShellIr)
        ):
            return Result.ok(source.output)
        return Result.failure(
            (
                _array_body_structural_sequence_source_unsupported_diagnostic(
                    "array-body structural sequence classification requires "
                    "the separate source to be an accepted M73 declaration "
                    "shell or array_initialization_declaration_shell_lowering "
                    "stage output",
                    _stage_output_location(source.output),
                ),
            )
        )
    if source is None:
        return Result.failure(
            (
                _array_body_structural_sequence_missing_ir_diagnostic(
                    "array-body structural sequence classification requires "
                    "an accepted M73 declaration-shell value when the primary "
                    "source is an M65 envelope",
                    None,
                ),
            )
        )
    return Result.failure(
        (
            _array_body_structural_sequence_source_unsupported_diagnostic(
                "array-body structural sequence classification requires an "
                "accepted M73 declaration-shell value",
                None,
            ),
        )
    )


def _predicate_path_structural_request_source(
    source: object,
) -> Result[ExactArrayBodyStructuralSequenceIr]:
    if isinstance(source, ExactArrayBodyStructuralSequenceIr):
        return Result.ok(source)

    if isinstance(source, GenerationLoweringStage):
        if (
            source.stage == "array_body_structural_sequence_classification"
            and isinstance(source.output, ExactArrayBodyStructuralSequenceIr)
        ):
            return Result.ok(source.output)
        return Result.failure(
            (
                _predicate_path_source_unsupported_diagnostic(
                    "predicate-path structural request lowering consumes "
                    "accepted M74 ExactArrayBodyStructuralSequenceIr values, "
                    "the array_body_structural_sequence_classification stage "
                    "output, or a LoweredImplementation carrying exactly one "
                    "M74 value",
                    _stage_output_location(source.output),
                ),
            )
        )

    if isinstance(source, LoweredImplementation):
        if len(source.array_body_structural_sequences) == 0:
            return Result.failure(
                (
                    _predicate_path_missing_ir_diagnostic(
                        "predicate-path structural request lowering requires "
                        "a LoweredImplementation carrying one accepted M74 "
                        "array_body_structural_sequences entry",
                        _lowered_implementation_location(source),
                    ),
                )
            )
        if len(source.array_body_structural_sequences) > 1:
            return Result.failure(
                (
                    _predicate_path_multiple_ir_diagnostic(
                        "predicate-path structural request lowering requires "
                        "exactly one M74 array_body_structural_sequences entry",
                        _lowered_implementation_location(source),
                    ),
                )
            )
        return Result.ok(source.array_body_structural_sequences[0])

    return Result.failure(
        (
            _predicate_path_source_unsupported_diagnostic(
                "predicate-path structural request lowering consumes only "
                "accepted M74 structural sequence typed sources",
                None,
            ),
        )
    )


def _array_initialization_envelope_slot(
    envelope: ExactArrayBodyEnvelopeIr,
) -> ExactArrayBodyEnvelopeSlot | None:
    if len(envelope.slots) <= 0:
        return None
    return envelope.slots[0]


def _validate_array_initialization_slot_position(
    envelope: ExactArrayBodyEnvelopeIr,
    slot: ExactArrayBodyEnvelopeOpaqueSlot,
) -> Diagnostic | None:
    if (
        slot.candidate_id != envelope.candidate_id
        or slot.selected_type_tag != envelope.selected_type_tag
        or slot.originating_branch_chain_id != envelope.originating_branch_chain_id
    ):
        return _array_initialization_slot_provenance_mismatch_diagnostic(
            "array-initialization slot provenance must match the M65 "
            "array-body envelope candidate id, selected type tag, and "
            "branch-chain identity",
            slot.source_location,
        )
    if (
        slot.label != "opaque_pre_branch_array_initialization"
        or slot.ordinal != 0
    ):
        return _array_initialization_slot_wrong_position_diagnostic(
            "array-initialization slot form lowering refines only the "
            "opaque_pre_branch_array_initialization slot at ordinal 0; got "
            f"label {slot.label!r} and ordinal {slot.ordinal!r}",
            slot.source_location,
        )
    return None


def _validate_array_initialization_helper_form_provenance(
    form: ExactArrayInitializationSlotFormIr,
) -> Diagnostic | None:
    if not isinstance(form.source_envelope, ExactArrayBodyEnvelopeIr):
        return _array_initialization_helper_request_provenance_mismatch_diagnostic(
            "array-initialization helper request lowering requires the M66 "
            "slot form to reference an M65 array-body envelope",
            form.source_location,
        )
    if (
        form.candidate_id != form.source_envelope.candidate_id
        or form.selected_type_tag != form.source_envelope.selected_type_tag
        or form.originating_branch_chain_id
        != form.source_envelope.originating_branch_chain_id
    ):
        return _array_initialization_helper_request_provenance_mismatch_diagnostic(
            "array-initialization helper request lowering requires M66 form "
            "provenance (candidate id, selected type tag, and branch-chain "
            "identity) to match its M65 envelope",
            form.source_location,
        )
    if form.slot_label != "opaque_pre_branch_array_initialization":
        return _array_initialization_helper_request_provenance_mismatch_diagnostic(
            "array-initialization helper request lowering requires the M66 "
            "opaque_pre_branch_array_initialization slot form",
            form.source_location,
        )
    if form.slot_ordinal != 0:
        return _array_initialization_helper_request_provenance_mismatch_diagnostic(
            "array-initialization helper request lowering requires the M66 "
            "slot form at ordinal 0",
            form.source_location,
        )
    if form.variable_token != "tmp":
        return _array_initialization_helper_request_provenance_mismatch_diagnostic(
            "array-initialization helper request lowering requires the M66 "
            "variable token tmp",
            form.variable_token_location or form.source_location,
        )
    return None


def _validate_array_initialization_base_type_request_ir_provenance(
    request_ir: ExactArrayInitializationHelperRequestIr,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    if request_ir.source_envelope != request_ir.source_form.source_envelope:
        diagnostics.append(
            _array_initialization_base_type_resolution_provenance_mismatch_diagnostic(
                "M67 helper-request IR envelope must match its M66 slot form "
                "envelope",
                request_ir.source_location,
            )
        )
    if request_ir.source_location != request_ir.source_form.source_location:
        diagnostics.append(
            _array_initialization_base_type_resolution_provenance_mismatch_diagnostic(
                "M67 helper-request IR source location must match its M66 slot "
                "form source location",
                request_ir.source_location,
            )
        )
    if (
        request_ir.candidate_id != request_ir.source_form.candidate_id
        or request_ir.selected_type_tag != request_ir.source_form.selected_type_tag
        or request_ir.originating_branch_chain_id
        != request_ir.source_form.originating_branch_chain_id
    ):
        diagnostics.append(
            _array_initialization_base_type_resolution_provenance_mismatch_diagnostic(
                "M67 helper-request IR provenance must match its M66 slot form",
                request_ir.source_location,
            )
        )
    if (
        request_ir.slot_label != request_ir.source_form.slot_label
        or request_ir.slot_ordinal != request_ir.source_form.slot_ordinal
        or request_ir.variable_token != request_ir.source_form.variable_token
    ):
        diagnostics.append(
            _array_initialization_base_type_resolution_provenance_mismatch_diagnostic(
                "M67 helper-request IR slot provenance must match its M66 "
                "slot form",
                request_ir.source_location,
            )
        )
    for request in request_ir.requests:
        if request.source_form != request_ir.source_form:
            diagnostics.append(
                _array_initialization_base_type_resolution_provenance_mismatch_diagnostic(
                    "M67 helper-request record source form must match the "
                    "source helper-request IR",
                    request.leaf_source_location,
                )
            )
        if request.source_envelope != request_ir.source_envelope:
            diagnostics.append(
                _array_initialization_base_type_resolution_provenance_mismatch_diagnostic(
                    "M67 helper-request record envelope must match the source "
                    "helper-request IR",
                    request.leaf_source_location,
                )
            )
        if (
            request.candidate_id != request_ir.candidate_id
            or request.selected_type_tag != request_ir.selected_type_tag
            or request.originating_branch_chain_id
            != request_ir.originating_branch_chain_id
            or request.slot_label != request_ir.slot_label
            or request.slot_ordinal != request_ir.slot_ordinal
            or request.variable_token != request_ir.variable_token
        ):
            diagnostics.append(
                _array_initialization_base_type_resolution_provenance_mismatch_diagnostic(
                    "M67 helper-request record provenance must match the "
                    "source helper-request IR",
                    request.leaf_source_location,
                )
            )
    return diagnostics


def _array_initialization_base_type_request_record(
    request_ir: ExactArrayInitializationHelperRequestIr,
    diagnostics: list[Diagnostic],
) -> ExactArrayInitializationHelperRequestRecord | None:
    rule = _EXACT_ARRAY_INITIALIZATION_BASE_TYPE_REQUEST_RULE
    base_records = tuple(
        request
        for request in request_ir.requests
        if request.helper_leaf_kind == rule.helper_leaf_kind
    )
    if not base_records:
        ordinal_or_kind_records = tuple(
            request
            for request in request_ir.requests
            if (
                request.request_ordinal == rule.request_ordinal
                or request.request_kind == rule.request_kind
            )
        )
        if ordinal_or_kind_records:
            for request in ordinal_or_kind_records:
                diagnostics.append(
                    _array_initialization_base_type_resolution_mismatch_diagnostic(
                        "array-initialization base-type request resolution "
                        "expected the M67 base request to carry ordinal "
                        f"{rule.request_ordinal}, kind {rule.request_kind!r}, "
                        f"and leaf kind {rule.helper_leaf_kind!r}; got ordinal "
                        f"{request.request_ordinal}, kind "
                        f"{request.request_kind!r}, and leaf kind "
                        f"{request.helper_leaf_kind!r}",
                        request.leaf_source_location,
                    )
                )
            return None
        diagnostics.append(
            _array_initialization_base_type_resolution_missing_request_diagnostic(
                "array-initialization base-type request resolution requires "
                "one M67 base-type request record",
                request_ir.source_location,
            )
        )
        return None
    if len(base_records) > 1:
        for request in base_records:
            diagnostics.append(
                _array_initialization_base_type_resolution_duplicate_request_diagnostic(
                    "array-initialization base-type request resolution requires "
                    "exactly one M67 base-type request record; duplicate "
                    f"record appeared at ordinal {request.request_ordinal}",
                    request.leaf_source_location,
                )
            )
        return None

    base_request = base_records[0]
    if (
        base_request.request_ordinal != rule.request_ordinal
        or base_request.request_kind != rule.request_kind
    ):
        diagnostics.append(
            _array_initialization_base_type_resolution_mismatch_diagnostic(
                "array-initialization base-type request resolution expected "
                f"ordinal {rule.request_ordinal} and kind "
                f"{rule.request_kind!r}; got ordinal "
                f"{base_request.request_ordinal} and kind "
                f"{base_request.request_kind!r}",
                base_request.leaf_source_location,
            )
        )
    if base_request.leaf_source_text != rule.expected_leaf_source_text:
        diagnostics.append(
            _array_initialization_base_type_resolution_unsupported_request_diagnostic(
                "array-initialization base-type request resolution preserves "
                "the M67 leaf source text only as provenance and accepts only "
                "the exact M67 base-type leaf text for that typed request; got "
                f"{base_request.leaf_source_text!r}",
                base_request.leaf_source_location,
            )
        )
    return base_request


def _validate_array_initialization_vector_length_resolution_provenance(
    base_resolution: ExactArrayInitializationBaseTypeResolutionIr,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    request_ir = base_resolution.source_request_ir
    if base_resolution.source_base_type_request not in request_ir.requests:
        diagnostics.append(
            _array_initialization_vector_length_provenance_mismatch_diagnostic(
                "M68 base-type resolution source request must come from its "
                "M67 helper-request IR",
                base_resolution.source_location,
            )
        )
    if base_resolution.source_location != request_ir.source_location:
        diagnostics.append(
            _array_initialization_vector_length_provenance_mismatch_diagnostic(
                "M68 base-type resolution source location must match its M67 "
                "helper-request IR",
                base_resolution.source_location,
            )
        )
    if (
        base_resolution.candidate_id != request_ir.candidate_id
        or base_resolution.selected_type_tag != request_ir.selected_type_tag
        or base_resolution.originating_branch_chain_id
        != request_ir.originating_branch_chain_id
    ):
        diagnostics.append(
            _array_initialization_vector_length_provenance_mismatch_diagnostic(
                "M68 base-type resolution provenance must match its M67 "
                "helper-request IR",
                base_resolution.source_location,
            )
        )
    if (
        base_resolution.slot_label != request_ir.slot_label
        or base_resolution.slot_ordinal != request_ir.slot_ordinal
        or base_resolution.variable_token != request_ir.variable_token
    ):
        diagnostics.append(
            _array_initialization_vector_length_provenance_mismatch_diagnostic(
                "M68 base-type resolution slot provenance must match its M67 "
                "helper-request IR",
                base_resolution.source_location,
            )
        )
    for request in base_resolution.unresolved_requests:
        if request.source_form != request_ir.source_form:
            diagnostics.append(
                _array_initialization_vector_length_provenance_mismatch_diagnostic(
                    "M68 unresolved request record source form must match the "
                    "source M67 helper-request IR",
                    request.leaf_source_location,
                )
            )
        if request.source_envelope != request_ir.source_envelope:
            diagnostics.append(
                _array_initialization_vector_length_provenance_mismatch_diagnostic(
                    "M68 unresolved request record envelope must match the "
                    "source M67 helper-request IR",
                    request.leaf_source_location,
                )
            )
        if (
            request.candidate_id != base_resolution.candidate_id
            or request.selected_type_tag != base_resolution.selected_type_tag
            or request.originating_branch_chain_id
            != base_resolution.originating_branch_chain_id
            or request.slot_label != base_resolution.slot_label
            or request.slot_ordinal != base_resolution.slot_ordinal
            or request.variable_token != base_resolution.variable_token
        ):
            diagnostics.append(
                _array_initialization_vector_length_provenance_mismatch_diagnostic(
                    "M68 unresolved request record provenance must match the "
                    "source base-type resolution",
                    request.leaf_source_location,
                )
            )
    return diagnostics


def _array_initialization_vector_length_request_record(
    base_resolution: ExactArrayInitializationBaseTypeResolutionIr,
    diagnostics: list[Diagnostic],
) -> ExactArrayInitializationHelperRequestRecord | None:
    rule = _EXACT_ARRAY_INITIALIZATION_VECTOR_LENGTH_REQUEST_RULE
    vector_length_records = tuple(
        request
        for request in base_resolution.unresolved_requests
        if request.helper_leaf_kind == rule.helper_leaf_kind
    )
    if not vector_length_records:
        ordinal_or_kind_records = tuple(
            request
            for request in base_resolution.unresolved_requests
            if (
                request.request_ordinal == rule.request_ordinal
                or request.request_kind == rule.request_kind
            )
        )
        if ordinal_or_kind_records:
            for request in ordinal_or_kind_records:
                diagnostics.append(
                    _array_initialization_vector_length_mismatch_diagnostic(
                        "array-initialization vector-length request resolution "
                        "expected the M67 vector-length request to carry "
                        f"ordinal {rule.request_ordinal}, kind "
                        f"{rule.request_kind!r}, and leaf kind "
                        f"{rule.helper_leaf_kind!r}; got ordinal "
                        f"{request.request_ordinal}, kind "
                        f"{request.request_kind!r}, and leaf kind "
                        f"{request.helper_leaf_kind!r}",
                        request.leaf_source_location,
                    )
                )
            return None
        diagnostics.append(
            _array_initialization_vector_length_missing_request_diagnostic(
                "array-initialization vector-length request resolution "
                "requires one M67 vector-length request record preserved by "
                "M68",
                base_resolution.source_location,
            )
        )
        return None
    if len(vector_length_records) > 1:
        for request in vector_length_records:
            diagnostics.append(
                _array_initialization_vector_length_duplicate_request_diagnostic(
                    "array-initialization vector-length request resolution "
                    "requires exactly one M67 vector-length request record; "
                    f"duplicate record appeared at ordinal "
                    f"{request.request_ordinal}",
                    request.leaf_source_location,
                )
            )
        return None

    vector_length_request = vector_length_records[0]
    if (
        vector_length_request.request_ordinal != rule.request_ordinal
        or vector_length_request.request_kind != rule.request_kind
    ):
        diagnostics.append(
            _array_initialization_vector_length_mismatch_diagnostic(
                "array-initialization vector-length request resolution "
                f"expected ordinal {rule.request_ordinal} and kind "
                f"{rule.request_kind!r}; got ordinal "
                f"{vector_length_request.request_ordinal} and kind "
                f"{vector_length_request.request_kind!r}",
                vector_length_request.leaf_source_location,
            )
        )
    if vector_length_request.leaf_source_text != rule.expected_leaf_source_text:
        diagnostics.append(
            _array_initialization_vector_length_unsupported_request_diagnostic(
                "array-initialization vector-length request resolution "
                "preserves the M67 leaf source text only as provenance and "
                "accepts only the exact M67 vector-length leaf text for that "
                f"typed request; got {vector_length_request.leaf_source_text!r}",
                vector_length_request.leaf_source_location,
            )
        )
    return vector_length_request


def _array_initialization_vector_length_metadata_for_context(
    context: GenerationContext,
    *,
    candidate_id: str,
    target_extension: str,
    source_extension: str,
    selected_type_tag: str,
    location: SourceLocation | None,
) -> Result[ExactArrayInitializationVectorLengthMetadata]:
    lookup_key = (
        candidate_id,
        target_extension,
        source_extension,
        selected_type_tag,
    )
    matches = tuple(
        metadata
        for metadata in context.array_initialization_vector_length_metadata
        if metadata.lookup_key == lookup_key
    )
    if not matches:
        return Result.failure(
            (
                _array_initialization_vector_length_metadata_missing_diagnostic(
                    "array-initialization vector-length request resolution "
                    "requires explicit typed vector-length metadata for "
                    f"candidate {candidate_id!r}, target extension "
                    f"{target_extension!r}, source extension "
                    f"{source_extension!r}, and selected type tag "
                    f"{selected_type_tag!r}",
                    location,
                ),
            )
        )
    if len(matches) > 1:
        values = tuple(metadata.vector_length for metadata in matches)
        code_detail = "conflicting" if len(set(values)) > 1 else "duplicate"
        diagnostic = (
            _array_initialization_vector_length_metadata_conflict_diagnostic
            if code_detail == "conflicting"
            else _array_initialization_vector_length_metadata_duplicate_diagnostic
        )
        return Result.failure(
            (
                diagnostic(
                    "array-initialization vector-length metadata requires "
                    f"exactly one entry for {lookup_key!r}; found "
                    f"{code_detail} entries",
                    matches[0].source_location or location,
                ),
            )
        )
    return Result.ok(matches[0])


def _validate_array_initialization_vector_alignment_resolution_provenance(
    vector_length_resolution: ExactArrayInitializationVectorLengthResolutionIr,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    base_resolution = vector_length_resolution.source_base_type_resolution
    if vector_length_resolution.source_vector_length_request not in (
        base_resolution.unresolved_requests
    ):
        diagnostics.append(
            _array_initialization_vector_alignment_provenance_mismatch_diagnostic(
                "M70 vector-length resolution source request must come from its "
                "M68 base-type resolution",
                vector_length_resolution.source_location,
            )
        )
    if vector_length_resolution.source_location != base_resolution.source_location:
        diagnostics.append(
            _array_initialization_vector_alignment_provenance_mismatch_diagnostic(
                "M70 vector-length resolution source location must match its "
                "M68 base-type resolution",
                vector_length_resolution.source_location,
            )
        )
    if (
        vector_length_resolution.candidate_id != base_resolution.candidate_id
        or vector_length_resolution.selected_type_tag
        != base_resolution.selected_type_tag
        or vector_length_resolution.originating_branch_chain_id
        != base_resolution.originating_branch_chain_id
    ):
        diagnostics.append(
            _array_initialization_vector_alignment_provenance_mismatch_diagnostic(
                "M70 vector-length resolution provenance must match its M68 "
                "base-type resolution",
                vector_length_resolution.source_location,
            )
        )
    if (
        vector_length_resolution.slot_label != base_resolution.slot_label
        or vector_length_resolution.slot_ordinal != base_resolution.slot_ordinal
        or vector_length_resolution.variable_token != base_resolution.variable_token
    ):
        diagnostics.append(
            _array_initialization_vector_alignment_provenance_mismatch_diagnostic(
                "M70 vector-length resolution slot provenance must match its "
                "M68 base-type resolution",
                vector_length_resolution.source_location,
            )
        )
    for request in vector_length_resolution.unresolved_requests:
        if request.source_form != base_resolution.source_request_ir.source_form:
            diagnostics.append(
                _array_initialization_vector_alignment_provenance_mismatch_diagnostic(
                    "M70 unresolved request record source form must match the "
                    "source M67 helper-request IR",
                    request.leaf_source_location,
                )
            )
        if request.source_envelope != base_resolution.source_request_ir.source_envelope:
            diagnostics.append(
                _array_initialization_vector_alignment_provenance_mismatch_diagnostic(
                    "M70 unresolved request record envelope must match the "
                    "source M67 helper-request IR",
                    request.leaf_source_location,
                )
            )
        if (
            request.candidate_id != vector_length_resolution.candidate_id
            or request.selected_type_tag
            != vector_length_resolution.selected_type_tag
            or request.originating_branch_chain_id
            != vector_length_resolution.originating_branch_chain_id
            or request.slot_label != vector_length_resolution.slot_label
            or request.slot_ordinal != vector_length_resolution.slot_ordinal
            or request.variable_token != vector_length_resolution.variable_token
        ):
            diagnostics.append(
                _array_initialization_vector_alignment_provenance_mismatch_diagnostic(
                    "M70 unresolved request record provenance must match the "
                    "source vector-length resolution",
                    request.leaf_source_location,
                )
            )
    return diagnostics


def _array_initialization_vector_alignment_request_record(
    vector_length_resolution: ExactArrayInitializationVectorLengthResolutionIr,
    diagnostics: list[Diagnostic],
) -> ExactArrayInitializationHelperRequestRecord | None:
    rule = _EXACT_ARRAY_INITIALIZATION_VECTOR_ALIGNMENT_REQUEST_RULE
    vector_alignment_records = tuple(
        request
        for request in vector_length_resolution.unresolved_requests
        if request.helper_leaf_kind == rule.helper_leaf_kind
    )
    if not vector_alignment_records:
        ordinal_or_kind_records = tuple(
            request
            for request in vector_length_resolution.unresolved_requests
            if (
                request.request_ordinal == rule.request_ordinal
                or request.request_kind == rule.request_kind
            )
        )
        if ordinal_or_kind_records:
            for request in ordinal_or_kind_records:
                diagnostics.append(
                    _array_initialization_vector_alignment_mismatch_diagnostic(
                        "array-initialization vector-alignment request "
                        "resolution expected the M67 vector-alignment request "
                        f"to carry ordinal {rule.request_ordinal}, kind "
                        f"{rule.request_kind!r}, and leaf kind "
                        f"{rule.helper_leaf_kind!r}; got ordinal "
                        f"{request.request_ordinal}, kind "
                        f"{request.request_kind!r}, and leaf kind "
                        f"{request.helper_leaf_kind!r}",
                        request.leaf_source_location,
                    )
                )
            return None
        diagnostics.append(
            _array_initialization_vector_alignment_missing_request_diagnostic(
                "array-initialization vector-alignment request resolution "
                "requires one M67 vector-alignment request record preserved by "
                "M70",
                vector_length_resolution.source_location,
            )
        )
        return None
    if len(vector_alignment_records) > 1:
        for request in vector_alignment_records:
            diagnostics.append(
                _array_initialization_vector_alignment_duplicate_request_diagnostic(
                    "array-initialization vector-alignment request resolution "
                    "requires exactly one M67 vector-alignment request record; "
                    f"duplicate record appeared at ordinal "
                    f"{request.request_ordinal}",
                    request.leaf_source_location,
                )
            )
        return None

    vector_alignment_request = vector_alignment_records[0]
    if (
        vector_alignment_request.request_ordinal != rule.request_ordinal
        or vector_alignment_request.request_kind != rule.request_kind
    ):
        diagnostics.append(
            _array_initialization_vector_alignment_mismatch_diagnostic(
                "array-initialization vector-alignment request resolution "
                f"expected ordinal {rule.request_ordinal} and kind "
                f"{rule.request_kind!r}; got ordinal "
                f"{vector_alignment_request.request_ordinal} and kind "
                f"{vector_alignment_request.request_kind!r}",
                vector_alignment_request.leaf_source_location,
            )
        )
    if vector_alignment_request.leaf_source_text != rule.expected_leaf_source_text:
        diagnostics.append(
            _array_initialization_vector_alignment_unsupported_request_diagnostic(
                "array-initialization vector-alignment request resolution "
                "preserves the M67 leaf source text only as provenance and "
                "accepts only the exact M67 vector-alignment leaf text for "
                f"that typed request; got "
                f"{vector_alignment_request.leaf_source_text!r}",
                vector_alignment_request.leaf_source_location,
            )
        )
    return vector_alignment_request


def _array_initialization_vector_alignment_metadata_for_context(
    context: GenerationContext,
    *,
    candidate_id: str,
    target_extension: str,
    source_extension: str,
    selected_type_tag: str,
    location: SourceLocation | None,
) -> Result[ExactArrayInitializationVectorAlignmentMetadata]:
    lookup_key = (
        candidate_id,
        target_extension,
        source_extension,
        selected_type_tag,
    )
    matches = tuple(
        metadata
        for metadata in context.array_initialization_vector_alignment_metadata
        if metadata.lookup_key == lookup_key
    )
    if not matches:
        return Result.failure(
            (
                _array_initialization_vector_alignment_metadata_missing_diagnostic(
                    "array-initialization vector-alignment request resolution "
                    "requires explicit typed vector-alignment metadata for "
                    f"candidate {candidate_id!r}, target extension "
                    f"{target_extension!r}, source extension "
                    f"{source_extension!r}, and selected type tag "
                    f"{selected_type_tag!r}",
                    location,
                ),
            )
        )
    if len(matches) > 1:
        values = tuple(metadata.vector_alignment for metadata in matches)
        code_detail = "conflicting" if len(set(values)) > 1 else "duplicate"
        diagnostic = (
            _array_initialization_vector_alignment_metadata_conflict_diagnostic
            if code_detail == "conflicting"
            else _array_initialization_vector_alignment_metadata_duplicate_diagnostic
        )
        return Result.failure(
            (
                diagnostic(
                    "array-initialization vector-alignment metadata requires "
                    f"exactly one entry for {lookup_key!r}; found "
                    f"{code_detail} entries",
                    matches[0].source_location or location,
                ),
            )
        )
    return Result.ok(matches[0])


def _validate_array_initialization_helper_set_completion_provenance(
    vector_alignment_resolution: ExactArrayInitializationVectorAlignmentResolutionIr,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    vector_length_resolution = (
        vector_alignment_resolution.source_vector_length_resolution
    )
    if vector_alignment_resolution.source_vector_alignment_request not in (
        vector_length_resolution.unresolved_requests
    ):
        diagnostics.append(
            _array_initialization_helper_set_provenance_mismatch_diagnostic(
                "M71 vector-alignment resolution source request must come "
                "from its M70 vector-length resolution",
                vector_alignment_resolution.source_location,
            )
        )
    if vector_alignment_resolution.source_location != (
        vector_length_resolution.source_location
    ):
        diagnostics.append(
            _array_initialization_helper_set_provenance_mismatch_diagnostic(
                "M71 vector-alignment resolution source location must match "
                "its M70 vector-length resolution",
                vector_alignment_resolution.source_location,
            )
        )
    if (
        vector_alignment_resolution.candidate_id
        != vector_length_resolution.candidate_id
        or vector_alignment_resolution.target_extension
        != vector_length_resolution.target_extension
        or vector_alignment_resolution.source_extension
        != vector_length_resolution.source_extension
        or vector_alignment_resolution.selected_type_tag
        != vector_length_resolution.selected_type_tag
        or vector_alignment_resolution.originating_branch_chain_id
        != vector_length_resolution.originating_branch_chain_id
    ):
        diagnostics.append(
            _array_initialization_helper_set_provenance_mismatch_diagnostic(
                "M71 vector-alignment resolution provenance must match its "
                "M70 vector-length resolution",
                vector_alignment_resolution.source_location,
            )
        )
    if (
        vector_alignment_resolution.slot_label
        != vector_length_resolution.slot_label
        or vector_alignment_resolution.slot_ordinal
        != vector_length_resolution.slot_ordinal
        or vector_alignment_resolution.variable_token
        != vector_length_resolution.variable_token
    ):
        diagnostics.append(
            _array_initialization_helper_set_provenance_mismatch_diagnostic(
                "M71 vector-alignment resolution slot provenance must match "
                "its M70 vector-length resolution",
                vector_alignment_resolution.source_location,
            )
        )
    for request in vector_alignment_resolution.unresolved_requests:
        if request.source_form != (
            vector_length_resolution.source_base_type_resolution
            .source_request_ir.source_form
        ):
            diagnostics.append(
                _array_initialization_helper_set_provenance_mismatch_diagnostic(
                    "M71 unresolved request record source form must match the "
                    "source M67 helper-request IR",
                    request.leaf_source_location,
                )
            )
        if request.source_envelope != (
            vector_length_resolution.source_base_type_resolution
            .source_request_ir.source_envelope
        ):
            diagnostics.append(
                _array_initialization_helper_set_provenance_mismatch_diagnostic(
                    "M71 unresolved request record envelope must match the "
                    "source M67 helper-request IR",
                    request.leaf_source_location,
                )
            )
        if (
            request.candidate_id != vector_alignment_resolution.candidate_id
            or request.selected_type_tag
            != vector_alignment_resolution.selected_type_tag
            or request.originating_branch_chain_id
            != vector_alignment_resolution.originating_branch_chain_id
            or request.slot_label != vector_alignment_resolution.slot_label
            or request.slot_ordinal != vector_alignment_resolution.slot_ordinal
            or request.variable_token != vector_alignment_resolution.variable_token
        ):
            diagnostics.append(
                _array_initialization_helper_set_provenance_mismatch_diagnostic(
                    "M71 unresolved request record provenance must match the "
                    "source vector-alignment resolution",
                    request.leaf_source_location,
                )
            )
    return diagnostics


def _array_initialization_backend_uninit_request_record(
    vector_alignment_resolution: ExactArrayInitializationVectorAlignmentResolutionIr,
    diagnostics: list[Diagnostic],
) -> ExactArrayInitializationHelperRequestRecord | None:
    rule = _EXACT_ARRAY_INITIALIZATION_BACKEND_UNINIT_REQUEST_RULE
    backend_uninit_records = tuple(
        request
        for request in vector_alignment_resolution.unresolved_requests
        if request.helper_leaf_kind == rule.helper_leaf_kind
    )
    if not backend_uninit_records:
        ordinal_or_kind_records = tuple(
            request
            for request in vector_alignment_resolution.unresolved_requests
            if (
                request.request_ordinal == rule.request_ordinal
                or request.request_kind == rule.request_kind
            )
        )
        if ordinal_or_kind_records:
            for request in ordinal_or_kind_records:
                diagnostics.append(
                    _array_initialization_helper_set_mismatch_diagnostic(
                        "array-initialization helper-set completion expected "
                        "the M67 backend-uninit request to carry ordinal "
                        f"{rule.request_ordinal}, kind {rule.request_kind!r}, "
                        f"and leaf kind {rule.helper_leaf_kind!r}; got "
                        f"ordinal {request.request_ordinal}, kind "
                        f"{request.request_kind!r}, and leaf kind "
                        f"{request.helper_leaf_kind!r}",
                        request.leaf_source_location,
                    )
                )
            return None
        diagnostics.append(
            _array_initialization_helper_set_missing_request_diagnostic(
                "array-initialization helper-set completion requires one M67 "
                "backend-uninit request record preserved by M71",
                vector_alignment_resolution.source_location,
            )
        )
        return None
    if len(backend_uninit_records) > 1:
        for request in backend_uninit_records:
            diagnostics.append(
                _array_initialization_helper_set_duplicate_request_diagnostic(
                    "array-initialization helper-set completion requires "
                    "exactly one M67 backend-uninit request record; duplicate "
                    f"record appeared at ordinal {request.request_ordinal}",
                    request.leaf_source_location,
                )
            )
        return None

    backend_uninit_request = backend_uninit_records[0]
    if (
        backend_uninit_request.request_ordinal != rule.request_ordinal
        or backend_uninit_request.request_kind != rule.request_kind
    ):
        diagnostics.append(
            _array_initialization_helper_set_mismatch_diagnostic(
                "array-initialization helper-set completion expected ordinal "
                f"{rule.request_ordinal} and kind {rule.request_kind!r}; got "
                f"ordinal {backend_uninit_request.request_ordinal} and kind "
                f"{backend_uninit_request.request_kind!r}",
                backend_uninit_request.leaf_source_location,
            )
        )
    if backend_uninit_request.leaf_source_text != rule.expected_leaf_source_text:
        diagnostics.append(
            _array_initialization_helper_set_unsupported_request_diagnostic(
                "array-initialization helper-set completion preserves the M67 "
                "backend-uninit leaf source text only as provenance and "
                "accepts only the exact M67 backend-uninit leaf text for that "
                f"typed request; got {backend_uninit_request.leaf_source_text!r}",
                backend_uninit_request.leaf_source_location,
            )
        )
    return backend_uninit_request


def _validate_array_initialization_declaration_shell(
    completion: ExactArrayInitializationHelperSetCompletionIr,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    vector_alignment_resolution = completion.source_vector_alignment_resolution
    vector_length_resolution = completion.source_vector_length_resolution
    base_type_resolution = completion.source_base_type_resolution
    helper_request_ir = base_type_resolution.source_request_ir
    source_form = helper_request_ir.source_form
    source_envelope = helper_request_ir.source_envelope
    backend_uninit = completion.unresolved_backend_uninit

    if vector_length_resolution is not (
        vector_alignment_resolution.source_vector_length_resolution
    ):
        diagnostics.append(
            _array_initialization_declaration_shell_provenance_mismatch_diagnostic(
                "M72 helper-set completion must carry the M70 vector-length "
                "resolution accepted by its M71 vector-alignment resolution",
                completion.source_location,
            )
        )
    if base_type_resolution is not vector_length_resolution.source_base_type_resolution:
        diagnostics.append(
            _array_initialization_declaration_shell_provenance_mismatch_diagnostic(
                "M72 helper-set completion must carry the M68 base-type "
                "resolution accepted by its M70 vector-length resolution",
                completion.source_location,
            )
        )
    if (
        completion.source_backend_uninit_request
        not in vector_alignment_resolution.unresolved_requests
    ):
        diagnostics.append(
            _array_initialization_declaration_shell_provenance_mismatch_diagnostic(
                "M72 helper-set completion backend-uninit request must come "
                "from the M71 unresolved request records",
                completion.source_location,
            )
        )
    if (
        backend_uninit.source_backend_uninit_request
        is not completion.source_backend_uninit_request
    ):
        diagnostics.append(
            _array_initialization_declaration_shell_provenance_mismatch_diagnostic(
                "M72 deferred backend-uninit boundary must reference the "
                "selected M67 backend-uninit request",
                completion.source_location,
            )
        )
    if backend_uninit.policy != "deferred_backend_value":
        diagnostics.append(
            _array_initialization_declaration_shell_backend_policy_mismatch_diagnostic(
                "array-initialization declaration-shell lowering preserves "
                "only the M72 deferred_backend_value backend-uninit policy; "
                f"got {backend_uninit.policy!r}",
                backend_uninit.source_location,
            )
        )

    if source_form.source_envelope is not source_envelope:
        diagnostics.append(
            _array_initialization_declaration_shell_provenance_mismatch_diagnostic(
                "M67 helper-request IR source envelope must be the M65 "
                "envelope carried by its M66 slot form",
                source_form.source_location,
            )
        )
    if (
        source_envelope.candidate_id != completion.candidate_id
        or source_envelope.selected_type_tag != completion.selected_type_tag
        or source_envelope.originating_branch_chain_id
        != completion.originating_branch_chain_id
    ):
        diagnostics.append(
            _array_initialization_declaration_shell_provenance_mismatch_diagnostic(
                "M65 envelope provenance must match the M72 helper-set "
                "completion candidate id, selected type tag, and branch-chain "
                "identity",
                source_envelope.source_location,
            )
        )
    for stage_name, source in (
        ("M66 slot form", source_form),
        ("M68 base-type resolution", base_type_resolution),
        ("M70 vector-length resolution", vector_length_resolution),
        ("M71 vector-alignment resolution", vector_alignment_resolution),
        ("M72 backend-uninit boundary", backend_uninit),
    ):
        if (
            source.candidate_id != completion.candidate_id
            or source.selected_type_tag != completion.selected_type_tag
            or source.originating_branch_chain_id
            != completion.originating_branch_chain_id
            or source.slot_label != completion.slot_label
            or source.slot_ordinal != completion.slot_ordinal
            or source.variable_token != completion.variable_token
        ):
            diagnostics.append(
                _array_initialization_declaration_shell_provenance_mismatch_diagnostic(
                    f"{stage_name} provenance must match the M72 helper-set "
                    "completion",
                    source.source_location,
                )
            )
    for stage_name, source in (
        ("M70 vector-length resolution", vector_length_resolution),
        ("M71 vector-alignment resolution", vector_alignment_resolution),
        ("M72 backend-uninit boundary", backend_uninit),
    ):
        if (
            source.target_extension != completion.target_extension
            or source.source_extension != completion.source_extension
        ):
            diagnostics.append(
                _array_initialization_declaration_shell_provenance_mismatch_diagnostic(
                    f"{stage_name} target/source extension provenance must "
                    "match the M72 helper-set completion",
                    source.source_location,
                )
            )

    if (
        completion.slot_label != "opaque_pre_branch_array_initialization"
        or completion.slot_ordinal != 0
        or completion.variable_token != "tmp"
        or source_form.slot_label != "opaque_pre_branch_array_initialization"
        or source_form.slot_ordinal != 0
        or source_form.variable_token != "tmp"
    ):
        diagnostics.append(
            _array_initialization_declaration_shell_malformed_diagnostic(
                "array-initialization declaration-shell lowering supports "
                "only the exact first-slot "
                "opaque_pre_branch_array_initialization var<typed>(..., tmp, "
                "...) shell",
                source_form.variable_token_location or source_form.source_location,
            )
        )
    expected_leaf_kinds = (
        source_form.base_type_leaf.kind,
        source_form.vector_length_leaf.kind,
        source_form.vector_alignment_leaf.kind,
        source_form.backend_uninit_leaf.kind,
    )
    if expected_leaf_kinds != (
        "type_generation_base_in",
        "value_generation_vector_length",
        "value_generation_vector_alignment",
        "value_backend_uninit_array",
    ):
        diagnostics.append(
            _array_initialization_declaration_shell_malformed_diagnostic(
                "array-initialization declaration-shell lowering requires the "
                "exact M66 helper-leaf shape for base type, vector length, "
                "vector alignment, and deferred backend uninit",
                source_form.source_location,
            )
        )
    if (
        base_type_resolution.resolved_type_ref.kind != "base.in"
        or base_type_resolution.resolved_type_ref.type_tag
        != completion.selected_type_tag
    ):
        diagnostics.append(
            _array_initialization_declaration_shell_malformed_diagnostic(
                "array-initialization declaration-shell lowering requires the "
                "accepted M68 base.in type fact for the selected type tag",
                base_type_resolution.source_location,
            )
        )
    if not isinstance(
        vector_length_resolution.resolved_vector_length,
        ExactArrayInitializationVectorLengthValue,
    ):
        diagnostics.append(
            _array_initialization_declaration_shell_malformed_diagnostic(
                "array-initialization declaration-shell lowering requires the "
                "accepted typed M70 vector-length fact",
                vector_length_resolution.source_location,
            )
        )
    if not isinstance(
        vector_alignment_resolution.resolved_vector_alignment,
        ExactArrayInitializationVectorAlignmentValue,
    ) or vector_alignment_resolution.resolved_vector_alignment.kind == "unsupported":
        diagnostics.append(
            _array_initialization_declaration_shell_malformed_diagnostic(
                "array-initialization declaration-shell lowering requires the "
                "accepted typed M71 vector-alignment fact",
                vector_alignment_resolution.source_location,
            )
        )
    return diagnostics


def _validate_array_body_structural_sequence_inputs(
    envelope: ExactArrayBodyEnvelopeIr,
    shell: ExactArrayInitializationDeclarationShellIr,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []

    if not isinstance(envelope, ExactArrayBodyEnvelopeIr):
        diagnostics.append(
            _array_body_structural_sequence_source_unsupported_diagnostic(
                "array-body structural sequence classification requires an "
                "accepted M65 ExactArrayBodyEnvelopeIr source",
                None,
            )
        )
        return diagnostics
    if not isinstance(shell, ExactArrayInitializationDeclarationShellIr):
        diagnostics.append(
            _array_body_structural_sequence_source_unsupported_diagnostic(
                "array-body structural sequence classification requires an "
                "accepted M73 ExactArrayInitializationDeclarationShellIr source",
                None,
            )
        )
        return diagnostics

    if not _exact_array_body_envelope_shape_is_supported(envelope):
        labels = tuple(slot.label for slot in envelope.slots)
        ordinals = tuple(slot.ordinal for slot in envelope.slots)
        if len(envelope.slots) == len(_EXACT_ARRAY_BODY_ENVELOPE_SLOT_LABELS):
            diagnostics.append(
                _array_body_structural_sequence_role_mismatch_diagnostic(
                    "array-body structural sequence classification requires "
                    "the accepted M65 five-slot source order "
                    f"{_EXACT_ARRAY_BODY_ENVELOPE_SLOT_LABELS!r}; got labels "
                    f"{labels!r} and ordinals {ordinals!r}",
                    envelope.source_location,
                )
            )
        else:
            diagnostics.append(
                _array_body_structural_sequence_malformed_diagnostic(
                    "array-body structural sequence classification requires "
                    f"exactly five accepted M65 slots; got {len(envelope.slots)}",
                    envelope.source_location,
                )
            )

    if (
        envelope.candidate_id != shell.candidate_id
        or envelope.selected_type_tag != shell.selected_type_tag
        or envelope.originating_branch_chain_id != shell.originating_branch_chain_id
    ):
        diagnostics.append(
            _array_body_structural_sequence_context_mismatch_diagnostic(
                "array-body structural sequence classification requires M65 "
                "envelope and M73 declaration shell candidate id, selected "
                "type tag, and branch-chain identity to match",
                shell.source_location,
            )
        )

    if shell.source_envelope is not envelope:
        diagnostics.append(
            _array_body_structural_sequence_provenance_mismatch_diagnostic(
                "M73 declaration shell must reference the same accepted M65 "
                "array-body envelope supplied to structural sequence "
                "classification",
                shell.source_location,
            )
        )
    if (
        shell.slot_label != "opaque_pre_branch_array_initialization"
        or shell.slot_ordinal != 0
    ):
        diagnostics.append(
            _array_body_structural_sequence_malformed_diagnostic(
                "array-body structural sequence classification attaches the "
                "M73 declaration shell only to the first M65 slot at ordinal 0",
                shell.source_location,
            )
        )
    if len(envelope.slots) >= 3:
        selected_slot = envelope.slots[2]
        if not isinstance(selected_slot, ExactArrayBodyEnvelopeSelectedSlot):
            diagnostics.append(
                _array_body_structural_sequence_role_mismatch_diagnostic(
                    "array-body structural sequence classification requires "
                    "the selected-body envelope role at slot ordinal 2",
                    getattr(selected_slot, "source_location", envelope.source_location),
                )
            )
        elif (
            selected_slot.selected_body_envelope.candidate_id != envelope.candidate_id
            or selected_slot.selected_body_envelope.selected_type_tag
            != envelope.selected_type_tag
            or selected_slot.selected_body_envelope.originating_branch_chain_id
            != envelope.originating_branch_chain_id
        ):
            diagnostics.append(
                _array_body_structural_sequence_provenance_mismatch_diagnostic(
                    "M65 selected-body slot must preserve the accepted M63 "
                    "selected/no-body envelope provenance",
                    selected_slot.source_location,
                )
            )
    return diagnostics


def _validate_predicate_path_structural_request_input(
    sequence: ExactArrayBodyStructuralSequenceIr,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    if not isinstance(sequence, ExactArrayBodyStructuralSequenceIr):
        return [
            _predicate_path_source_unsupported_diagnostic(
                "predicate-path structural request lowering requires an "
                "accepted M74 ExactArrayBodyStructuralSequenceIr source",
                None,
            )
        ]
    if tuple(role.role_label for role in sequence.roles) != (
        _EXACT_ARRAY_BODY_STRUCTURAL_ROLE_LABELS
    ) or tuple(role.role_ordinal for role in sequence.roles) != (
        _EXACT_ARRAY_BODY_ENVELOPE_SLOT_ORDINALS
    ):
        diagnostics.append(
            _predicate_path_malformed_diagnostic(
                "predicate-path structural request lowering requires the "
                "accepted M74 five-role source order",
                sequence.source_location,
            )
        )
        return diagnostics

    envelope = sequence.source_envelope
    if tuple(role.envelope_slot for role in sequence.roles) != envelope.slots:
        diagnostics.append(
            _predicate_path_provenance_mismatch_diagnostic(
                "M75 predicate-path roles must preserve the M74 source slot "
                "identity and order",
                sequence.source_location,
            )
        )
    for role in sequence.roles:
        if (
            role.candidate_id != sequence.candidate_id
            or role.selected_type_tag != sequence.selected_type_tag
            or role.originating_branch_chain_id
            != sequence.originating_branch_chain_id
            or role.target_extension != sequence.target_extension
            or role.source_extension != sequence.source_extension
        ):
            diagnostics.append(
                _predicate_path_context_mismatch_diagnostic(
                    "predicate-path structural request roles must match the "
                    "M74 sequence candidate, extension, selected type, and "
                    "branch-chain context",
                    role.source_location,
                )
            )

    init_role = sequence.roles[1]
    selected_role = sequence.roles[2]
    store_role = sequence.roles[3]
    if (
        init_role.role_label != "opaque_predicate_init_shaped_slot"
        or init_role.role_ordinal != 1
        or not isinstance(init_role.envelope_slot, ExactArrayBodyEnvelopeOpaqueSlot)
        or init_role.opaque_source_text != init_role.envelope_slot.opaque_source_text
    ):
        diagnostics.append(
            _predicate_path_malformed_diagnostic(
                "predicate-path structural request requires M74 role ordinal "
                "1 to be the opaque predicate-init-shaped slot",
                init_role.source_location,
            )
        )
    if (
        selected_role.role_label != "selected_body_envelope_slot"
        or selected_role.role_ordinal != 2
        or not isinstance(
            selected_role.selected_body_envelope,
            (SelectedBodyEnvelopeIr, NoSelectedBodyEnvelopeIr),
        )
        or selected_role.selected_body_envelope
        is not envelope.selected_body_slot.selected_body_envelope
    ):
        diagnostics.append(
            _predicate_path_provenance_mismatch_diagnostic(
                "predicate-path structural request requires M74 role ordinal "
                "2 to preserve the accepted M63 selected/no-body envelope",
                selected_role.source_location,
            )
        )
    if (
        store_role.role_label != "opaque_post_branch_store_call_shaped_slot"
        or store_role.role_ordinal != 3
        or not isinstance(store_role.envelope_slot, ExactArrayBodyEnvelopeOpaqueSlot)
        or store_role.opaque_source_text != store_role.envelope_slot.opaque_source_text
    ):
        diagnostics.append(
            _predicate_path_malformed_diagnostic(
                "predicate-path structural request requires M74 role ordinal "
                "3 to be the opaque post-branch store-call-shaped slot",
                store_role.source_location,
            )
        )

    if diagnostics:
        return diagnostics

    assert init_role.opaque_source_text is not None
    assert store_role.opaque_source_text is not None
    init_match = _EXACT_PREDICATE_INIT_SLOT_RE.match(init_role.opaque_source_text)
    if init_match is None:
        diagnostics.append(
            _predicate_path_malformed_diagnostic(
                "predicate-path structural request requires exact predicate-init "
                "shape 'svbool_t pg = intrin<svptrue_b8>();'",
                init_role.source_location,
            )
        )
    store_match = _EXACT_POST_BRANCH_STORE_PREDICATE_SLOT_RE.match(
        store_role.opaque_source_text,
    )
    if store_match is None:
        diagnostics.append(
            _predicate_path_malformed_diagnostic(
                "predicate-path structural request requires exact post-branch "
                "store-call predicate-token shape",
                store_role.source_location,
            )
        )

    if init_match is None or store_match is None:
        return diagnostics

    predicate_type = init_match.group("predicate_type")
    predicate_token = init_match.group("predicate_token")
    init_direct_token = init_match.group("direct_intrinsic_token")
    store_call_token = store_match.group("call_token")
    store_predicate_token = store_match.group("predicate_token")
    if (
        predicate_type != "svbool_t"
        or predicate_token != "pg"
        or init_direct_token != "svptrue_b8"
        or store_call_token != "svst1"
    ):
        diagnostics.append(
            _predicate_path_malformed_diagnostic(
                "predicate-path structural request requires the exact M75 "
                "predicate-init and store-call structural tokens",
                init_role.source_location,
            )
        )
    if store_predicate_token != predicate_token:
        diagnostics.append(
            _predicate_path_token_mismatch_diagnostic(
                "predicate-path structural request requires the slot-3 predicate "
                "argument token to match the slot-1 predicate token",
                store_role.source_location,
            )
        )

    selected_body_envelope = selected_role.selected_body_envelope
    if isinstance(selected_body_envelope, SelectedBodyEnvelopeIr):
        if len(selected_body_envelope.entries) != 1:
            diagnostics.append(
                _predicate_path_provenance_mismatch_diagnostic(
                    "predicate-path structural request requires the accepted "
                    "M63 selected-body envelope to carry exactly one M62 entry",
                    selected_body_envelope.source_location,
                )
            )
            return diagnostics
        entry = selected_body_envelope.entries[0]
        if (
            entry.candidate_id != selected_body_envelope.candidate_id
            or entry.selected_type_tag != selected_body_envelope.selected_type_tag
            or entry.originating_branch_chain_id
            != selected_body_envelope.originating_branch_chain_id
            or entry.source_location != selected_body_envelope.source_location
            or entry.source_body_ir.candidate_id != entry.candidate_id
            or entry.source_body_ir.selected_type_tag != entry.selected_type_tag
            or entry.source_body_ir.originating_branch_chain_id
            != entry.originating_branch_chain_id
            or entry.source_body_ir.source_location != entry.source_location
            or entry.source_body_ir.direct_intrinsic_token_text
            != entry.direct_intrinsic_token_text
        ):
            diagnostics.append(
                _predicate_path_provenance_mismatch_diagnostic(
                    "predicate-path structural request requires M63 selected-body "
                    "envelope and M62 direct-intrinsic body IR provenance to match",
                    entry.source_location,
                )
            )
        if entry.assignment_target_text != predicate_token:
            diagnostics.append(
                _predicate_path_token_mismatch_diagnostic(
                    "predicate-path structural request requires the selected-body "
                    "assignment target token to match the slot-1 predicate token",
                    entry.source_location,
                )
            )
    elif isinstance(selected_body_envelope, NoSelectedBodyEnvelopeIr):
        if (
            selected_body_envelope.entries
            or selected_body_envelope.source_body_ir.candidate_id
            != selected_body_envelope.candidate_id
            or selected_body_envelope.source_body_ir.selected_type_tag
            != selected_body_envelope.selected_type_tag
            or selected_body_envelope.source_body_ir.originating_branch_chain_id
            != selected_body_envelope.originating_branch_chain_id
            or selected_body_envelope.source_body_ir.source_location
            != selected_body_envelope.source_location
        ):
            diagnostics.append(
                _predicate_path_provenance_mismatch_diagnostic(
                    "predicate-path structural request requires accepted "
                    "no-selected-body envelope provenance to match its M62 "
                    "no-body IR",
                    selected_body_envelope.source_location,
                )
            )

    return diagnostics


def _exact_array_body_envelope_shape_is_supported(
    envelope: ExactArrayBodyEnvelopeIr,
) -> bool:
    return (
        tuple(slot.label for slot in envelope.slots)
        == _EXACT_ARRAY_BODY_ENVELOPE_SLOT_LABELS
        and tuple(slot.ordinal for slot in envelope.slots)
        == _EXACT_ARRAY_BODY_ENVELOPE_SLOT_ORDINALS
    )


def _structural_role_from_slot(
    role_label: ExactArrayBodyStructuralRoleLabel,
    slot: ExactArrayBodyEnvelopeSlot,
    shell: ExactArrayInitializationDeclarationShellIr,
    *,
    target_extension: str,
    source_extension: str,
) -> _ExactArrayBodyStructuralRole:
    declaration_shell: ExactArrayInitializationDeclarationShellIr | None = None
    selected_body_envelope: GenerationSelectedBodyEnvelopeIr | None = None
    opaque_source_text: str | None = None

    if role_label == "first_slot_declaration_shell":
        declaration_shell = shell
    elif role_label == "selected_body_envelope_slot":
        if not isinstance(slot, ExactArrayBodyEnvelopeSelectedSlot):
            raise ValueError(
                "selected-body role must be backed by the M65 selected-body slot"
            )
        selected_body_envelope = slot.selected_body_envelope
    else:
        if not isinstance(slot, ExactArrayBodyEnvelopeOpaqueSlot):
            raise ValueError("opaque structural role must be backed by an opaque slot")
        opaque_source_text = slot.opaque_source_text

    return _ExactArrayBodyStructuralRole(
        role_label=role_label,
        role_ordinal=slot.ordinal,
        envelope_slot=slot,
        source_location=slot.source_location,
        candidate_id=slot.candidate_id,
        target_extension=target_extension,
        source_extension=source_extension,
        selected_type_tag=slot.selected_type_tag,
        originating_branch_chain_id=slot.originating_branch_chain_id,
        declaration_shell=declaration_shell,
        selected_body_envelope=selected_body_envelope,
        opaque_source_text=opaque_source_text,
    )


def _array_initialization_leaf(
    kind: ExactArrayInitializationHelperLeafKind,
    slot_location: SourceLocation,
    match: re.Match[str],
    group_name: str,
) -> ExactArrayInitializationUnresolvedLeaf:
    return ExactArrayInitializationUnresolvedLeaf(
        kind=kind,
        source_text=match.group(group_name),
        source_location=_source_span_for_match_group(
            slot_location,
            match,
            group_name,
        ),
    )


def _source_span_for_match_group(
    source_location: SourceLocation,
    match: re.Match[str],
    group_name: str,
) -> SourceLocation:
    start = match.start(group_name)
    end = match.end(group_name)
    return SourceLocation(
        source_location.path,
        source_location.line,
        source_location.column + start,
        end_line=source_location.line,
        end_column=source_location.column + end,
    )


def _lowered_implementation_location(
    implementation: LoweredImplementation,
) -> SourceLocation | None:
    for array_envelope in implementation.array_body_envelopes:
        return array_envelope.source_location
    for declaration_shell in implementation.array_initialization_declaration_shells:
        return declaration_shell.source_location
    for selected_envelope in implementation.selected_body_envelopes:
        return selected_envelope.source_location
    for stage in implementation.generation_stages:
        location = _stage_output_location(stage.output)
        if location is not None:
            return location
    return None


def _validate_exact_array_body_envelope_skeleton(
    skeleton: ExactArrayBodyEnvelopeSkeleton,
    envelope: GenerationSelectedBodyEnvelopeIr,
) -> Diagnostic | None:
    if not skeleton.is_exact_array_body_shape:
        return _array_body_envelope_shape_unsupported_diagnostic(
            "array-body envelope slot assembly supports only the exact "
            "array.tsl:105-111 structural skeleton",
            skeleton.source_location,
        )

    slots = skeleton.slots
    if len(slots) != len(_EXACT_ARRAY_BODY_ENVELOPE_SLOT_LABELS):
        return _array_body_envelope_shape_unsupported_diagnostic(
            "array-body envelope slot assembly requires exactly five slots; "
            f"got {len(slots)}",
            skeleton.source_location,
        )

    labels = tuple(slot.label for slot in slots)
    if labels != _EXACT_ARRAY_BODY_ENVELOPE_SLOT_LABELS:
        if _has_exact_array_body_labels_once(labels):
            return Diagnostic.error(
                "TSL-LOWER-ARRAY-BODY-ENVELOPE-SLOT-ORDER",
                "array-body envelope slots must appear in the exact M64 "
                f"order {_EXACT_ARRAY_BODY_ENVELOPE_SLOT_LABELS!r}; got "
                f"{labels!r}",
                location=skeleton.source_location,
            )
        return _array_body_envelope_shape_unsupported_diagnostic(
            "array-body envelope slot assembly requires exactly one of each "
            f"M64 slot label {_EXACT_ARRAY_BODY_ENVELOPE_SLOT_LABELS!r}; got "
            f"{labels!r}",
            skeleton.source_location,
        )

    ordinals = tuple(slot.ordinal for slot in slots)
    if ordinals != _EXACT_ARRAY_BODY_ENVELOPE_SLOT_ORDINALS:
        return Diagnostic.error(
            "TSL-LOWER-ARRAY-BODY-ENVELOPE-SLOT-ORDER",
            "array-body envelope slot ordinals must be deterministic and "
            f"ordered as {_EXACT_ARRAY_BODY_ENVELOPE_SLOT_ORDINALS!r}; got "
            f"{ordinals!r}",
            location=skeleton.source_location,
        )

    for slot in slots:
        if (
            slot.candidate_id != skeleton.candidate_id
            or slot.selected_type_tag != skeleton.selected_type_tag
            or slot.originating_branch_chain_id
            != skeleton.originating_branch_chain_id
        ):
            return Diagnostic.error(
                "TSL-LOWER-ARRAY-BODY-ENVELOPE-PROVENANCE-MISMATCH",
                "array-body envelope skeleton slot provenance must match "
                "the skeleton candidate, selected type tag, and branch-chain "
                "identity",
                location=slot.source_location,
            )
        if (
            slot.label in _EXACT_ARRAY_BODY_ENVELOPE_OPAQUE_SLOT_LABELS
            and not (slot.opaque_source_text or "").strip()
        ):
            return _array_body_envelope_shape_unsupported_diagnostic(
                "array-body envelope opaque slots must preserve opaque source text",
                slot.source_location,
            )
        if slot.label == "selected_body_envelope" and slot.opaque_source_text is not None:
            return _array_body_envelope_shape_unsupported_diagnostic(
                "array-body envelope selected-body slot must reference the "
                "M63 envelope without carrying selected branch text",
                slot.source_location,
            )

    if (
        skeleton.candidate_id != envelope.candidate_id
        or skeleton.selected_type_tag != envelope.selected_type_tag
        or skeleton.originating_branch_chain_id
        != envelope.originating_branch_chain_id
    ):
        return Diagnostic.error(
            "TSL-LOWER-ARRAY-BODY-ENVELOPE-PROVENANCE-MISMATCH",
            "array-body envelope skeleton provenance must match the nested "
            "M63 envelope candidate id, selected type tag, and branch-chain "
            "identity",
            location=skeleton.source_location,
        )

    selected_slot = slots[2]
    if (
        selected_slot.candidate_id != envelope.candidate_id
        or selected_slot.selected_type_tag != envelope.selected_type_tag
        or selected_slot.originating_branch_chain_id
        != envelope.originating_branch_chain_id
    ):
        return Diagnostic.error(
            "TSL-LOWER-ARRAY-BODY-ENVELOPE-PROVENANCE-MISMATCH",
            "array-body envelope selected slot provenance must match the "
            "nested M63 envelope candidate id, selected type tag, and "
            "branch-chain identity",
            location=selected_slot.source_location,
        )

    return None


def _has_exact_array_body_labels_once(
    labels: tuple[ExactArrayBodyEnvelopeSlotLabel, ...],
) -> bool:
    if len(labels) != len(_EXACT_ARRAY_BODY_ENVELOPE_SLOT_LABELS):
        return False
    return all(
        labels.count(expected) == 1
        for expected in _EXACT_ARRAY_BODY_ENVELOPE_SLOT_LABELS
    )


def _array_body_envelope_shape_unsupported_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-BODY-ENVELOPE-SHAPE-UNSUPPORTED",
        detail,
        location=location,
    )


def _array_initialization_slot_source_unsupported_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-SLOT-SOURCE-UNSUPPORTED",
        detail,
        location=location,
    )


def _array_initialization_slot_missing_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-SLOT-MISSING",
        detail,
        location=location,
    )


def _array_initialization_slot_wrong_position_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-SLOT-WRONG-POSITION",
        detail,
        location=location,
    )


def _array_initialization_slot_malformed_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-SLOT-FORM-MALFORMED",
        detail,
        location=location,
    )


def _array_initialization_slot_helper_unsupported_diagnostic(
    slot: ExactArrayBodyEnvelopeOpaqueSlot,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-SLOT-HELPER-UNSUPPORTED",
        "array-initialization slot form lowering preserves only the exact "
        "unresolved helper leaves type<generation>(base::in), "
        "value<generation>(vector::length), "
        "value<generation>(vector::alignment), and "
        "value<backend>(uninit::array)",
        location=slot.source_location,
    )


def _array_initialization_slot_provenance_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-SLOT-PROVENANCE-MISMATCH",
        detail,
        location=location,
    )


def _array_initialization_helper_request_source_unsupported_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-HELPER-REQUEST-SOURCE-UNSUPPORTED",
        detail,
        location=location,
    )


def _array_initialization_helper_request_missing_form_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-HELPER-REQUEST-FORM-MISSING",
        detail,
        location=location,
    )


def _array_initialization_helper_request_missing_leaf_diagnostic(
    spec: _ExactArrayInitializationHelperLeafSpec,
    form: ExactArrayInitializationSlotFormIr,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-HELPER-REQUEST-LEAF-MISSING",
        "array-initialization helper request lowering requires the M66 "
        f"{spec.field_name} field to carry the unresolved helper leaf "
        f"{spec.expected_leaf_kind!r}",
        location=form.source_location,
    )


def _array_initialization_helper_request_mismatched_leaf_diagnostic(
    spec: _ExactArrayInitializationHelperLeafSpec,
    leaf: ExactArrayInitializationUnresolvedLeaf,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-HELPER-REQUEST-LEAF-MISMATCH",
        "array-initialization helper request lowering expected the M66 "
        f"{spec.field_name} field to carry leaf kind "
        f"{spec.expected_leaf_kind!r}, got {leaf.kind!r}",
        location=leaf.source_location,
    )


def _array_initialization_helper_request_duplicate_leaf_diagnostic(
    leaf: ExactArrayInitializationUnresolvedLeaf,
    form: ExactArrayInitializationSlotFormIr,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-HELPER-REQUEST-LEAF-DUPLICATE",
        "array-initialization helper request lowering requires each of the "
        "four M66 helper leaf kinds exactly once; duplicate leaf kind "
        f"{leaf.kind!r} appeared for variable {form.variable_token!r}",
        location=leaf.source_location,
    )


def _array_initialization_helper_request_unsupported_leaf_diagnostic(
    spec: _ExactArrayInitializationHelperLeafSpec,
    leaf: ExactArrayInitializationUnresolvedLeaf,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-HELPER-REQUEST-LEAF-UNSUPPORTED",
        "array-initialization helper request lowering preserves only the "
        "exact M66 unresolved helper leaf text for "
        f"{spec.expected_leaf_kind!r}; got {leaf.source_text!r}",
        location=leaf.source_location,
    )


def _array_initialization_helper_request_provenance_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-HELPER-REQUEST-PROVENANCE-MISMATCH",
        detail,
        location=location,
    )


def _array_initialization_base_type_resolution_source_unsupported_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-BASE-TYPE-REQUEST-SOURCE-UNSUPPORTED",
        detail,
        location=location,
    )


def _array_initialization_base_type_resolution_missing_ir_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-BASE-TYPE-REQUEST-IR-MISSING",
        detail,
        location=location,
    )


def _array_initialization_base_type_resolution_multiple_ir_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-BASE-TYPE-REQUEST-IR-MULTIPLE",
        detail,
        location=location,
    )


def _array_initialization_base_type_resolution_missing_request_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-BASE-TYPE-REQUEST-MISSING",
        detail,
        location=location,
    )


def _array_initialization_base_type_resolution_duplicate_request_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-BASE-TYPE-REQUEST-DUPLICATE",
        detail,
        location=location,
    )


def _array_initialization_base_type_resolution_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-BASE-TYPE-REQUEST-MISMATCH",
        detail,
        location=location,
    )


def _array_initialization_base_type_resolution_unsupported_request_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-BASE-TYPE-REQUEST-UNSUPPORTED",
        detail,
        location=location,
    )


def _array_initialization_base_type_resolution_provenance_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-BASE-TYPE-REQUEST-PROVENANCE-MISMATCH",
        detail,
        location=location,
    )


def _array_initialization_vector_length_source_unsupported_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-VECTOR-LENGTH-REQUEST-SOURCE-UNSUPPORTED",
        detail,
        location=location,
    )


def _array_initialization_vector_length_missing_ir_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-VECTOR-LENGTH-REQUEST-IR-MISSING",
        detail,
        location=location,
    )


def _array_initialization_vector_length_multiple_ir_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-VECTOR-LENGTH-REQUEST-IR-MULTIPLE",
        detail,
        location=location,
    )


def _array_initialization_vector_length_missing_request_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-VECTOR-LENGTH-REQUEST-MISSING",
        detail,
        location=location,
    )


def _array_initialization_vector_length_duplicate_request_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-VECTOR-LENGTH-REQUEST-DUPLICATE",
        detail,
        location=location,
    )


def _array_initialization_vector_length_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-VECTOR-LENGTH-REQUEST-MISMATCH",
        detail,
        location=location,
    )


def _array_initialization_vector_length_unsupported_request_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-VECTOR-LENGTH-REQUEST-UNSUPPORTED",
        detail,
        location=location,
    )


def _array_initialization_vector_length_metadata_missing_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-VECTOR-LENGTH-METADATA-MISSING",
        detail,
        location=location,
    )


def _array_initialization_vector_length_metadata_duplicate_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-VECTOR-LENGTH-METADATA-DUPLICATE",
        detail,
        location=location,
    )


def _array_initialization_vector_length_metadata_conflict_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-VECTOR-LENGTH-METADATA-CONFLICT",
        detail,
        location=location,
    )


def _array_initialization_vector_length_metadata_unsupported_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-VECTOR-LENGTH-METADATA-UNSUPPORTED",
        detail,
        location=location,
    )


def _array_initialization_vector_length_context_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-VECTOR-LENGTH-CONTEXT-MISMATCH",
        detail,
        location=location,
    )


def _array_initialization_vector_length_provenance_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-VECTOR-LENGTH-PROVENANCE-MISMATCH",
        detail,
        location=location,
    )


def _array_initialization_vector_alignment_source_unsupported_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-VECTOR-ALIGNMENT-REQUEST-SOURCE-UNSUPPORTED",
        detail,
        location=location,
    )


def _array_initialization_vector_alignment_missing_ir_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-VECTOR-ALIGNMENT-REQUEST-IR-MISSING",
        detail,
        location=location,
    )


def _array_initialization_vector_alignment_multiple_ir_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-VECTOR-ALIGNMENT-REQUEST-IR-MULTIPLE",
        detail,
        location=location,
    )


def _array_initialization_vector_alignment_missing_request_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-VECTOR-ALIGNMENT-REQUEST-MISSING",
        detail,
        location=location,
    )


def _array_initialization_vector_alignment_duplicate_request_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-VECTOR-ALIGNMENT-REQUEST-DUPLICATE",
        detail,
        location=location,
    )


def _array_initialization_vector_alignment_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-VECTOR-ALIGNMENT-REQUEST-MISMATCH",
        detail,
        location=location,
    )


def _array_initialization_vector_alignment_unsupported_request_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-VECTOR-ALIGNMENT-REQUEST-UNSUPPORTED",
        detail,
        location=location,
    )


def _array_initialization_vector_alignment_metadata_missing_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-VECTOR-ALIGNMENT-METADATA-MISSING",
        detail,
        location=location,
    )


def _array_initialization_vector_alignment_metadata_duplicate_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-VECTOR-ALIGNMENT-METADATA-DUPLICATE",
        detail,
        location=location,
    )


def _array_initialization_vector_alignment_metadata_conflict_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-VECTOR-ALIGNMENT-METADATA-CONFLICT",
        detail,
        location=location,
    )


def _array_initialization_vector_alignment_metadata_unsupported_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-VECTOR-ALIGNMENT-METADATA-UNSUPPORTED",
        detail,
        location=location,
    )


def _array_initialization_vector_alignment_context_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-VECTOR-ALIGNMENT-CONTEXT-MISMATCH",
        detail,
        location=location,
    )


def _array_initialization_vector_alignment_provenance_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-VECTOR-ALIGNMENT-PROVENANCE-MISMATCH",
        detail,
        location=location,
    )


def _array_initialization_helper_set_source_unsupported_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-HELPER-SET-SOURCE-UNSUPPORTED",
        detail,
        location=location,
    )


def _array_initialization_helper_set_missing_ir_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-HELPER-SET-IR-MISSING",
        detail,
        location=location,
    )


def _array_initialization_helper_set_multiple_ir_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-HELPER-SET-IR-MULTIPLE",
        detail,
        location=location,
    )


def _array_initialization_helper_set_missing_request_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-HELPER-SET-BACKEND-UNINIT-MISSING",
        detail,
        location=location,
    )


def _array_initialization_helper_set_duplicate_request_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-HELPER-SET-BACKEND-UNINIT-DUPLICATE",
        detail,
        location=location,
    )


def _array_initialization_helper_set_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-HELPER-SET-BACKEND-UNINIT-MISMATCH",
        detail,
        location=location,
    )


def _array_initialization_helper_set_unsupported_request_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-HELPER-SET-BACKEND-UNINIT-UNSUPPORTED",
        detail,
        location=location,
    )


def _array_initialization_helper_set_context_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-HELPER-SET-CONTEXT-MISMATCH",
        detail,
        location=location,
    )


def _array_initialization_helper_set_provenance_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-HELPER-SET-PROVENANCE-MISMATCH",
        detail,
        location=location,
    )


def _array_initialization_declaration_shell_source_unsupported_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-DECLARATION-SHELL-SOURCE-UNSUPPORTED",
        detail,
        location=location,
    )


def _array_initialization_declaration_shell_missing_ir_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-DECLARATION-SHELL-IR-MISSING",
        detail,
        location=location,
    )


def _array_initialization_declaration_shell_multiple_ir_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-DECLARATION-SHELL-IR-MULTIPLE",
        detail,
        location=location,
    )


def _array_initialization_declaration_shell_context_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-DECLARATION-SHELL-CONTEXT-MISMATCH",
        detail,
        location=location,
    )


def _array_initialization_declaration_shell_provenance_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-DECLARATION-SHELL-PROVENANCE-MISMATCH",
        detail,
        location=location,
    )


def _array_initialization_declaration_shell_malformed_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-DECLARATION-SHELL-MALFORMED",
        detail,
        location=location,
    )


def _array_initialization_declaration_shell_backend_policy_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-INIT-DECLARATION-SHELL-BACKEND-UNINIT-POLICY-MISMATCH",
        detail,
        location=location,
    )


def _array_body_structural_sequence_source_unsupported_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-BODY-STRUCTURAL-SEQUENCE-SOURCE-UNSUPPORTED",
        detail,
        location=location,
    )


def _array_body_structural_sequence_missing_ir_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-BODY-STRUCTURAL-SEQUENCE-IR-MISSING",
        detail,
        location=location,
    )


def _array_body_structural_sequence_multiple_ir_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-BODY-STRUCTURAL-SEQUENCE-IR-MULTIPLE",
        detail,
        location=location,
    )


def _array_body_structural_sequence_context_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-BODY-STRUCTURAL-SEQUENCE-CONTEXT-MISMATCH",
        detail,
        location=location,
    )


def _array_body_structural_sequence_provenance_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-BODY-STRUCTURAL-SEQUENCE-PROVENANCE-MISMATCH",
        detail,
        location=location,
    )


def _array_body_structural_sequence_role_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-BODY-STRUCTURAL-SEQUENCE-ROLE-MISMATCH",
        detail,
        location=location,
    )


def _array_body_structural_sequence_malformed_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-BODY-STRUCTURAL-SEQUENCE-MALFORMED",
        detail,
        location=location,
    )


def _predicate_path_source_unsupported_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-PREDICATE-PATH-SOURCE-UNSUPPORTED",
        detail,
        location=location,
    )


def _predicate_path_missing_ir_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-PREDICATE-PATH-IR-MISSING",
        detail,
        location=location,
    )


def _predicate_path_multiple_ir_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-PREDICATE-PATH-IR-MULTIPLE",
        detail,
        location=location,
    )


def _predicate_path_context_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-PREDICATE-PATH-CONTEXT-MISMATCH",
        detail,
        location=location,
    )


def _predicate_path_provenance_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-PREDICATE-PATH-PROVENANCE-MISMATCH",
        detail,
        location=location,
    )


def _predicate_path_malformed_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-PREDICATE-PATH-MALFORMED",
        detail,
        location=location,
    )


def _predicate_path_token_mismatch_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-PREDICATE-PATH-TOKEN-MISMATCH",
        detail,
        location=location,
    )


def _duplicate_array_body_envelope_skeleton_diagnostic(
    lookup_key: ExactArrayBodyEnvelopeSkeletonKey,
    skeleton: ExactArrayBodyEnvelopeSkeleton,
    *,
    conflicting: bool,
) -> Diagnostic:
    code = (
        "TSL-LOWER-ARRAY-BODY-ENVELOPE-SKELETON-CONFLICT"
        if conflicting
        else "TSL-LOWER-ARRAY-BODY-ENVELOPE-SKELETON-DUPLICATE"
    )
    detail = "conflicting" if conflicting else "duplicate"
    return Diagnostic.error(
        code,
        f"array-body envelope skeleton input has a {detail} skeleton for "
        f"candidate {lookup_key.candidate_id!r}, selected type tag "
        f"{lookup_key.selected_type_tag!r}, and branch-chain identity "
        f"{lookup_key.originating_branch_chain_id!r}; provide exactly one "
        "typed skeleton for that envelope key",
        location=skeleton.source_location,
    )


def _missing_array_body_envelope_skeleton_diagnostic(
    requirement: ExactArrayBodyEnvelopeSkeletonRequirement,
    envelope: GenerationSelectedBodyEnvelopeIr,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-BODY-ENVELOPE-SKELETON-MISSING",
        "array-body envelope skeleton input is required for candidate "
        f"{envelope.candidate_id!r}, selected type tag "
        f"{envelope.selected_type_tag!r}, and branch-chain identity "
        f"{envelope.originating_branch_chain_id!r}, but no matching typed "
        "ExactArrayBodyEnvelopeSkeleton was supplied",
        location=requirement.source_location or envelope.source_location,
    )


def _orphan_array_body_envelope_skeleton_diagnostic(
    lookup_key: ExactArrayBodyEnvelopeSkeletonKey,
    skeleton: ExactArrayBodyEnvelopeSkeleton,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-BODY-ENVELOPE-SKELETON-ORPHAN",
        "array-body envelope skeleton input was supplied for candidate "
        f"{lookup_key.candidate_id!r}, selected type tag "
        f"{lookup_key.selected_type_tag!r}, and branch-chain identity "
        f"{lookup_key.originating_branch_chain_id!r}, but normal lowering "
        "produced no M63 selected-body envelope for that candidate",
        location=skeleton.source_location,
    )


def _mismatched_array_body_envelope_skeleton_diagnostic(
    lookup_key: ExactArrayBodyEnvelopeSkeletonKey,
    skeleton: ExactArrayBodyEnvelopeSkeleton,
    envelope_keys: tuple[ExactArrayBodyEnvelopeSkeletonKey, ...],
) -> Diagnostic:
    candidate_envelope_keys = tuple(
        envelope_key
        for envelope_key in envelope_keys
        if envelope_key.candidate_id == lookup_key.candidate_id
    )
    expected = tuple(
        (
            envelope_key.selected_type_tag,
            envelope_key.originating_branch_chain_id,
        )
        for envelope_key in candidate_envelope_keys
    )
    return Diagnostic.error(
        "TSL-LOWER-ARRAY-BODY-ENVELOPE-SKELETON-PROVENANCE-MISMATCH",
        "array-body envelope skeleton input did not match the M63 envelope "
        "provenance for candidate "
        f"{lookup_key.candidate_id!r}; got selected type tag "
        f"{lookup_key.selected_type_tag!r} and branch-chain identity "
        f"{lookup_key.originating_branch_chain_id!r}, expected one of "
        f"{expected!r}",
        location=skeleton.source_location,
    )


def _validate_selected_body_envelope_source(
    body_ir: SelectedAssignmentDirectIntrinsicBodyIr,
) -> Diagnostic | None:
    if not body_ir.candidate_id:
        return _inconsistent_selected_body_envelope_diagnostic(
            "selected M62 body IR candidate id must be non-empty",
            body_ir.source_location,
        )
    if not body_ir.selected_type_tag:
        return _inconsistent_selected_body_envelope_diagnostic(
            "selected M62 body IR type tag must be non-empty",
            body_ir.source_location,
        )
    if body_ir.selected_literal not in (2, 4, 8):
        return _inconsistent_selected_body_envelope_diagnostic(
            "selected M62 body IR literal must be 2, 4, or 8",
            body_ir.source_location,
        )
    if not body_ir.originating_branch_chain_id:
        return _inconsistent_selected_body_envelope_diagnostic(
            "selected M62 body IR branch-chain id must be non-empty",
            body_ir.source_location,
        )
    if not body_ir.original_opaque_body_text.strip():
        return _inconsistent_selected_body_envelope_diagnostic(
            "selected M62 body IR original body text must be non-empty",
            body_ir.source_location,
        )
    if body_ir.source_location is None:
        return _inconsistent_selected_body_envelope_diagnostic(
            "selected M62 body IR requires source location",
            None,
        )
    if not body_ir.assignment_target_text:
        return _inconsistent_selected_body_envelope_diagnostic(
            "selected M62 body IR assignment target text must be non-empty",
            body_ir.source_location,
        )
    if not body_ir.opaque_rhs_text:
        return _inconsistent_selected_body_envelope_diagnostic(
            "selected M62 body IR RHS text must be non-empty",
            body_ir.source_location,
        )
    if not body_ir.direct_intrinsic_token_text:
        return _inconsistent_selected_body_envelope_diagnostic(
            "selected M62 body IR direct intrinsic token text must be non-empty",
            body_ir.source_location,
        )
    if tuple(body_ir.direct_intrinsic_argument_texts) != ():
        return _inconsistent_selected_body_envelope_diagnostic(
            "selected M62 body IR must carry an explicit empty argument list",
            body_ir.source_location,
        )
    return None


def _validate_no_selected_body_envelope_source(
    body_ir: NoSelectedAssignmentDirectIntrinsicBodyIr,
) -> Diagnostic | None:
    if not body_ir.candidate_id:
        return _inconsistent_selected_body_envelope_diagnostic(
            "no-body M62 IR candidate id must be non-empty",
            body_ir.source_location,
        )
    if not body_ir.selected_type_tag:
        return _inconsistent_selected_body_envelope_diagnostic(
            "no-body M62 IR type tag must be non-empty",
            body_ir.source_location,
        )
    if body_ir.source_location is None:
        return _inconsistent_selected_body_envelope_diagnostic(
            "no-body M62 IR requires source location",
            None,
        )
    if not body_ir.originating_branch_chain_id:
        return _inconsistent_selected_body_envelope_diagnostic(
            "no-body M62 IR branch-chain id must be non-empty",
            body_ir.source_location,
        )
    if tuple(body_ir.attempted_literals) != (2, 4, 8):
        return _inconsistent_selected_body_envelope_diagnostic(
            "no-body M62 IR attempted literals must be 2, 4, 8",
            body_ir.source_location,
        )
    return None


def _recognize_opaque_selected_branch_body_assignment_form(
    handoff: OpaqueSelectedBranchBodyHandoff,
) -> Result[SelectedBranchBodyAssignmentFormRecognition]:
    parsed = _parse_selected_body_assignment_form(
        handoff.opaque_body_text,
        handoff.source_location,
    )
    if not parsed.is_ok:
        return Result.failure(parsed.diagnostics)
    assignment_target_text, opaque_rhs_text, direct_intrinsic_token_text = (
        parsed.unwrap()
    )
    return Result.ok(
        SelectedBranchBodyAssignmentFormRecognition(
            candidate_id=handoff.candidate_id,
            selected_type_tag=handoff.selected_type_tag,
            selected_literal=handoff.selected_literal,
            originating_branch_chain_id=handoff.originating_branch_chain_id,
            original_opaque_body_text=handoff.opaque_body_text,
            selected_statement_location=handoff.source_location,
            assignment_target_text=assignment_target_text,
            opaque_rhs_text=opaque_rhs_text,
            direct_intrinsic_token_text=direct_intrinsic_token_text,
        )
    )


def _parse_selected_body_assignment_form(
    body_text: str,
    location: SourceLocation | None,
) -> Result[tuple[str, str, str]]:
    stripped = body_text.strip()
    if stripped.count(";") > 1:
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-LOWER-SELECTED-BODY-FORM-EXTRA-STATEMENTS",
                    "selected-body assignment-form recognition supports only one "
                    "selected statement",
                    location=location,
                ),
            )
        )
    if not stripped.endswith(";"):
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-LOWER-SELECTED-BODY-FORM-MALFORMED",
                    "selected-body assignment-form recognition supports only "
                    "'pg = intrin<svptrue_b16|svptrue_b32|svptrue_b64>();'",
                    location=location,
                ),
            )
        )

    statement_text = stripped[:-1].strip()
    if "=" not in statement_text:
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-LOWER-SELECTED-BODY-FORM-MALFORMED",
                    "selected-body assignment-form recognition requires one "
                    "assignment statement",
                    location=location,
                ),
            )
        )

    target_text, rhs_text = (
        part.strip()
        for part in statement_text.split("=", 1)
    )
    if not target_text or not rhs_text:
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-LOWER-SELECTED-BODY-FORM-MALFORMED",
                    "selected-body assignment-form recognition requires both "
                    "assignment target text and RHS text",
                    location=location,
                ),
            )
        )
    if target_text != _SELECTED_BODY_ASSIGNMENT_TARGET:
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-LOWER-SELECTED-BODY-FORM-TARGET-UNSUPPORTED",
                    "selected-body assignment-form recognition supports only "
                    "the exact assignment target text 'pg'; got "
                    f"{target_text!r}",
                    location=location,
                ),
            )
        )

    match = _SELECTED_BODY_ASSIGNMENT_RHS_RE.fullmatch(rhs_text)
    if match is None:
        return Result.failure(
            (
                _unsupported_selected_body_assignment_rhs_diagnostic(
                    rhs_text,
                    location,
                ),
            )
        )
    direct_intrinsic_token_text = match.group(1)
    if direct_intrinsic_token_text not in (
        _SELECTED_BODY_ASSIGNMENT_DIRECT_INTRINSIC_TOKENS
    ):
        return Result.failure(
            (
                _unsupported_selected_body_assignment_rhs_diagnostic(
                    rhs_text,
                    location,
                ),
            )
        )

    return Result.ok((target_text, rhs_text, direct_intrinsic_token_text))


def _resolve_generation_predicate_query_staged(
    query_text: str,
    context: GenerationContext,
    *,
    selected_candidate_type_tag: str | None,
    location: SourceLocation | None,
) -> Result[_StagedGenerationPredicate]:
    query = query_text.strip()
    parsed = _parse_generation_value_predicate_expression(query, location)
    if not parsed.is_ok:
        return Result.failure(parsed.diagnostics)

    expression = parsed.unwrap()
    if not expression.left_operand or not expression.right_operand:
        return Result.failure(
            (_malformed_generation_predicate_diagnostic(query, location),)
        )
    if expression.operator != "==":
        return Result.failure(
            (
                _unsupported_generation_predicate_operator_diagnostic(
                    query,
                    expression.operator,
                    location,
                ),
            )
        )
    if not expression.left_operand.startswith(_GENERATION_VALUE_MARKER):
        return Result.failure(
            (
                _unsupported_generation_predicate_operand_diagnostic(
                    query,
                    expression.left_operand,
                    location,
                ),
            )
        )
    if expression.right_operand not in ("2", "4", "8"):
        return Result.failure(
            (
                _unsupported_generation_predicate_literal_diagnostic(
                    query,
                    expression.right_operand,
                    location,
                ),
            )
        )

    inner = _generation_value_query_inner(expression.left_operand, location)
    if not inner.is_ok:
        return Result.failure(
            (
                _unsupported_generation_predicate_operand_diagnostic(
                    query,
                    expression.left_operand,
                    location,
                ),
            )
        )
    inner_text = inner.unwrap()
    if _parse_generation_value_call(inner_text, "type::size_bytes") is None:
        return Result.failure(
            (
                _unsupported_generation_predicate_operand_diagnostic(
                    query,
                    expression.left_operand,
                    location,
                ),
            )
        )
    size_bytes = _generation_value_from_inner(
        inner_text,
        expression.left_operand,
        context,
        selected_candidate_type_tag=selected_candidate_type_tag,
        location=location,
    )
    if not size_bytes.is_ok:
        return Result.failure(size_bytes.diagnostics)

    value = size_bytes.unwrap()
    if value.kind != "type.size_bytes":
        return Result.failure(
            (
                _unsupported_generation_predicate_operand_diagnostic(
                    query,
                    expression.left_operand,
                    location,
                ),
            )
        )
    literal = int(expression.right_operand)
    return Result.ok(
        _StagedGenerationPredicate(
            predicate=GenerationPredicate(
                kind="type.size_bytes.equals",
                literal=literal,
                value=value.value == literal,
                type_tag=value.type_tag,
            ),
            generation_values=(value,),
        )
    )


def _classify_payload(candidate: ImplementationCandidate) -> Result[ClassifiedPayload]:
    body = candidate.implementation.body
    text = body.text
    if body.kind == "tsil" and text is None:
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-LOWER-PAYLOAD-SHAPE",
                    f"candidate {candidate.candidate_id!r} has a TSIL payload "
                    "that is not text",
                    location=candidate.variant.source.declaration.source_span.location,
                ),
            )
        )

    return Result.ok(
        ClassifiedPayload(
            body_kind=body.kind,
            classification=body.classification,
            raw_payload=body.payload,
            text=text,
            has_generation_condition=(
                text is not None
                and _has_generation_helper(text)
            ),
        )
    )


def _lower_input(
    item: LoweringInput,
    request: LoweringRequest,
    skeleton_lookup: _ArrayBodyEnvelopeSkeletonLookup,
) -> Result[LoweredImplementation]:
    if item.payload.classification != "tsil":
        return Result.failure((_unsupported_payload_diagnostic(item),))

    text = item.payload.text or ""
    type_ref = _lower_generation_type_query_payload(item, request, text)
    if type_ref is not None:
        if not type_ref.is_ok:
            return Result.failure(type_ref.diagnostics)
        return Result.ok(
            LoweredImplementation(
                candidate_id=item.candidate_id,
                status="lowered",
                generation_type_refs=(type_ref.unwrap(),),
            )
        )

    generation_predicate = _lower_generation_predicate_query_payload(
        item,
        request,
        text,
    )
    if generation_predicate is not None:
        if not generation_predicate.is_ok:
            return Result.failure(generation_predicate.diagnostics)
        staged_predicate = generation_predicate.unwrap()
        return Result.ok(
            LoweredImplementation(
                candidate_id=item.candidate_id,
                status="lowered",
                generation_predicates=(staged_predicate.predicate,),
                generation_stages=(
                    _recognition_stage("generation.predicate", text),
                    *(
                        _generation_value_stage(value)
                        for value in staged_predicate.generation_values
                    ),
                    _generation_predicate_stage(staged_predicate.predicate),
                ),
            )
        )

    generation_value = _lower_generation_value_query_payload(item, request, text)
    if generation_value is not None:
        if not generation_value.is_ok:
            return Result.failure(generation_value.diagnostics)
        value = generation_value.unwrap()
        return Result.ok(
            LoweredImplementation(
                candidate_id=item.candidate_id,
                status="lowered",
                generation_values=(value,),
                generation_stages=(
                    _recognition_stage("generation.value", text),
                    _generation_value_stage(value),
                ),
            )
        )

    generation_branches: tuple[PrunedGenerationBranch, ...] = ()
    generation_stages: tuple[GenerationLoweringStage, ...] = ()
    if item.payload.has_generation_condition:
        if _GENERATION_CONDITION_MARKER not in text:
            return Result.failure((_unresolved_selected_branch_diagnostic(item, text),))
        branch_chain = _prune_generation_size_byte_branch_chain(item, request, text)
        if branch_chain is not None:
            if not branch_chain.is_ok:
                return Result.failure(branch_chain.diagnostics)
            staged_chain = branch_chain.unwrap()
            control_flow_stage = _generation_control_flow_stage(staged_chain.pruning)
            selected_body_handoff = handoff_opaque_selected_branch_body(
                item.candidate_id,
                control_flow_stage,
            )
            if not selected_body_handoff.is_ok:
                return Result.failure(selected_body_handoff.diagnostics)
            handoff = selected_body_handoff.unwrap()
            assignment_form = recognize_selected_branch_body_assignment_form(handoff)
            if not assignment_form.is_ok:
                return Result.failure(assignment_form.diagnostics)
            recognized_assignment_form = assignment_form.unwrap()
            body_ir_result = lower_selected_branch_body_ir(
                recognized_assignment_form,
            )
            if not body_ir_result.is_ok:
                return Result.failure(body_ir_result.diagnostics)
            body_ir = body_ir_result.unwrap()
            envelope_result = lower_selected_body_envelope(body_ir)
            if not envelope_result.is_ok:
                return Result.failure(envelope_result.diagnostics)
            envelope = envelope_result.unwrap()
            envelope_stage = _selected_body_envelope_stage(envelope)
            array_initialization_pipeline_result = (
                _lower_exact_array_initialization_stage_pipeline(
                    item,
                    request,
                    envelope_stage,
                    skeleton_lookup,
                )
            )
            if not array_initialization_pipeline_result.is_ok:
                return Result.failure(
                    array_initialization_pipeline_result.diagnostics
                )
            array_initialization_pipeline = (
                array_initialization_pipeline_result.unwrap()
            )
            return Result.ok(
                LoweredImplementation(
                    candidate_id=item.candidate_id,
                    status="lowered",
                    generation_predicates=staged_chain.generation_predicates,
                    generation_branch_chains=(staged_chain.pruning,),
                    selected_branch_body_handoffs=(handoff,),
                    selected_branch_body_assignment_forms=(
                        recognized_assignment_form,
                    ),
                    selected_branch_body_irs=(body_ir,),
                    selected_body_envelopes=(envelope,),
                    array_body_envelopes=(
                        array_initialization_pipeline.array_body_envelopes
                    ),
                    array_initialization_slot_forms=(
                        array_initialization_pipeline.array_initialization_slot_forms
                    ),
                    array_initialization_helper_requests=(
                        array_initialization_pipeline.array_initialization_helper_requests
                    ),
                    array_initialization_base_type_resolutions=(
                        array_initialization_pipeline.array_initialization_base_type_resolutions
                    ),
                    array_initialization_vector_length_resolutions=(
                        array_initialization_pipeline.array_initialization_vector_length_resolutions
                    ),
                    array_initialization_vector_alignment_resolutions=(
                        array_initialization_pipeline.array_initialization_vector_alignment_resolutions
                    ),
                    array_initialization_helper_set_completions=(
                        array_initialization_pipeline.array_initialization_helper_set_completions
                    ),
                    array_initialization_declaration_shells=(
                        array_initialization_pipeline.array_initialization_declaration_shells
                    ),
                    array_body_structural_sequences=(
                        array_initialization_pipeline.array_body_structural_sequences
                    ),
                    predicate_path_structural_requests=(
                        array_initialization_pipeline.predicate_path_structural_requests
                    ),
                    generation_stages=(
                        _recognition_stage(
                            "generation.control_flow",
                            item.payload.text or text,
                        ),
                        *(
                            _generation_value_stage(value)
                            for value in staged_chain.generation_values
                        ),
                        *(
                            _generation_predicate_stage(predicate)
                            for predicate in staged_chain.generation_predicates
                        ),
                        control_flow_stage,
                        _selected_body_stage(handoff),
                        _selected_body_form_recognition_stage(
                            recognized_assignment_form,
                        ),
                        _selected_body_ir_stage(body_ir),
                        envelope_stage,
                        *array_initialization_pipeline.stages,
                    ),
                )
            )
        pruned = _prune_generation_branch(item, request, text)
        if not pruned.is_ok:
            return Result.failure(pruned.diagnostics)
        branch = pruned.unwrap()
        text = branch.statement_text
        generation_branches = (branch,)
        generation_stages = (
            _recognition_stage("generation.control_flow", item.payload.text or text),
            _generation_control_flow_stage(branch),
        )
        if _has_generation_helper(text):
            return Result.failure((_unresolved_selected_branch_diagnostic(item, text),))

    statement = _mini_return_statement(item, text)
    if not statement.is_ok:
        return Result.failure(statement.diagnostics)
    lowered_statement = statement.unwrap()

    return Result.ok(
        LoweredImplementation(
            candidate_id=item.candidate_id,
            status="lowered",
            statements=(lowered_statement,),
            generation_branches=generation_branches,
            generation_stages=(
                *generation_stages,
                _selected_body_stage(lowered_statement),
            ),
        )
    )


def _lower_generation_type_query_payload(
    item: LoweringInput,
    request: LoweringRequest,
    text: str,
) -> Result[GenerationTypeRef] | None:
    if _GENERATION_TYPE_MARKER not in text:
        return None
    stripped = text.strip()
    if not stripped.startswith(_GENERATION_TYPE_MARKER):
        return None
    context = _context_for_candidate(item, request)
    selected_candidate_type_tag = (
        item.candidate.type_tag
        if request.generation_context.use_candidate_type_tag
        else None
    )
    return resolve_generation_type_query(
        stripped,
        context,
        selected_candidate_type_tag=selected_candidate_type_tag,
        location=item.source_location,
    )


def _lower_generation_predicate_query_payload(
    item: LoweringInput,
    request: LoweringRequest,
    text: str,
) -> Result[_StagedGenerationPredicate] | None:
    if _GENERATION_VALUE_MARKER not in text:
        return None
    stripped = text.strip()
    if not stripped.startswith(_GENERATION_VALUE_MARKER):
        return None
    if not _has_top_level_generation_comparison_operator(stripped):
        return None
    context = _context_for_candidate(item, request)
    selected_candidate_type_tag = (
        item.candidate.type_tag
        if request.generation_context.use_candidate_type_tag
        else None
    )
    return _resolve_generation_predicate_query_staged(
        stripped,
        context,
        selected_candidate_type_tag=selected_candidate_type_tag,
        location=item.source_location,
    )


def _lower_generation_value_query_payload(
    item: LoweringInput,
    request: LoweringRequest,
    text: str,
) -> Result[GenerationValue] | None:
    if _GENERATION_VALUE_MARKER not in text:
        return None
    stripped = text.strip()
    if not stripped.startswith(_GENERATION_VALUE_MARKER):
        return None
    context = _context_for_candidate(item, request)
    selected_candidate_type_tag = (
        item.candidate.type_tag
        if request.generation_context.use_candidate_type_tag
        else None
    )
    return resolve_generation_value_query(
        stripped,
        context,
        selected_candidate_type_tag=selected_candidate_type_tag,
        location=item.source_location,
    )


def _mini_return_statement(
    item: LoweringInput,
    text: str | None = None,
) -> Result[TsilReturnStatement]:
    text = item.payload.text or "" if text is None else text
    match = _DIRECT_PARAMETER_ADD_RETURN_RE.fullmatch(text)
    if match is not None:
        return _direct_parameter_add_return_statement(item, match)
    if _INTRIN_COMPOSE_MARKER_RE.search(text):
        return _intrinsic_compose_return_statement(item, text)
    if _EMIT_RETURN_HEAD_RE.match(text):
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-LOWER-TSIL-RETURN-SHAPE",
                    "mini TSIL lowering supports only direct parameter addition "
                    "returns shaped as 'emit_return(<parameter> + <parameter>);' "
                    "or intrinsic-compose returns shaped as "
                    "'emit_return(intrin_compose<add>(<parameter>, <parameter>));'",
                    location=item.source_location,
                ),
            )
        )
    return Result.failure((_unsupported_payload_diagnostic(item),))


@dataclass(frozen=True, slots=True)
class _ParsedGenerationIf:
    condition_text: str
    true_branch_text: str
    false_branch_text: str
    else_syntax: GenerationElseSyntax


@dataclass(frozen=True, slots=True)
class _ParsedSizeByteBranchChainArm:
    condition_text: str
    statement_text: str


@dataclass(frozen=True, slots=True)
class _ParsedSizeByteBranchChain:
    arms: tuple[_ParsedSizeByteBranchChainArm, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "arms", tuple(self.arms))


@dataclass(frozen=True, slots=True)
class _ResolvedGenerationCondition:
    condition: TsilGenerationCondition
    value: bool


@dataclass(frozen=True, slots=True)
class _ParsedGenerationValueArithmeticExpression:
    operator: str
    left_operand: str
    right_operand: str


@dataclass(frozen=True, slots=True)
class _ParsedGenerationValuePredicateExpression:
    operator: str
    left_operand: str
    right_operand: str


def _prune_generation_branch(
    item: LoweringInput,
    request: LoweringRequest,
    text: str,
) -> Result[PrunedGenerationBranch]:
    parsed = _parse_generation_if(item, text)
    if not parsed.is_ok:
        return Result.failure(parsed.diagnostics)
    parsed_branch = parsed.unwrap()

    condition = _generation_branch_condition(item, request, parsed_branch.condition_text)
    if not condition.is_ok:
        return Result.failure(condition.diagnostics)
    resolved_condition = condition.unwrap()
    if (
        parsed_branch.else_syntax == "else"
        and not isinstance(resolved_condition.condition, TsilTypeSignednessCondition)
    ):
        return Result.failure((_unsupported_plain_else_generation_branch(item),))

    selected_branch: GenerationBranchChoice = (
        "true" if resolved_condition.value else "false"
    )
    statement_text = (
        parsed_branch.true_branch_text
        if resolved_condition.value
        else parsed_branch.false_branch_text
    ).strip()
    return Result.ok(
        PrunedGenerationBranch(
            condition=resolved_condition.condition,
            selected_branch=selected_branch,
            statement_text=statement_text,
            else_syntax=parsed_branch.else_syntax,
            condition_location=item.source_location,
        )
    )


def _prune_generation_size_byte_branch_chain(
    item: LoweringInput,
    request: LoweringRequest,
    text: str,
) -> Result[_StagedGenerationSizeByteBranchChain] | None:
    if "else if<generation>" not in text:
        return None

    parsed = _parse_generation_size_byte_branch_chain(item, text)
    if not parsed.is_ok:
        return Result.failure(parsed.diagnostics)

    context = _context_for_candidate(item, request)
    selected_candidate_type_tag = (
        item.candidate.type_tag
        if request.generation_context.use_candidate_type_tag
        else None
    )
    expected_literals = (2, 4, 8)
    values_by_key: dict[tuple[str, int, str], GenerationValue] = {}
    predicates: list[GenerationPredicate] = []
    arms: list[GenerationSizeByteBranchChainArm] = []

    for expected_literal, parsed_arm in zip(
        expected_literals,
        parsed.unwrap().arms,
        strict=True,
    ):
        staged = _resolve_generation_predicate_query_staged(
            parsed_arm.condition_text,
            context,
            selected_candidate_type_tag=selected_candidate_type_tag,
            location=item.source_location,
        )
        if not staged.is_ok:
            return Result.failure(staged.diagnostics)

        staged_predicate = staged.unwrap()
        predicate = staged_predicate.predicate
        if predicate.kind != "type.size_bytes.equals" or predicate.literal != expected_literal:
            return Result.failure((_malformed_generation_if_diagnostic(item),))
        for value in staged_predicate.generation_values:
            values_by_key.setdefault(value.key, value)
        predicates.append(predicate)
        arms.append(
            GenerationSizeByteBranchChainArm(
                literal=expected_literal,
                predicate=predicate,
                statement_text=parsed_arm.statement_text,
            )
        )

    type_tags = tuple(dict.fromkeys(predicate.type_tag for predicate in predicates))
    if len(type_tags) != 1:
        return Result.failure((_malformed_generation_if_diagnostic(item),))

    selected_arms = tuple(arm for arm in arms if arm.predicate.value)
    if len(selected_arms) > 1:
        return Result.failure((_malformed_generation_if_diagnostic(item),))
    selected_arm = selected_arms[0] if selected_arms else None
    return Result.ok(
        _StagedGenerationSizeByteBranchChain(
            pruning=GenerationSizeByteBranchChainPruning(
                arms=tuple(arms),
                type_tag=type_tags[0],
                selected_literal=(
                    selected_arm.literal if selected_arm is not None else None
                ),
                selected_statement_text=(
                    selected_arm.statement_text if selected_arm is not None else None
                ),
                condition_location=item.source_location,
            ),
            generation_values=tuple(values_by_key.values()),
            generation_predicates=tuple(predicates),
        )
    )


def _primitive_attributes_for(
    item: LoweringInput,
    request: LoweringRequest,
) -> FrozenMap[str, CatalogValue] | None:
    request_attributes = request.generation_context.primitive_attributes
    if request_attributes is not None:
        return request_attributes
    if request.generation_context.use_candidate_attributes:
        return item.candidate.variant.attributes
    return None


def _context_for_candidate(
    item: LoweringInput,
    request: LoweringRequest,
) -> GenerationContext:
    context = request.generation_context
    parameters = context.parameters or tuple(
        parameter.name
        for parameter in item.candidate.variant.source.declaration.parameters
    )
    selected_type_tag = context.selected_type_tag
    if selected_type_tag is None and context.use_candidate_type_tag:
        selected_type_tag = item.candidate.type_tag
    return GenerationContext(
        values=context.values,
        primitive_attributes=context.primitive_attributes,
        use_candidate_attributes=context.use_candidate_attributes,
        selected_primitive_name=(
            context.selected_primitive_name or item.candidate.source_primitive_name
        ),
        emitted_primitive_name=(
            context.emitted_primitive_name or item.candidate.emitted_primitive_name
        ),
        selected_candidate_id=context.selected_candidate_id or item.candidate_id,
        normalized_signature=(
            context.normalized_signature
            or item.candidate.variant.source.signature.normalized
        ),
        parameters=parameters,
        selected_type_tag=selected_type_tag,
        type_tag_override=context.type_tag_override,
        use_candidate_type_tag=context.use_candidate_type_tag,
        concrete_integer_generation_rules=context.concrete_integer_generation_rules,
        scalar_size_bytes_generation_rules=(
            context.scalar_size_bytes_generation_rules
        ),
        array_initialization_vector_length_metadata=(
            context.array_initialization_vector_length_metadata
        ),
        array_initialization_vector_alignment_metadata=(
            context.array_initialization_vector_alignment_metadata
        ),
        implementation_source_location=(
            context.implementation_source_location or item.source_location
        ),
    )


def _generation_type_query_inner(
    query_text: str,
    location: SourceLocation | None,
) -> Result[str]:
    query = query_text.strip()
    if not query.startswith(_GENERATION_TYPE_MARKER):
        return Result.failure(
            (
                _unsupported_generation_type_query_diagnostic(
                    query_text,
                    location,
                ),
            )
        )

    cursor = len(_GENERATION_TYPE_MARKER)
    cursor = _skip_whitespace(query, cursor)
    if cursor >= len(query) or query[cursor] != "(":
        return Result.failure(
            (_malformed_generation_type_query_diagnostic(query_text, location),)
        )
    query_end = _matching_delimiter(query, cursor, "(", ")")
    if query_end is None:
        return Result.failure(
            (_malformed_generation_type_query_diagnostic(query_text, location),)
        )
    tail = query[query_end + 1:].strip()
    if tail:
        return Result.failure(
            (_malformed_generation_type_query_diagnostic(query_text, location),)
        )
    return Result.ok(query[cursor + 1:query_end].strip())


def _generation_type_ref_from_inner(
    inner: str,
    query_text: str,
    context: GenerationContext,
    *,
    selected_candidate_type_tag: str | None,
    location: SourceLocation | None,
) -> Result[GenerationTypeRef]:
    if inner == "base::in":
        type_tag = _effective_generation_type_tag(
            context,
            selected_candidate_type_tag=selected_candidate_type_tag,
            query_text=query_text,
            location=location,
        )
        if not type_tag.is_ok:
            return Result.failure(type_tag.diagnostics)
        return _base_in_type_ref(
            type_tag.unwrap(),
            context.concrete_integer_generation_rules,
            query_text,
            location,
        )

    helper_forms: tuple[tuple[str, GenerationTypeRefKind], ...] = (
        ("base::signed_of", "base.signed_of"),
        ("base::unsigned_of", "base.unsigned_of"),
    )
    for helper_name, kind in helper_forms:
        parsed = _parse_generation_type_call(inner, helper_name)
        if parsed is None:
            continue
        if len(parsed) != 1:
            return Result.failure(
                (_malformed_generation_type_query_diagnostic(query_text, location),)
            )
        nested = parsed[0].strip()
        if nested == "base::in":
            return Result.failure(
                (
                    _unsupported_generation_type_shorthand_diagnostic(
                        query_text,
                        helper_name,
                        location,
                    ),
                )
            )
        nested_inner = _generation_type_query_inner(nested, location)
        if not nested_inner.is_ok:
            return Result.failure(
                (
                    _unsupported_nested_generation_type_query_diagnostic(
                        query_text,
                        nested,
                        location,
                    ),
                )
            )
        if nested_inner.unwrap() != "base::in":
            return Result.failure(
                (
                    _unsupported_nested_generation_type_query_diagnostic(
                        query_text,
                        nested,
                        location,
                    ),
                )
            )
        source_type_tag = _effective_generation_type_tag(
            context,
            selected_candidate_type_tag=selected_candidate_type_tag,
            query_text=query_text,
            location=location,
        )
        if not source_type_tag.is_ok:
            return Result.failure(source_type_tag.diagnostics)
        companion = _integer_companion_type_tag(
            source_type_tag.unwrap(),
            kind,
            context.concrete_integer_generation_rules,
            query_text,
            location,
        )
        if not companion.is_ok:
            return Result.failure(companion.diagnostics)
        return Result.ok(
            GenerationTypeRef(
                kind=kind,
                type_tag=companion.unwrap(),
                source_type_tag=source_type_tag.unwrap(),
            )
        )

    if "base::signed_of(base::in)" in inner:
        return Result.failure(
            (
                _unsupported_generation_type_shorthand_diagnostic(
                    query_text,
                    "base::signed_of",
                    location,
                ),
            )
        )
    if "base::unsigned_of(base::in)" in inner:
        return Result.failure(
            (
                _unsupported_generation_type_shorthand_diagnostic(
                    query_text,
                    "base::unsigned_of",
                    location,
                ),
            )
        )
    return Result.failure(
        (_unsupported_generation_type_query_diagnostic(query_text, location),)
    )


def _generation_value_query_inner(
    query_text: str,
    location: SourceLocation | None,
) -> Result[str]:
    query = query_text.strip()
    if not query.startswith(_GENERATION_VALUE_MARKER):
        return Result.failure(
            (
                _unsupported_generation_value_query_diagnostic(
                    query_text,
                    location,
                ),
            )
        )

    cursor = len(_GENERATION_VALUE_MARKER)
    cursor = _skip_whitespace(query, cursor)
    if cursor >= len(query) or query[cursor] != "(":
        return Result.failure(
            (_malformed_generation_value_query_diagnostic(query_text, location),)
        )
    query_end = _matching_delimiter(query, cursor, "(", ")")
    if query_end is None:
        return Result.failure(
            (_malformed_generation_value_query_diagnostic(query_text, location),)
        )
    tail = query[query_end + 1:].strip()
    if tail:
        return Result.failure(
            (_malformed_generation_value_query_diagnostic(query_text, location),)
        )
    return Result.ok(query[cursor + 1:query_end].strip())


def _generation_size_bits_value_expression(
    query: str,
    context: GenerationContext,
    *,
    selected_candidate_type_tag: str | None,
    location: SourceLocation | None,
) -> Result[GenerationValue] | None:
    parsed = _parse_generation_value_arithmetic_expression(query, location)
    if parsed is None:
        return None
    if not parsed.is_ok:
        return Result.failure(parsed.diagnostics)

    expression = parsed.unwrap()
    if not expression.left_operand or not expression.right_operand:
        return Result.failure(
            (_malformed_generation_value_arithmetic_diagnostic(query, location),)
        )
    if expression.operator != "*":
        return Result.failure(
            (
                _unsupported_generation_value_arithmetic_operator_diagnostic(
                    query,
                    expression.operator,
                    location,
                ),
            )
        )
    if not expression.left_operand.startswith(_GENERATION_VALUE_MARKER):
        return Result.failure(
            (
                _unsupported_generation_value_arithmetic_operand_diagnostic(
                    query,
                    expression.left_operand,
                    location,
                ),
            )
        )
    if expression.right_operand != "8":
        return Result.failure(
            (
                _unsupported_generation_value_arithmetic_literal_diagnostic(
                    query,
                    expression.right_operand,
                    location,
                ),
            )
        )

    inner = _generation_value_query_inner(expression.left_operand, location)
    if not inner.is_ok:
        return Result.failure(inner.diagnostics)
    size_bytes = _generation_value_from_inner(
        inner.unwrap(),
        expression.left_operand,
        context,
        selected_candidate_type_tag=selected_candidate_type_tag,
        location=location,
    )
    if not size_bytes.is_ok:
        return Result.failure(size_bytes.diagnostics)

    value = size_bytes.unwrap()
    if value.kind != "type.size_bytes":
        return Result.failure(
            (
                _unsupported_generation_value_arithmetic_operand_diagnostic(
                    query,
                    expression.left_operand,
                    location,
                ),
            )
        )
    return Result.ok(
        GenerationValue(
            kind="type.size_bits",
            value=value.value * 8,
            type_tag=value.type_tag,
        )
    )


def _parse_generation_value_arithmetic_expression(
    query: str,
    location: SourceLocation | None,
) -> Result[_ParsedGenerationValueArithmeticExpression] | None:
    depth = 0
    index = 0
    while index < len(query):
        character = query[index]
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
            if depth < 0:
                return Result.failure(
                    (_malformed_generation_value_arithmetic_diagnostic(query, location),)
                )
        elif depth == 0:
            if query.startswith("==", index):
                return Result.ok(
                    _ParsedGenerationValueArithmeticExpression(
                        operator="==",
                        left_operand=query[:index].strip(),
                        right_operand=query[index + 2:].strip(),
                    )
                )
            if character in ("*", "/", "+", "-", "%"):
                return Result.ok(
                    _ParsedGenerationValueArithmeticExpression(
                        operator=character,
                        left_operand=query[:index].strip(),
                        right_operand=query[index + 1:].strip(),
                    )
                )
        index += 1
    return None


def _parse_generation_value_predicate_expression(
    query: str,
    location: SourceLocation | None,
) -> Result[_ParsedGenerationValuePredicateExpression]:
    parsed = _parse_top_level_generation_binary_expression(
        query,
        include_arithmetic=True,
    )
    if parsed is None:
        return Result.failure((_malformed_generation_predicate_diagnostic(query, location),))
    operator, left_operand, right_operand = parsed
    return Result.ok(
        _ParsedGenerationValuePredicateExpression(
            operator=operator,
            left_operand=left_operand,
            right_operand=right_operand,
        )
    )


def _has_top_level_generation_comparison_operator(query: str) -> bool:
    parsed = _parse_top_level_generation_binary_expression(
        query,
        include_arithmetic=False,
    )
    return parsed is not None and parsed[0] in ("==", "!=", "<=", ">=", "<", ">")


def _parse_top_level_generation_binary_expression(
    query: str,
    *,
    include_arithmetic: bool,
) -> tuple[str, str, str] | None:
    depth = 0
    index = 0
    while index < len(query):
        if query.startswith(_GENERATION_VALUE_MARKER, index):
            index += len(_GENERATION_VALUE_MARKER)
            continue
        if query.startswith(_GENERATION_TYPE_MARKER, index):
            index += len(_GENERATION_TYPE_MARKER)
            continue

        character = query[index]
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
            if depth < 0:
                return None
        elif depth == 0:
            for operator in ("==", "!=", "<=", ">="):
                if query.startswith(operator, index):
                    return (
                        operator,
                        query[:index].strip(),
                        query[index + len(operator):].strip(),
                    )
            if character in ("<", ">"):
                return (
                    character,
                    query[:index].strip(),
                    query[index + 1:].strip(),
                )
            if include_arithmetic and character in ("*", "/", "+", "-", "%"):
                return (
                    character,
                    query[:index].strip(),
                    query[index + 1:].strip(),
                )
        index += 1
    if depth != 0:
        return None
    return None


def _generation_value_from_inner(
    inner: str,
    query_text: str,
    context: GenerationContext,
    *,
    selected_candidate_type_tag: str | None,
    location: SourceLocation | None,
) -> Result[GenerationValue]:
    parsed = _parse_generation_value_call(inner, "type::size_bytes")
    if parsed is None:
        return Result.failure(
            (_unsupported_generation_value_query_diagnostic(query_text, location),)
        )
    if len(parsed) != 1:
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-LOWER-GEN-VALUE-ARITY",
                    "generation-time scalar size-bytes value query requires "
                    "exactly one nested type query argument; got "
                    f"{len(parsed)} in {query_text!r}",
                    location=location,
                ),
            )
        )

    nested = parsed[0].strip()
    nested_inner = _generation_type_query_inner(nested, location)
    if not nested_inner.is_ok or nested_inner.unwrap() != "base::in":
        return Result.failure(
            (
                _unsupported_nested_generation_value_query_diagnostic(
                    query_text,
                    nested,
                    location,
                ),
            )
        )

    type_tag = _effective_generation_value_type_tag(
        context,
        selected_candidate_type_tag=selected_candidate_type_tag,
        query_text=query_text,
        location=location,
    )
    if not type_tag.is_ok:
        return Result.failure(type_tag.diagnostics)
    return _type_size_bytes_generation_value(
        type_tag.unwrap(),
        context.scalar_size_bytes_generation_rules,
        query_text,
        location,
    )


def _parse_generation_type_call(text: str, function_name: str) -> tuple[str, ...] | None:
    stripped = text.strip()
    if not stripped.startswith(function_name):
        return None
    open_index = _skip_whitespace(stripped, len(function_name))
    if open_index >= len(stripped) or stripped[open_index] != "(":
        return None
    close_index = _matching_delimiter(stripped, open_index, "(", ")")
    if close_index is None or stripped[close_index + 1:].strip():
        return ()
    return _split_generation_type_arguments(stripped[open_index + 1:close_index])


def _parse_generation_value_call(text: str, function_name: str) -> tuple[str, ...] | None:
    stripped = text.strip()
    if not stripped.startswith(function_name):
        return None
    open_index = _skip_whitespace(stripped, len(function_name))
    if open_index >= len(stripped) or stripped[open_index] != "(":
        return None
    close_index = _matching_delimiter(stripped, open_index, "(", ")")
    if close_index is None or stripped[close_index + 1:].strip():
        return ()
    return _split_generation_value_arguments(stripped[open_index + 1:close_index])


def _split_generation_type_arguments(text: str) -> tuple[str, ...]:
    arguments: list[str] = []
    start = 0
    depth = 0
    for index, character in enumerate(text):
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
            if depth < 0:
                return ()
        elif character == "," and depth == 0:
            arguments.append(text[start:index].strip())
            start = index + 1
    if depth != 0:
        return ()
    tail = text[start:].strip()
    if tail:
        arguments.append(tail)
    return tuple(arguments)


def _split_generation_value_arguments(text: str) -> tuple[str, ...]:
    arguments: list[str] = []
    start = 0
    depth = 0
    for index, character in enumerate(text):
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
            if depth < 0:
                return ()
        elif character == "," and depth == 0:
            arguments.append(text[start:index].strip())
            start = index + 1
    if depth != 0:
        return ()
    tail = text[start:].strip()
    if tail or arguments:
        arguments.append(tail)
    return tuple(arguments)


def _effective_generation_type_tag(
    context: GenerationContext,
    *,
    selected_candidate_type_tag: str | None,
    query_text: str,
    location: SourceLocation | None,
) -> Result[str]:
    type_tag = (
        context.type_tag_override
        or context.selected_type_tag
        or selected_candidate_type_tag
    )
    if type_tag is None:
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-LOWER-GEN-TYPE-CONTEXT-MISSING",
                    "generation-time type query requires a selected candidate "
                    "type tag or GenerationContext.type_tag_override; query "
                    f"was {query_text!r}",
                    location=location,
                ),
            )
        )
    return Result.ok(type_tag)


def _effective_generation_value_type_tag(
    context: GenerationContext,
    *,
    selected_candidate_type_tag: str | None,
    query_text: str,
    location: SourceLocation | None,
) -> Result[str]:
    type_tag = (
        context.type_tag_override
        or context.selected_type_tag
        or selected_candidate_type_tag
    )
    if type_tag is None:
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-LOWER-GEN-VALUE-CONTEXT-MISSING",
                    "generation-time scalar size-bytes value query requires a "
                    "selected candidate type tag or "
                    "GenerationContext.type_tag_override; query was "
                    f"{query_text!r}",
                    location=location,
                ),
            )
        )
    return Result.ok(type_tag)


def _base_in_type_ref(
    type_tag: str,
    rule_set: ConcreteIntegerGenerationRuleSet,
    query_text: str,
    location: SourceLocation | None,
) -> Result[GenerationTypeRef]:
    supported = _supported_generation_type_tag(type_tag, rule_set, query_text, location)
    if not supported.is_ok:
        return Result.failure(supported.diagnostics)
    return Result.ok(GenerationTypeRef(kind="base.in", type_tag=type_tag))


def _supported_generation_type_tag(
    type_tag: str,
    rule_set: ConcreteIntegerGenerationRuleSet,
    query_text: str,
    location: SourceLocation | None,
) -> Result[None]:
    if rule_set.rule_for(type_tag) is not None:
        return Result.ok(None)
    status = classify_concrete_integer_generation_type_tag(type_tag)
    if status in ("selected", "unsupported"):
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-LOWER-GEN-TYPE-TAG-UNSUPPORTED",
                    "generation-time base type query supports only concrete "
                    "integer type tags "
                    f"{_quoted_join(rule_set.supported_type_tags)}; got "
                    f"{type_tag!r} for query {query_text!r}",
                    location=location,
                ),
            )
        )
    return Result.failure(
        (
            Diagnostic.error(
                "TSL-LOWER-GEN-TYPE-TAG-UNKNOWN",
                "generation-time base type query received unknown type tag "
                f"{type_tag!r} for query {query_text!r}",
                location=location,
            ),
        )
    )


def _type_size_bytes_generation_value(
    type_tag: str,
    rule_set: ScalarSizeBytesGenerationRuleSet,
    query_text: str,
    location: SourceLocation | None,
) -> Result[GenerationValue]:
    rule = rule_set.rule_for(type_tag)
    if rule is not None:
        return Result.ok(
            GenerationValue(
                kind="type.size_bytes",
                value=rule.size_bytes,
                type_tag=rule.type_tag,
            )
        )
    status = classify_scalar_size_bytes_generation_type_tag(type_tag)
    if status in ("selected", "unsupported"):
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-LOWER-GEN-VALUE-TAG-UNSUPPORTED",
                    "generation-time scalar size-bytes value query supports "
                    "only selected scalar type tags "
                    f"{_quoted_join(rule_set.supported_type_tags)}; got "
                    f"{type_tag!r} for query {query_text!r}",
                    location=location,
                ),
            )
        )
    return Result.failure(
        (
            Diagnostic.error(
                "TSL-LOWER-GEN-VALUE-TAG-UNKNOWN",
                "generation-time scalar size-bytes value query received "
                f"unknown type tag {type_tag!r} for query {query_text!r}",
                location=location,
            ),
        )
    )


def _integer_companion_type_tag(
    source_type_tag: str,
    kind: GenerationTypeRefKind,
    rule_set: ConcreteIntegerGenerationRuleSet,
    query_text: str,
    location: SourceLocation | None,
) -> Result[str]:
    rule = rule_set.rule_for(source_type_tag)
    if rule is not None:
        if kind == "base.signed_of":
            return Result.ok(rule.signed_type_tag)
        if kind == "base.unsigned_of":
            return Result.ok(rule.unsigned_type_tag)
    if is_non_integer_generation_type_tag(source_type_tag):
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-LOWER-GEN-TYPE-NON-INTEGER",
                    "generation-time signed/unsigned companion query requires "
                    f"a concrete integer type tag; got {source_type_tag!r} "
                    f"for query {query_text!r}",
                    location=location,
                ),
            )
        )
    supported = _supported_generation_type_tag(
        source_type_tag,
        rule_set,
        query_text,
        location,
    )
    if supported.is_ok:
        raise AssertionError("supported companion type tags must be handled directly")
    return Result.failure(supported.diagnostics)


def _quoted_join(values: tuple[str, ...]) -> str:
    return ", ".join(repr(value) for value in values)


def _parse_generation_if(
    item: LoweringInput,
    text: str,
) -> Result[_ParsedGenerationIf]:
    stripped = text.strip()
    if not stripped.startswith(_GENERATION_CONDITION_MARKER):
        return Result.failure((_unsupported_generation_condition_diagnostic(item, text),))

    cursor = len(_GENERATION_CONDITION_MARKER)
    cursor = _skip_whitespace(stripped, cursor)
    if cursor >= len(stripped) or stripped[cursor] != "(":
        return Result.failure((_malformed_generation_if_diagnostic(item),))
    condition_end = _matching_delimiter(stripped, cursor, "(", ")")
    if condition_end is None:
        return Result.failure((_malformed_generation_if_diagnostic(item),))
    condition_text = stripped[cursor + 1:condition_end].strip()

    cursor = _skip_whitespace(stripped, condition_end + 1)
    if cursor >= len(stripped) or stripped[cursor] != "{":
        return Result.failure((_malformed_generation_if_diagnostic(item),))
    true_end = _matching_delimiter(stripped, cursor, "{", "}")
    if true_end is None:
        return Result.failure((_malformed_generation_if_diagnostic(item),))
    true_branch_text = stripped[cursor + 1:true_end].strip()

    cursor = _skip_whitespace(stripped, true_end + 1)
    else_syntax: GenerationElseSyntax
    else_generation_marker = "else<generation>"
    plain_else_marker = "else"
    if stripped.startswith(else_generation_marker, cursor):
        else_syntax = "else<generation>"
        cursor += len(else_generation_marker)
    elif stripped.startswith(plain_else_marker, cursor):
        else_syntax = "else"
        cursor += len(plain_else_marker)
    else:
        return Result.failure((_malformed_generation_if_diagnostic(item),))
    cursor = _skip_whitespace(stripped, cursor)
    if cursor >= len(stripped) or stripped[cursor] != "{":
        return Result.failure((_malformed_generation_if_diagnostic(item),))
    false_end = _matching_delimiter(stripped, cursor, "{", "}")
    if false_end is None:
        return Result.failure((_malformed_generation_if_diagnostic(item),))
    false_branch_text = stripped[cursor + 1:false_end].strip()

    tail = stripped[false_end + 1:].strip()
    if tail:
        return Result.failure((_malformed_generation_if_diagnostic(item),))
    return Result.ok(
        _ParsedGenerationIf(
            condition_text=condition_text,
            true_branch_text=true_branch_text,
            false_branch_text=false_branch_text,
            else_syntax=else_syntax,
        )
    )


def _parse_generation_size_byte_branch_chain(
    item: LoweringInput,
    text: str,
) -> Result[_ParsedSizeByteBranchChain]:
    stripped = text.strip()
    cursor = 0
    arms: list[_ParsedSizeByteBranchChainArm] = []
    for marker in ("if<generation>", "else if<generation>", "else if<generation>"):
        if not stripped.startswith(marker, cursor):
            return Result.failure((_malformed_generation_if_diagnostic(item),))
        cursor += len(marker)
        cursor = _skip_whitespace(stripped, cursor)
        if cursor >= len(stripped) or stripped[cursor] != "(":
            return Result.failure((_malformed_generation_if_diagnostic(item),))
        condition_end = _matching_delimiter(stripped, cursor, "(", ")")
        if condition_end is None:
            return Result.failure((_malformed_generation_if_diagnostic(item),))
        condition_text = stripped[cursor + 1:condition_end].strip()

        cursor = _skip_whitespace(stripped, condition_end + 1)
        if cursor >= len(stripped) or stripped[cursor] != "{":
            return Result.failure((_malformed_generation_if_diagnostic(item),))
        body_end = _matching_delimiter(stripped, cursor, "{", "}")
        if body_end is None:
            return Result.failure((_malformed_generation_if_diagnostic(item),))
        statement_text = stripped[cursor + 1:body_end].strip()
        if not statement_text or _GENERATION_CONDITION_MARKER in statement_text:
            return Result.failure((_malformed_generation_if_diagnostic(item),))
        arms.append(
            _ParsedSizeByteBranchChainArm(
                condition_text=condition_text,
                statement_text=statement_text,
            )
        )
        cursor = _skip_whitespace(stripped, body_end + 1)

    if stripped[cursor:].strip():
        return Result.failure((_malformed_generation_if_diagnostic(item),))
    return Result.ok(_ParsedSizeByteBranchChain(tuple(arms)))


def _generation_branch_condition(
    item: LoweringInput,
    request: LoweringRequest,
    condition_text: str,
) -> Result[_ResolvedGenerationCondition]:
    primitive_condition = _primitive_attribute_condition(condition_text)
    if primitive_condition is not None:
        return _resolve_primitive_attribute_condition(
            item,
            request,
            primitive_condition,
        )
    return _resolve_type_signedness_condition(item, request, condition_text)


def _primitive_attribute_condition(
    condition_text: str,
) -> TsilPrimitiveAttributeCondition | None:
    match = _PRIMITIVE_ATTRIBUTE_CONDITION_RE.fullmatch(condition_text)
    if match is None:
        return None
    return TsilPrimitiveAttributeCondition(match.group(1))


def _resolve_primitive_attribute_condition(
    item: LoweringInput,
    request: LoweringRequest,
    attribute_condition: TsilPrimitiveAttributeCondition,
) -> Result[_ResolvedGenerationCondition]:
    attributes = _primitive_attributes_for(item, request)
    if attributes is None:
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-LOWER-GEN-CONTEXT-MISSING",
                    "generation-time primitive-attribute lowering requires "
                    "primitive attributes in GenerationContext or on the "
                    "selected candidate",
                    location=item.source_location,
                ),
            )
        )

    if attribute_condition.attribute_name != "aligned":
        if attribute_condition.attribute_name not in attributes:
            return Result.failure(
                (
                    Diagnostic.error(
                        "TSL-LOWER-GEN-ATTRIBUTE-UNKNOWN",
                        "generation-time primitive-attribute condition "
                        f"references unknown primitive attribute "
                        f"{attribute_condition.attribute_name!r}",
                        location=item.source_location,
                    ),
                )
            )
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-LOWER-GEN-IF-UNSUPPORTED",
                    "generation-time branch pruning supports only primitive "
                    "attribute 'aligned'; got "
                    f"{attribute_condition.attribute_name!r}",
                    location=item.source_location,
                ),
            )
        )

    if attribute_condition.attribute_name not in attributes:
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-LOWER-GEN-ATTRIBUTE-MISSING",
                    "generation-time branch pruning requires primitive "
                    "attribute 'aligned'",
                    location=item.source_location,
                ),
            )
        )
    value = attributes[attribute_condition.attribute_name]
    if not isinstance(value, bool):
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-LOWER-GEN-ATTRIBUTE-TYPE",
                    "generation-time branch pruning requires primitive "
                    f"attribute 'aligned' to be boolean; got {value!r}",
                    location=item.source_location,
                ),
            )
        )

    return Result.ok(
        _ResolvedGenerationCondition(
            condition=attribute_condition,
            value=value,
        )
    )


def _resolve_type_signedness_condition(
    item: LoweringInput,
    request: LoweringRequest,
    condition_text: str,
) -> Result[_ResolvedGenerationCondition]:
    value_call = _parse_generation_type_call(condition_text, "value<generation>")
    if value_call is None or len(value_call) != 1:
        return Result.failure(
            (_unsupported_generation_condition_diagnostic(item, condition_text),)
        )
    predicate_call = _parse_generation_type_call(value_call[0], "type::is_signed")
    if predicate_call is None or len(predicate_call) != 1:
        return Result.failure(
            (_unsupported_generation_condition_diagnostic(item, condition_text),)
        )

    type_query = predicate_call[0].strip()
    context = _context_for_candidate(item, request)
    selected_candidate_type_tag = (
        item.candidate.type_tag
        if request.generation_context.use_candidate_type_tag
        else None
    )
    type_ref = resolve_generation_type_query(
        type_query,
        context,
        selected_candidate_type_tag=selected_candidate_type_tag,
        location=item.source_location,
    )
    if not type_ref.is_ok:
        return Result.failure(type_ref.diagnostics)

    resolved_type_ref = type_ref.unwrap()
    if resolved_type_ref.kind != "base.in":
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-LOWER-GEN-IF-UNSUPPORTED",
                    "generation-time signedness branch pruning supports only "
                    "'type::is_signed(type<generation>(base::in))'; got "
                    f"{condition_text!r}",
                    location=item.source_location,
                ),
            )
        )

    rule = context.concrete_integer_generation_rules.rule_for(resolved_type_ref.type_tag)
    if rule is None:
        supported = _supported_generation_type_tag(
            resolved_type_ref.type_tag,
            context.concrete_integer_generation_rules,
            type_query,
            item.source_location,
        )
        if not supported.is_ok:
            return Result.failure(supported.diagnostics)
        raise AssertionError("supported signedness type tags must be handled directly")

    return Result.ok(
        _ResolvedGenerationCondition(
            condition=TsilTypeSignednessCondition(resolved_type_ref),
            value=rule.is_signed,
        )
    )


def _skip_whitespace(text: str, index: int) -> int:
    cursor = index
    while cursor < len(text) and text[cursor].isspace():
        cursor += 1
    return cursor


def _matching_delimiter(
    text: str,
    opening_index: int,
    opening: str,
    closing: str,
) -> int | None:
    if opening_index >= len(text) or text[opening_index] != opening:
        return None
    depth = 0
    for index in range(opening_index, len(text)):
        char = text[index]
        if char == opening:
            depth += 1
        elif char == closing:
            depth -= 1
            if depth == 0:
                return index
    return None


def _direct_parameter_add_return_statement(
    item: LoweringInput,
    match: re.Match[str],
) -> Result[TsilReturnStatement]:
    left_name, right_name = match.groups()
    unknown = _unknown_parameter_names(item, (left_name, right_name))
    if unknown:
        return Result.failure((_unknown_parameter_diagnostic(item, unknown),))

    return Result.ok(
        TsilReturnStatement(
            expression=TsilBinaryExpression(
                operator="+",
                left=TsilParameterReference(left_name),
                right=TsilParameterReference(right_name),
            )
        )
    )


def _intrinsic_compose_return_statement(
    item: LoweringInput,
    text: str,
) -> Result[TsilReturnStatement]:
    match = _INTRIN_COMPOSE_RETURN_RE.fullmatch(text)
    if match is None:
        return Result.failure((_malformed_intrinsic_compose_diagnostic(item),))

    intrinsic_name, arguments_text = match.groups()
    if intrinsic_name != "add":
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-LOWER-TSIL-INTRIN-UNSUPPORTED",
                    "mini TSIL lowering supports only intrinsic-compose "
                    f"intrinsic 'add'; got {intrinsic_name!r}",
                    location=item.source_location,
                ),
            )
        )

    argument_names = _intrinsic_argument_names(arguments_text)
    invalid_arguments = tuple(
        argument
        for argument in argument_names
        if _TSIL_IDENTIFIER_RE.fullmatch(argument) is None
    )
    if invalid_arguments:
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-LOWER-TSIL-INTRIN-ARGUMENT",
                    "mini TSIL lowering supports only primitive parameter "
                    "references as intrin_compose<add> arguments; invalid "
                    f"argument(s): "
                    f"{', '.join(repr(argument) for argument in invalid_arguments)}",
                    location=item.source_location,
                ),
            )
        )

    if len(argument_names) != 2:
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-LOWER-TSIL-INTRIN-ARITY",
                    "mini TSIL lowering supports only "
                    "intrin_compose<add> with exactly two arguments; got "
                    f"{len(argument_names)}",
                    location=item.source_location,
                ),
            )
        )

    unknown = _unknown_parameter_names(item, argument_names)
    if unknown:
        return Result.failure((_unknown_parameter_diagnostic(item, unknown),))

    return Result.ok(
        TsilReturnStatement(
            expression=TsilIntrinsicComposeExpression(
                intrinsic=intrinsic_name,
                arguments=tuple(
                    TsilParameterReference(argument) for argument in argument_names
                ),
            )
        )
    )


def _intrinsic_argument_names(arguments_text: str) -> tuple[str, ...]:
    stripped = arguments_text.strip()
    if not stripped:
        return ()
    return tuple(argument.strip() for argument in arguments_text.split(","))


def _unknown_parameter_names(
    item: LoweringInput,
    names: tuple[str, ...],
) -> tuple[str, ...]:
    parameter_names = tuple(
        parameter.name
        for parameter in item.candidate.variant.source.declaration.parameters
    )
    return tuple(name for name in names if name not in parameter_names)


def _unknown_parameter_diagnostic(
    item: LoweringInput,
    unknown_names: tuple[str, ...],
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-TSIL-UNKNOWN-PARAMETER",
        "mini TSIL lowering can reference only declared primitive "
        f"parameters; unknown name(s): "
        f"{', '.join(repr(name) for name in unknown_names)}",
        location=item.source_location,
    )


def _malformed_intrinsic_compose_diagnostic(
    item: LoweringInput,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-TSIL-INTRIN-MALFORMED",
        "mini TSIL lowering supports only intrinsic-compose returns shaped as "
        "'emit_return(intrin_compose<add>(<parameter>, <parameter>));'",
        location=item.source_location,
    )


def _malformed_generation_if_diagnostic(
    item: LoweringInput,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-GEN-IF-MALFORMED",
        "generation-time branch pruning supports only branches shaped as "
        "'if<generation>(<supported condition>) { ... } else<generation> "
        "{ ... }', plus plain 'else { ... }' for the exact signedness "
        "predicate branch form, and the exact no-final-else size-byte "
        "branch chain with == 2, == 4, then == 8 arms",
        location=item.source_location,
    )


def _unsupported_selected_body_assignment_rhs_diagnostic(
    rhs_text: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-SELECTED-BODY-FORM-RHS-UNSUPPORTED",
        "selected-body assignment-form recognition supports only opaque RHS "
        "text shaped as 'intrin<svptrue_b16>()', 'intrin<svptrue_b32>()', "
        "or 'intrin<svptrue_b64>()'; got "
        f"{rhs_text!r}",
        location=location,
    )


def _inconsistent_selected_body_envelope_diagnostic(
    detail: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-SELECTED-BODY-ENVELOPE-INCONSISTENT",
        "selected-body envelope lowering received inconsistent M62 body IR "
        f"boundary state: {detail}",
        location=location,
    )


def _unsupported_generation_condition_diagnostic(
    item: LoweringInput,
    condition_text: str,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-GEN-IF-UNSUPPORTED",
        "generation-time branch pruning supports only conditions "
        "'value<generation>(primitive::attribute(aligned))' and "
        "'value<generation>(type::is_signed(type<generation>(base::in)))'; "
        "got "
        f"{condition_text!r}",
        location=item.source_location,
    )


def _unsupported_plain_else_generation_branch(
    item: LoweringInput,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-GEN-IF-UNSUPPORTED",
        "plain 'else' generation branch syntax is supported only for "
        "'if<generation>(value<generation>(type::is_signed("
        "type<generation>(base::in))))'; use 'else<generation>' for other "
        "supported generation-time branch forms",
        location=item.source_location,
    )


def _malformed_generation_type_query_diagnostic(
    query_text: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-GEN-TYPE-MALFORMED",
        "generation-time type query must be shaped as "
        "'type<generation>(...)'; got "
        f"{query_text!r}",
        location=location,
    )


def _unsupported_generation_type_query_diagnostic(
    query_text: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-GEN-TYPE-UNSUPPORTED",
        "generation-time type lowering supports only "
        "'type<generation>(base::in)', "
        "'type<generation>(base::signed_of(type<generation>(base::in)))', "
        "and "
        "'type<generation>(base::unsigned_of(type<generation>(base::in)))'; "
        f"got {query_text!r}",
        location=location,
    )


def _unsupported_generation_type_shorthand_diagnostic(
    query_text: str,
    helper_name: str,
    location: SourceLocation | None,
) -> Diagnostic:
    exact_form = (
        f"type<generation>({helper_name}"
        "(type<generation>(base::in)))"
    )
    return Diagnostic.error(
        "TSL-LOWER-GEN-TYPE-UNSUPPORTED",
        "generation-time type lowering does not accept shorthand "
        f"{helper_name}(base::in); use exact nested form {exact_form!r}; "
        f"got {query_text!r}",
        location=location,
    )


def _unsupported_nested_generation_type_query_diagnostic(
    query_text: str,
    nested_text: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-GEN-TYPE-NESTED-UNSUPPORTED",
        "generation-time signed/unsigned companion lowering supports only "
        "nested 'type<generation>(base::in)' input; got nested query "
        f"{nested_text!r} in {query_text!r}",
        location=location,
    )


def _malformed_generation_value_query_diagnostic(
    query_text: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-GEN-VALUE-MALFORMED",
        "generation-time value query must be shaped as "
        "'value<generation>(...)'; got "
        f"{query_text!r}",
        location=location,
    )


def _unsupported_generation_value_query_diagnostic(
    query_text: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-GEN-VALUE-UNSUPPORTED",
        "generation-time value lowering supports only "
        "'value<generation>(type::size_bytes("
        "type<generation>(base::in)))' and the exact "
        "'value<generation>(type::size_bytes("
        "type<generation>(base::in))) * 8' expression; "
        f"got {query_text!r}",
        location=location,
    )


def _unsupported_nested_generation_value_query_diagnostic(
    query_text: str,
    nested_text: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-GEN-VALUE-NESTED-UNSUPPORTED",
        "generation-time scalar size-bytes lowering supports only nested "
        "'type<generation>(base::in)' input; got nested query "
        f"{nested_text!r} in {query_text!r}",
        location=location,
    )


def _malformed_generation_value_arithmetic_diagnostic(
    query_text: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-GEN-VALUE-ARITH-MALFORMED",
        "generation-time scalar bit-width value arithmetic must be shaped as "
        "'value<generation>(type::size_bytes(type<generation>(base::in))) * 8'; "
        f"got {query_text!r}",
        location=location,
    )


def _unsupported_generation_value_arithmetic_operator_diagnostic(
    query_text: str,
    operator: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-GEN-VALUE-ARITH-OPERATOR",
        "generation-time scalar bit-width value arithmetic supports only the "
        f"exact '*' operator with right literal 8; got operator {operator!r} "
        f"in {query_text!r}",
        location=location,
    )


def _unsupported_generation_value_arithmetic_literal_diagnostic(
    query_text: str,
    literal_text: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-GEN-VALUE-ARITH-LITERAL",
        "generation-time scalar bit-width value arithmetic supports only the "
        f"exact right literal '8'; got {literal_text!r} in {query_text!r}",
        location=location,
    )


def _unsupported_generation_value_arithmetic_operand_diagnostic(
    query_text: str,
    operand_text: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-GEN-VALUE-ARITH-OPERAND",
        "generation-time scalar bit-width value arithmetic supports only "
        "the M55 scalar size-bytes query as the left operand; got "
        f"{operand_text!r} in {query_text!r}",
        location=location,
    )


def _malformed_generation_predicate_diagnostic(
    query_text: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-GEN-PREDICATE-MALFORMED",
        "generation-time scalar size-byte equality predicate must be shaped as "
        "'value<generation>(type::size_bytes(type<generation>(base::in))) == "
        "2|4|8'; got "
        f"{query_text!r}",
        location=location,
    )


def _unsupported_generation_predicate_operator_diagnostic(
    query_text: str,
    operator: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-GEN-PREDICATE-OPERATOR",
        "generation-time scalar size-byte equality predicate supports only "
        f"the exact '==' operator; got operator {operator!r} in {query_text!r}",
        location=location,
    )


def _unsupported_generation_predicate_literal_diagnostic(
    query_text: str,
    literal_text: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-GEN-PREDICATE-LITERAL",
        "generation-time scalar size-byte equality predicate supports only "
        f"right literal '2', '4', or '8'; got {literal_text!r} in {query_text!r}",
        location=location,
    )


def _unsupported_generation_predicate_operand_diagnostic(
    query_text: str,
    operand_text: str,
    location: SourceLocation | None,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-LOWER-GEN-PREDICATE-OPERAND",
        "generation-time scalar size-byte equality predicate supports only "
        "the M55 scalar size-bytes query as the left operand; got "
        f"{operand_text!r} in {query_text!r}",
        location=location,
    )


def _unresolved_selected_branch_diagnostic(
    item: LoweringInput,
    branch_text: str,
) -> Diagnostic:
    helper_names = tuple(
        marker for marker in _GENERATION_HELPER_MARKERS if marker in branch_text
    )
    helper_message = (
        f"; unresolved helper marker(s): {', '.join(repr(name) for name in helper_names)}"
        if helper_names
        else ""
    )
    return Diagnostic.error(
        "TSL-LOWER-GEN-UNRESOLVED-SELECTED-BRANCH",
        "generation-time branch pruning selected a branch that still contains "
        f"unsupported generation-time helper text{helper_message}",
        location=item.source_location,
    )


def _unsupported_payload_diagnostic(
    item: LoweringInput,
    *,
    strategy: LoweringStrategy = "mini_tsil",
) -> Diagnostic:
    if item.payload.classification == "tsil":
        code = "TSL-LOWER-TSIL-UNSUPPORTED"
        if strategy == "typed_opaque":
            message = (
                f"candidate {item.candidate_id!r} has a TSIL payload; semantic "
                "TSIL lowering is disabled by the typed-opaque strategy"
            )
        else:
            message = (
                f"candidate {item.candidate_id!r} has a TSIL payload; semantic "
                "TSIL lowering supports only the mini direct parameter-add return "
                "and intrinsic-compose add return slices"
            )
        if item.payload.has_generation_condition:
            message += (
                " and contains generation-time helpers that must be evaluated "
                "by a future lowering slice"
            )
    else:
        code = "TSL-LOWER-PAYLOAD-UNSUPPORTED"
        message = (
            f"candidate {item.candidate_id!r} has unsupported implementation "
            f"payload kind {item.payload.body_kind!r}"
        )
    return Diagnostic.error(code, message, location=item.source_location)


def _has_generation_helper(text: str) -> bool:
    return any(marker in text for marker in _GENERATION_HELPER_MARKERS)
