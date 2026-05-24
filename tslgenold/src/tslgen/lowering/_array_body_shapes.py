from __future__ import annotations

import re

from tslgen.lowering._array_body_models import (
    ExactArrayInitializationHelperLeafFieldName,
    ExactArrayInitializationHelperLeafKind,
    ExactArrayInitializationHelperRequestKind,
    _EXACT_ARRAY_INITIALIZATION_BACKEND_UNINIT_REQUEST_RULE,
    _EXACT_ARRAY_INITIALIZATION_BASE_TYPE_REQUEST_RULE,
    _EXACT_ARRAY_INITIALIZATION_HELPER_LEAF_SPECS,
    _EXACT_ARRAY_INITIALIZATION_HELPER_TEXT_BY_KIND,
    _EXACT_ARRAY_INITIALIZATION_VECTOR_ALIGNMENT_REQUEST_RULE,
    _EXACT_ARRAY_INITIALIZATION_VECTOR_LENGTH_REQUEST_RULE,
    _ExactArrayInitializationBackendUninitRequestRule,
    _ExactArrayInitializationBaseTypeRequestRule,
    _ExactArrayInitializationHelperLeafSpec,
    _ExactArrayInitializationVectorAlignmentRequestRule,
    _ExactArrayInitializationVectorLengthRequestRule,
)


_MODEL_OWNED_SHAPE_EXPORTS = (
    ExactArrayInitializationHelperLeafFieldName,
    ExactArrayInitializationHelperLeafKind,
    ExactArrayInitializationHelperRequestKind,
    _EXACT_ARRAY_INITIALIZATION_BACKEND_UNINIT_REQUEST_RULE,
    _EXACT_ARRAY_INITIALIZATION_BASE_TYPE_REQUEST_RULE,
    _EXACT_ARRAY_INITIALIZATION_HELPER_LEAF_SPECS,
    _EXACT_ARRAY_INITIALIZATION_HELPER_TEXT_BY_KIND,
    _EXACT_ARRAY_INITIALIZATION_VECTOR_ALIGNMENT_REQUEST_RULE,
    _EXACT_ARRAY_INITIALIZATION_VECTOR_LENGTH_REQUEST_RULE,
    _ExactArrayInitializationBackendUninitRequestRule,
    _ExactArrayInitializationBaseTypeRequestRule,
    _ExactArrayInitializationHelperLeafSpec,
    _ExactArrayInitializationVectorAlignmentRequestRule,
    _ExactArrayInitializationVectorLengthRequestRule,
)


_TSIL_IDENTIFIER = r"[A-Za-z_][A-Za-z0-9_]*"

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
