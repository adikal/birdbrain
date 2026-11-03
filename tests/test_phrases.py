import pytest

from birdbrain.phrases import load


def test_builtin_phrases_read_as_approval_and_disapproval():
    phrases = load()
    assert phrases.valence("Nice!") == 1
    assert phrases.valence("Well done.") == 1
    assert phrases.valence("I don't like that") == -1
    assert phrases.valence("Don’t do that!") == -1
    assert phrases.valence("nice try") == 0              # whole utterances only
    assert phrases.valence("where is the ball") == 0


def test_another_list_can_be_used_without_editing_code(tmp_path, monkeypatch):
    path = tmp_path / "phrases.toml"
    path.write_text('[positive]\nphrases = ["bravo"]\n[negative]\nphrases = ["nein"]\n', encoding="utf-8")
    monkeypatch.setenv("BIRDBRAIN_PHRASES", str(path))
    phrases = load()
    assert phrases.valence("Bravo!") == 1 and phrases.valence("nein") == -1 and phrases.valence("nice") == 0


def test_a_phrase_on_both_lists_is_an_error(tmp_path):
    path = tmp_path / "phrases.toml"
    path.write_text('[positive]\nphrases = ["ok"]\n[negative]\nphrases = ["OK!"]\n', encoding="utf-8")
    with pytest.raises(ValueError, match="both"):
        load(path)
