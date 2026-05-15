import type { Storyline } from "./types";

type StorylineCompleteProps = {
  storyline: Storyline;
  onNewStoryline: () => void;
  onReplay: () => void;
};

export function StorylineComplete({ storyline, onNewStoryline, onReplay }: StorylineCompleteProps) {
  return (
    <div className="panel" style={{ textAlign: "center", padding: "24px 16px" }}>
      <div style={{ fontSize: 36, marginBottom: 12 }}>
        {/* eslint-disable-next-line */}
        🎉
      </div>
      <h3 style={{ margin: "0 0 4px 0", fontSize: 16 }}>
        {storyline.title} — 完成
      </h3>
      <p className="muted" style={{ marginBottom: 16 }}>
        {storyline.node_count}/{storyline.node_count} 个节点已读 · 约 {storyline.estimated_minutes} 分钟
      </p>

      <div style={{ display: "flex", gap: 8, justifyContent: "center", flexWrap: "wrap" }}>
        <button
          className="toolbar-btn"
          onClick={async () => {
            const lines = storyline.nodes.map(
              (n) => `- [${n.order === 0 ? "x" : " "}] **${n.title}** — \`${n.file_path}:${n.line_start}\``,
            );
            const markdown = `# ${storyline.title}\n\n${storyline.description}\n\n${lines.join("\n")}\n`;
            try {
              await fetch("/api/notes", {
                method: "POST",
                headers: { "content-type": "application/json" },
                body: JSON.stringify({ title: storyline.title, answer: markdown }),
              });
            } catch {
              // Silently fail for export
            }
          }}
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
