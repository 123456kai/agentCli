import type { Storyline } from "./types";

type StorylineDiscoveryProps = {
  storylines: Storyline[];
  loading: boolean;
  error: string | null;
  onSelect: (storyline: Storyline) => void;
  onRefresh: () => void;
  onStartTutor?: (domainId: string, domainName: string) => void;
  enhancementState?: {
    enhancing: boolean;
    enhancedCount: number;
    totalNodes: number;
    complete: boolean;
  };
};

export function StorylineDiscovery({
  storylines,
  loading,
  error,
  onSelect,
  onRefresh,
  onStartTutor,
  enhancementState,
}: StorylineDiscoveryProps) {
  return (
    <div className="panel" style={{ display: "flex", flexDirection: "column" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
        <div>
          <h3 style={{ margin: 0, fontSize: 14 }}>代码研读</h3>
          <p className="muted" style={{ margin: "2px 0 0", fontSize: 10 }}>
            选择一条主线，AI 带你逐段阅读源码
          </p>
        </div>
        <button className="toolbar-btn" onClick={onRefresh} disabled={loading} type="button">
          {loading ? "加载中..." : "刷新"}
        </button>
      </div>

      {enhancementState?.enhancing && (
        <div style={{
          fontSize: 10,
          color: "var(--text-muted)",
          marginBottom: 8,
          display: "flex",
          alignItems: "center",
          gap: 6,
        }}>
          <span style={{
            display: "inline-block",
            width: 8,
            height: 8,
            borderRadius: 99,
            background: "var(--accent)",
            animation: "pulse 1s ease-in-out infinite",
          }} />
          AI 正在增强节点叙事...
          {enhancementState.enhancedCount > 0 && (
            <span>
              ({enhancementState.enhancedCount}/{enhancementState.totalNodes})
            </span>
          )}
        </div>
      )}
      {enhancementState?.complete && enhancementState.enhancedCount > 0 && (
        <div style={{ fontSize: 10, color: "#059669", marginBottom: 8 }}>
          全部 {enhancementState.enhancedCount} 个节点已增强
        </div>
      )}

      {error ? (
        <p style={{ color: "#b91c1c", fontSize: 12 }}>{error}</p>
      ) : null}

      {loading ? (
        <p className="muted">正在发现可用主线...</p>
      ) : storylines.length === 0 ? (
        <p className="muted">暂无可读主线。项目可能需要更多 Python 文件来生成阅读路径。</p>
      ) : (
        <div style={{ display: "grid", gap: 8 }}>
          {storylines.map((s, idx) => (
            <button
              key={s.id}
              onClick={() => onSelect(s)}
              style={{
                textAlign: "left",
                padding: "10px 12px",
                border: `1px solid ${idx === 0 ? "var(--accent)" : "var(--border)"}`,
                borderRadius: 8,
                background: idx === 0 ? "#f8faff" : "#fff",
                cursor: "pointer",
                transition: "border-color 0.15s, box-shadow 0.15s, background 0.15s",
                position: "relative",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = "var(--accent)";
                e.currentTarget.style.boxShadow = "0 0 0 2px rgba(37,99,235,0.08)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = idx === 0 ? "var(--accent)" : "var(--border)";
                e.currentTarget.style.boxShadow = "none";
              }}
            >
              {idx === 0 && (
                <span style={{
                  position: "absolute",
                  top: 6,
                  right: 8,
                  fontSize: 9,
                  background: "var(--accent)",
                  color: "#fff",
                  padding: "1px 6px",
                  borderRadius: 99,
                }}>
                  推荐
                </span>
              )}
              <div style={{ fontWeight: 600, fontSize: 13, color: "var(--text-body)", paddingRight: idx === 0 ? 50 : 0 }}>
                {s.title}
              </div>
              <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 2, lineHeight: 1.5 }}>
                {s.description}
              </div>
              <div style={{ display: "flex", gap: 12, marginTop: 6, fontSize: 10 }}>
                <span style={{ color: "#6366f1", background: "#eef2ff", padding: "1px 6px", borderRadius: 99 }}>
                  {s.node_count} 节点
                </span>
                <span style={{ color: "#059669", background: "#ecfdf5", padding: "1px 6px", borderRadius: 99 }}>
                  ~{s.estimated_minutes} 分钟
                </span>
                <span style={{ color: "#d97706", background: "#fffbeb", padding: "1px 6px", borderRadius: 99 }}>
                  {s.file_count} 文件
                </span>
              </div>
              {/* Node chain preview */}
              <div style={{
                display: "flex",
                alignItems: "center",
                gap: 4,
                marginTop: 6,
                flexWrap: "wrap",
              }}>
                {s.nodes.slice(0, 5).map((n, i) => (
                  <span key={i} style={{ display: "flex", alignItems: "center", gap: 4 }}>
                    <span style={{
                      fontSize: 9,
                      color: i === 0 ? "var(--text-body)" : "var(--text-muted)",
                      background: i === 0 ? "#f3f4f6" : "transparent",
                      padding: "1px 4px",
                      borderRadius: 3,
                      maxWidth: 100,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}>
                      {n.title}
                    </span>
                    {i < Math.min(s.nodes.length, 5) - 1 && (
                      <span style={{ color: "var(--border)", fontSize: 9 }}>→</span>
                    )}
                  </span>
                ))}
                {s.nodes.length > 5 && (
                  <span style={{ fontSize: 9, color: "var(--text-muted)" }}>
                    +{s.nodes.length - 5}
                  </span>
                )}
              </div>
              {/* Tutor mode button */}
              {onStartTutor && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onStartTutor(s.theme || s.id, s.title);
                  }}
                  style={{
                    marginTop: 8,
                    padding: "4px 10px",
                    fontSize: 11,
                    color: "#7c3aed",
                    background: "#f5f3ff",
                    border: "1px solid #ddd6fe",
                    borderRadius: 6,
                    cursor: "pointer",
                    width: "100%",
                    textAlign: "center",
                  }}
                >
                  对话模式 — AI 导游反问引导
                </button>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
