import { AgentEvent } from "../../api/events";

type AgentTimelineProps = {
  events: AgentEvent[];
};

export function AgentTimeline({ events }: AgentTimelineProps) {
  return (
    <div className="panel">
      <h3>Timeline</h3>
      <div className="timeline">
        {events.map((event) => (
          <div className={event.type === "run_error" ? "timelineItem timelineError" : "timelineItem"} key={event.id}>
            <div className="timelineType">{event.type}</div>
            <div className="timelinePayload">{summarize(event)}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function summarize(event: AgentEvent): string {
  if (event.type === "tool_started") return String(event.payload.tool_name ?? "tool");
  if (event.type === "file_opened") return String(event.payload.path ?? "file");
  if (event.type === "line_range_read") {
    return `${event.payload.path ?? ""}:${event.payload.start_line ?? "?"}-${event.payload.end_line ?? "?"}`;
  }
  if (event.type === "answer_final") return "Final answer received";
  if (event.type === "run_error") return String(event.payload.error ?? "Unknown error");
  return JSON.stringify(event.payload);
}
