"""Lifetimes (design section 5) and the Milestone 6 options: no memory, a changing owner."""

from birdbrain import run


def _fake_rooms(monkeypatch):
    calls = []

    def fake(seed, **kwargs):
        calls.append(kwargs)
        return {"seed": seed}

    monkeypatch.setattr(run, "run_one", fake)
    return calls


def test_owner_change_takes_effect_from_its_room(monkeypatch, tmp_path):
    calls = _fake_rooms(monkeypatch)
    rows = run.run_lifetime(3, 4, tmp_path, owner_change=(3, "hers"), owner="basket")
    assert [c["owner"] for c in calls] == ["basket", "basket", "hers", "hers"]
    assert all(r["ownerChangedAt"] == 3 for r in rows)
    assert [r["room_seed"] for r in rows] == [301, 302, 303, 304]


def test_agent_a_keeps_no_memory(monkeypatch):
    calls = _fake_rooms(monkeypatch)
    rows = run.run_lifetime(1, 2, None)
    assert [c["memory_dir"] for c in calls] == [None, None]
    assert not rows[0]["memoryKept"]
    assert "ownerChangedAt" not in rows[0]


def test_prospects_drop_poor_toys_unless_none_is_left():
    from birdbrain.goals import _prospects
    assert _prospects(["a", "b"], None) == ["a", "b"]
    assert _prospects(["a", "b"], lambda e: e == "a") == ["b"]
    assert _prospects(["a", "b"], lambda e: True) == ["a", "b"]
