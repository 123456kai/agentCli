from types import SimpleNamespace

from agentcli.llm.adapter import DeepSeekOpenAIAdapter


def test_deepseek_adapter_returns_tool_call(monkeypatch) -> None:
    fake_message = SimpleNamespace(
        content="",
        reasoning_content="thinking trace",
        tool_calls=[
            SimpleNamespace(
                id="call_1",
                function=SimpleNamespace(name="search_files", arguments='{"pattern": "main.py"}'),
            )
        ],
    )
    fake_response = SimpleNamespace(choices=[SimpleNamespace(message=fake_message)])

    class FakeClient:
        def __init__(self, api_key: str, base_url: str) -> None:
            self.chat = SimpleNamespace(
                completions=SimpleNamespace(create=lambda **kwargs: fake_response)
            )

    monkeypatch.setattr("agentcli.llm.adapter.OpenAI", FakeClient)
    adapter = DeepSeekOpenAIAdapter(
        api_key="test-key",
        base_url="https://api.deepseek.com",
        model="deepseek-v4-flash",
    )
    result = adapter.respond(
        messages=[{"role": "user", "content": "find entry"}],
        tools=[],
    )
    assert result["type"] == "tool_call"
    assert result["tool_name"] == "search_files"
    assert result["arguments"] == {"pattern": "main.py"}
    assert result["assistant_message"]["reasoning_content"] == "thinking trace"


def test_deepseek_adapter_returns_final_content(monkeypatch) -> None:
    fake_message = SimpleNamespace(content="real answer", tool_calls=None)
    fake_response = SimpleNamespace(choices=[SimpleNamespace(message=fake_message)])

    class FakeClient:
        def __init__(self, api_key: str, base_url: str) -> None:
            self.chat = SimpleNamespace(
                completions=SimpleNamespace(create=lambda **kwargs: fake_response)
            )

    monkeypatch.setattr("agentcli.llm.adapter.OpenAI", FakeClient)
    adapter = DeepSeekOpenAIAdapter(
        api_key="test-key",
        base_url="https://api.deepseek.com",
        model="deepseek-v4-flash",
    )
    result = adapter.respond(
        messages=[{"role": "user", "content": "find entry"}],
        tools=[],
    )
    assert result == {"type": "final", "content": "real answer"}
