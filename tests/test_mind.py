from birdbrain.body import Observation
from birdbrain.kr import Position
from birdbrain.mind import Choice, Mind, ProviderError


class Scripted:
    name = "scripted"

    def __init__(self, choices):
        self.choices = list(choices)
        self.requests = []

    def choose(self, request):
        self.requests.append(request)
        item = self.choices.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def recorder():
    log = []
    return log, lambda kind, payload: log.append((kind, payload))


def observe(mind, t):
    return mind.step(Observation(t=t, odom=(0.0, 0.0, 0.0), speed=0.0, holding=False, reflex=None, bumped=False))


def with_toy(mind):
    toy = mind.kb.new_entity("toy", 0.0)
    mind.kb.tell("at", (toy,), Position.round(0.5, 0.0, 0.02), t=0.0, conf=1.0)
    return toy


def test_valid_cloud_choice_is_executed_and_logged():
    log = []
    provider = Scripted([Choice("rest", {}, "tired", p=0.9, provider="scripted")] * 3)
    mind = Mind(provider=provider, log=lambda k, p: log.append((k, p)))
    observe(mind, 0.0)
    decision = next(p for k, p in log if k == "DECISION")
    assert decision["skill"] == "rest" and decision["fallback"] is None and decision["p_model"] == 0.9
    assert mind.stats == {"decisions": 1, "fallbacks": 0, "invalid": 0, "provider_errors": 0}


def test_invalid_choices_never_reach_the_body():
    for bad in (Choice("fly", {}, "?", provider="s"),                       # unknown tool
                Choice("pick", {"x": "toy#99"}, "?", provider="s"),          # unknown entity
                Choice("rest", {}, "?", p=1.7, provider="s")):               # not a probability
        log, record = recorder()
        mind = Mind(provider=Scripted([bad]), log=record)
        with_toy(mind)
        observe(mind, 0.0)
        decision = next(p for k, p in log if k == "DECISION")
        assert decision["provider"] == "local" and decision["fallback"].startswith("invalid")
        assert mind.stats["invalid"] == 1 and any(k == "CHOICE_REJECTED" for k, _ in log)


def test_provider_errors_and_budget_fall_back():
    mind = Mind(provider=Scripted([ProviderError("throttled")]))
    observe(mind, 0.0)
    assert mind.stats["provider_errors"] == 1 and mind.stats["fallbacks"] == 1
    spent = Mind(provider=Scripted([]), token_budget=0)
    observe(spent, 0.0)
    assert spent.stats["fallbacks"] == 1


def test_outcome_scores_the_structured_prediction():
    log = []
    mind = Mind(provider=Scripted([Choice("rest", {}, "r", p=0.25, provider="s")] * 3),
                log=lambda k, p: log.append((k, p)))
    t = 0.0
    while not any(k == "OUTCOME" for k, _ in log):
        observe(mind, t)
        t += 0.02
    outcome = next(p for k, p in log if k == "OUTCOME")
    assert outcome["expect"] == "true" and outcome["effect_held"] is True
    assert abs(outcome["surprise_model"] - 1.3863) < 1e-3          # -ln(0.25)
    assert mind.records["rest"].trials == 1


def test_briefing_mentions_known_objects_and_tools_need_known_targets():
    mind = Mind(provider=Scripted([]))
    observe(mind, 0.0)
    assert "pick" not in [t.name for t in mind.request().tools]
    toy = with_toy(mind)
    request = mind.request()
    assert toy in request.briefing
    assert next(t for t in request.tools if t.name == "pick").params == {"x": [toy]}
