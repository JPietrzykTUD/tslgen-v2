"""Rust backend emitter."""

from tslgen.backends.rust.backend import RustBackend
from tslgen.backends.rust.intrinsic_calls import (
    RustArchitectureModule,
    RustIntrinsicCallRenderResult,
    RustIntrinsicCallText,
    RustRenderedIntrinsicCall,
    render_rust_intrinsic_invocation_call,
)

__all__ = [
    "RustArchitectureModule",
    "RustBackend",
    "RustIntrinsicCallRenderResult",
    "RustIntrinsicCallText",
    "RustRenderedIntrinsicCall",
    "render_rust_intrinsic_invocation_call",
]
