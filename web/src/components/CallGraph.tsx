import { AgentEvent } from "../api/events";

type CallGraphProps = {
  events: AgentEvent[];
};

export function CallGraph({ events }: CallGraphProps) {
  const traceEvents = events.filter((event) => event.type === "tool_finished" && event.payload.tool_name === "trace_flow");

  return (
    <div className="panel">
      <h3>CallGraph</h3>
      {traceEvents.length === 0 ? <p className="muted">Trace results appear here when available.</p> : null}
      {traceEvents.map((event) => (
        <pre key={event.id}>{JSON.stringify(event.payload.result, null, 2)}</pre>
      ))}
    </div>
  );
}
