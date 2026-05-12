import { useState } from "react";
import { AgentEvent, EvidenceItem } from "../../api/events";

type EvidencePanelProps = {
  events: AgentEvent[];
  onOpenEvidence: (evidence: EvidenceItem) => void;
};

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

function shortName(path: string): string {
  return path.split("/").at(-1) ?? path;
}

export function EvidencePanel({ events, onOpenEvidence }: EvidencePanelProps) {
  const claims = events.filter((event) => event.type === "claim_added");
  const evidence = events
    .filter((event) => event.type === "evidence_added" || event.type === "line_range_read")
    .map(toEvidence);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  return (
    <div className="panel evidencePanel">
      <h3>Evidence ({evidence.length})</h3>

      {claims.length > 0 && (
        <div className="evidenceSection">
          <div className="evidenceSectionLabel">Claims</div>
          {claims.map((claim) => (
            <div className="evidenceRow evidenceRowClaim" key={claim.id}>
              <span className="evidenceDot evidenceDotClaim" />
              <span className="evidenceText">{String(claim.payload.text ?? "")}</span>
            </div>
          ))}
        </div>
      )}

      {evidence.length === 0 ? (
        <p className="muted">Evidence items appear as the agent discovers them.</p>
      ) : (
        <div className="evidenceSection">
          <div className="evidenceSectionLabel">Sources</div>
          {evidence.slice(0, collapsedCount(expandedId, evidence)).map((item) => (
            <div key={item.id}>
              <button
                className="evidenceRow"
                onClick={() => {
                  setExpandedId(expandedId === item.id ? null : item.id);
                  onOpenEvidence(item);
                }}
                title={item.path}
              >
                <span className={`evidenceDot ${item.source === "tool" ? "evidenceDotTool" : "evidenceDotAnswer"}`} />
                <span className="evidenceFile">{shortName(item.path)}</span>
                {item.startLine && (
                  <span className="evidenceLines">
                    L{item.startLine}{item.endLine && item.endLine !== item.startLine ? `-${item.endLine}` : ""}
                  </span>
                )}
                <span className="evidenceTag">{item.source}</span>
              </button>
              {expandedId === item.id && item.quote && (
                <div className="evidenceQuote">
                  <pre>{item.quote}</pre>
                  <div className="evidenceQuotePath">{item.path}</div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function collapsedCount(expandedId: string | null, evidence: EvidenceItem[]): number {
  // always show all — the "collapse" is per-item detail, not list length
  return evidence.length;
}
