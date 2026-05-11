import json
from pathlib import Path

from agentcli.session import AnalysisSession


class SessionStore:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root.resolve()
        self.sessions_dir = self.repo_root / ".agentcli" / "sessions"

    def save(self, session: AnalysisSession) -> Path:
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        path = self.sessions_dir / f"{session.session_id}.json"
        path.write_text(json.dumps(session.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def load(self, session_id: str) -> AnalysisSession | None:
        path = self.sessions_dir / f"{session_id}.json"
        if not path.exists():
            return None
        return AnalysisSession.model_validate_json(path.read_text(encoding="utf-8"))

    def load_latest(self) -> AnalysisSession | None:
        if not self.sessions_dir.exists():
            return None
        files = sorted(self.sessions_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not files:
            return None
        return AnalysisSession.model_validate_json(files[0].read_text(encoding="utf-8"))
