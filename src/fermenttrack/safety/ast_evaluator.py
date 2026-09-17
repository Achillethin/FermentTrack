"""Allow-listed evaluator for safety-rule expressions."""

from __future__ import annotations

import ast
from collections.abc import Mapping
from typing import Any, NoReturn


_SAFE_CALLS = {
    "abs": abs,
    "min": min,
    "max": max,
    "round": round,
}
_CONSTANT_TYPES = (int, float, str, bool, type(None))


class SafetyDSLParseError(ValueError):
    """Raised when a safety-rule expression uses unsupported syntax."""

    def __init__(
        self,
        node_type: str,
        line: int,
        column: int,
        detail: str | None = None,
    ) -> None:
        message = f"Disallowed {node_type} at line {line}, column {column}"
        if detail:
            message = f"{message}: {detail}"
        super().__init__(message)
        self.node_type = node_type
        self.line = line
        self.column = column


def evaluate_condition(expression: str, state_vars: Mapping[str, Any]) -> bool:
    """Evaluate an expression using only the safety DSL allow-list."""
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise SafetyDSLParseError(
            "SyntaxError",
            exc.lineno or 1,
            exc.offset or 0,
            exc.msg,
        ) from exc

    _validate(tree.body)
    return bool(_evaluate(tree.body, state_vars))


def _reject(node: ast.expr | ast.keyword, detail: str | None = None) -> NoReturn:
    raise SafetyDSLParseError(
        type(node).__name__,
        node.lineno,
        node.col_offset,
        detail,
    )


def _reject_operator(node: ast.expr, operator: ast.AST) -> NoReturn:
    raise SafetyDSLParseError(
        type(operator).__name__,
        node.lineno,
        node.col_offset,
    )


def _validate(node: ast.expr) -> None:
    if isinstance(node, ast.Constant):
        if type(node.value) not in _CONSTANT_TYPES:
            _reject(node)
        return

    if isinstance(node, ast.Name):
        if "__" in node.id:
            _reject(node, "dunder names are not allowed")
        return

    if isinstance(node, ast.BoolOp):
        if not isinstance(node.op, (ast.And, ast.Or)):
            _reject_operator(node, node.op)
        for value in node.values:
            _validate(value)
        return

    if isinstance(node, ast.Compare):
        _validate(node.left)
        for operator in node.ops:
            if not isinstance(
                operator,
                (ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE),
            ):
                _reject_operator(node, operator)
        for comparator in node.comparators:
            _validate(comparator)
        return

    if isinstance(node, ast.BinOp):
        if not isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            _reject_operator(node, node.op)
        _validate(node.left)
        _validate(node.right)
        return

    if isinstance(node, ast.UnaryOp):
        if not isinstance(node.op, (ast.USub, ast.Not)):
            _reject_operator(node, node.op)
        _validate(node.operand)
        return

    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            _reject(node.func, "only direct calls to safe functions are allowed")
        if node.func.id not in _SAFE_CALLS:
            _reject(node.func, f"call to {node.func.id!r} is not allowed")
        if node.keywords:
            _reject(node.keywords[0], "keyword arguments are not allowed")
        for argument in node.args:
            _validate(argument)
        return

    _reject(node)


def _evaluate(node: ast.expr, state_vars: Mapping[str, Any]) -> Any:
    if isinstance(node, ast.Constant):
        if type(node.value) not in _CONSTANT_TYPES:
            _reject(node)
        return node.value

    if isinstance(node, ast.Name):
        if "__" in node.id:
            _reject(node, "dunder names are not allowed")
        if node.id in state_vars:
            return state_vars[node.id]
        if node.id in _SAFE_CALLS:
            return _SAFE_CALLS[node.id]
        raise NameError(f"Unknown safety DSL name: {node.id}")

    if isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.And):
            for value in node.values:
                if not _evaluate(value, state_vars):
                    return False
            return True
        if isinstance(node.op, ast.Or):
            for value in node.values:
                if _evaluate(value, state_vars):
                    return True
            return False
        _reject(node)

    if isinstance(node, ast.Compare):
        left = _evaluate(node.left, state_vars)
        for operator, comparator_node in zip(node.ops, node.comparators):
            right = _evaluate(comparator_node, state_vars)
            if isinstance(operator, ast.Eq):
                matched = left == right
            elif isinstance(operator, ast.NotEq):
                matched = left != right
            elif isinstance(operator, ast.Lt):
                matched = left < right
            elif isinstance(operator, ast.LtE):
                matched = left <= right
            elif isinstance(operator, ast.Gt):
                matched = left > right
            elif isinstance(operator, ast.GtE):
                matched = left >= right
            else:
                _reject_operator(node, operator)
            if not matched:
                return False
            left = right
        return True

    if isinstance(node, ast.BinOp):
        left = _evaluate(node.left, state_vars)
        right = _evaluate(node.right, state_vars)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        _reject_operator(node, node.op)

    if isinstance(node, ast.UnaryOp):
        operand = _evaluate(node.operand, state_vars)
        if isinstance(node.op, ast.USub):
            return -operand
        if isinstance(node.op, ast.Not):
            return not operand
        _reject_operator(node, node.op)

    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            _reject(node.func, "only direct calls to safe functions are allowed")
        if node.func.id not in _SAFE_CALLS:
            _reject(node.func, f"call to {node.func.id!r} is not allowed")
        if node.keywords:
            _reject(node.keywords[0], "keyword arguments are not allowed")
        arguments = [_evaluate(argument, state_vars) for argument in node.args]
        return _SAFE_CALLS[node.func.id](*arguments)

    _reject(node)
