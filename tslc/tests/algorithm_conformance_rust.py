"""Rust compile-witness adapter for the test-owned algorithm inventory."""

from __future__ import annotations

from collections.abc import Sequence

from tslc.backend.rust_algorithm_contracts import (
    rust_profile_scaled_checked_algorithm_declarations,
)
from tslc.backend.rust_algorithm_public_declarations import (
    rust_profile_algorithm_public_declarations,
)
from tslc.backend.rust_public_declarations import RustPublicDeclaration
from tslc.backend.public_declarations import PublicDeclarationStability

from algorithm_conformance import AlgorithmBehaviorCase


_REACHABILITY = ("crate", "profile", "selection:conformance", "algo")


def rust_algorithm_compile_declarations() -> tuple[RustPublicDeclaration, ...]:
    declarations = (
        *rust_profile_algorithm_public_declarations(_REACHABILITY),
        *rust_profile_scaled_checked_algorithm_declarations(_REACHABILITY),
    )
    return tuple(
        declaration
        for declaration in declarations
        if declaration.stability is PublicDeclarationStability.STABLE
    )


def rust_algorithm_compile_identities() -> frozenset[str]:
    return frozenset(
        declaration.identity for declaration in rust_algorithm_compile_declarations()
    )


def _effective_declaration(
    declaration: RustPublicDeclaration,
    by_name: dict[str, RustPublicDeclaration],
) -> RustPublicDeclaration:
    if declaration.reexport_target is None:
        return declaration
    return by_name[declaration.reexport_target.rsplit("::", 1)[-1]]


def _generic_arguments(declaration: RustPublicDeclaration) -> str:
    arguments: list[str] = []
    for parameter in declaration.generic_parameters:
        if parameter.name == "SCALE":
            arguments.append("4")
        elif parameter.name == "Layout":
            arguments.append("profile::algo::mask_layout::Bytes")
        elif parameter.name == "T":
            arguments.append("i32")
        elif parameter.name in {"Policy", "Op"}:
            arguments.append("_")
        else:
            raise ValueError(
                f"unsupported Rust conformance generic {parameter.name!r}"
            )
    return f"::<{', '.join(arguments)}>" if arguments else ""


def _argument(declaration: RustPublicDeclaration, name: str, spelling: str) -> str:
    pointer = spelling.startswith("*const") or spelling.startswith("*mut")
    mutable = spelling.startswith("*mut") or spelling.startswith("&mut")
    if name == "policy":
        return "policy"
    if name == "op":
        return "&mut witness"
    if name in {"count", "selected_count"}:
        return "0"
    if name in {"data", "input", "left", "right"}:
        value = "input" if name in {"data", "input"} else name
        if pointer:
            return f"{value}.as_ptr()"
        return f"&{value}"
    if name == "output":
        return "output.as_mut_ptr()" if pointer else "&mut output"
    if name in {"input_indices", "indices"}:
        value = "output_indices" if mutable else "selected_indices"
        if pointer:
            suffix = "as_mut_ptr()" if mutable else "as_ptr()"
            return f"{value}.{suffix}"
        return f"&mut {value}" if mutable else f"&{value}"
    if name == "output_indices":
        return (
            "output_indices.as_mut_ptr()"
            if pointer
            else "&mut output_indices"
        )
    if name == "masks":
        value = (
            "byte_masks"
            if "_mask_layout" in declaration.name
            else "integral_masks"
        )
        if pointer:
            suffix = "as_mut_ptr()" if mutable else "as_ptr()"
            return f"{value}.{suffix}"
        return f"&mut {value}" if mutable else f"&{value}"
    raise ValueError(
        f"unsupported Rust conformance parameter {declaration.identity}:{name}"
    )


def _render_call(
    declaration: RustPublicDeclaration,
    by_name: dict[str, RustPublicDeclaration],
) -> str:
    effective = _effective_declaration(declaration, by_name)
    arguments = ", ".join(
        _argument(effective, parameter.name, str(parameter.type_spelling))
        for parameter in effective.parameters
    )
    call = (
        f"profile::algo::{declaration.name}"
        f"{_generic_arguments(effective)}({arguments})"
    )
    expression = f"unsafe {{ {call} }}" if effective.unsafe else call
    return (
        f"    // witness: {declaration.identity}\n"
        f"    let _ = {expression};"
    )


def render_rust_algorithm_compile_witness(
    declarations: Sequence[RustPublicDeclaration] | None = None,
) -> tuple[str, frozenset[str]]:
    all_declarations = rust_algorithm_compile_declarations()
    by_name = {declaration.name: declaration for declaration in all_declarations}
    selected = tuple(
        all_declarations if declarations is None else declarations
    )
    calls = "\n".join(
        _render_call(declaration, by_name) for declaration in selected
    )
    source = f"""use tsl::profile;
use tsl::tsl_algorithm::{{MaskLayout, VectorFor}};
use tsl::tsl_core::StaticSimdVector;

struct Witness;

impl<V: StaticSimdVector> profile::algo::UnaryKernel<V> for Witness {{
    fn apply(&mut self, _: V::RegisterType) -> V::RegisterType {{ unreachable!() }}
}}

impl<V: StaticSimdVector> profile::algo::BinaryKernel<V> for Witness {{
    fn apply(&mut self, _: V::RegisterType, _: V::RegisterType) -> V::RegisterType {{
        unreachable!()
    }}
}}

impl<V: StaticSimdVector> profile::algo::UnaryPredicateKernel<V> for Witness {{
    fn test(&mut self, _: V::RegisterType) -> V::MaskType {{ unreachable!() }}
}}

impl<V: StaticSimdVector> profile::algo::BinaryPredicateKernel<V> for Witness {{
    fn test(&mut self, _: V::RegisterType, _: V::RegisterType) -> V::MaskType {{
        unreachable!()
    }}
}}

impl<V: StaticSimdVector> profile::algo::MaskedUnaryKernel<V> for Witness {{
    fn apply(&mut self, _: V::MaskType, _: V::RegisterType) -> V::RegisterType {{
        unreachable!()
    }}
}}

impl<V: StaticSimdVector> profile::algo::MaskedBinaryKernel<V> for Witness {{
    fn apply(
        &mut self,
        _: V::MaskType,
        _: V::RegisterType,
        _: V::RegisterType,
    ) -> V::RegisterType {{
        unreachable!()
    }}
}}

impl<V: StaticSimdVector> profile::algo::UnaryConsumeKernel<V> for Witness {{
    fn consume(&mut self, _: V::RegisterType) {{}}
}}

impl<V: StaticSimdVector> profile::algo::BinaryConsumeKernel<V> for Witness {{
    fn consume(&mut self, _: V::RegisterType, _: V::RegisterType) {{}}
}}

impl<V: StaticSimdVector> profile::algo::MaskedUnaryConsumeKernel<V> for Witness {{
    fn consume(&mut self, _: V::MaskType, _: V::RegisterType) {{}}
}}

impl<V: StaticSimdVector> profile::algo::MaskedBinaryConsumeKernel<V> for Witness {{
    fn consume(&mut self, _: V::MaskType, _: V::RegisterType, _: V::RegisterType) {{}}
}}

impl<V: StaticSimdVector> profile::algo::UnaryAggregateKernel<V> for Witness {{
    type Output = i64;
    fn accumulate(&mut self, _: V::RegisterType) {{}}
    fn finalize(&self) -> Self::Output {{ 0 }}
}}

impl<V: StaticSimdVector> profile::algo::BinaryAggregateKernel<V> for Witness {{
    type Output = i64;
    fn accumulate(&mut self, _: V::RegisterType, _: V::RegisterType) {{}}
    fn finalize(&self) -> Self::Output {{ 0 }}
}}

impl<V: StaticSimdVector> profile::algo::MaskedUnaryAggregateKernel<V> for Witness {{
    type Output = i64;
    fn accumulate(&mut self, _: V::MaskType, _: V::RegisterType) {{}}
    fn finalize(&self) -> Self::Output {{ 0 }}
}}

impl<V: StaticSimdVector> profile::algo::MaskedBinaryAggregateKernel<V> for Witness {{
    type Output = i64;
    fn accumulate(&mut self, _: V::MaskType, _: V::RegisterType, _: V::RegisterType) {{}}
    fn finalize(&self) -> Self::Output {{ 0 }}
}}

impl<V: StaticSimdVector> profile::algo::ChunkKernel<V> for Witness {{
    unsafe fn apply(&mut self, _: *const V::BaseType, _: usize, _: usize) {{}}
}}

fn main() {{
    type Policy = tsl::dataparallel::Generic<4>;
    type Vec4 = <Policy as VectorFor<profile::algo::Profile, i32>>::Vec;
    type IntegralMask = <profile::algo::mask_layout::Integral as
        MaskLayout<profile::algo::Profile, Vec4>>::Storage;
    let policy = tsl::dataparallel::generic::<4>();
    let input = Vec::<i32>::new();
    let left = Vec::<i32>::new();
    let right = Vec::<i32>::new();
    let mut output = Vec::<i32>::new();
    let selected_indices = Vec::<usize>::new();
    let mut output_indices = Vec::<usize>::new();
    let mut integral_masks = Vec::<IntegralMask>::new();
    let mut byte_masks = Vec::<u8>::new();
    let mut witness = Witness;
{calls}
}}
"""
    return source, frozenset(declaration.identity for declaration in selected)


def render_rust_algorithm_behavior(case: AlgorithmBehaviorCase) -> str:
    values = ", ".join(str(value) for value in case.input_values)
    lengths = ", ".join(str(length) for length in case.lengths)
    return f"""use tsl::profile;
use tsl::tsl_core::StaticSimdVector;

struct UnaryIdentity {{ calls: usize }}

impl<V: StaticSimdVector> profile::algo::UnaryKernel<V> for UnaryIdentity {{
    fn apply(&mut self, value: V::RegisterType) -> V::RegisterType {{
        self.calls += 1;
        value
    }}
}}

struct BinaryIdentity {{ calls: usize }}

impl<V: StaticSimdVector> profile::algo::BinaryKernel<V> for BinaryIdentity {{
    fn apply(&mut self, left: V::RegisterType, _: V::RegisterType) -> V::RegisterType {{
        self.calls += 1;
        left
    }}
}}

fn print_values(values: &[i32]) -> String {{
    values
        .iter()
        .map(i32::to_string)
        .collect::<Vec<_>>()
        .join(",")
}}

fn main() {{
    let policy = tsl::dataparallel::generic::<4>();
    let input = vec![{values}];
    let lengths = [{lengths}];
    let mut output = vec![{case.sentinel}; input.len()];
    let mut unary = UnaryIdentity {{ calls: 0 }};
    for length in lengths {{
        let prefix = input[..length].to_vec();
        let mut produced = vec![{case.sentinel}; length];
        profile::algo::transform_unary_checked(
            policy,
            &mut unary,
            &prefix,
            &mut produced,
        )
        .expect("shared transform conformance");
        assert_eq!(produced, prefix);
        if length == input.len() {{
            output = produced;
        }}
    }}

    let mut alias = input.clone();
    let alias_ptr = alias.as_mut_ptr();
    unsafe {{
        profile::algo::transform_unary(
            policy,
            &mut unary,
            alias_ptr,
            alias_ptr,
            alias.len(),
        )
    }};

    let short_right = &input[..input.len() - 1];
    let mut failure_output = vec![{case.sentinel}; input.len()];
    let mut binary = BinaryIdentity {{ calls: 0 }};
    let failure = profile::algo::transform_binary_checked(
        policy,
        &mut binary,
        &input,
        short_right,
        &mut failure_output,
    )
    .expect_err("short secondary input must fail");
    let failure_name = match failure {{
        tsl::PreconditionError::InsufficientInput => "insufficient_input",
        _ => "unexpected",
    }};
    let unchanged = failure_output.iter().all(|value| *value == {case.sentinel});

    print!(
        "values={{}};alias={{}};failure={{}};unchanged={{}};failure_calls={{}}",
        print_values(&output),
        print_values(&alias),
        failure_name,
        unchanged,
        binary.calls,
    );
}}
"""


__all__ = (
    "render_rust_algorithm_behavior",
    "render_rust_algorithm_compile_witness",
    "rust_algorithm_compile_declarations",
    "rust_algorithm_compile_identities",
)
