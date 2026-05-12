from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Protocol
from uuid import uuid4

from pydantic import BaseModel, Field


class AgentEvent(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    type: str
    run_id: str
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    payload: dict[str, object] = Field(default_factory=dict)

    def to_sse(self) -> str:
        data = json.dumps(self.model_dump(), ensure_ascii=False, separators=(",", ":"))
        return f"event: {self.type}\ndata: {data}\n\n"


class EventSink(Protocol):
    def emit(self, event_type: str, *, run_id: str, **payload: object) -> AgentEvent:
        """Record an event and return the normalized event object."""


class NullEventSink:
    def emit(self, event_type: str, *, run_id: str, **payload: object) -> AgentEvent:
        return AgentEvent(type=event_type, run_id=run_id, payload=dict(payload))


class InMemoryEventSink:
    def __init__(self) -> None:
        self.events: list[AgentEvent] = []

    def emit(self, event_type: str, *, run_id: str, **payload: object) -> AgentEvent:
        event = AgentEvent(type=event_type, run_id=run_id, payload=dict(payload))
        self.events.append(event)
        return event
