"""Typed capabilities for supported primitive signature kinds."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal

from tslc.catalog.signatures import LANE_LIST_KIND

PointerMutability = Literal["const", "mutable"]


@dataclass(frozen=True, slots=True)
class SignatureKindCapability:
    """Compiler behavior for one signature kind token.

    The token itself is source-visible. This model owns only language-neutral
    semantics; target-language type projections belong to each backend.
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
        ),
        SignatureKindCapability("s"),
        SignatureKindCapability(
            "m",
            maskable_result=True,
            overload_token="mask",
        ),
        SignatureKindCapability("im", maskable_result=True),
        SignatureKindCapability(
            "usize",
            requires_vector_axis=False,
        ),
        SignatureKindCapability("sImm", immediate_operand=True),
        SignatureKindCapability(
            "ptr",
            pointer_mutability="mutable",
            requires_vector_axis=False,
            overload_token="ptr",
        ),
        SignatureKindCapability(
            "ptr+",
            pointer_mutability="mutable",
            requires_vector_axis=False,
            overload_token="ptr",
        ),
        SignatureKindCapability(
            "cptr",
            pointer_mutability="const",
            requires_vector_axis=False,
            overload_token="const_ptr",
        ),
        SignatureKindCapability(
            "cptr+",
            pointer_mutability="const",
            requires_vector_axis=False,
            overload_token="const_ptr",
        ),
        SignatureKindCapability(
            "void",
            maskable_result=True,
            requires_vector_axis=False,
        ),
        SignatureKindCapability(
            "s[]",
            borrowed_parameter=True,
            scalable_deferred=True,
            overload_token="array",
        ),
        SignatureKindCapability(
            LANE_LIST_KIND,
            borrowed_parameter=True,
            lane_list=True,
            scalable_deferred=True,
            overload_token="lane_list",
        ),
        SignatureKindCapability("vt", overload_token="target_register"),
        SignatureKindCapability(
            "vidx",
            index_vector=True,
            overload_token="index_register",
        ),
        SignatureKindCapability("o"),
    )
)


__all__ = (
    "DEFAULT_SIGNATURE_KINDS",
    "PointerMutability",
    "SignatureKindCapability",
    "SignatureKindCatalog",
)
