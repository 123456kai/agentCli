from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, UTC
from pathlib import Path


@dataclass
class TutorMessage:
    """A single message in the tutor conversation."""
    role: str           # "tutor" | "user"
    content: str
    code_ref: dict[str, object] | None = None  # {file_path, line_start, line_end, graph_node_id}
    branch_id: str = ""                         # which branch this message belongs to
    parent_index: int = -1                      # index of parent message in branch tree
    active: bool = True                         # False = greyed out (old branch)
    timestamp: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "role": self.role,
            "content": self.content,
            "code_ref": self.code_ref,
            "branch_id": self.branch_id,
            "parent_index": self.parent_index,
            "active": self.active,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, d: dict[str, object]) -> "TutorMessage":
        return cls(
            role=str(d.get("role", "")),
            content=str(d.get("content", "")),
            code_ref=d.get("code_ref") if d.get("code_ref") else None,
            branch_id=str(d.get("branch_id", "")),
            parent_index=int(d.get("parent_index", -1)),
            active=bool(d.get("active", True)),
            timestamp=str(d.get("timestamp", "")),
        )


@dataclass
class Checkpoint:
    """A revert point in the conversation."""
    id: int
    message_index: int  # which message in _history this checkpoint marks
    label: str          # human-readable label (e.g. "反问: adapter.respond")


class CodeTutorContext:
    """Manages conversation history with checkpoint/revert capability.

    Inspired by kimi-cli's Context class. Key differences:
    - No _system_prompt / _usage record types (simpler scope)
    - Token count tracking via estimate (lightweight)
    - JSONL incremental writes: each append_message writes one line
    """

    def __init__(self, context_file: Path) -> None:
        self._context_file = context_file
        self._history: list[TutorMessage] = []
        self._checkpoints: list[Checkpoint] = []
        self._next_checkpoint_id = 0

    # ── Persistence ──

    def restore(self) -> None:
        """Load history from context.jsonl."""
        if not self._context_file.exists():
            return
        with open(self._context_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                role = str(record.get("role", ""))
                if role == "_checkpoint":
                    self._checkpoints.append(Checkpoint(
                        id=int(record.get("id", 0)),
                        message_index=int(record.get("message_index", 0)),
                        label=str(record.get("label", "")),
                    ))
                    self._next_checkpoint_id = max(
                        self._next_checkpoint_id,
                        int(record.get("id", 0)) + 1,
                    )
                else:
                    msg = TutorMessage.from_dict(record)
                    self._history.append(msg)

    def append_message(self, msg: TutorMessage) -> None:
        """Append a message to in-memory history and persist to JSONL."""
        msg.timestamp = datetime.now(UTC).isoformat()
        self._history.append(msg)
        record = msg.to_dict()
        self._context_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self._context_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            f.flush()

    # ── Checkpoint ──

    def checkpoint(self, label: str = "") -> Checkpoint:
        """Create a checkpoint at current history position.

        Call BEFORE the system asks a question, so the user can revert
        to this point if they change direction.
        """
        cp = Checkpoint(
            id=self._next_checkpoint_id,
            message_index=len(self._history),
            label=label,
        )
        self._next_checkpoint_id += 1
        self._checkpoints.append(cp)
        self._context_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self._context_file, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "role": "_checkpoint",
                "id": cp.id,
                "message_index": cp.message_index,
                "label": cp.label,
            }, ensure_ascii=False) + "\n")
            f.flush()
        return cp

    def revert_to(self, checkpoint_id: int) -> list[TutorMessage]:
        """Rollback to a checkpoint, marking subsequent messages as inactive.

        Returns the active message history after revert.
        """
        target_cp = None
        for cp in self._checkpoints:
            if cp.id == checkpoint_id:
                target_cp = cp
                break
        if target_cp is None:
            raise ValueError(f"Checkpoint {checkpoint_id} not found")

        for i in range(target_cp.message_index, len(self._history)):
            self._history[i].active = False

        self._rewrite_context_file()
        return [m for m in self._history if m.active]

    def _rewrite_context_file(self) -> None:
        """Rewrite context.jsonl from in-memory history + checkpoints."""
        tmp = self._context_file.with_suffix(".jsonl.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            for cp in self._checkpoints:
                f.write(json.dumps({
                    "role": "_checkpoint",
                    "id": cp.id,
                    "message_index": cp.message_index,
                    "label": cp.label,
                }, ensure_ascii=False) + "\n")
            for msg in self._history:
                f.write(json.dumps(msg.to_dict(), ensure_ascii=False) + "\n")
        tmp.replace(self._context_file)

    # ── Query ──

    def get_active_messages(self) -> list[TutorMessage]:
        return [m for m in self._history if m.active]

    def get_visited_nodes(self, max_nodes: int = 8) -> list[dict[str, str]]:
        """Return summary of visited code nodes for LLM context (sliding window)."""
        visited: list[dict[str, str]] = []
        for m in self._history:
            if m.role == "tutor" and m.code_ref and m.active:
                cr = m.code_ref
                visited.append({
                    "file": str(cr.get("file_path", "")),
                    "node": str(cr.get("graph_node_id", "")),
                    "summary": m.content[:100],
                })
        return visited[-max_nodes:]

    def get_breadcrumbs(self, domain_name: str = "") -> str:
        """Build breadcrumb string: 'Domain > node_1 > node_2 > ...'"""
        parts: list[str] = [domain_name] if domain_name else []
        for m in self._history:
            if m.role == "tutor" and m.code_ref and m.active:
                node_id = str(m.code_ref.get("graph_node_id", ""))
                if node_id:
                    short = node_id.split("::")[-1] if "::" in node_id else node_id
                    if short not in parts:
                        parts.append(short)
        return " > ".join(parts) if parts else "(起点)"

    def get_recent_context(self, max_turns: int = 6) -> list[dict[str, str]]:
        """Return recent active messages for LLM context."""
        active = self.get_active_messages()
        recent = active[-(max_turns * 2):]
        return [{"role": m.role, "content": m.content[:300]} for m in recent]

    @property
    def message_count(self) -> int:
        return len(self._history)

    @property
    def checkpoint_count(self) -> int:
        return len(self._checkpoints)
