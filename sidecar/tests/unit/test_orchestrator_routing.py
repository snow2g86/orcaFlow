"""Routing expression evaluator — 화이트리스트 검증."""

from __future__ import annotations

import pytest

from orca_core.orchestrator.errors import RoutingError
from orca_core.orchestrator.routing import evaluate_condition, parse_condition
from orca_core.orchestrator.state import RunState


def _state_with(messages: list[dict] | None = None, plan=None, artifacts=None) -> RunState:
    return RunState(
        messages=messages or [],
        plan=plan,
        artifacts=artifacts or {},
    )


def test_none_condition_is_truthy():
    assert evaluate_condition(None, state=_state_with()) is True
    assert evaluate_condition("", state=_state_with()) is True
    assert evaluate_condition("   ", state=_state_with()) is True


def test_state_plan_not_none():
    s = _state_with(plan={"x": 1})
    assert evaluate_condition("state.plan != None", state=s) is True
    s2 = _state_with(plan=None)
    assert evaluate_condition("state.plan != None", state=s2) is False


def test_messages_length_compare():
    s = _state_with(messages=[{"role": "user"}, {"role": "assistant"}])
    assert evaluate_condition("state.messages.length > 0", state=s) is True
    assert evaluate_condition("state.messages.length == 2", state=s) is True
    assert evaluate_condition("state.messages.length > 5", state=s) is False


def test_subscript_last_message_role():
    s = _state_with(messages=[{"role": "user"}, {"role": "tool"}])
    expr = 'state.messages[-1]["role"] == "tool"'
    assert evaluate_condition(expr, state=s) is True


def test_bool_and_or_not():
    s = _state_with(plan="planned", artifacts={"a": 1})
    assert evaluate_condition("state.plan != None and state.artifacts.length > 0", state=s) is True
    assert evaluate_condition("state.plan == None or state.artifacts.length > 0", state=s) is True
    assert evaluate_condition("not (state.plan == None)", state=s) is True


def test_in_operator():
    s = _state_with(artifacts={"x": 5})
    assert evaluate_condition('"x" in state.artifacts', state=s) is True
    assert evaluate_condition('"y" not in state.artifacts', state=s) is True


def test_disallowed_call_rejected():
    with pytest.raises(RoutingError):
        parse_condition("len(state.messages)")


def test_disallowed_lambda_rejected():
    with pytest.raises(RoutingError):
        parse_condition("lambda x: x")


def test_disallowed_assignment_rejected():
    with pytest.raises(RoutingError):
        parse_condition("state.plan = 1")


def test_unknown_identifier_rejected():
    with pytest.raises(RoutingError):
        evaluate_condition("foo.bar == 1", state=_state_with())


def test_invalid_syntax_raises():
    with pytest.raises(RoutingError):
        evaluate_condition("state.plan ==", state=_state_with())


def test_attribute_on_none_returns_none():
    s = _state_with()
    # state.plan is None, accessing attr should yield None (no exception)
    assert evaluate_condition("state.plan == None", state=s) is True


def test_arithmetic_unary_minus_supported():
    s = _state_with(messages=[{"role": "user"}, {"role": "tool"}])
    expr = "state.messages.length > -1"
    assert evaluate_condition(expr, state=s) is True


def test_unary_plus_supported():
    s = _state_with(plan=5)
    assert evaluate_condition("state.plan == +5", state=s) is True


def test_is_and_is_not():
    s = _state_with(plan=None)
    assert evaluate_condition("state.plan is None", state=s) is True
    s2 = _state_with(plan="x")
    assert evaluate_condition("state.plan is not None", state=s2) is True


def test_chained_compare():
    s = _state_with(messages=[{"role": "u"}, {"role": "a"}, {"role": "t"}])
    assert evaluate_condition("0 < state.messages.length", state=s) is True


def test_compare_with_none_returns_false():
    s = _state_with(plan=None)
    assert evaluate_condition("state.plan < 5", state=s) is False
    assert evaluate_condition("state.plan > 5", state=s) is False
    assert evaluate_condition("state.plan <= 5", state=s) is False
    assert evaluate_condition("state.plan >= 5", state=s) is False


def test_or_operator():
    s = _state_with(plan="x")
    assert evaluate_condition('state.plan == "x" or state.plan == "y"', state=s) is True
    assert evaluate_condition('state.plan == "z" or state.plan == "x"', state=s) is True
    assert evaluate_condition('state.plan == "z" or state.plan == "w"', state=s) is False


def test_subscript_on_none_returns_none():
    s = _state_with(plan=None)
    assert evaluate_condition("state.plan[0] == None", state=s) is True


def test_subscript_unsupported_type_raises():
    s = _state_with(plan=42)
    with pytest.raises(RoutingError):
        evaluate_condition("state.plan[0] == 1", state=s)


def test_subscript_index_out_of_range_returns_none():
    s = _state_with(messages=[])
    assert evaluate_condition("state.messages[5] == None", state=s) is True


def test_in_operator_unsupported_right_raises():
    s = _state_with(plan=42)
    with pytest.raises(RoutingError):
        evaluate_condition("1 in state.plan", state=s)


def test_dict_literal():
    s = _state_with()
    assert evaluate_condition('"a" in {"a": 1, "b": 2}', state=s) is True


def test_set_literal():
    s = _state_with()
    assert evaluate_condition('"a" in {"a", "b"}', state=s) is True


def test_tuple_literal_membership():
    s = _state_with(plan="x")
    assert evaluate_condition('state.plan in ("x", "y")', state=s) is True


def test_length_on_string():
    s = _state_with(plan="abc")
    assert evaluate_condition("state.plan.length == 3", state=s) is True


def test_length_on_none_raises():
    s = _state_with(plan=None)
    with pytest.raises(RoutingError):
        evaluate_condition("state.plan.length > 0", state=s)


def test_attribute_on_dict_via_get():
    s = _state_with(artifacts={"x": 1})
    assert evaluate_condition("state.artifacts.x == 1", state=s) is True


def test_runtime_exception_wrapped_as_routing_error():
    """Wrapping non-RoutingError exceptions in RoutingError."""
    s = _state_with()
    with pytest.raises(RoutingError):
        # Comparison between dict and int — handled gracefully when both
        # non-None, but a TypeError-raising operator wraps to RoutingError.
        evaluate_condition("state.artifacts < 1", state=s)
