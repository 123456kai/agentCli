from pydantic import BaseModel


class RunRequest(BaseModel):
    question: str


class RunResponse(BaseModel):
    run_id: str
    answer: str
