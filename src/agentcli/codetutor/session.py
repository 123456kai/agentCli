from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, UTC
from pathlib import Path
from uuid import uuid4

from agentcli.codetutor.context import CodeTutorContext


@dataclass
class CodeTutorSession:
    """A CodeTutor conversation session.

    Each session has a directory:
        .agentcli/codetutor-sessions/{session_id}/
            context.jsonl    # conversation history (JSONL, incremental)
            state.json       # session metadata
    """
    session_id: str
    domain_id: str
    domain_name: str
    domain_description: str
    repo_root: str
    created_at: str
    updated_at: str = ""
    current_file: str = ""
    current_line_start: int = 0
    current_line_end: int = 0

    context: CodeTutorContext | None = field(default=None, repr=False)

    @classmethod
    def new(
        cls,
        repo_root: Path,
        domain_id: str,
        domain_name: str,
        domain_description: str,
    ) -> "CodeTutorSession":
        session_id = uuid4().hex[:12]
        timestamp = datetime.now(UTC).isoformat()
        session_dir = cls._session_dir(repo_root, session_id)
        session_dir.mkdir(parents=True, exist_ok=True)
        return cls(
            session_id=session_id,
            domain_id=domain_id,
            domain_name=domain_name,
            domain_description=domain_description,
            repo_root=repo_root.resolve().as_posix(),
            created_at=timestamp,
            updated_at=timestamp,
        )

    @staticmethod
    def _session_dir(repo_root: Path, session_id: str) -> Path:
        return repo_root / ".agentcli" / "codetutor-sessions" / session_id

    @property
    def session_dir(self) -> Path:
        return self._session_dir(Path(self.repo_root), self.session_id)

    @property
    def context_file(self) -> Path:
        return self.session_dir / "context.jsonl"

    @property
    def state_file(self) -> Path:
        return self.session_dir / "state.json"

    def get_context(self) -> CodeTutorContext:
        """Get or lazily load the conversation context."""
        if self.context is None:
            self.context = CodeTutorContext(self.context_file)
            self.context.restore()
        return self.context

    def save_state(self) -> None:
        """Persist session metadata to state.json (atomic write)."""
        self.updated_at = datetime.now(UTC).isoformat()
        state = {
            "session_id": self.session_id,
            "domain_id": self.domain_id,
            "domain_name": self.domain_name,
            "domain_description": self.domain_description,
            "repo_root": self.repo_root,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "current_file": self.current_file,
            "current_line_start": self.current_line_start,
            "current_line_end": self.current_line_end,
        }
        self.session_dir.mkdir(parents=True, exist_ok=True)
        tmp = self.state_file.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        tmp.replace(self.state_file)

    @classmethod
    def load(cls, repo_root: Path, session_id: str) -> "CodeTutorSession | None":
        state_file = cls._session_dir(repo_root, session_id) / "state.json"
        if not state_file.exists():
            return None
        state = json.loads(state_file.read_text(encoding="utf-8"))
        return cls(
            session_id=state["session_id"],
            domain_id=state["domain_id"],
            domain_name=state["domain_name"],
            domain_description=state["domain_description"],
            repo_root=state["repo_root"],
            created_at=state["created_at"],
            updated_at=state.get("updated_at", ""),
            current_file=state.get("current_file", ""),
            current_line_start=state.get("current_line_start", 0),
            current_line_end=state.get("current_line_end", 0),
        )

    @classmethod
    def list_sessions(cls, repo_root: Path) -> list[dict[str, str]]:
        sessions_dir = repo_root / ".agentcli" / "codetutor-sessions"
        if not sessions_dir.exists():
            return []
        result: list[dict[str, str]] = []
        for d in sorted(
            sessions_dir.iterdir(),
            key=lambda p: p.stat().st_mtime, reverse=True,
        ):
            if d.is_dir() and (d / "state.json").exists():
                try:
                    st = json.loads((d / "state.json").read_text(encoding="utf-8"))
                    result.append({
                        "session_id": st.get("session_id", d.name),
                        "domain_name": st.get("domain_name", ""),
                        "updated_at": st.get("updated_at", ""),
                    })
                except (json.JSONDecodeError, OSError):
                    pass
        return result
