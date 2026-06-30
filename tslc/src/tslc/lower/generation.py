"""Generation-time integer expression helpers."""

from __future__ import annotations

import ast
import operator
from collections.abc import Callable

from tslc.ir.segments import Segment
from tslc.lower.context import LoweringSession
from tslc.render.model import RenderText, render_text

RenderBody = Callable[[tuple[Segment, ...]], RenderText]


def evaluate_generation_int_segments(
    segments: tuple[Segment, ...],
    context: LoweringSession,
    render: RenderBody,
) -> int | None:
    """Render query islands in ``segments`` and evaluate the resulting integer expression."""

    return evaluate_generation_int_text(render_text(render(segments)).strip(), context)


def evaluate_generation_int_text(text: str, context: LoweringSession) -> int | None:
    """Evaluate a deliberately tiny generation-time integer expression.

    Accepted leaves are integer literals and symbols bound by ``loop<generation>``.
    Accepted operators are ``+``, ``-``, ``*``, and exact integer ``/`` or ``//``.
    Everything else returns ``None`` so callers can emit source diagnostics rather
    than guessing.
    """

    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError:
        return None
    return _IntEvaluator(context).visit(tree.body)


class _IntEvaluator(ast.NodeVisitor):
    _BINOPS: dict[type[ast.operator], Callable[[int, int], int | None]] = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.FloorDiv: lambda left, right: (
            None if right == 0 or left % right != 0 else left // right
        ),
        ast.Div: lambda left, right: (
            None if right == 0 or left % right != 0 else left // right
        ),
    }

    def __init__(self, context: LoweringSession) -> None:
        self._context = context

    def visit_Constant(self, node: ast.Constant) -> int | None:  # noqa: N802
        if isinstance(node.value, int) and not isinstance(node.value, bool):
            return node.value
        return None

    def visit_Name(self, node: ast.Name) -> int | None:  # noqa: N802
        return self._context.scope.resolve_generation_int(node.id)

    def visit_UnaryOp(self, node: ast.UnaryOp) -> int | None:  # noqa: N802
        value = self.visit(node.operand)
        if value is None:
            return None
        if isinstance(node.op, ast.UAdd):
            return value
        if isinstance(node.op, ast.USub):
            return -value
        return None

    def visit_BinOp(self, node: ast.BinOp) -> int | None:  # noqa: N802
        left = self.visit(node.left)
        right = self.visit(node.right)
        if left is None or right is None:
            return None
        operation = self._BINOPS.get(type(node.op))
        return None if operation is None else operation(left, right)

    def generic_visit(self, node: ast.AST) -> int | None:
        del node
        return None
