"""Compiler-owned Rust benchmark code-generation contract."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RustBenchmarkCodegenContract:
    """Settings the generated Cargo benchmark profile and policy both name."""

    schema_version: int
    opt_level: int
    debug: bool
    debug_assertions: bool
    overflow_checks: bool
    lto: bool
    panic: str
    incremental: bool
    codegen_units: int

    @property
    def identity(self) -> str:
        return ";".join(
            (
                f"profile.bench:v{self.schema_version}",
                f"opt-level={self.opt_level}",
                f"debug={_toml_bool(self.debug)}",
                f"debug-assertions={_toml_bool(self.debug_assertions)}",
                f"overflow-checks={_toml_bool(self.overflow_checks)}",
                f"lto={_toml_bool(self.lto)}",
                f"panic={self.panic}",
                f"incremental={_toml_bool(self.incremental)}",
                f"codegen-units={self.codegen_units}",
            )
        )

    def render_cargo_profile(self) -> str:
        return "\n".join(
            (
                "[profile.bench]",
                f"opt-level = {self.opt_level}",
                f"debug = {_toml_bool(self.debug)}",
                f"debug-assertions = {_toml_bool(self.debug_assertions)}",
                f"overflow-checks = {_toml_bool(self.overflow_checks)}",
                f"lto = {_toml_bool(self.lto)}",
                f'panic = "{self.panic}"',
                f"incremental = {_toml_bool(self.incremental)}",
                f"codegen-units = {self.codegen_units}",
            )
        )


def _toml_bool(value: bool) -> str:
    return str(value).lower()


RUST_BENCHMARK_CODEGEN_CONTRACT = RustBenchmarkCodegenContract(
    schema_version=1,
    opt_level=3,
    debug=False,
    debug_assertions=False,
    overflow_checks=False,
    lto=False,
    panic="unwind",
    incremental=False,
    codegen_units=16,
)


__all__ = (
    "RUST_BENCHMARK_CODEGEN_CONTRACT",
    "RustBenchmarkCodegenContract",
)
