from pydantic import BaseModel


class RunRequest(BaseModel):
    question: str


class RunResponse(BaseModel):
    run_id: str
    answer: str


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
