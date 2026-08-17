"""Backend-owned Rust benchmark runtime feature-detection strategies."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class RustBenchmarkDetectionStrategy:
    """Concrete Rust syntax for one source-selected detection strategy."""

    strategy_id: str
    target_arch: str
    feature_macro: str


RUST_BENCHMARK_DETECTION_STRATEGIES = MappingProxyType(
    {
        "x86_builtin": RustBenchmarkDetectionStrategy(
            strategy_id="x86_builtin",
            target_arch="x86_64",
            feature_macro="std::arch::is_x86_feature_detected",
        ),
    }
)
RUST_BENCHMARK_DETECTION_KINDS = frozenset(
    RUST_BENCHMARK_DETECTION_STRATEGIES
)


def rust_benchmark_detection_strategy(
    strategy_id: str,
) -> RustBenchmarkDetectionStrategy | None:
    return RUST_BENCHMARK_DETECTION_STRATEGIES.get(strategy_id)


__all__ = (
    "RUST_BENCHMARK_DETECTION_KINDS",
    "RustBenchmarkDetectionStrategy",
    "rust_benchmark_detection_strategy",
)
