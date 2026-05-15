import { useCallback, useEffect, useState } from "react";

import type { Storyline, StorylineNode } from "./types";
import type { StorylineNodeResponse } from "./types";
import { fetchStorylineNode, askAboutNode } from "../../api/client";
import { NarrativeCards } from "./NarrativeCards";
import { NodeQA } from "./NodeQA";

type StorylineReaderProps = {
  storyline: Storyline;
  currentNode: StorylineNode;
  currentNodeIndex: number;
  totalNodes: number;
  onAdvance: () => void;
  onPrevious: () => void;
  onGoToNode: (index: number) => void;
  onExit: () => void;
  onOpenFile: (path: string, line?: number) => void;
};

export function StorylineReader({
  storyline,
  currentNode,
  currentNodeIndex,
  totalNodes,
  onAdvance,
  onPrevious,
  onGoToNode,
  onExit,
  onOpenFile,
}: StorylineReaderProps) {
  const [nodeData, setNodeData] = useState<StorylineNodeResponse | null>(null);
  const [loadingNode, setLoadingNode] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadNode = useCallback(async () => {
    setLoadingNode(true);
    setError(null);
    try {
      const data = await fetchStorylineNode(storyline.id, currentNode.graph_node_id);
      setNodeData(data);
      if (data.node.file_path) {
        onOpenFile(data.node.file_path, data.node.line_start);
      }
    } catch {
      setError("加载节点失败");
    } finally {
      setLoadingNode(false);
    }
  }, [storyline.id, currentNode.graph_node_id, onOpenFile]);

  useEffect(() => {
    loadNode();
  }, [loadNode]);

  async function handleAsk(question: string): Promise<string> {
    const resp = await askAboutNode(storyline.id, currentNode.graph_node_id, question);
    return resp.answer;
  }

  const progressPct = ((currentNodeIndex + 1) / totalNodes) * 100;

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", minHeight: 0 }}>
      {/* Progress bar */}
      <div style={{ background: "var(--border)", height: 3, flexShrink: 0 }}>
        <div style={{
          background: "var(--accent)",
          height: 3,
          width: `${progressPct}%`,
          transition: "width 0.3s",
        }} />
      </div>

      {/* Header */}
      <div style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "6px 12px",
        background: "var(--surface)",
        borderBottom: "1px solid var(--border)",
        fontSize: 11,
        flexShrink: 0,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontWeight: 600 }}>{storyline.title}</span>
          <span style={{ color: "var(--text-muted)" }}>
            {currentNodeIndex + 1}/{totalNodes}
          </span>
        </div>
        <button className="toolbar-btn" onClick={onExit} type="button" style={{ fontSize: 10 }}>
          退出
        </button>
      </div>

      {/* Main: 70/30 split */}
      <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
        {/* 70% Source code */}
        <div style={{ flex: 7, minHeight: 0, display: "flex", flexDirection: "column", borderRight: "1px solid var(--border)" }}>
          <div style={{
            padding: "4px 10px",
            background: "#fafbfc",
            borderBottom: "1px solid var(--border)",
            fontSize: 10,
            color: "var(--text-muted)",
            flexShrink: 0,
          }}>
            {currentNode.file_path}
          </div>
          <div style={{
            flex: 1,
            overflow: "auto",
            background: "#1e1e2e",
            padding: 10,
            fontFamily: "'Cascadia Code', 'Fira Code', monospace",
            fontSize: 11,
            lineHeight: 1.6,
            color: "#d4d4d4",
          }}>
            {loadingNode ? (
              <span style={{ color: "#888" }}>Loading...</span>
            ) : error ? (
              <span style={{ color: "#f0a0a0" }}>{error}</span>
            ) : nodeData ? (
              <pre style={{ margin: 0, whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
                {nodeData.source_code}
              </pre>
            ) : null}
          </div>
        </div>

        {/* 30% Explanation + Q&A */}
        <div style={{
          flex: 3,
          display: "flex",
          flexDirection: "column",
          padding: 10,
          overflow: "auto",
          gap: 10,
          minHeight: 0,
        }}>
          {/* Narrative cards */}
          <NarrativeCards
            narrative={nodeData?.narrative ?? null}
            loading={loadingNode}
          />

          {/* Separator */}
          <div style={{ borderTop: "1px solid var(--border)" }} />

          {/* Q&A */}
          <NodeQA onAsk={handleAsk} />
        </div>
      </div>

      {/* Footer controls */}
      <div style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "8px 12px",
        borderTop: "1px solid var(--border)",
        background: "var(--surface)",
        flexShrink: 0,
      }}>
        <div style={{ display: "flex", gap: 6 }}>
          <button
            className="toolbar-btn"
            onClick={onPrevious}
            disabled={currentNodeIndex === 0}
            type="button"
          >
            上一步
          </button>
          <button
            className="toolbar-btn"
            onClick={() => onGoToNode(currentNodeIndex - 1)}
            disabled={currentNodeIndex === 0}
            type="button"
          >
            回看已读
          </button>
        </div>

        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
          {/* Node timeline dots */}
          <div style={{ display: "flex", gap: 3, marginRight: 8 }}>
            {Array.from({ length: totalNodes }).map((_, i) => (
              <button
                key={i}
                onClick={() => onGoToNode(i)}
                style={{
                  width: 18,
                  height: 18,
                  borderRadius: "99px",
                  border: "2px solid",
                  borderColor: i < currentNodeIndex ? "#22c55e" : i === currentNodeIndex ? "var(--accent)" : "var(--border)",
                  background: i <= currentNodeIndex ? (i === currentNodeIndex ? "#eff6ff" : "#22c55e") : "transparent",
                  color: i < currentNodeIndex ? "#fff" : i === currentNodeIndex ? "var(--accent)" : "var(--text-muted)",
                  fontSize: 9,
                  fontWeight: 700,
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  padding: 0,
                  transition: "all 0.2s",
                }}
                type="button"
              >
                {i < currentNodeIndex ? "✓" : i + 1}
              </button>
            ))}
          </div>

          <button
            className="primaryButton"
            onClick={onAdvance}
            style={{
              fontSize: 12,
              padding: "6px 16px",
              flex: "0 0 auto",
              minWidth: 100,
            }}
            type="button"
          >
            {currentNodeIndex + 1 >= totalNodes ? "完成主线" : "理解了 ✓"}
          </button>
        </div>
      </div>
    </div>
  );
}
