"""Identity-based recursive flattening for parsed PIVOT bodies."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from tslc.catalog.machine_profiles import MachineProfile
from tslc.diagnostics import SourceSpan
from tslc.lower.lowerer import LoweredSpecialization
from tslc.select.selector import SelectedImplementation
from tslc_pivot.body_ir import (
    PivotBindingId,
    PivotBodyBuildResult,
    PivotCall,
    PivotFixedCall,
)
from tslc_pivot.model import PivotLanguage
from tslc_pivot.target_expression import (
    PivotBindingReference,
    PivotDelimiterGroup,
    PivotExpressionNode,
    PivotParsedBody,
    PivotParsedCall,
    PivotParsedExpression,
    PivotParsedFixedCall,
    PivotTargetName,
    PivotTargetParseError,
    PivotToken,
    PivotTokenKind,
    is_simple_target_value,
    normalize_target_text,
    parse_pivot_body,
)


@dataclass(frozen=True, slots=True)
class PivotInlineSlot:
    specialization: LoweredSpecialization
    body: PivotBodyBuildResult


@dataclass(frozen=True, slots=True)
class PivotEmission:
    direct: tuple[str, ...]
    specialization: LoweredSpecialization
    body_trace: tuple[PivotBodyBuildResult, ...]


@dataclass(frozen=True, slots=True)
class PivotRenderedExpression:
    text: str

    def __post_init__(self) -> None:
        if not self.text:
            raise ValueError("a rendered PIVOT expression cannot be empty")

    def as_binding_value(self) -> PivotRenderedExpression:
        if is_simple_target_value(self.text):
            return self
        return PivotRenderedExpression(f"({self.text})")


@dataclass(slots=True)
class PivotNameAllocator:
    next_value: int = 0

    def allocate(self, role: str) -> str:
        value = f"__pivot_{role}_{self.next_value}"
        self.next_value += 1
        return value


class PivotInliningError(ValueError):
    def __init__(
        self,
        code: str,
        message: str,
        source: SourceSpan | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.source = source


type LoadInlineSlot = Callable[[SelectedImplementation], PivotInlineSlot]
type ResolveInlineCall = Callable[
    [MachineProfile, SelectedImplementation, PivotCall, int],
    SelectedImplementation,
]
type SlotIdentity = Callable[[SelectedImplementation], tuple[object, ...]]
type RenderInlineFixedCall = Callable[
    [PivotFixedCall, tuple[str, ...]],
    str,
]


class PivotInliner:
    """Flatten retained calls and lexical bindings without rewriting text."""

    def __init__(
        self,
        language: PivotLanguage,
        *,
        load_slot: LoadInlineSlot,
        resolve_call: ResolveInlineCall,
        slot_identity: SlotIdentity,
        render_fixed_call: RenderInlineFixedCall,
    ) -> None:
        self.language = language
        self._load_slot = load_slot
        self._resolve_call = resolve_call
        self._slot_identity = slot_identity
        self._render_fixed_call_text = render_fixed_call
        self._parsed: dict[tuple[object, ...], PivotParsedBody | PivotInliningError] = {}

    def emit(
        self,
        profile: MachineProfile,
        slot: SelectedImplementation,
        actual_args: tuple[str, ...],
        *,
        destination: str,
        declare_destination: bool,
    ) -> PivotEmission:
        allocator = PivotNameAllocator()
        trace: list[PivotBodyBuildResult] = []
        direct, specialization = self._emit_slot(
            profile,
            slot,
            tuple(PivotRenderedExpression(value) for value in actual_args),
            destination=destination,
            declare_destination=declare_destination,
            stack=(),
            allocator=allocator,
            trace=trace,
        )
        return PivotEmission(direct, specialization, tuple(trace))

    def emit_retained_body(
        self,
        profile: MachineProfile,
        slot: SelectedImplementation,
        retained: PivotBodyBuildResult,
        specialization: LoweredSpecialization,
        actual_args: tuple[str, ...],
        *,
        destination: str,
        declare_destination: bool,
    ) -> PivotEmission:
        """Render a PIVOT-owned synthetic body through the same typed renderer."""

        key = ("synthetic", *self._slot_identity(slot))
        body = self._parsed_body(key, retained)
        if body.statements:
            raise PivotInliningError(
                "TSL-PIVOT-SYNTHETIC-STATEMENTS",
                "a synthetic PIVOT wrapper cannot contain local statements",
                body.source,
            )
        if len(actual_args) != len(body.parameters):
            raise PivotInliningError(
                "TSL-PIVOT-CALL-ARITY",
                f"synthetic wrapper supplies {len(actual_args)} arguments but "
                f"expects {len(body.parameters)}",
                body.source,
            )
        environment = {
            binding.identity: PivotRenderedExpression(argument).as_binding_value()
            for binding, argument in zip(body.parameters, actual_args)
        }
        allocator = PivotNameAllocator()
        trace = [retained]
        prepended, result = self._render_expression(
            body.result,
            environment,
            profile,
            slot,
            (key,),
            allocator,
            trace,
            return_value=True,
        )
        direct = [*prepended]
        if declare_destination:
            direct.append(
                f"{_destination_prefix(self.language)} {destination} = {result.text};"
            )
        else:
            direct.append(f"{destination} = {result.text};")
        return PivotEmission(
            tuple(direct),
            specialization,
            tuple(trace),
        )

    def _emit_slot(
        self,
        profile: MachineProfile,
        slot: SelectedImplementation,
        actual_args: tuple[PivotRenderedExpression, ...],
        *,
        destination: str,
        declare_destination: bool,
        stack: tuple[tuple[object, ...], ...],
        allocator: PivotNameAllocator,
        trace: list[PivotBodyBuildResult],
    ) -> tuple[tuple[str, ...], LoweredSpecialization]:
        key = self._slot_identity(slot)
        if key in stack:
            cycle = " -> ".join(str(item[0]) for item in (*stack, key))
            raise PivotInliningError(
                "TSL-PIVOT-RECURSIVE-CALL",
                f"recursive primitive-call cycle cannot be inlined: {cycle}",
                slot.implementation.body_source,
            )

        loaded = self._load_slot(slot)
        body = self._parsed_body(key, loaded.body)
        if len(actual_args) != len(body.parameters):
            raise PivotInliningError(
                "TSL-PIVOT-CALL-ARITY",
                f"call supplies {len(actual_args)} arguments but "
                f"{slot.primitive.name!r} expects {len(body.parameters)}",
                slot.implementation.body_source,
            )
        trace.append(loaded.body)

        local_names = {
            statement.binding.identity: allocator.allocate("local")
            for statement in body.statements
        }
        environment = {
            binding.identity: argument.as_binding_value()
            for binding, argument in zip(body.parameters, actual_args)
        }
        output: list[str] = []
        active_stack = (*stack, key)
        for statement in body.statements:
            prepended, initializer = self._render_expression(
                statement.initializer,
                environment,
                profile,
                slot,
                active_stack,
                allocator,
                trace,
            )
            output.extend(prepended)
            local_name = local_names[statement.binding.identity]
            output.append(
                f"{_local_prefix(self.language, statement.mutable)} "
                f"{local_name} = {initializer.text};"
            )
            environment[statement.binding.identity] = PivotRenderedExpression(
                local_name
            )

        prepended, result = self._render_expression(
            body.result,
            environment,
            profile,
            slot,
            active_stack,
            allocator,
            trace,
            return_value=True,
        )
        output.extend(prepended)
        if declare_destination:
            output.append(
                f"{_destination_prefix(self.language)} {destination} = {result.text};"
            )
        else:
            output.append(f"{destination} = {result.text};")
        return tuple(output), loaded.specialization

    def _parsed_body(
        self,
        key: tuple[object, ...],
        result: PivotBodyBuildResult,
    ) -> PivotParsedBody:
        cached = self._parsed.get(key)
        if cached is not None:
            if isinstance(cached, PivotInliningError):
                raise cached
            return cached
        if result.body is None:
            unsupported = result.unsupported[0]
            error = PivotInliningError(
                unsupported.code,
                unsupported.message,
                unsupported.source,
            )
            self._parsed[key] = error
            raise error
        try:
            parsed = parse_pivot_body(result.body)
        except PivotTargetParseError as exc:
            error = PivotInliningError(exc.code, str(exc), exc.source)
            self._parsed[key] = error
            raise error from exc
        self._parsed[key] = parsed
        return parsed

    def _render_expression(
        self,
        expression: PivotParsedExpression,
        environment: dict[PivotBindingId, PivotRenderedExpression],
        profile: MachineProfile,
        caller: SelectedImplementation,
        stack: tuple[tuple[object, ...], ...],
        allocator: PivotNameAllocator,
        trace: list[PivotBodyBuildResult],
        *,
        return_value: bool = False,
    ) -> tuple[tuple[str, ...], PivotRenderedExpression]:
        nodes = expression.items
        if return_value and self.language is PivotLanguage.RUST:
            nodes = _rust_return_nodes(nodes)
        prepended, text = self._render_nodes(
            nodes,
            environment,
            profile,
            caller,
            stack,
            allocator,
            trace,
        )
        normalized = normalize_target_text(text)
        if not normalized:
            raise PivotInliningError(
                "TSL-PIVOT-EMPTY-EXPRESSION",
                "PIVOT expression is empty after rendering",
                expression.source,
            )
        return prepended, PivotRenderedExpression(normalized)

    def _render_nodes(
        self,
        nodes: tuple[PivotExpressionNode, ...],
        environment: dict[PivotBindingId, PivotRenderedExpression],
        profile: MachineProfile,
        caller: SelectedImplementation,
        stack: tuple[tuple[object, ...], ...],
        allocator: PivotNameAllocator,
        trace: list[PivotBodyBuildResult],
    ) -> tuple[tuple[str, ...], str]:
        output: list[str] = []
        fragments: list[str] = []
        for node in nodes:
            if isinstance(node, PivotToken):
                fragments.append(node.text)
                continue
            if isinstance(node, PivotTargetName):
                fragments.append(node.text)
                continue
            if isinstance(node, PivotBindingReference):
                value = environment.get(node.binding.identity)
                if value is None:
                    raise PivotInliningError(
                        "TSL-PIVOT-UNBOUND-IDENTITY",
                        f"PIVOT binding {node.binding.authored_name!r} is out of scope",
                        node.binding.source,
                    )
                fragments.append(value.text)
                continue
            if isinstance(node, PivotDelimiterGroup):
                nested_output, nested = self._render_nodes(
                    node.items,
                    environment,
                    profile,
                    caller,
                    stack,
                    allocator,
                    trace,
                )
                output.extend(nested_output)
                fragments.extend((node.opening, nested, node.closing))
                continue
            if isinstance(node, PivotParsedCall):
                call_output, replacement = self._render_call(
                    node,
                    environment,
                    profile,
                    caller,
                    stack,
                    allocator,
                    trace,
                )
                output.extend(call_output)
                fragments.append(replacement)
                continue
            if isinstance(node, PivotParsedFixedCall):
                fixed_output, fixed = self._render_fixed_call(
                    node,
                    environment,
                    profile,
                    caller,
                    stack,
                    allocator,
                    trace,
                )
                output.extend(fixed_output)
                fragments.append(fixed)
                continue
            raise PivotInliningError(
                "TSL-PIVOT-UNKNOWN-EXPRESSION-NODE",
                "PIVOT inliner found an unknown expression node",
                caller.implementation.body_source,
            )
        return tuple(output), "".join(fragments)

    def _render_call(
        self,
        parsed: PivotParsedCall,
        environment: dict[PivotBindingId, PivotRenderedExpression],
        profile: MachineProfile,
        caller: SelectedImplementation,
        stack: tuple[tuple[object, ...], ...],
        allocator: PivotNameAllocator,
        trace: list[PivotBodyBuildResult],
    ) -> tuple[tuple[str, ...], str]:
        prepended: list[str] = []
        arguments: list[PivotRenderedExpression] = []
        for argument in parsed.arguments:
            argument_output, rendered = self._render_expression(
                argument,
                environment,
                profile,
                caller,
                stack,
                allocator,
                trace,
            )
            prepended.extend(argument_output)
            arguments.append(rendered)
        callee = self._resolve_call(
            profile,
            caller,
            parsed.call,
            len(arguments),
        )
        temp = allocator.allocate("tmp")
        callee_direct, _specialization = self._emit_slot(
            profile,
            callee,
            tuple(arguments),
            destination=temp,
            declare_destination=True,
            stack=stack,
            allocator=allocator,
            trace=trace,
        )
        prepended.extend(callee_direct)
        return tuple(prepended), temp

    def _render_fixed_call(
        self,
        parsed: PivotParsedFixedCall,
        environment: dict[PivotBindingId, PivotRenderedExpression],
        profile: MachineProfile,
        caller: SelectedImplementation,
        stack: tuple[tuple[object, ...], ...],
        allocator: PivotNameAllocator,
        trace: list[PivotBodyBuildResult],
    ) -> tuple[tuple[str, ...], str]:
        prepended: list[str] = []
        arguments: list[str] = []
        for argument in parsed.arguments:
            argument_output, rendered = self._render_expression(
                argument,
                environment,
                profile,
                caller,
                stack,
                allocator,
                trace,
            )
            prepended.extend(argument_output)
            arguments.append(rendered.text)
        call = self._render_fixed_call_text(
            parsed.call,
            tuple(arguments),
        )
        return tuple(prepended), call


def _local_prefix(language: PivotLanguage, mutable: bool) -> str:
    if language is PivotLanguage.CPP:
        return "auto" if mutable else "auto const"
    return "let mut" if mutable else "let"


def _destination_prefix(language: PivotLanguage) -> str:
    return "auto" if language is PivotLanguage.CPP else "let"


def _rust_return_nodes(
    nodes: tuple[PivotExpressionNode, ...],
) -> tuple[PivotExpressionNode, ...]:
    significant = tuple(
        node
        for node in nodes
        if not (
            isinstance(node, PivotToken)
            and node.kind is PivotTokenKind.TRIVIA
        )
    )
    if len(significant) != 1 or not isinstance(
        significant[0], PivotDelimiterGroup
    ):
        return nodes
    group = significant[0]
    if group.opening != "(" or any(
        isinstance(node, PivotToken) and node.text == "," for node in group.items
    ):
        return nodes
    return group.items


__all__ = (
    "PivotNameAllocator",
    "PivotRenderedExpression",
    "PivotEmission",
    "PivotInliningError",
    "PivotInliner",
    "PivotInlineSlot",
)
