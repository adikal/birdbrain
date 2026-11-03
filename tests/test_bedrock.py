import pytest

from birdbrain.mind import DecisionRequest, ProviderError, ToolSpec
from birdbrain.providers.bedrock import BedrockProvider, tool_spec

REQUEST = DecisionRequest(1.0, "goal", "briefing", (
    ToolSpec("pick", "Pick a toy.", "holding(self, x)", {"x": ["toy#1", "toy#2"]}, 0.5, 0),
    ToolSpec("rest", "Rest.", "true", {}, 0.5, 0)))


class FakeClient:
    def __init__(self, response=None, error=None):
        self.response, self.error, self.calls = response, error, []

    def converse(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.response


def reply(*blocks):
    return {"output": {"message": {"content": list(blocks)}}, "usage": {"inputTokens": 100, "outputTokens": 20}}


def test_tool_schema_enumerates_entities_and_asks_for_p():
    spec = tool_spec(REQUEST.tools[0])["toolSpec"]
    props = spec["inputSchema"]["json"]["properties"]
    assert props["x"]["enum"] == ["toy#1", "toy#2"] and "p" in props and "reason" in props
    assert "holding(self, x)" in spec["description"]


def test_choice_is_parsed_from_the_tool_call():
    client = FakeClient(reply({"text": "thinking"},
                              {"toolUse": {"name": "pick", "toolUseId": "1",
                                           "input": {"x": "toy#2", "p": 0.7, "reason": "close"}}}))
    choice = BedrockProvider(client=client, model="m").choose(REQUEST)
    assert (choice.skill, choice.args, choice.p, choice.reason) == ("pick", {"x": "toy#2"}, 0.7, "close")
    assert choice.usage == {"input": 100, "output": 20}
    assert client.calls[0]["toolConfig"]["toolChoice"] == {"auto": {}}


def test_missing_tool_call_and_errors_become_categories():
    with pytest.raises(ProviderError, match="no_tool_call"):
        BedrockProvider(client=FakeClient(reply({"text": "no"})), model="m").choose(REQUEST)

    class Throttled(Exception):
        def __init__(self):
            super().__init__("secret details")
            self.response = {"Error": {"Code": "ThrottlingException", "Message": "secret details"}}

    with pytest.raises(ProviderError) as info:
        BedrockProvider(client=FakeClient(error=Throttled()), model="m").choose(REQUEST)
    assert info.value.category == "throttled" and "secret" not in str(info.value)
