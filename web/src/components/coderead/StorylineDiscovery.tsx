import type { Storyline } from "./types";

type StorylineDiscoveryProps = {
  storylines: Storyline[];
  loading: boolean;
  error: string | null;
  onSelect: (storyline: Storyline) => void;
  onRefresh: () => void;
};

export function StorylineDiscovery({
  storylines,
  loading,
  error,
  onSelect,
  onRefresh,
}: StorylineDiscoveryProps) {
  return (
    <div className="panel" style={{ display: "flex", flexDirection: "column" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
        <h3 style={{ margin: 0, fontSize: 14 }}>代码研读</h3>
        <button className="toolbar-btn" onClick={onRefresh} disabled={loading} type="button">
          {loading ? "加载中..." : "刷新"}
        </button>
      </div>

      {error ? (
        <p style={{ color: "#b91c1c", fontSize: 12 }}>{error}</p>
      ) : null}

      {loading ? (
        <p className="muted">正在发现可用主线...</p>
      ) : storylines.length === 0 ? (
        <p className="muted">暂无可读主线。项目可能需要更多 Python 文件来生成阅读路径。</p>
      ) : (
        <div style={{ display: "grid", gap: 8 }}>
          {storylines.map((s) => (
            <button
              key={s.id}
              onClick={() => onSelect(s)}
              style={{
                textAlign: "left",
                padding: "10px 12px",
                border: "1px solid var(--border)",
                borderRadius: "var(--radius-md)",
                background: "#fff",
                cursor: "pointer",
                transition: "border-color 0.15s, box-shadow 0.15s",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = "var(--accent)";
                e.currentTarget.style.boxShadow = "0 0 0 2px rgba(37,99,235,0.1)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = "var(--border)";
                e.currentTarget.style.boxShadow = "none";
              }}
            >
              <div style={{ fontWeight: 600, fontSize: 13, color: "var(--text-body)" }}>
                {s.title}
              </div>
              <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 2 }}>
                {s.description}
              </div>
              <div style={{ display: "flex", gap: 12, marginTop: 6, fontSize: 10, color: "#9ca3af" }}>
                <span>{s.node_count} 个节点</span>
                <span>约 {s.estimated_minutes} 分钟</span>
                <span>{s.file_count} 个文件</span>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
