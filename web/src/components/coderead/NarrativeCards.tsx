type NarrativeCardsProps = {
  narrative: {
    summary: string;
    design_notes: string;
    warnings: string | null;
  } | null;
  loading: boolean;
};

export function NarrativeCards({ narrative, loading }: NarrativeCardsProps) {
  if (loading) {
    return (
      <div style={{ padding: "12px 0" }}>
        <p className="muted" style={{ fontSize: 11 }}>AI 正在分析这段代码...</p>
        <div style={{ background: "#f3f4f6", borderRadius: 4, height: 4, overflow: "hidden", marginTop: 8 }}>
          <div style={{
            background: "var(--accent)",
            height: 4,
            width: "60%",
            borderRadius: 4,
            animation: "pulse 1s ease-in-out infinite",
          }} />
        </div>
      </div>
    );
  }

  if (!narrative) {
    return <p className="muted" style={{ fontSize: 11 }}>解释暂不可用</p>;
  }

  return (
    <div style={{ display: "grid", gap: 8 }}>
      <div style={{
        borderLeft: "2px solid var(--accent)",
        paddingLeft: 10,
        fontSize: 12,
        lineHeight: 1.6,
        color: "var(--text-body)",
      }}>
        <div style={{ fontSize: 10, fontWeight: 600, color: "var(--accent)", marginBottom: 2 }}>
          做什么
        </div>
        {narrative.summary}
      </div>

      <div style={{
        borderLeft: "2px solid #f59e0b",
        paddingLeft: 10,
        fontSize: 12,
        lineHeight: 1.6,
        color: "var(--text-body)",
      }}>
        <div style={{ fontSize: 10, fontWeight: 600, color: "#b45309", marginBottom: 2 }}>
          为什么这样设计
        </div>
        {narrative.design_notes}
      </div>

      {narrative.warnings ? (
        <div style={{
          borderLeft: "2px solid #ef4444",
          paddingLeft: 10,
          fontSize: 12,
          lineHeight: 1.6,
          color: "var(--text-body)",
          background: "#fef2f2",
          padding: "8px 10px",
          borderRadius: "0 4px 4px 0",
        }}>
          <div style={{ fontSize: 10, fontWeight: 600, color: "#b91c1c", marginBottom: 2 }}>
            注意
          </div>
          {narrative.warnings}
        </div>
      ) : null}
    </div>
  );
}
