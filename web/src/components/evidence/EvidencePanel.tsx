import { AgentEvent, EvidenceItem } from "../../api/events";

type EvidencePanelProps = {
  events: AgentEvent[];
  onOpenEvidence: (evidence: EvidenceItem) => void;
};

export function EvidencePanel({ events, onOpenEvidence }: EvidencePanelProps) {
  const claims = events.filter((event) => event.type === "claim_added");
  const evidence = events
    .filter((event) => event.type === "evidence_added" || event.type === "line_range_read")
    .map(toEvidence);

  return (
    <div className="panel">
      <h3>Evidence</h3>
      {claims.map((claim) => (
        <div className="claimCard" key={claim.id}>
          <div className="cardLabel">Claim</div>
          <div>{String(claim.payload.text ?? "")}</div>
        </div>
      ))}
      {evidence.map((item) => (
        <button className="evidenceCard" key={item.id} onClick={() => onOpenEvidence(item)}>
          <div className="cardLabel">{item.source ?? "evidence"}</div>
          <div>{item.path}</div>
          {item.startLine ? <div className="muted">lines {item.startLine}-{item.endLine ?? item.startLine}</div> : null}
        </button>
      ))}
    </div>
  );
}

function toEvidence(event: AgentEvent): EvidenceItem {
  return {
    id: String(event.payload.id ?? event.id),
    path: String(event.payload.path ?? ""),
    startLine: event.payload.start_line ? Number(event.payload.start_line) : undefined,
    endLine: event.payload.end_line ? Number(event.payload.end_line) : undefined,
    quote: event.payload.quote ? String(event.payload.quote) : undefined,
    source: event.type === "line_range_read" ? "tool" : String(event.payload.source ?? "answer"),
  };
}
