"""Typed capabilities for supported primitive signature kinds."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from string import Formatter
from types import MappingProxyType
from typing import Literal

from tslc.catalog.signatures import LANE_LIST_KIND

PointerMutability = Literal["const", "mutable"]
_FORMATTER = Formatter()


@dataclass(frozen=True, slots=True)
class SignatureKindCapability:
    """Compiler behavior for one signature kind token.

    The token itself is source-visible, but these projections are compiler
    semantics: overload identity, pointer/borrow categories, and backend type
    projections. Keeping them together prevents a new kind from needing separate
    edits in support policy, lowering, and every backend renderer.
    """

    kind: str
    maskable_result: bool = False
    mask_deferred_param: bool = False
    pointer_mutability: PointerMutability | None = None
    borrowed_parameter: bool = False
    immediate_operand: bool = False
    lane_list: bool = False
    index_vector: bool = False
    scalable_deferred: bool = False
    requires_vector_axis: bool = True
    overload_token: str = "base"
    overload_token_when_register_is_base: str | None = None
    cpp_result_type: str | None = None
    cpp_param_type: str | None = None
    cpp_free_type: str | None = None
    rust_owner_type: str | None = None
    rust_param_type: str | None = None
    rust_free_type: str | None = None
    rust_concrete_type: str | None = None

    def overload_identity_token(self, *, register_is_base: bool) -> str:
        if register_is_base and self.overload_token_when_register_is_base is not None:
            return self.overload_token_when_register_is_base
        return self.overload_token


@dataclass(frozen=True, slots=True)
class SignatureKindCatalog:
    capabilities: tuple[SignatureKindCapability, ...]
    _by_kind: Mapping[str, SignatureKindCapability] = field(
        init=False,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        by_kind: dict[str, SignatureKindCapability] = {}
        duplicates: list[str] = []
        for capability in self.capabilities:
            if capability.kind in by_kind:
                duplicates.append(capability.kind)
            by_kind[capability.kind] = capability
        if duplicates:
            raise ValueError(
                "duplicate signature kind capabilities: "
                + ", ".join(sorted(set(duplicates)))
            )
        object.__setattr__(self, "_by_kind", MappingProxyType(by_kind))
        for flag in ("immediate_operand", "lane_list", "index_vector"):
            self._validate_single_kind(flag)

    @property
    def by_kind(self) -> Mapping[str, SignatureKindCapability]:
        return self._by_kind

    @property
    def supported_kinds(self) -> frozenset[str]:
        return frozenset(self.by_kind)

    @property
    def maskable_result_kinds(self) -> frozenset[str]:
        return frozenset(
            capability.kind
            for capability in self.capabilities
            if capability.maskable_result
        )

    @property
    def mask_deferred_param_kinds(self) -> frozenset[str]:
        return frozenset(
            capability.kind
            for capability in self.capabilities
            if capability.mask_deferred_param
        )

    @property
    def pointer_kinds(self) -> frozenset[str]:
        return frozenset(
            capability.kind
            for capability in self.capabilities
            if capability.pointer_mutability is not None
        )

    @property
    def const_pointer_kinds(self) -> frozenset[str]:
        return frozenset(
            capability.kind
            for capability in self.capabilities
            if capability.pointer_mutability == "const"
        )

    @property
    def mutable_pointer_kinds(self) -> frozenset[str]:
        return frozenset(
            capability.kind
            for capability in self.capabilities
            if capability.pointer_mutability == "mutable"
        )

    @property
    def borrowed_parameter_kinds(self) -> frozenset[str]:
        return frozenset(
            capability.kind
            for capability in self.capabilities
            if capability.borrowed_parameter
        )

    @property
    def scalable_deferred_kinds(self) -> frozenset[str]:
        return frozenset(
            capability.kind
            for capability in self.capabilities
            if capability.scalable_deferred
        )

    @property
    def immediate_kind(self) -> str:
        return self._single_kind("immediate_operand")

    @property
    def lane_list_kind(self) -> str:
        return self._single_kind("lane_list")

    @property
    def index_vector_kind(self) -> str:
        return self._single_kind("index_vector")

    def supports(self, kind: str) -> bool:
        return kind in self.by_kind

    def unsupported_kinds(self, kinds: set[str]) -> frozenset[str]:
        return frozenset(kind for kind in kinds if not self.supports(kind))

    def is_const_pointer(self, kind: str) -> bool:
        capability = self.by_kind.get(kind)
        return capability is not None and capability.pointer_mutability == "const"

    def is_mutable_pointer(self, kind: str) -> bool:
        capability = self.by_kind.get(kind)
        return capability is not None and capability.pointer_mutability == "mutable"

    def is_borrowed_parameter(self, kind: str) -> bool:
        capability = self.by_kind.get(kind)
        return capability is not None and capability.borrowed_parameter

    def requires_vector_axis(self, kind: str) -> bool:
        return self._capability(kind).requires_vector_axis

    def is_free_function_signature(
        self,
        result_kind: str,
        param_kinds: tuple[str, ...],
    ) -> bool:
        """Whether a signature has no SIMD-vector axis and renders as a plain function."""

        kinds = (result_kind, *param_kinds)
        return all(not self.requires_vector_axis(kind) for kind in kinds)

    def overload_identity_token(self, kind: str, *, register_is_base: bool) -> str:
        return self._capability(kind).overload_identity_token(
            register_is_base=register_is_base
        )

    def cpp_result_type(self, kind: str) -> str:
        return self._projection(kind, "cpp_result_type")

    def cpp_param_type(
        self,
        kind: str,
        *,
        index_type: str | None = None,
        target_vector: str = "ToVec",
    ) -> str:
        return self._projection(
            kind,
            "cpp_param_type",
            index_type=index_type,
            target_vector=target_vector,
        )

    def cpp_free_type(self, kind: str, *, base_type: str) -> str:
        return self._projection(kind, "cpp_free_type", base=base_type)

    def rust_owner_type(self, kind: str, *, owner: str) -> str:
        return self._projection(kind, "rust_owner_type", owner=owner)

    def rust_param_type(self, kind: str, *, owner: str) -> str:
        return self._projection(kind, "rust_param_type", owner=owner)

    def rust_free_type(self, kind: str, *, base_type: str) -> str:
        if self.is_const_pointer(kind) and base_type.startswith("*mut "):
            return "*const " + base_type[len("*mut ") :]
        return self._projection(kind, "rust_free_type", base=base_type)

    def rust_concrete_type(
        self,
        kind: str,
        *,
        base_type: str,
        register_type: str,
        array_type: str,
    ) -> str:
        return self._projection(
            kind,
            "rust_concrete_type",
            base=base_type,
            register=register_type,
            array=array_type,
        )

    def _single_kind(self, flag: str) -> str:
        self._validate_single_kind(flag)
        return next(
            capability.kind
            for capability in self.capabilities
            if bool(getattr(capability, flag))
        )

    def _validate_single_kind(self, flag: str) -> None:
        matches = tuple(
            capability.kind
            for capability in self.capabilities
            if bool(getattr(capability, flag))
        )
        if len(matches) != 1:
            raise ValueError(f"expected exactly one signature kind with {flag}")

    def _projection(self, kind: str, projection_name: str, **values: str | None) -> str:
        template = getattr(self._capability(kind), projection_name)
        if template is None:
            raise KeyError(
                f"signature kind {kind!r} has no {projection_name} projection"
            )
        required = frozenset(
            field_name
            for _literal, field_name, _format_spec, _conversion in _FORMATTER.parse(
                template
            )
            if field_name
        )
        missing = tuple(sorted(name for name in required if values.get(name) is None))
        if missing:
            raise ValueError(
                f"signature kind {kind!r} {projection_name} projection requires "
                + ", ".join(missing)
            )
        return template.format(**values)

    def _capability(self, kind: str) -> SignatureKindCapability:
        capability = self.by_kind.get(kind)
        if capability is None:
            raise KeyError(f"unsupported signature kind {kind!r}")
        return capability


DEFAULT_SIGNATURE_KINDS = SignatureKindCatalog(
    (
        SignatureKindCapability(
            "v",
            maskable_result=True,
            overload_token="register",
            overload_token_when_register_is_base="base",
            cpp_result_type="typename Vec::register_type",
            cpp_param_type="typename tsl::reg_param<Vec>::type",
            rust_owner_type="{owner}::RegisterType",
            rust_param_type="{owner}::RegisterType",
            rust_concrete_type="{register}",
        ),
        SignatureKindCapability(
            "s",
            cpp_result_type="typename Vec::base_type",
            cpp_param_type="typename Vec::base_type",
            cpp_free_type="{base}",
            rust_owner_type="{owner}::BaseType",
            rust_param_type="{owner}::BaseType",
            rust_free_type="{base}",
            rust_concrete_type="{base}",
        ),
        SignatureKindCapability(
            "m",
            maskable_result=True,
            overload_token="mask",
            cpp_result_type="typename Vec::mask_type",
            cpp_param_type="typename Vec::mask_type",
            rust_owner_type="{owner}::MaskType",
            rust_param_type="{owner}::MaskType",
            rust_concrete_type="{register}",
        ),
        SignatureKindCapability(
            "im",
            maskable_result=True,
            cpp_result_type="typename Vec::imask_type",
            cpp_param_type="typename Vec::imask_type",
            rust_owner_type="{owner}::ImaskType",
            rust_param_type="{owner}::ImaskType",
            rust_concrete_type="{register}",
        ),
        SignatureKindCapability(
            "usize",
            requires_vector_axis=False,
            cpp_result_type="std::size_t",
            cpp_param_type="std::size_t",
            cpp_free_type="std::size_t",
            rust_owner_type="usize",
            rust_param_type="usize",
            rust_free_type="usize",
            rust_concrete_type="usize",
        ),
        SignatureKindCapability(
            "sImm",
            immediate_operand=True,
        ),
        SignatureKindCapability(
            "ptr",
            pointer_mutability="mutable",
            requires_vector_axis=False,
            overload_token="ptr",
            cpp_param_type="typename Vec::base_type *",
            cpp_free_type="{base}",
            rust_owner_type="*mut {owner}::BaseType",
            rust_param_type="*mut {owner}::BaseType",
            rust_free_type="{base}",
            rust_concrete_type="*mut {base}",
        ),
        SignatureKindCapability(
            "ptr+",
            pointer_mutability="mutable",
            requires_vector_axis=False,
            overload_token="ptr",
            cpp_param_type="typename Vec::base_type *",
            cpp_free_type="{base}",
            rust_owner_type="*mut {owner}::BaseType",
            rust_param_type="*mut {owner}::BaseType",
            rust_free_type="{base}",
            rust_concrete_type="*mut {base}",
        ),
        SignatureKindCapability(
            "cptr",
            pointer_mutability="const",
            requires_vector_axis=False,
            overload_token="const_ptr",
            cpp_param_type="typename Vec::base_type const *",
            cpp_free_type="const {base}",
            rust_owner_type="*const {owner}::BaseType",
            rust_param_type="*const {owner}::BaseType",
            rust_free_type="*const {base}",
            rust_concrete_type="*const {base}",
        ),
        SignatureKindCapability(
            "cptr+",
            pointer_mutability="const",
            requires_vector_axis=False,
            overload_token="const_ptr",
            cpp_param_type="typename Vec::base_type const *",
            cpp_free_type="const {base}",
            rust_owner_type="*const {owner}::BaseType",
            rust_param_type="*const {owner}::BaseType",
            rust_free_type="*const {base}",
            rust_concrete_type="*const {base}",
        ),
        SignatureKindCapability(
            "void",
            maskable_result=True,
            requires_vector_axis=False,
            cpp_result_type="void",
            cpp_free_type="void",
            rust_owner_type="()",
            rust_free_type="()",
            rust_concrete_type="()",
        ),
        SignatureKindCapability(
            "s[]",
            borrowed_parameter=True,
            scalable_deferred=True,
            overload_token="array",
            cpp_result_type="typename ::tsl::array_for<Vec>::type",
            cpp_param_type="typename ::tsl::array_param<Vec>::type",
            rust_owner_type="{owner}::Array",
            rust_param_type="&{owner}::Array",
            rust_concrete_type="{array}",
        ),
        SignatureKindCapability(
            LANE_LIST_KIND,
            borrowed_parameter=True,
            lane_list=True,
            scalable_deferred=True,
            overload_token="lane_list",
            cpp_param_type="typename ::tsl::array_param<Vec>::type",
            rust_owner_type="{owner}::Array",
            rust_param_type="&{owner}::Array",
            rust_concrete_type="{array}",
        ),
        SignatureKindCapability(
            "vt",
            overload_token="target_register",
            cpp_param_type="typename tsl::reg_param<{target_vector}>::type",
            rust_owner_type="{owner}::RegisterType",
            rust_param_type="{owner}::RegisterType",
            rust_concrete_type="{register}",
        ),
        SignatureKindCapability(
            "vidx",
            mask_deferred_param=True,
            index_vector=True,
            overload_token="index_register",
            cpp_param_type="typename tsl::reg_param<{index_type}>::type",
            rust_owner_type="{owner}::RegisterType",
            rust_param_type="{owner}::RegisterType",
            rust_concrete_type="{register}",
        ),
        SignatureKindCapability(
            "o",
            cpp_result_type="std::string &",
            cpp_param_type="std::string &",
            rust_owner_type="&mut String",
            rust_param_type="&mut String",
            rust_concrete_type="{base}",
        ),
    )
)


__all__ = (
    "DEFAULT_SIGNATURE_KINDS",
    "PointerMutability",
    "SignatureKindCapability",
    "SignatureKindCatalog",
)
