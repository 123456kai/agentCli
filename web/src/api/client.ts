import { AgentEvent, SourceFile } from "./events";

export type RunResult = {
  runId: string;
  answer: string;
  events: AgentEvent[];
};

export async function runAnalysis(question: string): Promise<RunResult> {
  const events: AgentEvent[] = [];
  const { runId, answer } = await streamRunAnalysis(question, (event) => events.push(event));
  return { runId, answer, events };
}

export async function streamRunAnalysis(
  question: string,
  onEvent: (event: AgentEvent) => void,
): Promise<{ runId: string; answer: string }> {
  const response = await fetch("/api/runs", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ question }),
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
  return { runId: payload.run_id, answer };
}

export async function startRun(question: string): Promise<string> {
  const response = await fetch("/api/runs", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ question }),
  });
  const payload = await response.json();
  return String(payload.run_id);
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
