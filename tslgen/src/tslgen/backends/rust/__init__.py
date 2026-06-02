"""Rust backend emitter."""

from tslgen.backends.rust.backend import RustBackend
from tslgen.backends.rust.body_tokens import (
    RustBodyText,
    RustBodyTokenRenderResult,
    RustRenderedBodyTokens,
    render_rust_body_tokens_from_intrinsic_handoff,
)
from tslgen.backends.rust.intrinsic_calls import (
    RustArchitectureModule,
    RustIntrinsicCallRenderResult,
    RustIntrinsicCallText,
    RustRenderedIntrinsicCall,
    render_rust_intrinsic_invocation_call,
)

__all__ = [
    "RustArchitectureModule",
    "RustBodyText",
    "RustBodyTokenRenderResult",
    "RustBackend",
    "RustIntrinsicCallRenderResult",
    "RustIntrinsicCallText",
    "RustRenderedBodyTokens",
    "RustRenderedIntrinsicCall",
    "render_rust_body_tokens_from_intrinsic_handoff",
    "render_rust_intrinsic_invocation_call",
]
