"""A small, safe expression language over the knowledge base.

Skill conditions, queries, and predictions are written as Python-like
expressions, for example

    near(self, x, 0.12) and facing(x, 0.1)
    nearest(toy, known(it) and not inside(it, basket))
    holding(self, 'toy#2')

Expressions are parsed with Python's `ast` and only a whitelist of node types
is evaluated, so nothing in an expression can execute code. Names resolve to
bound variables, `self`, `none`/`true`/`false`, or an object class. A class
name used where an entity is expected means the best-known entity of that
class. `nearest`, `exists`, and `count` take a class and a condition in which
`it` is the candidate.
"""

from __future__ import annotations

import ast
import math
import operator
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from birdbrain.kr import SELF, KnowledgeBase
from birdbrain.relations import FUNCTIONS, distance, known

SPECIAL = {"nearest", "exists", "count"}
# What a relation evaluates to when one of its entity arguments is unknown.
NONE_ON_MISSING = {"distance": math.inf, "bearing": math.nan, "seen_since": math.inf, "beyond": None,
                   "attempts": 0, "failures": 0}
CONSTANTS = {"none": None, "None": None, "true": True, "True": True, "false": False, "False": False}
_ALLOWED = (
    ast.Expression, ast.BoolOp, ast.And, ast.Or, ast.UnaryOp, ast.Not, ast.USub,
    ast.Compare, ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Is, ast.IsNot,
    ast.Call, ast.Name, ast.Load, ast.Constant, ast.BinOp, ast.Add, ast.Sub, ast.Mult,
)


class ExprError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ClassRef:
    cls: str


@lru_cache(maxsize=512)
def parse(source: str) -> ast.Expression:
    try:
        tree = ast.parse(source.strip(), mode="eval")
    except SyntaxError as error:
        raise ExprError(f"cannot parse {source!r}: {error.msg}") from None
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED):
            raise ExprError(f"{type(node).__name__} is not allowed in {source!r}")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.keywords:
                raise ExprError(f"only plain calls are allowed in {source!r}")
            if node.func.id not in FUNCTIONS and node.func.id not in SPECIAL:
                raise ExprError(f"unknown function {node.func.id!r} in {source!r}")
        if isinstance(node, ast.Constant) and not isinstance(node.value, (int, float, str, bool, type(None))):
            raise ExprError(f"unsupported constant in {source!r}")
    return tree


def names(source: str) -> set[str]:
    """Free names an expression uses (excluding functions and constants)."""
    tree = parse(source)
    calls = {id(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)}
    return {n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and id(n) not in calls
            and n.id not in CONSTANTS}


class Evaluator:
    def __init__(self, kb: KnowledgeBase, classes: set[str]) -> None:
        self.kb, self.classes = kb, classes

    def eval(self, source: str, env: Mapping[str, Any], t: float) -> Any:
        return self._eval(parse(source).body, dict(env), t)

    def entity(self, value: Any, t: float) -> Any:
        """Resolve a class reference to the best-known entity of that class."""
        if not isinstance(value, ClassRef):
            return value
        best, best_key = None, None
        for e in self.kb.of_class(value.cls):
            a = self.kb.get("at", e)
            if a is None:
                continue
            key = (a.conf, -a.value.sigma)
            if best_key is None or key > best_key:
                best, best_key = e, key
        return best

    def _eval(self, node: ast.AST, env: dict[str, Any], t: float) -> Any:
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            if node.id in env:
                return env[node.id]
            if node.id == "self":
                return SELF
            if node.id in CONSTANTS:
                return CONSTANTS[node.id]
            if node.id in self.classes:
                return ClassRef(node.id)
            raise ExprError(f"unbound name {node.id!r}")
        if isinstance(node, ast.BoolOp):
            values = (self._eval(v, env, t) for v in node.values)
            return all(values) if isinstance(node.op, ast.And) else any(values)
        if isinstance(node, ast.UnaryOp):
            v = self._eval(node.operand, env, t)
            return (not v) if isinstance(node.op, ast.Not) else -v
        if isinstance(node, ast.BinOp):
            a, b = self._eval(node.left, env, t), self._eval(node.right, env, t)
            try:
                return _ARITHMETIC[type(node.op)](a, b)
            except TypeError as error:
                raise ExprError(str(error)) from None
        if isinstance(node, ast.Compare):
            left = self._eval(node.left, env, t)
            for op, right_node in zip(node.ops, node.comparators, strict=True):
                right = self._eval(right_node, env, t)
                if not _compare(op, self.entity(left, t), self.entity(right, t)):
                    return False
                left = right
            return True
        if isinstance(node, ast.Call):
            name = node.func.id
            if name in SPECIAL:
                return self._special(name, node.args, env, t)
            args = [self.entity(self._eval(a, env, t), t) for a in node.args]
            if any(a is None for a in args):
                return NONE_ON_MISSING.get(name, False)
            return FUNCTIONS[name](self.kb, t, *args)
        raise ExprError(f"cannot evaluate {type(node).__name__}")

    def _special(self, name: str, args: list[ast.AST], env: dict[str, Any], t: float) -> Any:
        if not args or not isinstance(args[0], ast.Name) or args[0].id not in self.classes:
            raise ExprError(f"{name}() needs a class as its first argument")
        cls = args[0].id
        candidates = [e for e in self.kb.of_class(cls) if known(self.kb, t, e)]
        if len(args) > 1:
            candidates = [e for e in candidates
                          if self._eval(args[1], {**env, "it": e}, t)]
        if name == "exists":
            return bool(candidates)
        if name == "count":
            return len(candidates)
        return min(candidates, key=lambda e: distance(self.kb, t, SELF, e), default=None)


def _compare(op: ast.cmpop, a: Any, b: Any) -> bool:
    if isinstance(op, ast.Is):
        return a is b
    if isinstance(op, ast.IsNot):
        return a is not b
    if isinstance(op, ast.Eq):
        return a == b
    if isinstance(op, ast.NotEq):
        return a != b
    if a is None or b is None:
        return False
    try:
        return _ORDER[type(op)](a, b)
    except TypeError as error:
        raise ExprError(str(error)) from None


_ARITHMETIC = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul}
_ORDER = {ast.Lt: operator.lt, ast.LtE: operator.le, ast.Gt: operator.gt, ast.GtE: operator.ge}
