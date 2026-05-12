import { useEffect, useRef, useState } from "react";
import { AgentEvent, RunStatus } from "../../api/events";

type AgentTimelineProps = {
  events: AgentEvent[];
  status: RunStatus;
};

function eventCategory(event: AgentEvent): string {
  if (event.type === "run_error") return "timelineItemError";
  if (event.type === "tool_started" || event.type === "tool_finished") return "timelineItemTool";
  if (event.type === "file_opened") return "timelineItemFile";
  if (event.type === "line_range_read") return "timelineItemRead";
  if (event.type === "answer_final") return "timelineItemAnswer";
  if (event.type === "claim_added" || event.type === "evidence_added") return "timelineItemClaim";
  return "";
}

function summarize(event: AgentEvent): string {
  if (event.type === "tool_started") return String(event.payload.tool_name ?? "tool");
  if (event.type === "tool_finished") {
    const tool = String(event.payload.tool_name ?? "tool");
    const result = event.payload.result as Record<string, unknown> | undefined;
    if (result?.kind) return `${tool} → ${result.kind}`;
    return `${tool} done`;
  }
  if (event.type === "file_opened") return String(event.payload.path ?? "file");
  if (event.type === "line_range_read") {
    const file = String(event.payload.path ?? "").split("/").at(-1) ?? "";
    return `${file}:${event.payload.start_line ?? "?"}-${event.payload.end_line ?? "?"}`;
  }
  if (event.type === "answer_final") return "Answer ready";
  if (event.type === "run_error") return String(event.payload.error ?? "Error");
  if (event.type === "claim_added") return String(event.payload.text ?? "Claim");
  if (event.type === "evidence_added") return String(event.payload.path ?? "Evidence");
  return event.type;
}

export function AgentTimeline({ events, status }: AgentTimelineProps) {
  const [collapsed, setCollapsed] = useState(false);
  const bodyRef = useRef<HTMLDivElement>(null);
  const prevLength = useRef(events.length);
  const [newItemIds, setNewItemIds] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (events.length > prevLength.current) {
      const fresh = new Set<string>();
      for (let i = prevLength.current; i < events.length; i++) {
        fresh.add(events[i].id);
      }
      setNewItemIds(fresh);
      const timer = setTimeout(() => setNewItemIds(new Set()), 400);
      prevLength.current = events.length;
      return () => clearTimeout(timer);
    }
    prevLength.current = events.length;
  }, [events]);

  useEffect(() => {
    if (!collapsed && bodyRef.current) {
      bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
    }
  }, [events, collapsed]);

  const isLive = status === "running";

  return (
    <div className="panel">
      <div className="timelineHeader" onClick={() => setCollapsed(!collapsed)}>
        <h3>
          Timeline
          {isLive && <span className="timelineLiveDot" />}
        </h3>
        <span className={`timelineCollapse ${!collapsed ? "timelineCollapseOpen" : ""}`}>
          ›
        </span>
      </div>
      <div
        ref={bodyRef}
        className={`timelineBody ${collapsed ? "timelineBodyCollapsed" : ""}`}
      >
        <div className="timeline">
          {events.map((event) => (
            <div
              className={`timelineItem ${eventCategory(event)} ${newItemIds.has(event.id) ? "timelineItemNew" : ""}`}
              key={event.id}
            >
              <div className="timelineConnector">
                <div className="timelineDot" />
                <div className="timelineLine" />
              </div>
              <div className="timelineCard">
                <div className="timelineType">{event.type.replace(/_/g, " ")}</div>
                <div className="timelinePayload">{summarize(event)}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
