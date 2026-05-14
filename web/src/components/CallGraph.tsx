import { useRef } from "react";

import { useCallGraph } from "../graph/useCallGraph";

type CallGraphProps = {
  onOpenFile: (path: string, line?: number) => void;
};

export function CallGraph({ onOpenFile }: CallGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const { state, loadSkeleton, fit } = useCallGraph(containerRef, onOpenFile);
  const selected = state.selectedNode?.node;

  return (
    <div className="panel" style={{ display: "flex", flexDirection: "column", minHeight: 360 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
        <h3 style={{ margin: 0 }}>Call Graph</h3>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span className="muted" style={{ fontSize: 11 }}>
            {state.nodeCount} nodes / {state.edgeCount} edges
          </span>
          <button className="toolbar-btn" onClick={fit} type="button">
            Fit
          </button>
          <button className="toolbar-btn" disabled={state.isLoading} onClick={loadSkeleton} type="button">
            Refresh
          </button>
        </div>
      </div>

      {state.warning ? (
        <p className="muted" style={{ marginBottom: 0 }}>
          {state.warning}
        </p>
      ) : null}

      {state.skippedFiles.length > 0 ? (
        <p className="muted" style={{ marginBottom: 0 }}>
          Skipped {state.skippedFiles.length} file(s) with syntax or encoding errors.
        </p>
      ) : null}

      {state.error ? (
        <div style={{ marginTop: 8, color: "#f0a0a0", fontSize: 12 }}>
          {state.error}
        </div>
      ) : null}

      <div
        ref={containerRef}
        style={{
          flex: "1 1 260px",
          minHeight: 260,
          marginTop: 10,
          border: "1px solid var(--border)",
          borderRadius: 8,
          background: "#0b1020",
        }}
      />

      <div className="muted" style={{ marginTop: 8, fontSize: 11 }}>
        Double-click opens source. Right-click expands a node. Click selects details.
      </div>

      {selected ? (
        <div style={{ marginTop: 8, fontSize: 12 }}>
          <strong>{selected.label}</strong>
          <div className="muted">
            {selected.path}:{selected.line} · in {state.selectedNode?.incoming.length ?? 0} / out{" "}
            {state.selectedNode?.outgoing.length ?? 0}
          </div>
        </div>
      ) : null}
    </div>
  );
}
