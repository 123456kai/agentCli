from __future__ import annotations

from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class Evidence(BaseModel):
    id: str = Field(default_factory=lambda: f"ev_{uuid4().hex[:12]}")
    path: str
    start_line: int | None = None
    end_line: int | None = None
    quote: str | None = None
    source: str = "analysis"


class Claim(BaseModel):
    id: str = Field(default_factory=lambda: f"claim_{uuid4().hex[:12]}")
    text: str
    confidence: Literal["high", "medium", "low"] = "medium"
    evidence_ids: list[str] = Field(default_factory=list)


class OpenQuestion(BaseModel):
    id: str = Field(default_factory=lambda: f"oq_{uuid4().hex[:12]}")
    text: str
    priority: Literal["high", "medium", "low"] = "medium"
    status: Literal["open", "resolved"] = "open"


class NextAction(BaseModel):
    id: str = Field(default_factory=lambda: f"next_{uuid4().hex[:12]}")
    text: str
    target: str | None = None


class KnowledgeState(BaseModel):
    claims: list[Claim] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    files_read: list[str] = Field(default_factory=list)
    open_questions: list[OpenQuestion] = Field(default_factory=list)
    next_actions: list[NextAction] = Field(default_factory=list)
    focus_stack: list[str] = Field(default_factory=list)

    def add_file_evidence(self, path: str) -> Evidence:
        for existing in self.evidence:
            if existing.path == path and existing.start_line is None and existing.end_line is None:
                return existing
        evidence = Evidence(path=path)
        self.evidence.append(evidence)
        if path not in self.files_read:
            self.files_read.append(path)
        return evidence

    def add_claim(self, text: str, evidence_ids: list[str] | None = None) -> None:
        if not text:
            return
        for existing in self.claims:
            if existing.text == text:
                for evidence_id in evidence_ids or []:
                    if evidence_id not in existing.evidence_ids:
                        existing.evidence_ids.append(evidence_id)
                return
        self.claims.append(Claim(text=text, evidence_ids=evidence_ids or []))

    def replace_open_questions(self, questions: list[str]) -> None:
        self.open_questions = [OpenQuestion(text=question) for question in questions if question]

    def replace_next_actions(self, paths: list[str]) -> None:
        self.next_actions = [NextAction(text=f"Read {path}", target=path) for path in paths if path]
