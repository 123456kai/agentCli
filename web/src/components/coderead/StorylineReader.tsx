import { useCallback, useEffect, useMemo, useState } from "react";

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
  onOpenFile: (path: string, startLine: number, endLine: number) => void;
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

  // Track previous node id to detect node changes
  const prevNodeId = useMemo(() => currentNode.graph_node_id, [
    storyline.id,
    currentNodeIndex,
  ]);

  const loadNode = useCallback(async () => {
    setLoadingNode(true);
    setError(null);
    try {
      const data = await fetchStorylineNode(storyline.id, currentNode.graph_node_id);
      setNodeData(data);
      if (data.node.file_path) {
        onOpenFile(data.node.file_path, data.node.line_start, data.node.line_end);
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
  const isLastNode = currentNodeIndex + 1 >= totalNodes;

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", minHeight: 0 }}>
      {/* Progress bar */}
      <div style={{ background: "var(--border)", height: 3, flexShrink: 0 }}>
        <div style={{
          background: "var(--accent)",
          height: 3,
          width: `${progressPct}%`,
          transition: "width 0.3s ease",
        }} />
      </div>

      {/* Header */}
      <div style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "8px 12px",
        background: "var(--surface)",
        borderBottom: "1px solid var(--border)",
        flexShrink: 0,
      }}>
        <div>
          <div style={{ fontWeight: 600, fontSize: 12 }}>{storyline.title}</div>
          <div style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 1 }}>
            {currentNodeIndex + 1}/{totalNodes} · {currentNode.file_path || "—"}
            {currentNode.line_start > 0 ? ` 第 ${currentNode.line_start}-${currentNode.line_end} 行` : ""}
          </div>
        </div>
        <button
          className="toolbar-btn"
          onClick={onExit}
          type="button"
          style={{ fontSize: 10, flexShrink: 0 }}
        >
          退出
        </button>
      </div>

      {/* Body: scrollable content area */}
      <div style={{
        flex: 1,
        display: "flex",
        overflow: "hidden",
        minHeight: 0,
      }}>
        {/* Left: vertical node timeline */}
        <div style={{
          width: 28,
          flexShrink: 0,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          paddingTop: 10,
          borderRight: "1px solid var(--border)",
          overflow: "hidden",
        }}>
          {storyline.nodes.map((_, i) => {
            const isDone = i < currentNodeIndex;
            const isCurrent = i === currentNodeIndex;
            return (
              <div
                key={i}
                style={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  minHeight: isCurrent ? 60 : 28,
                  cursor: "pointer",
                }}
                onClick={() => onGoToNode(i)}
              >
                {/* Vertical line */}
                {i > 0 && (
                  <div style={{
                    width: 2,
                    height: 12,
                    background: i <= currentNodeIndex ? "var(--accent)" : "var(--border)",
                  }} />
                )}
                {/* Dot */}
                <div style={{
                  width: isCurrent ? 14 : 10,
                  height: isCurrent ? 14 : 10,
                  borderRadius: "99px",
                  background: isDone ? "#22c55e" : isCurrent ? "var(--accent)" : "var(--border)",
                  border: isCurrent ? "2px solid #bfdbfe" : "none",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 7,
                  color: isDone ? "#fff" : "var(--text-muted)",
                  fontWeight: 700,
                  transition: "all 0.2s",
                  flexShrink: 0,
                }}>
                  {isDone ? "✓" : isCurrent ? "" : ""}
                </div>
              </div>
            );
          })}
        </div>

        {/* Right: content */}
        <div style={{
          flex: 1,
          overflow: "auto",
          padding: 10,
          display: "flex",
          flexDirection: "column",
          gap: 8,
          minWidth: 0,
        }}>
          {/* Current node title */}
          <div style={{
            fontSize: 11,
            fontWeight: 600,
            color: "var(--text-body)",
          }}>
            {currentNode.title}
          </div>

          {/* Narrative cards */}
          <NarrativeCards
            narrative={nodeData?.narrative ?? null}
            loading={loadingNode}
            lineStart={currentNode.line_start}
            lineEnd={currentNode.line_end}
            filePath={currentNode.file_path}
          />

          {error ? (
            <p style={{ color: "#b91c1c", fontSize: 11 }}>{error}</p>
          ) : null}

          {/* Separator */}
          <div style={{ borderTop: "1px solid var(--border)" }} />

          {/* Q&A */}
          <NodeQA
            onAsk={handleAsk}
            nodeContext={currentNode.title}
            key={prevNodeId}
          />
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
        <button
          className="toolbar-btn"
          onClick={onPrevious}
          disabled={currentNodeIndex === 0}
          type="button"
          style={{ fontSize: 11 }}
        >
          上一步
        </button>

        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
          {/* Dot indicators */}
          <div style={{ display: "flex", gap: 3, marginRight: 4 }}>
            {Array.from({ length: totalNodes }).map((_, i) => (
              <div
                key={i}
                onClick={() => onGoToNode(i)}
                style={{
                  width: 6,
                  height: 6,
                  borderRadius: "99px",
                  background: i < currentNodeIndex ? "#22c55e" : i === currentNodeIndex ? "var(--accent)" : "var(--border)",
                  cursor: "pointer",
                  transition: "background 0.2s",
                }}
              />
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
            {isLastNode ? "完成主线" : "理解了 ✓"}
          </button>
        </div>
      </div>
    </div>
  );
}
