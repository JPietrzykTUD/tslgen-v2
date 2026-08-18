"""Lane models: how a value test materializes lanes — compile-time-fixed vs runtime-scalable.

Every authored value test is one of a few shapes — a value result compared lane-for-lane, a
mask result verified as a predicate, a mask conversion — and each shape is the *same* code
regardless of whether the target is a fixed-width ``generic<N>`` (``N`` a compile-time
constant) or a scalable SVE vector (lane count known only at runtime). Only the codegen
*primitives* differ, along four axes:

1. how the SIMD type and lane count are spelled (``generic<N>`` + constant ``N`` vs the
   extension type + a runtime ``lanes`` variable);
2. how the call arguments are bound (vectors into an indexable ``register_type`` and masks as
   raw bitmask literals, vs vectors filled into a runtime-length ``std::vector`` + ``load`` and
   masks built from the extension's mask-from-bits expression);
3. how a value result is captured and compared (read the register directly over ``N`` lanes vs
   ``store`` into a runtime-length buffer and compare over ``lanes``);
4. how a mask result is verified (materialize a bit array + ``check_mask`` vs the extension's
   mask-check expression — an SVE predicate cannot be read as a flat bit array).

A :class:`LaneModel` encapsulates those four. The renderers (:func:`render_value_case`,
:func:`render_mask_case`, :func:`render_mask_conversion`) ask :func:`lane_model_for` and drive
the model, never branching on fixed-vs-scalable themselves. This collapses what used to be two
parallel renderer families (``_generic_*``/``_mask_*`` and ``_scalable_*``) into one renderer
per shape.

Tiling caveat (scalable only): the scalable model tiles the authored fixed-length pattern
across the runtime lane count with ``i % authored_lanes``. That identity holds *only for
lane-local (elementwise) ops* — output lane ``i`` must depend solely on input lane ``i``.
Compile-time indexed-lane cases use a distinct typed expectation: tile the input, then replace
the one global runtime lane named by the index. Other cross-lane ops (reduce, shuffle,
compress, conflict, iota) must not be routed through a tiled scalable case; the case planners
gate this on the corpus-declared ``cross_lane`` fact (see
``_case_scalable_common.tiling_is_safe``), never here.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from tslc.catalog.model import TestComparison
from tslc.value_tests.lane_math import runtime_tile_index
from tslc.value_tests.literals import cpp_literal, cpp_literal_list, token_truthy
from tslc.value_tests.model import ValueTestCasePlan
from tslc.value_tests.render_cpp_helpers import (
    append_call_args,
    append_runtime_vector_input,
    scalable_header,
    scalable_mask_check,
    scalable_mask_from_bits,
)


class LaneModel(ABC):
    """The fixed-vs-scalable codegen strategy shared by every value-test renderer."""

    @abstractmethod
    def open(self, case: ValueTestCasePlan) -> list[str]:
        """Open the function: signature, the ``Vec`` alias, and any lane-count binding."""

    @abstractmethod
    def bind_call_args(self, lines: list[str], case: ValueTestCasePlan) -> list[str]:
        """Bind every call argument (vectors, masks) per ``param_kinds``; return their names."""

    @abstractmethod
    def append_result_check(
        self, lines: list[str], case: ValueTestCasePlan, call: str
    ) -> None:
        """Capture the value result of ``call`` and emit the lane-for-lane comparison + return."""

    @abstractmethod
    def verify_mask(self, lines: list[str], case: ValueTestCasePlan) -> None:
        """Verify the mask predicate held in the local ``result`` and emit the return."""


class _FixedLaneModel(LaneModel):
    """Compile-time-fixed lanes: ``generic<N>``, register-indexed inputs, direct compare."""

    def open(self, case: ValueTestCasePlan) -> list[str]:
        lines = [
            f"int {case.function_name}() {{",
            f"  using Vec = tsl::simd<{case.base_spelling}, tsl::generic<{case.lanes}>>;",
        ]
        if "vidx" in case.invocation.param_kinds:
            index = case.index
            if index is None or index.base_spelling is None or index.lanes is None:
                raise ValueError("indexed C++ value test requires an index-vector layout")
            lines.append(
                f"  using Indices = tsl::simd<{index.base_spelling}, "
                f"tsl::generic<{index.lanes}>>;"
            )
        return lines

    def bind_call_args(self, lines: list[str], case: ValueTestCasePlan) -> list[str]:
        return append_call_args(lines, case)

    def append_result_check(
        self, lines: list[str], case: ValueTestCasePlan, call: str
    ) -> None:
        if case.invocation.result_kind == "m":
            bits = ", ".join("1" if token_truthy(v) else "0" for v in case.expectation.values)
            lines.append(f"  typename Vec::mask_type result = {call};")
            lines.append(f"  static const int expected[{case.lanes}] = {{{bits}}};")
            lines.append(
                f'  return tsl::test::check_mask("{case.case_name}", result, expected, '
                f"{case.lanes});"
            )
        else:
            expected = cpp_literal_list(case.expectation.values, case.type_tag)
            check = (
                "check_lanes_bitwise"
                if case.expectation.comparison is TestComparison.BITWISE
                else "check_lanes"
            )
            lines.append(f"  typename Vec::register_type result = {call};")
            lines.append(
                f"  static const {case.base_spelling} expected[{case.lanes}] = {{{expected}}};"
            )
            lines.append(
                f"  return tsl::test::{check}<{case.base_spelling}>("
                f'"{case.case_name}", result, expected, {case.lanes});'
            )

    def verify_mask(self, lines: list[str], case: ValueTestCasePlan) -> None:
        expected_int = int(case.expectation.values[0])
        bits = ", ".join("1" if (expected_int >> i) & 1 else "0" for i in range(case.lanes))
        lines.append(f"  static const int expected[{case.lanes}] = {{{bits}}};")
        lines.append(
            f'  return tsl::test::check_mask("{case.case_name}", result, expected, {case.lanes});'
        )


class _ScalableLaneModel(LaneModel):
    """Runtime-length lanes (SVE): runtime ``lanes``, load/store buffers, tiled compare."""

    def open(self, case: ValueTestCasePlan) -> list[str]:
        # Only the facts the header itself spells are required here; load/store/mask facts are
        # validated by the steps that consume them (bind_call_args, append_result_check, ...),
        # since mask-logic/constant/conversion cases legitimately have no vector I/O.
        if case.scalable is None:
            raise ValueError("scalable C++ value test requires extension and lanes facts")
        return scalable_header(case)

    def bind_call_args(self, lines: list[str], case: ValueTestCasePlan) -> list[str]:
        scalable = case.scalable
        assert scalable is not None
        args: list[str] = []
        vector_index = 0
        mask_index = 0
        scalar_index = 0
        for kind in case.invocation.param_kinds:
            if kind == "v":
                args.append(append_runtime_vector_input(lines, case, vector_index))
                vector_index += 1
            elif kind == "m":
                lines.append(
                    f"  typename Vec::mask_type m{mask_index} = "
                    f"{scalable_mask_from_bits(case, mask_index)};"
                )
                args.append(f"m{mask_index}")
                mask_index += 1
            elif kind == "sImm":
                continue
            elif kind == "s":
                value = cpp_literal(case.inputs.scalars[scalar_index], case.type_tag)
                lines.append(f"  {case.base_spelling} s{scalar_index} = {value};")
                args.append(f"s{scalar_index}")
                scalar_index += 1
            else:
                raise ValueError(
                    f"scalable value test does not support argument kind {kind!r}"
                )
        return args

    def append_result_check(
        self, lines: list[str], case: ValueTestCasePlan, call: str
    ) -> None:
        if case.invocation.result_kind == "m":
            raise ValueError(
                "scalable value result cannot be a mask; use render_mask_case"
            )
        scalable = case.scalable
        if scalable is None or scalable.store_name is None:
            raise ValueError("scalable value result requires a store fact")
        expected = cpp_literal_list(case.expectation.values, case.type_tag)
        check = (
            "check_lanes_bitwise"
            if case.expectation.comparison is TestComparison.BITWISE
            else "check_lanes"
        )
        lines.extend(
            [
                f"  static const {case.base_spelling} authored_expected[{case.lanes}] = "
                f"{{{expected}}};",
                f"  std::vector<{case.base_spelling}> expected(lanes);",
                f"  std::vector<{case.base_spelling}> actual(lanes);",
            ]
        )
        if case.expectation.scalable_layout == "indexed_lane":
            index = case.index
            if (
                index is None
                or index.value is None
                or len(case.inputs.vectors) != 1
            ):
                raise ValueError(
                    "indexed-lane scalable expectation requires one vector input "
                    "and an index value"
                )
            lines.extend(
                [
                    f"  for (std::size_t i = 0; i < lanes; ++i) expected[i] = "
                    f"authored0[{runtime_tile_index('i', case.lanes)}];",
                    f"  if ({index.value} < lanes) "
                    f"expected[{index.value}] = authored_expected[{index.value}];",
                ]
            )
        else:
            lines.append(
                f"  for (std::size_t i = 0; i < lanes; ++i) expected[i] = "
                f"authored_expected[{runtime_tile_index('i', case.lanes)}];"
            )
        lines.extend(
            [
                f"  typename Vec::register_type result = {call};",
                f"  tsl::{scalable.store_name}<Vec, false>(actual.data(), result);",
                f"  return tsl::test::{check}<{case.base_spelling}>("
                f'"{case.case_name}", actual.data(), expected.data(), lanes);',
            ]
        )

    def verify_mask(self, lines: list[str], case: ValueTestCasePlan) -> None:
        scalable = case.scalable
        if scalable is None or scalable.mask_check_template is None:
            raise ValueError("scalable mask result requires a mask-check fact")
        lines.append(f"  return {scalable_mask_check(case)};")


_FIXED = _FixedLaneModel()
_SCALABLE = _ScalableLaneModel()


def lane_model_for(case: ValueTestCasePlan) -> LaneModel:
    """Pick the lane model from the case's data: scalable iff a runtime lane count is set."""

    return _SCALABLE if case.scalable is not None else _FIXED


def render_value_case(case: ValueTestCasePlan) -> str:
    """Render a value-result case (golden or masked) for either lane model.

    The mask, if any, is just another call argument — ``bind_call_args`` interleaves it at its
    ``m`` parameter position, so golden and masked share this one skeleton.
    """

    model = lane_model_for(case)
    lines = model.open(case)
    args = model.bind_call_args(lines, case)
    template_args = ["Vec"]
    if "vidx" in case.invocation.param_kinds:
        template_args.append("Indices")
    if case.index is not None and case.index.value is not None:
        template_args.append(case.index.value)
    if case.invocation.immediate is not None:
        template_args.append(case.invocation.immediate)
    template_args.extend(case.invocation.generic_defaults)
    call = f"tsl::{case.call_name}<{', '.join(template_args)}>({', '.join(args)})"
    model.append_result_check(lines, case, call)
    lines.append("}")
    return "\n".join(lines)


def render_mask_case(case: ValueTestCasePlan) -> str:
    """Render a mask-result case (comparison, mask logic, masked comparison, mask constant)."""

    model = lane_model_for(case)
    lines = model.open(case)
    args = model.bind_call_args(lines, case)
    call = f"tsl::{case.call_name}<Vec>({', '.join(args)})"
    lines.append(f"  typename Vec::mask_type result = {call};")
    model.verify_mask(lines, case)
    lines.append("}")
    return "\n".join(lines)


def render_mask_conversion(case: ValueTestCasePlan) -> str:
    """Render a mask<->imask conversion: a typed input and a typed result, verified as a mask."""

    model = lane_model_for(case)
    scalable = case.scalable
    assert scalable is not None
    lines = model.open(case)
    input_type = (
        "typename Vec::mask_type" if case.invocation.param_kinds == ("m",) else "typename Vec::imask_type"
    )
    result_type = (
        "typename Vec::mask_type" if case.invocation.result_kind == "m" else "typename Vec::imask_type"
    )
    lines.append(f"  {input_type} input = {scalable_mask_from_bits(case, 0)};")
    lines.append(f"  {result_type} result = tsl::{case.call_name}<Vec>(input);")
    model.verify_mask(lines, case)
    lines.append("}")
    return "\n".join(lines)


__all__ = [
    "LaneModel",
    "lane_model_for",
    "render_mask_case",
    "render_mask_conversion",
    "render_value_case",
]
