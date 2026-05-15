import { AgentEvent, SourceFile } from "./events";
import type { ExpandData, NodeDetailData, SkeletonData } from "../graph/types";
import type {
  StorylineListResponse,
  StorylineDetailResponse,
  StorylineNodeResponse,
  StorylineGenerateResponse,
  NodeAskResponse,
} from "../components/coderead/types";

export type RunResult = {
  runId: string;
  answer: string;
  events: AgentEvent[];
};

export type ProjectInfo = {
  repoRoot: string;
  name: string;
  model: string;
  fileCount: number;
  truncated: boolean;
};

export type FileSearchResult = {
  matches: string[];
  totalMatches: number;
  truncated: boolean;
};

export async function runAnalysis(question: string, sessionId: string): Promise<RunResult> {
  const events: AgentEvent[] = [];
  const { runId, answer } = await streamRunAnalysis(question, sessionId, (event) => events.push(event));
  return { runId, answer, events };
}

export async function streamRunAnalysis(
  question: string,
  sessionId: string,
  onEvent: (event: AgentEvent) => void,
): Promise<{ runId: string; answer: string; sessionId: string }> {
  const response = await fetch("/api/runs", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ question, session_id: sessionId }),
  });
  const payload = await response.json();
  let answer = "";
  await new Promise<void>((resolve, reject) => {
    const source = new EventSource(`/api/runs/${payload.run_id}/events`);
    const handle = (event: MessageEvent) => {
      const parsed = JSON.parse(event.data) as AgentEvent;
      onEvent(parsed);
      if (parsed.type === "answer_final") {
        answer = String(parsed.payload.answer ?? "");
      }
    };
    [
      "run_started",
      "project_map_ready",
      "reading_plan_created",
      "tool_started",
      "tool_finished",
      "file_opened",
      "line_range_read",
      "claim_added",
      "evidence_added",
      "open_question_added",
      "answer_final",
      "run_error",
    ].forEach((type) => source.addEventListener(type, handle));
    source.addEventListener("run_finished", (event) => {
      handle(event);
      source.close();
      resolve();
    });
    source.onerror = () => {
      source.close();
      reject(new Error("SSE stream failed"));
    };
  });
  return { runId: payload.run_id, answer, sessionId: String(payload.session_id ?? sessionId) };
}

export async function startRun(question: string, sessionId: string): Promise<{ runId: string; sessionId: string }> {
  const response = await fetch("/api/runs", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ question, session_id: sessionId }),
  });
  const payload = await response.json();
  return {
    runId: String(payload.run_id),
    sessionId: String(payload.session_id ?? sessionId),
  };
}

export function subscribeRunEvents(
  runId: string,
  onEvent: (event: AgentEvent) => void,
  onDone: () => void,
  onError: (error: Error) => void,
): EventSource {
  const source = new EventSource(`/api/runs/${runId}/events`);
  const handle = (event: MessageEvent) => {
    onEvent(JSON.parse(event.data) as AgentEvent);
  };
  [
    "run_started",
    "project_map_ready",
    "reading_plan_created",
    "tool_started",
    "tool_finished",
    "file_opened",
    "line_range_read",
    "claim_added",
    "evidence_added",
    "open_question_added",
    "answer_final",
    "run_error",
  ].forEach((type) => source.addEventListener(type, handle));
  source.addEventListener("run_finished", (event) => {
    handle(event);
    source.close();
    onDone();
  });
  source.onerror = () => {
    source.close();
    onError(new Error("SSE stream failed"));
  };
  return source;
}

export async function readSourceFile(path: string, lineOffset = 1): Promise<SourceFile> {
  const response = await fetch(`/api/file?path=${encodeURIComponent(path)}&line_offset=${lineOffset}`);
  const payload = await response.json();
  return {
    path: String(payload.path ?? path),
    content: String(payload.content ?? ""),
    totalLines: Number(payload.total_lines ?? 0) || undefined,
  };
}

export async function searchProjectFiles(pattern = ""): Promise<string[]> {
  const params = pattern ? `?pattern=${encodeURIComponent(pattern)}` : "";
  const response = await fetch(`/api/files${params}`);
  const payload = await response.json();
  return Array.isArray(payload.matches) ? payload.matches.map(String) : [];
}

export async function searchProjectFilesDetailed(pattern = ""): Promise<FileSearchResult> {
  const params = pattern ? `?pattern=${encodeURIComponent(pattern)}` : "";
  const response = await fetch(`/api/files${params}`);
  const payload = await response.json();
  return {
    matches: Array.isArray(payload.matches) ? payload.matches.map(String) : [],
    totalMatches: Number(payload.total_matches ?? 0),
    truncated: Boolean(payload.truncated),
  };
}

export async function getProjectInfo(): Promise<ProjectInfo> {
  const response = await fetch("/api/project");
  const payload = await response.json();
  return {
    repoRoot: String(payload.repo_root ?? ""),
    name: String(payload.name ?? ""),
    model: String(payload.model ?? ""),
    fileCount: Number(payload.file_count ?? 0),
    truncated: Boolean(payload.truncated),
  };
}

export async function getLatestSession(): Promise<string | null> {
  const response = await fetch("/api/sessions/latest");
  const payload = await response.json();
  const sessionId = payload.session_id;
  if (!sessionId) return null;
  return String(sessionId);
}

export async function createSession(): Promise<string> {
  const response = await fetch("/api/sessions", { method: "POST" });
  const payload = await response.json();
  return String(payload.session_id);
}

export async function cancelRun(runId: string): Promise<void> {
  await fetch(`/api/runs/${runId}/cancel`, { method: "POST" });
}

export async function saveAnalysisNote(question: string, answer: string): Promise<string> {
  const response = await fetch("/api/notes", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ question, answer }),
  });
  const payload = await response.json();
  return String(payload.note_path ?? "");
}

async function readJsonResponse<T>(response: Response, fallbackMessage: string): Promise<T> {
  if (!response.ok) {
    throw new Error(`${fallbackMessage}: ${response.status}`);
  }
  return (await response.json()) as T;
}

export async function fetchGraphSkeleton(signal?: AbortSignal): Promise<SkeletonData> {
  const response = await fetch("/api/graph/skeleton", { signal });
  return readJsonResponse<SkeletonData>(response, "Failed to load graph skeleton");
}

export async function fetchGraphExpand(nodeId: string, depth = 3, signal?: AbortSignal): Promise<ExpandData> {
  const params = new URLSearchParams({ node_id: nodeId, depth: String(depth) });
  const response = await fetch(`/api/graph/expand?${params.toString()}`, { signal });
  return readJsonResponse<ExpandData>(response, "Failed to expand graph node");
}

export async function fetchGraphNode(nodeId: string, signal?: AbortSignal): Promise<NodeDetailData> {
  const params = new URLSearchParams({ node_id: nodeId });
  const response = await fetch(`/api/graph/node?${params.toString()}`, { signal });
  return readJsonResponse<NodeDetailData>(response, "Failed to load graph node");
}

export async function fetchStorylines(signal?: AbortSignal): Promise<StorylineListResponse> {
  const response = await fetch("/api/storylines", { signal });
  return readJsonResponse<StorylineListResponse>(response, "Failed to load storylines");
}

export async function fetchStorylineDetail(id: string, signal?: AbortSignal): Promise<StorylineDetailResponse> {
  const response = await fetch(`/api/storylines/${encodeURIComponent(id)}`, { signal });
  return readJsonResponse<StorylineDetailResponse>(response, "Failed to load storyline");
}

export async function fetchStorylineNode(
  storylineId: string,
  nodeId: string,
  signal?: AbortSignal,
): Promise<StorylineNodeResponse> {
  const url = `/api/storylines/${encodeURIComponent(storylineId)}/nodes/${encodeURIComponent(nodeId)}`;
  const response = await fetch(url, { signal });
  return readJsonResponse<StorylineNodeResponse>(response, "Failed to load node");
}

export async function generateStoryline(
  description: string,
  signal?: AbortSignal,
): Promise<StorylineGenerateResponse> {
  const response = await fetch("/api/storylines/generate", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ description }),
    signal,
  });
  return readJsonResponse<StorylineGenerateResponse>(response, "Failed to generate storyline");
}

export async function askAboutNode(
  storylineId: string,
  nodeId: string,
  question: string,
  history: { role: string; content: string }[] = [],
  signal?: AbortSignal,
): Promise<NodeAskResponse> {
  const url = `/api/storylines/${encodeURIComponent(storylineId)}/nodes/${encodeURIComponent(nodeId)}/ask`;
  const response = await fetch(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ question, history }),
    signal,
  });
  return readJsonResponse<NodeAskResponse>(response, "Failed to ask about node");
}
