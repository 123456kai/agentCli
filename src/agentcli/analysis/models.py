from typing import Literal

from pydantic import BaseModel, Field


class EvidenceRef(BaseModel):
    path: str
    start_line: int | None = None
    end_line: int | None = None
    quote: str | None = None
    tool: str | None = None
    step_index: int | None = None


class Claim(BaseModel):
    text: str
    confidence: Literal["high", "medium", "low"] = "medium"
    supporting_evidence: list[EvidenceRef] = Field(default_factory=list)
    contradicting_evidence: list[EvidenceRef] = Field(default_factory=list)


class ReadingPlan(BaseModel):
    steps: list[str] = Field(default_factory=list)


class OpenQuestion(BaseModel):
    question: str
    priority: Literal["high", "medium", "low"] = "medium"
    status: Literal["open", "resolved"] = "open"


class AnalysisResult(BaseModel):
    answer: str
    conclusion: str
    key_files: list[str] = Field(default_factory=list)
    reading_order: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)


class MapNode(BaseModel):
    path: str
    kind: Literal["directory", "file"] = "directory"
    role: str


class EntryCandidate(BaseModel):
    path: str
    reason: str
    confidence: Literal["high", "medium", "low"] = "medium"


class ProjectMap(BaseModel):
    repo_root: str
    tech_stack: list[str] = Field(default_factory=list)
    nodes: list[MapNode] = Field(default_factory=list)
    entry_candidates: list[EntryCandidate] = Field(default_factory=list)
    important_files: list[str] = Field(default_factory=list)
    test_directories: list[str] = Field(default_factory=list)


class CallChainStep(BaseModel):
    symbol: str
    path: str
    line: int
    confidence: Literal["high", "medium", "low"] = "medium"


class CallChain(BaseModel):
    symbol: str
    steps: list[CallChainStep] = Field(default_factory=list)
