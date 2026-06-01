"""C++ intrinsic call rendering over assembled backend invocation values."""

from __future__ import annotations

from dataclasses import dataclass
from typing import NewType

from tslgen.backends.intrinsic_invocations import (
    BackendAssembledIntrinsicInvocation,
    BackendComposedIntrinsicInvocation,
    BackendDirectIntrinsicInvocation,
    BackendIntrinsicInvocationImmediate,
)
from tslgen.core.diagnostics import Diagnostic, SourceLocation

CppIntrinsicCallText = NewType("CppIntrinsicCallText", str)


@dataclass(frozen=True, slots=True)
class CppRenderedIntrinsicCall:
    invocation: BackendAssembledIntrinsicInvocation
    call_text: CppIntrinsicCallText
    immediates: tuple[BackendIntrinsicInvocationImmediate, ...]
    source: SourceLocation


@dataclass(frozen=True, slots=True)
class CppIntrinsicCallRenderResult:
    call: CppRenderedIntrinsicCall | None
    diagnostics: tuple[Diagnostic, ...] = ()


def render_cpp_intrinsic_invocation_call(
    invocation: BackendAssembledIntrinsicInvocation,
) -> CppIntrinsicCallRenderResult:
    """Render an assembled intrinsic invocation as one C++ call expression."""

    if not isinstance(
        invocation,
        BackendDirectIntrinsicInvocation | BackendComposedIntrinsicInvocation,
    ):
        return CppIntrinsicCallRenderResult(
            call=None,
            diagnostics=(_unsupported_invocation_diagnostic(invocation),),
        )

    if str(invocation.backend) != "cpp":
        return CppIntrinsicCallRenderResult(
            call=None,
            diagnostics=(_unsupported_backend_diagnostic(invocation),),
        )

    return CppIntrinsicCallRenderResult(
        call=CppRenderedIntrinsicCall(
            invocation=invocation,
            call_text=CppIntrinsicCallText(
                f"{str(invocation.intrinsic_name)}({str(invocation.arguments.text)})",
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


def _unsupported_backend_diagnostic(
    invocation: BackendAssembledIntrinsicInvocation,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-CPP-INTRINSIC-CALL-UNSUPPORTED-BACKEND",
        message=(
            "C++ intrinsic call rendering supports only backend 'cpp'; got "
            f"{str(invocation.backend)!r}"
        ),
        location=invocation.source,
    )


def _unsupported_invocation_diagnostic(object_value: object) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-CPP-INTRINSIC-CALL-UNSUPPORTED-INVOCATION",
        message=(
            "C++ intrinsic call rendering requires an assembled direct or "
            f"composed intrinsic invocation; got {type(object_value).__name__!r}"
        ),
        location=None,
    )
