import type { Storyline } from "./types";
import { saveAnalysisNote } from "../../api/client";

type StorylineCompleteProps = {
  storyline: Storyline;
  onNewStoryline: () => void;
  onReplay: () => void;
};

export function StorylineComplete({ storyline, onNewStoryline, onReplay }: StorylineCompleteProps) {
  async function handleExport() {
    const lines = storyline.nodes.map(
      (n) => `- [ ] **${n.title}** — \`${n.file_path}:${n.line_start}-${n.line_end}\``,
    );
    const markdown = `# ${storyline.title}\n\n${storyline.description}\n\n## 节点清单\n\n${lines.join("\n")}\n`;
    try {
      await saveAnalysisNote(storyline.title, markdown);
    } catch {
      // Silently fail for export
    }
  }

  const completedCount = storyline.node_count;

  return (
    <div className="panel" style={{
      textAlign: "center",
      padding: "24px 16px",
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      gap: 12,
    }}>
      <div style={{ fontSize: 40, lineHeight: 1 }}>
        {/* eslint-disable-next-line */}
        🎉
      </div>
      <div>
        <h3 style={{ margin: "0 0 2px 0", fontSize: 15 }}>
          {storyline.title}
        </h3>
        <p className="muted" style={{ margin: 0, fontSize: 11 }}>
          阅读完成 · {completedCount}/{completedCount} 个节点 · 约 {storyline.estimated_minutes} 分钟
        </p>
      </div>

      {/* Node summary list */}
      <div style={{
        width: "100%",
        textAlign: "left",
        border: "1px solid var(--border)",
        borderRadius: 8,
        overflow: "hidden",
      }}>
        {storyline.nodes.map((n, i) => (
          <div
            key={n.graph_node_id}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              padding: "6px 10px",
              borderBottom: i < storyline.nodes.length - 1 ? "1px solid var(--border)" : "none",
              fontSize: 11,
            }}
          >
            <span style={{
              width: 18,
              height: 18,
              borderRadius: "99px",
              background: "#22c55e",
              color: "#fff",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 9,
              fontWeight: 700,
              flexShrink: 0,
            }}>
              ✓
            </span>
            <span style={{ fontWeight: 500 }}>{n.title}</span>
            <span style={{ fontSize: 10, color: "var(--text-muted)", marginLeft: "auto" }}>
              {n.file_path}
            </span>
          </div>
        ))}
      </div>

      <div style={{ display: "flex", gap: 8, justifyContent: "center", flexWrap: "wrap" }}>
        <button
          className="toolbar-btn"
          onClick={handleExport}
          type="button"
        >
          导出笔记
        </button>
        <button className="toolbar-btn" onClick={onReplay} type="button">
          重走一遍
        </button>
        <button
          className="primaryButton"
          onClick={onNewStoryline}
          style={{ fontSize: 12, flex: "0 0 auto" }}
          type="button"
        >
          下一条主线
        </button>
      </div>
    </div>
  );
}
