"""Edge.condition — 안전한 Python expression subset 평가기.

design.md 6.1.1 Edge.condition 을 Python ast 기반 화이트리스트로 구현한다.
built-in Python expression 실행 함수는 절대 사용하지 않는다. 모든 노드는
_SAFE_NODES 에 포함된 타입만 허용한다.

지원:
    - Constant (str/int/float/bool/None)
    - Name  (state)
    - Attribute (state.plan, state.messages)
    - Subscript (state.messages[-1], state.artifacts["x"])
    - Compare (==, !=, <, >, <=, >=, in, not in, is, is not)
    - BoolOp (and, or)
    - UnaryOp (not)
    - Tuple/List/Dict literals
    - Pseudo property .length  ->  len(target)

금지:
    Call, Lambda, Assign, Import, f-string, comprehension, attribute write.
"""

from __future__ import annotations

import ast
import logging
from typing import Any

from .errors import RoutingError

__all__ = ["evaluate_condition", "parse_condition"]

_LOGGER = logging.getLogger("orca_core.orchestrator.routing")


_SAFE_NODES: tuple[type[ast.AST], ...] = (
    ast.Expression,
    ast.BoolOp,
    ast.UnaryOp,
    ast.Compare,
    ast.Name,
    ast.Load,
    ast.Constant,
    ast.Attribute,
    ast.Subscript,
    ast.Tuple,
    ast.List,
    ast.Dict,
    ast.Set,
    ast.And,
    ast.Or,
    ast.Not,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    ast.In,
    ast.NotIn,
    ast.Is,
    ast.IsNot,
    ast.USub,
    ast.UAdd,
    ast.Index,
)


def parse_condition(expression: str) -> ast.Expression:
    """사용자/플래너 expression 을 화이트리스트 기준으로 파싱."""
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise RoutingError(
            f"invalid routing expression: {exc.msg}",
            details={"expression": expression},
        ) from exc

    for node in ast.walk(tree):
        if not isinstance(node, _SAFE_NODES):
            raise RoutingError(
                f"routing expression uses disallowed syntax: {type(node).__name__}",
                details={"expression": expression, "node": type(node).__name__},
            )
    return tree


def evaluate_condition(expression: str | None, *, state: Any) -> bool:
    """Edge.condition 평가.

    expression 이 None 이거나 공백이면 True 반환 (무조건 전이).
    """
    if expression is None or not expression.strip():
        return True
    tree = parse_condition(expression)
    try:
        value = _walk(tree.body, state)
    except RoutingError:
        raise
    except Exception as exc:  # defensive: any runtime error -> routing error
        raise RoutingError(
            f"routing expression raised {type(exc).__name__}: {exc}",
            details={"expression": expression},
        ) from exc
    return bool(value)


def _walk(node: ast.AST, state: Any) -> Any:  # noqa: PLR0911, PLR0912
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        if node.id != "state":
            raise RoutingError(f"unknown identifier: {node.id}")
        return state
    if isinstance(node, ast.Attribute):
        target = _walk(node.value, state)
        attr = node.attr
        if attr == "length":
            try:
                return len(target)
            except TypeError as exc:
                raise RoutingError(f".length on non-iterable: {type(target).__name__}") from exc
        if target is None:
            return None
        if isinstance(target, dict):
            return target.get(attr)
        return getattr(target, attr, None)
    if isinstance(node, ast.Subscript):
        target = _walk(node.value, state)
        key = _walk(node.slice, state)
        if target is None:
            return None
        try:
            return target[key]
        except (KeyError, IndexError):
            # H16: record a DEBUG trace so silent None returns are observable
            # when diagnosing missing routes. None is still a legitimate value
            # in edge conditions (e.g. `state.plan != None`), so we do not
            # raise unless the caller asked for strict mode.
            _LOGGER.debug(
                "routing.subscript_missing",
                extra={
                    "event": "routing.subscript_missing",
                    "target_type": type(target).__name__,
                    "key": repr(key),
                },
            )
            return None
        except TypeError as exc:
            raise RoutingError(f"subscript on unsupported type: {type(target).__name__}") from exc
    if isinstance(node, ast.Compare):
        left = _walk(node.left, state)
        result = True
        for op, comparator in zip(node.ops, node.comparators, strict=True):
            right = _walk(comparator, state)
            result = result and _apply_cmp(op, left, right)
            if not result:
                return False
            left = right
        return result
    if isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.And):
            result = True
            for value in node.values:
                result = result and bool(_walk(value, state))
                if not result:
                    return False
            return result
        for value in node.values:  # noqa: SIM110
            if bool(_walk(value, state)):
                return True
        return False
    if isinstance(node, ast.UnaryOp):
        operand = _walk(node.operand, state)
        if isinstance(node.op, ast.Not):
            return not operand
        if isinstance(node.op, ast.USub):
            return -operand
        if isinstance(node.op, ast.UAdd):
            return +operand
        raise RoutingError(f"unsupported unary op: {type(node.op).__name__}")
    if isinstance(node, ast.Tuple | ast.List):
        return [_walk(e, state) for e in node.elts]
    if isinstance(node, ast.Set):
        return {_walk(e, state) for e in node.elts}
    if isinstance(node, ast.Dict):
        return {
            _walk(k, state) if k is not None else None: _walk(v, state)
            for k, v in zip(node.keys, node.values, strict=True)
        }
    raise RoutingError(f"unsupported expression node: {type(node).__name__}")


def _apply_cmp(op: ast.cmpop, left: Any, right: Any) -> bool:  # noqa: PLR0911
    if isinstance(op, ast.Eq):
        return bool(left == right)
    if isinstance(op, ast.NotEq):
        return bool(left != right)
    if isinstance(op, ast.Lt):
        return bool(left < right) if left is not None and right is not None else False
    if isinstance(op, ast.LtE):
        return bool(left <= right) if left is not None and right is not None else False
    if isinstance(op, ast.Gt):
        return bool(left > right) if left is not None and right is not None else False
    if isinstance(op, ast.GtE):
        return bool(left >= right) if left is not None and right is not None else False
    if isinstance(op, ast.In):
        try:
            return left in right
        except TypeError as exc:
            raise RoutingError(f"in-operator on unsupported right: {type(right).__name__}") from exc
    if isinstance(op, ast.NotIn):
        try:
            return left not in right
        except TypeError as exc:
            raise RoutingError(
                f"not in-operator on unsupported right: {type(right).__name__}"
            ) from exc
    if isinstance(op, ast.Is):
        return left is right
    if isinstance(op, ast.IsNot):
        return left is not right
    raise RoutingError(f"unsupported comparator: {type(op).__name__}")
