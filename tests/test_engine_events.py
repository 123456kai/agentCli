from agentcli.engine.events import AgentEvent, InMemoryEventSink


def test_in_memory_event_sink_records_serializable_events() -> None:
    sink = InMemoryEventSink()

    event = sink.emit("tool_started", run_id="run_1", step=1, tool_name="read_file")

    assert isinstance(event, AgentEvent)
    assert event.type == "tool_started"
    assert event.run_id == "run_1"
    assert event.payload == {"step": 1, "tool_name": "read_file"}
    assert sink.events == [event]
    assert event.to_sse().startswith("event: tool_started\n")
    assert '"tool_name":"read_file"' in event.to_sse()
