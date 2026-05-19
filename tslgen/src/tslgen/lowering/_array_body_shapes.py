from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Literal


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
