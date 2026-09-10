"""Typed identity and form inventory for public whole-array algorithms."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType


class AlgorithmSemanticFamily(StrEnum):
    UTILITY = "utility"
    ITERATION = "iteration"
    PREDICATE = "predicate"
    COUNT = "count"
    SELECT = "select"
    TRANSFORM = "transform"
    CONSUME = "consume"
    AGGREGATE = "aggregate"


class AlgorithmArity(StrEnum):
    NONE = "none"
    UNARY = "unary"
    BINARY = "binary"


class AlgorithmShape(StrEnum):
    CHUNK_COUNT = "chunk_count"
    CHUNK_ITERATION = "chunk_iteration"
    PLAIN = "plain"
    MASKED = "masked"
    SELECTED = "selected"
    INDICES = "indices"
    MASKED_INDICES = "masked_indices"
    SELECTED_INDICES = "selected_indices"
    WHERE = "where"


class AlgorithmMaskForm(StrEnum):
    DEFAULT = "default"
    LAYOUT = "layout"


class AlgorithmResultKind(StrEnum):
    VOID = "void"
    COUNT = "count"
    VALUE = "value"


@dataclass(frozen=True, slots=True)
class AlgorithmSurfaceFamily:
    """One stable semantic algorithm family and its repeated form axes."""

    name: str
    semantic_family: AlgorithmSemanticFamily
    arity: AlgorithmArity
    shape: AlgorithmShape
    result_kind: AlgorithmResultKind
    has_contract: bool
    has_mask_layout_form: bool = False
    has_scaled_form: bool = False
    has_raw_form: bool = True

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("algorithm surface families require a name")
        if self.has_mask_layout_form and not self.has_contract:
            raise ValueError("algorithm mask-layout forms require a checked contract")
        if self.has_scaled_form and (
            not self.has_contract
            or self.shape
            not in {AlgorithmShape.SELECTED, AlgorithmShape.SELECTED_INDICES}
        ):
            raise ValueError("scaled algorithms require a selected checked form")
        if (
            self.shape is AlgorithmShape.CHUNK_COUNT
            and self.semantic_family is not AlgorithmSemanticFamily.UTILITY
        ):
            raise ValueError("algorithm chunk counts must be utility families")
        if (
            self.semantic_family is AlgorithmSemanticFamily.UTILITY
            and self.arity is not AlgorithmArity.NONE
        ):
            raise ValueError("algorithm utility families cannot have an arity")

    @property
    def callable_forms(self) -> tuple[AlgorithmCallableForm, ...]:
        return (
            AlgorithmCallableForm(self, AlgorithmMaskForm.DEFAULT, self.name),
            *(
                (
                    AlgorithmCallableForm(
                        self,
                        AlgorithmMaskForm.LAYOUT,
                        f"{self.name}_mask_layout",
                    ),
                )
                if self.has_mask_layout_form
                else ()
            ),
        )


@dataclass(frozen=True, slots=True)
class AlgorithmCallableForm:
    """One target-neutral callable identity derived from a semantic family."""

    family: AlgorithmSurfaceFamily
    mask_form: AlgorithmMaskForm
    name: str

    def __post_init__(self) -> None:
        expected = (
            self.family.name
            if self.mask_form is AlgorithmMaskForm.DEFAULT
            else f"{self.family.name}_mask_layout"
        )
        if self.name != expected:
            raise ValueError("algorithm callable form name disagrees with its axes")
        if (
            self.mask_form is AlgorithmMaskForm.LAYOUT
            and not self.family.has_mask_layout_form
        ):
            raise ValueError("algorithm family does not admit a mask-layout form")

    @property
    def checked_name(self) -> str | None:
        return f"{self.name}_checked" if self.family.has_contract else None

    @property
    def raw_name(self) -> str | None:
        return f"{self.name}_raw" if self.family.has_raw_form else None

    @property
    def scaled_raw_name(self) -> str | None:
        if self.family.has_scaled_form and self.mask_form is AlgorithmMaskForm.DEFAULT:
            return f"{self.name}_scaled_raw"
        return None

    @property
    def scaled_checked_name(self) -> str | None:
        if self.family.has_scaled_form and self.mask_form is AlgorithmMaskForm.DEFAULT:
            return f"{self.name}_scaled_checked"
        return None


@dataclass(frozen=True, slots=True)
class AlgorithmBackendFormSupport:
    """One backend's explicit disposition for an inventory form."""

    backend_id: str
    form: AlgorithmCallableForm
    supported: bool
    reason: str | None = None

    def __post_init__(self) -> None:
        if not self.backend_id:
            raise ValueError("algorithm backend support requires a backend")
        if self.supported and self.reason is not None:
            raise ValueError("supported algorithm forms cannot have a reason")
        if not self.supported and self.reason is None:
            raise ValueError(
                "unsupported algorithm forms require a reason"
            )


def _family(
    name: str,
    semantic_family: AlgorithmSemanticFamily,
    arity: AlgorithmArity,
    shape: AlgorithmShape,
    result_kind: AlgorithmResultKind,
    *,
    checked: bool,
    mask_layout: bool = False,
    scaled: bool = False,
    raw: bool = True,
) -> AlgorithmSurfaceFamily:
    return AlgorithmSurfaceFamily(
        name,
        semantic_family,
        arity,
        shape,
        result_kind,
        checked,
        mask_layout,
        scaled,
        raw,
    )


_ARITIES = (
    ("unary", AlgorithmArity.UNARY),
    ("binary", AlgorithmArity.BINARY),
)

ALGORITHM_SURFACE_FAMILIES = (
    *(
        _family(
            name,
            AlgorithmSemanticFamily.UTILITY,
            AlgorithmArity.NONE,
            AlgorithmShape.CHUNK_COUNT,
            AlgorithmResultKind.COUNT,
            checked=False,
            raw=False,
        )
        for name in (
            "integral_mask_chunk_count",
            "native_mask_chunk_count",
            "mask_chunk_count",
            "byte_mask_count",
            "bit_mask_count",
        )
    ),
    _family(
        "for_each_chunk",
        AlgorithmSemanticFamily.ITERATION,
        AlgorithmArity.NONE,
        AlgorithmShape.CHUNK_ITERATION,
        AlgorithmResultKind.VOID,
        checked=False,
    ),
    *(
        _family(
            f"predicate_{arity_name}",
            AlgorithmSemanticFamily.PREDICATE,
            arity,
            AlgorithmShape.PLAIN,
            AlgorithmResultKind.COUNT,
            checked=True,
            mask_layout=True,
        )
        for arity_name, arity in _ARITIES
    ),
    _family(
        "count_unary",
        AlgorithmSemanticFamily.COUNT,
        AlgorithmArity.UNARY,
        AlgorithmShape.PLAIN,
        AlgorithmResultKind.COUNT,
        checked=False,
    ),
    _family(
        "count_binary",
        AlgorithmSemanticFamily.COUNT,
        AlgorithmArity.BINARY,
        AlgorithmShape.PLAIN,
        AlgorithmResultKind.COUNT,
        checked=True,
    ),
    *(
        _family(
            f"count_masked_{arity_name}",
            AlgorithmSemanticFamily.COUNT,
            arity,
            AlgorithmShape.MASKED,
            AlgorithmResultKind.COUNT,
            checked=True,
            mask_layout=True,
        )
        for arity_name, arity in _ARITIES
    ),
    *(
        _family(
            f"count_selected_{arity_name}",
            AlgorithmSemanticFamily.COUNT,
            arity,
            AlgorithmShape.SELECTED,
            AlgorithmResultKind.COUNT,
            checked=True,
            scaled=True,
        )
        for arity_name, arity in _ARITIES
    ),
    *(
        _family(
            f"select_{prefix}{arity_name}",
            AlgorithmSemanticFamily.SELECT,
            arity,
            shape,
            AlgorithmResultKind.COUNT,
            checked=True,
            mask_layout=shape
            in {AlgorithmShape.MASKED, AlgorithmShape.MASKED_INDICES},
            scaled=shape is AlgorithmShape.SELECTED_INDICES,
        )
        for prefix, shape in (
            ("", AlgorithmShape.PLAIN),
            ("masked_", AlgorithmShape.MASKED),
            ("indices_", AlgorithmShape.INDICES),
            ("masked_indices_", AlgorithmShape.MASKED_INDICES),
            ("selected_indices_", AlgorithmShape.SELECTED_INDICES),
        )
        for arity_name, arity in _ARITIES
    ),
    *(
        _family(
            f"transform_{prefix}{arity_name}",
            AlgorithmSemanticFamily.TRANSFORM,
            arity,
            shape,
            AlgorithmResultKind.VOID,
            checked=True,
            mask_layout=shape in {AlgorithmShape.WHERE, AlgorithmShape.MASKED},
            scaled=shape is AlgorithmShape.SELECTED,
        )
        for prefix, shape in (
            ("", AlgorithmShape.PLAIN),
            ("selected_", AlgorithmShape.SELECTED),
            ("where_", AlgorithmShape.WHERE),
            ("masked_", AlgorithmShape.MASKED),
        )
        for arity_name, arity in _ARITIES
    ),
    *(
        _family(
            f"{semantic_family.value}_{prefix}{arity_name}",
            semantic_family,
            arity,
            shape,
            result_kind,
            checked=shape is not AlgorithmShape.PLAIN
            or arity is AlgorithmArity.BINARY,
            scaled=shape is AlgorithmShape.SELECTED,
        )
        for semantic_family, result_kind in (
            (AlgorithmSemanticFamily.CONSUME, AlgorithmResultKind.VOID),
            (AlgorithmSemanticFamily.AGGREGATE, AlgorithmResultKind.VALUE),
        )
        for prefix, shape in (
            ("", AlgorithmShape.PLAIN),
            ("masked_", AlgorithmShape.MASKED),
            ("selected_", AlgorithmShape.SELECTED),
        )
        for arity_name, arity in _ARITIES
    ),
)

_family_names = tuple(family.name for family in ALGORITHM_SURFACE_FAMILIES)
if len(set(_family_names)) != len(_family_names):
    raise ValueError("algorithm surface family names must be unique")

ALGORITHM_CALLABLE_FORMS = tuple(
    form
    for family in ALGORITHM_SURFACE_FAMILIES
    for form in family.callable_forms
)
_forms_by_name = {form.name: form for form in ALGORITHM_CALLABLE_FORMS}
if len(_forms_by_name) != len(ALGORITHM_CALLABLE_FORMS):
    raise ValueError("algorithm callable form names must be unique")

ALGORITHM_FORMS_BY_NAME: Mapping[str, AlgorithmCallableForm] = MappingProxyType(
    _forms_by_name
)
ALGORITHM_PUBLIC_FAMILIES = frozenset(_family_names)
ALGORITHM_ORDINARY_NAMES = frozenset(_forms_by_name)
ALGORITHM_RAW_NAMES = frozenset(
    name
    for form in ALGORITHM_CALLABLE_FORMS
    if (name := form.raw_name) is not None
)
ALGORITHM_CHECKED_NAMES = frozenset(
    name
    for form in ALGORITHM_CALLABLE_FORMS
    if (name := form.checked_name) is not None
)
ALGORITHM_SCALED_RAW_NAMES = frozenset(
    name
    for form in ALGORITHM_CALLABLE_FORMS
    if (name := form.scaled_raw_name) is not None
)
ALGORITHM_SCALED_CHECKED_NAMES = frozenset(
    name
    for form in ALGORITHM_CALLABLE_FORMS
    if (name := form.scaled_checked_name) is not None
)
_callable_name_sets = (
    ALGORITHM_ORDINARY_NAMES,
    ALGORITHM_RAW_NAMES,
    ALGORITHM_CHECKED_NAMES,
    ALGORITHM_SCALED_RAW_NAMES,
    ALGORITHM_SCALED_CHECKED_NAMES,
)
if len(set().union(*_callable_name_sets)) != sum(
    len(names) for names in _callable_name_sets
):
    raise ValueError("algorithm callable identities must be unique")
ALGORITHM_CHECKED_TWINS: Mapping[str, str] = MappingProxyType(
    {
        form.checked_name: form.name
        for form in ALGORITHM_CALLABLE_FORMS
        if form.checked_name is not None
    }
)
ALGORITHM_SCALED_CHECKED_TWINS: Mapping[str, str] = MappingProxyType(
    {
        form.scaled_checked_name: form.scaled_raw_name
        for form in ALGORITHM_CALLABLE_FORMS
        if form.scaled_checked_name is not None
        and form.scaled_raw_name is not None
    }
)


__all__ = (
    "ALGORITHM_CALLABLE_FORMS",
    "ALGORITHM_CHECKED_NAMES",
    "ALGORITHM_CHECKED_TWINS",
    "ALGORITHM_FORMS_BY_NAME",
    "ALGORITHM_ORDINARY_NAMES",
    "ALGORITHM_PUBLIC_FAMILIES",
    "ALGORITHM_RAW_NAMES",
    "ALGORITHM_SCALED_CHECKED_NAMES",
    "ALGORITHM_SCALED_CHECKED_TWINS",
    "ALGORITHM_SCALED_RAW_NAMES",
    "ALGORITHM_SURFACE_FAMILIES",
    "AlgorithmArity",
    "AlgorithmBackendFormSupport",
    "AlgorithmCallableForm",
    "AlgorithmMaskForm",
    "AlgorithmResultKind",
    "AlgorithmSemanticFamily",
    "AlgorithmShape",
    "AlgorithmSurfaceFamily",
)
