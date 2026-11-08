from birdbrain.advice import MAX_WORTH, Advice, appearance, prompt
from birdbrain.body import Observation
from birdbrain.kr import Position
from birdbrain.mind import Mind


class FakeJudge:
    def __init__(self):
        self.asked = []

    def judge(self, text):
        self.asked.append(text)
        return {"p_hold": 0.1, "p_delivered": 0.8, "p_fall": 0.05, "worth_trials": 8, "reason": "too wide"}, \
            {"input": 10, "output": 5}


def test_an_appearance_is_asked_about_once_and_its_weight_is_capped():
    judge = FakeJudge()
    a = Advice(judge)
    first = a.pseudo_outcomes("red", "5 to 7.5 cm")
    again = a.pseudo_outcomes("red", "5 to 7.5 cm")
    assert len(judge.asked) == 1 and first == again
    assert {w for *_, w in first} == {MAX_WORTH}
    assert ("effect", "pick", {"target colour": "red", "target size": "5 to 7.5 cm"}, 0.1, MAX_WORTH) in first
    assert "red" in prompt("red", "5 to 7.5 cm") and "3.6 cm" in prompt("red", "5 to 7.5 cm")


def test_only_what_the_duck_has_seen_is_asked_about():
    assert appearance({"target colour": "unknown", "target size": "3 to 5 cm"}, "target") is None
    assert appearance({"target colour": "red", "target size": "3 to 5 cm"}, "target") == ("red", "3 to 5 cm")


def test_the_mind_turns_a_judgement_into_a_prior_for_its_rules(tmp_path):
    judge = FakeJudge()
    mind = Mind(judge=judge, memory_dir=tmp_path)
    mind.step(Observation(t=0.0, odom=(0.0, 0.0, 0.0), speed=0.0, holding=False, reflex=None, bumped=False))
    e = mind.kb.new_entity("toy", 0.0)
    mind.kb.tell("at", (e,), Position.round(0.5, 0.0, 0.02), t=0.0, conf=1.0)
    mind.kb.tell("color", (e,), "red", t=0.0)
    mind.kb.tell("size", (e,), 0.06, t=0.0)
    mind._advise(1.0)
    ex = mind.rules["effect"].examples["pick"]
    assert ex[-1][1] == 0.1 and ex[-1][2] == MAX_WORTH
    mind.close()
    again = Mind(judge=judge, memory_dir=tmp_path)            # the next room: not asked again
    again._advise(2.0)
    assert len(judge.asked) == 1
