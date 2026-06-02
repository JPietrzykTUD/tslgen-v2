"""Rust intrinsic call rendering over assembled backend invocation values."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import NewType

from tslgen.backends.intrinsic_invocations import (
    BackendAssembledIntrinsicInvocation,
    BackendComposedIntrinsicInvocation,
    BackendDirectIntrinsicInvocation,
    BackendIntrinsicInvocationImmediate,
)
from tslgen.core.diagnostics import Diagnostic, SourceLocation

RustIntrinsicCallText = NewType("RustIntrinsicCallText", str)

_RUST_MODULE_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")


@dataclass(frozen=True, slots=True)
class RustArchitectureModule:
    name: str

    def __str__(self) -> str:
        return self.name


@dataclass(frozen=True, slots=True)
class RustRenderedIntrinsicCall:
    invocation: BackendAssembledIntrinsicInvocation
    architecture_module: RustArchitectureModule
    call_text: RustIntrinsicCallText
    immediates: tuple[BackendIntrinsicInvocationImmediate, ...]
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class RustIntrinsicCallRenderResult:
    call: RustRenderedIntrinsicCall | None
    diagnostics: tuple[Diagnostic, ...] = ()


def render_rust_intrinsic_invocation_call(
    invocation: object,
    architecture_module: RustArchitectureModule | None,
) -> RustIntrinsicCallRenderResult:
    """Render an assembled intrinsic invocation as one Rust call expression."""

    if not isinstance(
        invocation,
        BackendDirectIntrinsicInvocation | BackendComposedIntrinsicInvocation,
    ):
        return RustIntrinsicCallRenderResult(
            call=None,
            diagnostics=(_unsupported_invocation_diagnostic(invocation),),
        )

    if str(invocation.backend) != "rust":
        return RustIntrinsicCallRenderResult(
            call=None,
            diagnostics=(_unsupported_backend_diagnostic(invocation),),
        )

    architecture_diagnostic = _architecture_module_diagnostic(
        architecture_module,
        invocation.source,
    )
    if architecture_diagnostic is not None:
        return RustIntrinsicCallRenderResult(
            call=None,
            diagnostics=(architecture_diagnostic,),
        )

    assert isinstance(architecture_module, RustArchitectureModule)
    return RustIntrinsicCallRenderResult(
        call=RustRenderedIntrinsicCall(
            invocation=invocation,
            architecture_module=architecture_module,
            call_text=RustIntrinsicCallText(
                "core::arch::"
                f"{architecture_module.name}::"
                f"{str(invocation.intrinsic_name)}"
                f"({str(invocation.arguments.text)})"
            ),
            immediates=(
                invocation.immediates
                if isinstance(invocation, BackendComposedIntrinsicInvocation)
                else ()
            ),
            source=invocation.source,
        ),
        diagnostics=(),
    )


def _architecture_module_diagnostic(
    architecture_module: object | None,
    location: SourceLocation,
) -> Diagnostic | None:
    if architecture_module is None:
        return Diagnostic(
            severity="error",
            code="TSL-RUST-INTRINSIC-CALL-MISSING-ARCHITECTURE-MODULE",
            message=(
                "Rust intrinsic call rendering requires an explicit typed "
                "architecture module such as 'x86_64' or 'aarch64'"
            ),
            location=location,
        )
    if not isinstance(architecture_module, RustArchitectureModule):
        return Diagnostic(
            severity="error",
            code="TSL-RUST-INTRINSIC-CALL-UNSUPPORTED-ARCHITECTURE-MODULE",
            message=(
                "Rust intrinsic call rendering requires RustArchitectureModule; "
                f"got {type(architecture_module).__name__!r}"
            ),
            location=location,
        )
    if not isinstance(architecture_module.name, str):
        return Diagnostic(
            severity="error",
            code="TSL-RUST-INTRINSIC-CALL-INVALID-ARCHITECTURE-MODULE",
            message=(
                "Rust architecture module must be one Rust module segment; "
                f"got {type(architecture_module.name).__name__!r}"
            ),
            location=location,
        )
    if _RUST_MODULE_RE.fullmatch(architecture_module.name) is None:
        return Diagnostic(
            severity="error",
            code="TSL-RUST-INTRINSIC-CALL-INVALID-ARCHITECTURE-MODULE",
            message=(
                "Rust architecture module must be one Rust module segment; "
                f"got {architecture_module.name!r}"
            ),
            location=location,
        )
    return None


def _unsupported_backend_diagnostic(
    invocation: BackendAssembledIntrinsicInvocation,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-RUST-INTRINSIC-CALL-UNSUPPORTED-BACKEND",
        message=(
            "Rust intrinsic call rendering supports only backend 'rust'; got "
            f"{str(invocation.backend)!r}"
        ),
        location=invocation.source,
    )


def _unsupported_invocation_diagnostic(object_value: object) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-RUST-INTRINSIC-CALL-UNSUPPORTED-INVOCATION",
        message=(
            "Rust intrinsic call rendering requires an assembled direct or "
            f"composed intrinsic invocation; got {type(object_value).__name__!r}"
        ),
        location=None,
    )
