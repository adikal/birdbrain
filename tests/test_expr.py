import pytest

from birdbrain.expr import Evaluator, ExprError, names, parse
from birdbrain.kr import SELF, KnowledgeBase, Position


@pytest.fixture()
def world():
    kb = KnowledgeBase()
    kb.tell("at", (SELF,), Position.round(0.0, 0.0, 0.01), t=0.0)
    kb.tell("heading", (SELF,), 0.0, t=0.0)
    basket = kb.new_entity("basket", 0.0)
    kb.tell("at", (basket,), Position.round(1.0, 1.0, 0.02), t=0.0)
    near, far, inside = (kb.new_entity("toy", 0.0) for _ in range(3))
    kb.tell("at", (near,), Position.round(0.3, 0.0, 0.02), t=0.0)
    kb.tell("at", (far,), Position.round(-1.0, 0.0, 0.02), t=0.0)
    kb.tell("at", (inside,), Position.round(1.05, 0.95, 0.02), t=0.0)
    return kb, Evaluator(kb, {"toy", "basket"}), (near, far, inside, basket)


@pytest.mark.parametrize("source", ["__import__('os')", "x.y", "(lambda: 1)()", "[1, 2]", "f(a=1)", "open('x')"])
def test_parse_rejects_anything_outside_the_language(source):
    with pytest.raises(ExprError):
        parse(source)


def test_names_lists_free_variables():
    assert names("near(self, x, 0.1) and not holding(self)") == {"self", "x"}


def test_relations_and_special_forms(world):
    _, ev, (near, far, inside, _) = world
    assert ev.eval("near(self, x, 0.5)", {"x": near}, 0.0)
    assert not ev.eval("near(self, x, 0.5)", {"x": far}, 0.0)
    assert ev.eval("inside(x, basket)", {"x": inside}, 0.0)
    assert ev.eval("nearest(toy, not inside(it, basket))", {}, 0.0) == near
    assert ev.eval("count(toy, inside(it, basket))", {}, 0.0) == 1
    assert ev.eval("exists(toy, distance(self, it) > 1.2)", {}, 0.0)
    assert ev.eval("nearest(toy, false)", {}, 0.0) is None
    assert ev.eval("facing(x, 0.1)", {"x": near}, 0.0)


def test_unknown_entities_make_relations_false(world):
    _, ev, _ = world
    assert ev.eval("near(self, x, 1.0)", {"x": None}, 0.0) is False
    with pytest.raises(ExprError):
        ev.eval("near(self, nobody, 1.0)", {}, 0.0)
