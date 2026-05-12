import { AgentEvent } from "../api/events";

type EvidencePanelProps = {
  events: AgentEvent[];
};

export function EvidencePanel({ events }: EvidencePanelProps) {
  const evidenceEvents = events.filter((event) =>
    ["file_opened", "line_range_read", "evidence_added", "claim_added"].includes(event.type),
  );

  return (
    <section>
      <h2>EvidencePanel</h2>
      {evidenceEvents.length === 0 ? <p className="muted">Evidence appears here as files are read.</p> : null}
      {evidenceEvents.map((event) => (
        <div className="event" key={event.id}>
          <strong>{event.type}</strong>
          <pre>{JSON.stringify(event.payload, null, 2)}</pre>
        </div>
      ))}
    </section>
  );
}
