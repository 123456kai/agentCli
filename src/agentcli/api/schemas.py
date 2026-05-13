from pydantic import BaseModel


class RunRequest(BaseModel):
    question: str
    session_id: str | None = None


class RunResponse(BaseModel):
    run_id: str
    answer: str
    session_id: str | None = None


class SessionResponse(BaseModel):
    session_id: str | None = None


class ProjectResponse(BaseModel):
    repo_root: str
    name: str
    model: str
    file_count: int
    truncated: bool


class SaveNoteRequest(BaseModel):
    question: str
    answer: str
    title: str | None = None


class SaveNoteResponse(BaseModel):
    note_path: str


class TourStep(BaseModel):
    order: int
    title: str
    file: str
    description: str
    next_read: dict | None = None
    key_lines: str | None = None


class TourResponse(BaseModel):
    title: str
    steps: list[TourStep]
    warning: str | None = None
