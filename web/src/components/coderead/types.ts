export type StorylineNode = {
  order: number;
  title: string;
  file_path: string;
  line_start: number;
  line_end: number;
  graph_node_id: string;
  summary: string | null;
  design_notes: string | null;
  warnings: string | null;
  next_teaser: string | null;
};

export type Storyline = {
  id: string;
  title: string;
  description: string;
  theme: string;
  nodes: StorylineNode[];
  node_count: number;
  estimated_minutes: number;
  file_count: number;
};

export type StorylineListResponse = {
  storylines: Storyline[];
};

export type StorylineDetailResponse = Storyline;

export type StorylineNodeResponse = {
  node: StorylineNode;
  source_code: string;
  narrative: {
    summary: string;
    design_notes: string;
    warnings: string | null;
    next_teaser?: string | null;
  } | null;
};

export type StorylineGenerateResponse = {
  storyline: Storyline;
  status: "ready" | "generating";
};

export type NodeAskResponse = {
  answer: string;
  source_refs: { path: string; line_start: number; line_end: number }[];
};

export type ReadingState = "discovery" | "reading" | "complete" | "tutor";

// ── CodeTutor types ──

export type TutorCodeRef = {
  file_path: string;
  line_start: number;
  line_end: number;
  graph_node_id: string;
};

export type TutorMessage = {
  role: "tutor" | "user";
  content: string;
  code_ref: TutorCodeRef | null;
  branch_id: string;
  parent_index: number;
  active: boolean;
  timestamp: string;
};

export type CodeTutorStartResponse = {
  session_id: string;
  message: TutorMessage;
  breadcrumbs: string;
};

export type CodeTutorMessageResponse = {
  session_id: string;
  message: TutorMessage;
  breadcrumbs: string;
};
