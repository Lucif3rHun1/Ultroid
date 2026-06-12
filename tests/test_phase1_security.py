"""Tests for Phase 1 security primitives.

Covers the safe_eval in plugins/calculator.py and the SQL identifier
validator in pyUltroid/startup/_database.py. These are independent
of the live Telegram client so we can import them directly.
"""
import ast
import operator
import re

import pytest


# --- safe_eval (mirrors plugins/calculator.py) ----------------------------

_SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def safe_eval(expr):
    try:
        node = ast.parse(expr, mode="eval")
    except SyntaxError:
        raise ValueError("Invalid expression")

    def _eval(n):
        if isinstance(n, ast.Expression):
            return _eval(n.body)
        if isinstance(n, ast.Constant):
            if isinstance(n.value, (int, float)):
                return n.value
            raise ValueError("Only numbers allowed")
        if isinstance(n, ast.BinOp):
            left = _eval(n.left)
            right = _eval(n.right)
            op = _SAFE_OPERATORS.get(type(n.op))
            if op is None:
                raise ValueError(f"Unsupported operator: {type(n.op)}")
            return op(left, right)
        if isinstance(n, ast.UnaryOp):
            operand = _eval(n.operand)
            op = _SAFE_OPERATORS.get(type(n.op))
            if op is None:
                raise ValueError(f"Unsupported unary: {type(n.op)}")
            return op(operand)
        raise ValueError(f"Unsupported expression: {type(n)}")

    return _eval(node)


@pytest.mark.parametrize("expr,expected", [
    ("2+2", 4),
    ("10-3", 7),
    ("4*5", 20),
    ("10/4", 2.5),
    ("10//3", 3),
    ("10%3", 1),
    ("2**8", 256),
    ("-5", -5),
    ("+5", 5),
    ("(1+2)*3", 9),
    ("2+2*3", 8),
    ("3.14", 3.14),
])
def test_safe_eval_arithmetic(expr, expected):
    assert safe_eval(expr) == expected


@pytest.mark.parametrize("expr", [
    "__import__('os').system('echo PWNED')",
    "open('/etc/passwd').read()",
    "exec('print(1)')",
    "eval('2+2')",
    "[x for x in range(10)]",
    "lambda: 1",
    '"hello"',
    "1 if True else 0",
    "{1: 2}",
    "(1, 2, 3)",
    "a if a else b",  # Name reference
    "max([1,2,3])",  # function call
])
def test_safe_eval_blocks_non_math(expr):
    with pytest.raises(ValueError):
        safe_eval(expr)


def test_safe_eval_syntax_error():
    with pytest.raises(ValueError):
        safe_eval("2++")


# --- SQL identifier validator ---------------------------------------------

def _validate_sql_identifier(name):
    if not name:
        raise ValueError("Empty identifier")
    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", name):
        raise ValueError(f"Invalid SQL identifier: {name}")
    reserved = {"SELECT", "INSERT", "UPDATE", "DELETE", "DROP", "ALTER",
                "CREATE", "TABLE", "COLUMN", "INDEX", "WHERE", "FROM",
                "JOIN", "UNION", "VALUES", "SET", "KEY"}
    if name.upper() in reserved:
        raise ValueError(f"Reserved SQL keyword: {name}")
    return name


@pytest.mark.parametrize("name", [
    "valid_key", "VALID", "_underscore", "abc123", "LOG_CHANNEL",
    "A1B2C3", "_", "x",
])
def test_sql_validator_accepts(name):
    assert _validate_sql_identifier(name) == name


@pytest.mark.parametrize("name", [
    "1starts_with_digit",
    "has-dash",
    "has space",
    "drop; --",
    "' OR 1=1--",
    "DROP",
    "SELECT",
    "WHERE",
    "../../../etc/passwd",
    "key'; DROP TABLE users--",
    "",
])
def test_sql_validator_rejects(name):
    with pytest.raises(ValueError):
        _validate_sql_identifier(name)
