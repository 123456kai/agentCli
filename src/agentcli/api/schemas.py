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


class GraphNode(BaseModel):
    id: str
    label: str
    path: str
    line: int
    kind: str
    degree: int = 0


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    relation: str = "calls"
    is_cycle: bool = False


class SkeletonResponse(BaseModel):
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    warning: str | None = None
    skipped_files: list[str] = []


class ExpandResponse(BaseModel):
    root: str
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []


class NodeDetailResponse(BaseModel):
    node: GraphNode | None = None
    incoming: list[GraphEdge] = []
    outgoing: list[GraphEdge] = []


class StorylineNodeSchema(BaseModel):
    order: int
    title: str
    file_path: str
    line_start: int
    line_end: int
    graph_node_id: str
    summary: str | None = None
    design_notes: str | None = None
    warnings: str | None = None
    next_teaser: str | None = None


class StorylineSchema(BaseModel):
    id: str
    title: str
    description: str
    theme: str = ""
    nodes: list[StorylineNodeSchema] = []
    node_count: int = 0
    estimated_minutes: int = 1
    file_count: int = 0


class StorylineListResponse(BaseModel):
    storylines: list[StorylineSchema]


class StorylineDetailResponse(BaseModel):
    id: str
    title: str
    description: str
    nodes: list[StorylineNodeSchema]
    node_count: int
    estimated_minutes: int
    file_count: int


class StorylineNodeResponse(BaseModel):
    node: StorylineNodeSchema
    source_code: str
    narrative: dict[str, str | None] | None = None


class StorylineGenerateRequest(BaseModel):
    description: str


class StorylineGenerateResponse(BaseModel):
    storyline: StorylineSchema
    status: str


class NodeAskRequest(BaseModel):
    question: str
    history: list[dict[str, str]] = []


class NodeAskResponse(BaseModel):
    answer: str
    source_refs: list[dict[str, object]] = []
    debug_context: str = ""  # temporary: full context sent to LLM


# ── CodeTutor schemas ──


class CodeTutorStartRequest(BaseModel):
    domain_id: str


class CodeTutorMessageRequest(BaseModel):
    session_id: str
    message: str


class CodeTutorCodeRef(BaseModel):
    file_path: str
    line_start: int
    line_end: int
    graph_node_id: str


class CodeTutorMessageResponse(BaseModel):
    session_id: str
    message: dict[str, object]
    breadcrumbs: str = ""


class CodeTutorSessionEntry(BaseModel):
    session_id: str
    domain_name: str
    updated_at: str
