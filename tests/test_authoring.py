"""Milestone 5: skills written by the cloud brain, tried and kept on merit (ledger E-019)."""

import random

from birdbrain.authoring import Authoring, failure_reasons
from birdbrain.mind import Mind
from birdbrain.rules import RuleLearner
from birdbrain.skills import Library

GOOD = {"name": "Deliver Closer", "doc": "Walk nearer the basket, look again, then deliver.",
        "body": [{"call": "walk_toward", "args": {"x": "basket", "stop_at": 0.8, "look": "'level'"}, "timeout": 30},
                 {"call": "stand", "args": {"seconds": 1.0}}, {"call": "deliver"}],
        "reason": "the basket estimate drifts with distance"}


class Scripted:
    def __init__(self, *answers):
        self.answers, self.prompts = list(answers), []

    def write(self, prompt):
        self.prompts.append(prompt)
        return self.answers.pop(0), {"input": 1000, "output": 200}


def rules_with_weakness():
    rules = RuleLearner("its expected effect holds")
    rng = random.Random(0)
    for _ in range(80):
        far = rng.random() < 0.5
        rules.add("deliver", {"basket distance": "far" if far else "mid"}, float(rng.random() < (0.3 if far else 0.9)))
    return rules


def test_the_weakest_condition_of_a_compound_skill_is_found():
    weak = Authoring().weakness(rules_with_weakness(), Library())
    assert weak[:3] == ("deliver", "basket distance", "far") and weak[3]["rate"] < 0.5


def test_a_written_skill_is_checked_and_opens_a_trial():
    library, author = Library(), Scripted(GOOD)
    a = Authoring(author=author)
    entry = a.propose("deliver", "basket distance", "far", {"rate": 0.3, "n": 40, "rate_otherwise": 0.9,
                                                          "n_otherwise": 40}, {"failed: basket moved": 12},
                      library)
    assert entry["status"] == "trial" and entry["child"] == "w_deliver_closer" and "w_deliver_closer" in library
    child = library["w_deliver_closer"]
    assert child.expect == library["deliver"].expect and child.params == library["deliver"].params
    assert "basket distance is far" in author.prompts[0] and "failed: basket moved: 12 times" in author.prompts[0]
    assert a.trials[0].counts == {"deliver": [0.0, 0.0, 0.0], "w_deliver_closer": [0.0, 0.0, 0.0]}


def test_a_program_outside_the_language_is_refused_after_one_retry():
    library = Library()
    bad = {"name": "x", "doc": "d", "body": [{"call": "teleport", "args": {}}], "reason": ""}
    selfcall = {"name": "x", "doc": "d", "body": [{"call": "w_x"}], "reason": ""}
    a = Authoring(author=Scripted(bad, selfcall))
    entry = a.propose("deliver", "basket distance", "far", {"rate": 0.3, "n": 40, "rate_otherwise": 0.9,
                                                          "n_otherwise": 40}, {}, library)
    assert entry["status"] == "refused" and "itself" in entry["problem"] and "w_x" not in library
    assert not a.trials and a.attempts == {"deliver|basket distance=far": 1}


def test_trials_are_fair_and_stay_under_review():
    ev = {"rate": 0.3, "n": 40, "rate_otherwise": 0.9, "n_otherwise": 40}
    a = Authoring(author=Scripted(GOOD), min_trials=8)
    a.propose("deliver", "basket distance", "far", ev, {}, Library())
    trial, rng = a.trials[0], random.Random(1)
    assert trial.counts == {"deliver": [0.0, 0.0, 0.0], "w_deliver_closer": [0.0, 0.0, 0.0]}   # no biased prior
    assert a.choose("deliver", {"basket distance": "mid"}, rng) == ("deliver", [])         # not its situation
    turns = []                                       # the two take turns until each has 8 outcomes
    for _ in range(16):
        ran, trials = a.choose("deliver", {"basket distance": "far"}, rng)
        turns.append(ran)
        a.record(trials, ran, ran != "deliver", False)
    assert turns.count("deliver") == turns.count("w_deliver_closer") == 8
    assert a.review(rng)[0]["status"] == "kept"
    for _ in range(40):                              # a kept skill stays under review
        a.record([trial], "w_deliver_closer", False, True)
        a.record([trial], "deliver", True, False)
    assert a.review(rng)[0]["status"] == "retired"
    assert a.choose("deliver", {"basket distance": "far"}, rng) == ("deliver", [])


def test_written_skills_persist_and_are_tried_in_the_next_episode(tmp_path):
    first = Mind(memory_dir=tmp_path)
    first.authoring.author = Scripted(GOOD)
    first.rules["effect"] = rules_with_weakness()
    first.outcomes = [{"skill": "deliver", "features": {"basket distance": "far"}, "status": "failed",
                       "reason": "basket moved", "held": False, "fell": False}] * 5
    first.close()
    assert first.stats["skills_written"] == 1
    again = Mind(memory_dir=tmp_path)
    assert "w_deliver_closer" in again.library and again.authoring.trials[0].counts["deliver"] == [0.0, 0.0, 0.0]
    assert failure_reasons(again.outcomes, "deliver", "basket distance", "far") == {"failed: basket moved": 5}


def test_a_relation_called_with_the_wrong_arguments_is_refused_at_load():
    import pytest
    library = Library()
    with pytest.raises(ValueError, match="seen_since"):
        library.add("w_bad", {"params": {}, "body": [{"call": "require", "args": {"condition": "seen_since(self, basket, 3) < 2"}}]})
    assert "w_bad" not in library


EVIDENCE = {"rate": 0.3, "n": 40, "rate_otherwise": 0.9, "n_otherwise": 40}


def test_malformed_programs_are_refused_not_crashed_on():
    """Review of E-019: shapes the runtime trusts are checked, so a program that breaks
    them is refused instead of crashing the reflection or the next room."""
    for body in ([{"call": "deliver", "args": []}], [{"if": True, "then": [{"call": "deliver"}]}],
                 [{"bind": "z", "to": 5}, {"call": "deliver"}], [{"call": "deliver", "until": True}],
                 [{"call": "deliver", "timeout": "5"}], [{"if": "true", "then": {"call": "deliver"}}]):
        library = Library()
        answer = {"name": "x", "doc": "d", "body": body, "reason": ""}
        entry = Authoring(author=Scripted(answer, answer)).propose("deliver", "basket distance", "far", EVIDENCE,
                                                                   {}, library)
        assert entry["status"] == "refused", body
        assert "w_x" not in library


def test_a_written_skill_that_calls_another_loads_whatever_their_names(tmp_path):
    """Review of E-019: skills are saved in name order, so a caller can sort before its callee."""
    library = Library()
    caller = {"name": "a first", "doc": "d", "body": [{"call": "w_deliver_closer"}], "reason": ""}
    a = Authoring(author=Scripted(GOOD, caller))
    a.propose("deliver", "basket distance", "far", EVIDENCE, {}, library)
    a.propose("deliver", "basket", "vague", EVIDENCE, {}, library)
    assert [t.child for t in a.trials] == ["w_deliver_closer", "w_a_first"]
    again, fresh = Authoring(), Library()
    again.load(a.to_json(), fresh)
    assert "w_a_first" in fresh and [t.status for t in again.trials] == ["trial", "trial"]


def test_overlapping_trials_both_run_where_their_situations_overlap():
    """Review of E-019: the first matching trial no longer takes every run in the overlap;
    a parent run counts in every trial whose situation held, a written run only in its own."""
    library = Library()
    other = {**GOOD, "name": "Deliver Vague"}
    a = Authoring(author=Scripted(GOOD, other))
    a.propose("deliver", "basket distance", "far", EVIDENCE, {}, library)
    a.propose("deliver", "basket", "vague", EVIDENCE, {}, library)
    rng, both = random.Random(3), {"basket distance": "far", "basket": "vague"}
    names = set()
    for _ in range(30):
        ran, trials = a.choose("deliver", both, rng)
        assert len(trials) == 2
        names.add(ran)
        a.record(trials, ran, True, False)
    assert names == {"deliver", "w_deliver_closer", "w_deliver_vague"}
    first, second = a.trials
    assert first.counts["deliver"] == second.counts["deliver"]
    assert "w_deliver_vague" not in first.counts


def test_a_written_variant_counts_as_a_try_of_its_parent_once():
    """Review of E-019: give-up, `target tried before` and the failed-pick measure count
    a run of `w_pick_*` as a pick, and a pick nested inside it as the same try."""
    from birdbrain.kr import KnowledgeBase
    from birdbrain.relations import attempts, failures
    kb = KnowledgeBase()
    outer = kb.begin("action", 0.0, ["toy#1"], skill="w_pick_x", depth=0, variant_of="pick")
    inner = kb.begin("action", 1.0, ["toy#1"], skill="pick", depth=1)
    kb.end(inner, 5.0, outcome="failed")
    kb.end(outer, 6.0, outcome="failed")
    plain = kb.begin("action", 7.0, ["toy#1"], skill="pick", depth=0)
    kb.end(plain, 9.0, outcome="failed")
    alone = kb.begin("action", 10.0, ["toy#1"], skill="w_pick_x", depth=0, variant_of="pick")
    kb.end(alone, 12.0, outcome="timeout")
    assert failures(kb, 12.0, "pick", "toy#1") == 3 and attempts(kb, 12.0, "pick", "toy#1") == 3


def test_written_skills_record_their_parent_in_action_events(tmp_path):
    library = Library()
    Authoring(author=Scripted(GOOD)).propose("deliver", "basket distance", "far", EVIDENCE, {}, library)
    assert library["w_deliver_closer"].variant_of == "deliver" and library["deliver"].variant_of is None


def test_a_kept_written_skill_can_be_improved_on():
    library = Library()
    a = Authoring(author=Scripted(GOOD, {**GOOD, "name": "closer still"}), min_trials=2)
    ev = {"rate": 0.3, "n": 40, "rate_otherwise": 0.9, "n_otherwise": 40}
    a.propose("deliver", "basket distance", "far", ev, {}, library)
    a.trials[0].status = "kept"
    rules = rules_with_weakness()
    rules.examples["w_deliver_closer"] = rules.examples.pop("deliver")
    assert a.weakness(rules, library)[0] == "w_deliver_closer"                  # kept: open to improvement
    a.propose("w_deliver_closer", "basket", "vague", ev, {}, library)
    ran, trials = a.choose("deliver", {"basket distance": "far", "basket": "vague"}, random.Random(0))
    assert ran in {"w_deliver_closer", "w_closer_still"} and len(trials) == 2
