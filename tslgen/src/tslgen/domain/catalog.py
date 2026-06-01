"""Minimal typed catalog values for the tiny clean restart slice."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, NewType

from tslgen.core.diagnostics import SourceLocation
from tslgen.domain.signatures import PrimitiveSignature, SignatureParameterTerm

ExtensionName = NewType("ExtensionName", str)
TypeTag = NewType("TypeTag", str)
ReturnTypeBindingKind = Literal["base", "extension"]


@dataclass(frozen=True, slots=True)
class LowerableOperationFragment:
    operation: str
    arguments: tuple[str, ...]
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class RawStringToken:
    text: str
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class SelfPrimitiveReference:
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class NamedPrimitiveReference:
    name: str
    source: SourceLocation


PrimitiveCallTarget = SelfPrimitiveReference | NamedPrimitiveReference


@dataclass(frozen=True, slots=True)
class PrimitiveCallSelector:
    target: PrimitiveCallTarget
    specialization: str | None
    attrs: str | None
    source_text: str
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class PrimitiveCallArgument:
    text: str
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class PrimitiveCall:
    selector: PrimitiveCallSelector
    payload: str
    source: SourceLocation
    arguments: tuple[PrimitiveCallArgument, ...] = ()


@dataclass(frozen=True, slots=True)
class LowerableDirective:
    name: str
    arguments: tuple[str, ...]
    source: SourceLocation
    primitive_call: PrimitiveCall | None = None
    payload_tokens: tuple[PayloadToken, ...] = ()


PayloadToken = RawStringToken | LowerableDirective
BodyToken = RawStringToken | LowerableOperationFragment | LowerableDirective


@dataclass(frozen=True, slots=True)
class ImplementationBody:
    tokens: tuple[BodyToken, ...]
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class Implementation:
    extension: str
    type_tag: str
    body: ImplementationBody
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class PrimitiveAttribute:
    key: str
    value: str
    source: SourceLocation
    key_argument: str | None = None
    declared_value: str | None = None


@dataclass(frozen=True, slots=True)
class ReturnTypeBindingDeclaration:
    kind: ReturnTypeBindingKind
    name: str
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class Primitive:
    name: str
    signature: str
    parameters: tuple[str, ...]
    template: str
    implementations: tuple[Implementation, ...]
    source: SourceLocation
    attributes: tuple[PrimitiveAttribute, ...] = ()
    declared_attributes: tuple[PrimitiveAttribute, ...] = ()
    return_type_binding: ReturnTypeBindingDeclaration | None = None
    signature_model: PrimitiveSignature | None = None
    parameter_signature_terms: tuple[SignatureParameterTerm, ...] = ()


@dataclass(frozen=True, slots=True)
class TypeGroup:
    name: str
    type_tags: tuple[str, ...]
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class ExtensionBackendMetadata:
    supported: bool | None
    type_name: str | None
    generation_support: tuple[str, ...]
    headers: tuple[str, ...]
    header_guard: str | None
    test_suite_name: str | None
    test_support_header: str | None
    source: SourceLocation | None = None


@dataclass(frozen=True, slots=True)
class BackendTypeSpelling:
    backend: str
    spelling: str
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class BackendLaneTypeSpelling:
    backend: str
    lanes: int
    spelling: str
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class VectorRegisterTypeEntry:
    selector: str
    spellings: tuple[BackendTypeSpelling, ...]
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class ResolvedVectorRegisterType:
    extension: str
    type_tag: str
    backend: str
    spelling: str
    source: SourceLocation


ExtensionTypePolicyKind = Literal[
    "base_type",
    "fixed_array",
    "lane_bitmask",
    "native_predicate",
    "native_predicate_by_lanes",
    "same_as_mask_type",
    "bool",
    "unsigned_scalar",
]


@dataclass(frozen=True, slots=True)
class ExtensionTypePolicy:
    kind: ExtensionTypePolicyKind
    source: SourceLocation
    element: str | None = None
    length: str | None = None
    width: str | None = None
    spellings: tuple[BackendTypeSpelling, ...] = ()
    lane_spellings: tuple[BackendLaneTypeSpelling, ...] = ()


@dataclass(frozen=True, slots=True)
class ExtensionSizeParameter:
    kind: str
    name: str
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class Extension:
    name: str
    extension_name: str | None
    vendor: str | None
    inherits: str | None
    family: str | None
    intrinsic_style: str | None
    vector_bits: int | str | None
    native_sort_order: int | None
    autodetect: bool | None
    lscpu_flags: tuple[str, ...]
    mask_repr: str | None
    mask_width: int | str | None
    mask_vector_loadable: bool | None
    runtime_lanes: bool | None
    default_test_target: bool | None
    cpp: ExtensionBackendMetadata
    rust: ExtensionBackendMetadata
    signature_support_exclude: tuple[str, ...]
    test_filter_exclude_templates: tuple[str, ...]
    test_sizes_bits: tuple[int, ...]
    vector_register_types: tuple[VectorRegisterTypeEntry, ...]
    resolved_vector_register_types: tuple[ResolvedVectorRegisterType, ...]
    vector_register_type_policy: ExtensionTypePolicy | None
    size_parameter: ExtensionSizeParameter | None
    mask_type_policy: ExtensionTypePolicy | None
    integral_mask_type_policy: ExtensionTypePolicy | None
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class ExtensionCatalog:
    extensions: tuple[Extension, ...] = ()

    def get(self, name: str) -> Extension | None:
        for extension in self.extensions:
            if extension.name == name:
                return extension
        return None


@dataclass(frozen=True, slots=True)
class Catalog:
    primitives: tuple[Primitive, ...]
    type_groups: tuple[TypeGroup, ...] = ()
    extensions: ExtensionCatalog = field(default_factory=ExtensionCatalog)
