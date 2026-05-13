export type AgentEvent = {
  id: string;
  type: string;
  run_id: string;
  created_at: string;
  payload: Record<string, unknown>;
};

export type RunStatus = "idle" | "running" | "finished" | "failed" | "cancelled";

export type SourceFile = {
  path: string;
  content: string;
  totalLines?: number;
};

export type HighlightedRange = {
  path: string;
  startLine: number;
  endLine: number;
};

export type EvidenceItem = {
  id: string;
  path: string;
  startLine?: number;
  endLine?: number;
  quote?: string;
  source?: string;
};

export function parseSseEvents(text: string): AgentEvent[] {
  return text
    .split("\n\n")
    .filter(Boolean)
    .map((chunk) => chunk.split("\n").find((line) => line.startsWith("data: ")))
    .filter((line): line is string => Boolean(line))
    .map((line) => JSON.parse(line.slice(6)) as AgentEvent);
}
