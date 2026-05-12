from datetime import datetime, UTC
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from agentcli.analysis.models import AnalysisResult
from agentcli.knowledge.models import KnowledgeState


class SessionTurn(BaseModel):
    question: str
    answer: str
    conclusion: str
    key_files: list[str] = Field(default_factory=list)
    reading_order: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)


class AnalysisSession(BaseModel):
    session_id: str
    repo_root: str
    current_goal: str = ""
    created_at: str
    updated_at: str
    turns: list[SessionTurn] = Field(default_factory=list)
    claims: list[str] = Field(default_factory=list)
    evidence_index: list[str] = Field(default_factory=list)
    focus_stack: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    messages: list[dict[str, object]] = Field(default_factory=list)
    knowledge: KnowledgeState = Field(default_factory=KnowledgeState)

    @classmethod
    def new(cls, repo_root: Path) -> "AnalysisSession":
        timestamp = datetime.now(UTC).isoformat()
        return cls(
            session_id=uuid4().hex,
            repo_root=repo_root.resolve().as_posix(),
            created_at=timestamp,
            updated_at=timestamp,
        )

    def record_turn(self, question: str, result: AnalysisResult) -> None:
        if not self.current_goal:
            self.current_goal = question
        self.turns.append(
            SessionTurn(
                question=question,
                answer=result.answer,
                conclusion=result.conclusion,
                key_files=result.key_files,
                reading_order=result.reading_order,
                uncertainties=result.uncertainties,
            )
        )

        if result.conclusion and result.conclusion not in self.claims:
            self.claims.append(result.conclusion)

        evidence_ids: list[str] = []
        for path in result.key_files:
            if path not in self.evidence_index:
                self.evidence_index.append(path)
            evidence_ids.append(self.knowledge.add_file_evidence(path).id)

        if result.key_files:
            self.focus_stack = [result.key_files[0]]
        elif result.reading_order:
            self.focus_stack = [result.reading_order[0]]

        self.open_questions = list(result.uncertainties)
        self.knowledge.add_claim(result.conclusion, evidence_ids=evidence_ids)
        self.knowledge.replace_open_questions(result.uncertainties)
        self.knowledge.replace_next_actions(result.reading_order)
        self.knowledge.focus_stack = list(self.focus_stack)
        self.updated_at = datetime.now(UTC).isoformat()

    def render_summary(self) -> str:
        lines = [
            "Session summary:",
            f"- Previous turns: {len(self.turns)}",
        ]
        if self.focus_stack:
            lines.append(f"- Current focus: {', '.join(self.focus_stack[:3])}")
        if self.claims:
            lines.append(f"- Confirmed conclusions: {self.claims[-1]}")
        if self.open_questions:
            lines.append(f"- Open questions: {'; '.join(self.open_questions[:3])}")
        return "\n".join(lines)
