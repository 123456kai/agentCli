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

type GuidanceOption = {
  label: string;
  action: "next" | "jump" | "deep";
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
  const [showGuidance, setShowGuidance] = useState(false);

  // Track previous node id to detect node changes
  const prevNodeId = useMemo(() => currentNode.graph_node_id, [
    storyline.id,
    currentNodeIndex,
  ]);

  const loadNode = useCallback(async () => {
    setLoadingNode(true);
    setError(null);
    setShowGuidance(false);
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

  function handleAskSuggestion(question: string) {
    // Scroll to Q&A section and pre-fill
    handleAsk(question);
  }

  const nextNode = currentNodeIndex + 1 < totalNodes
    ? storyline.nodes[currentNodeIndex + 1]
    : null;

  const guidanceOptions: GuidanceOption[] = [];
  if (nextNode) {
    guidanceOptions.push({
      label: nextNode.title || "继续下一步",
      action: "next",
    });
  }
  // Add other nodes that haven't been read yet
  const unreadNodes = storyline.nodes
    .map((n, i) => ({ node: n, index: i }))
    .filter(({ index }) => index > currentNodeIndex + 1)
    .slice(0, 2);
  for (const { node, index } of unreadNodes) {
    guidanceOptions.push({
      label: `跳到：${node.title || "节点 " + (index + 1)}`,
      action: "jump",
    });
  }
  guidanceOptions.push({
    label: "深入探索当前节点",
    action: "deep",
  });

  function handleGuidanceChoice(option: GuidanceOption) {
    setShowGuidance(false);
    if (option.action === "next") {
      onAdvance();
    } else if (option.action === "jump") {
      const target = unreadNodes.find(
        ({ node }) => (node.title || "") === option.label.replace(/^跳到：/, "")
      );
      if (target) {
        onGoToNode(target.index);
      }
    }
    // "deep" — stay on current node, focus Q&A
  }

  const progressPct = ((currentNodeIndex + 1) / totalNodes) * 100;
  const isLastNode = currentNodeIndex + 1 >= totalNodes;

  const nextTeaser = nodeData?.narrative?.next_teaser ?? currentNode.next_teaser;

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

          {/* Narrative cards with suggested questions */}
          <NarrativeCards
            narrative={nodeData?.narrative ? { ...nodeData.narrative, next_teaser: nextTeaser } : null}
            loading={loadingNode}
            lineStart={currentNode.line_start}
            lineEnd={currentNode.line_end}
            filePath={currentNode.file_path}
            onAskSuggestion={handleAskSuggestion}
          />

          {error ? (
            <p style={{ color: "#b91c1c", fontSize: 11 }}>{error}</p>
          ) : null}

          {/* Guidance panel: shown after user clicks "理解了" */}
          {showGuidance && (
            <div style={{
              border: "1px solid var(--accent)",
              borderRadius: 8,
              padding: "10px 12px",
              background: "#f8faff",
            }}>
              <div style={{
                fontSize: 11,
                fontWeight: 600,
                color: "var(--accent)",
                marginBottom: 8,
              }}>
                这个节点理解了！接下来你想了解什么？
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                {guidanceOptions.map((opt, i) => (
                  <button
                    key={i}
                    onClick={() => handleGuidanceChoice(opt)}
                    style={{
                      textAlign: "left",
                      padding: "6px 10px",
                      border: `1px solid ${i === 0 ? "var(--accent)" : "var(--border)"}`,
                      borderRadius: 6,
                      background: i === 0 ? "#eff6ff" : "#fff",
                      cursor: "pointer",
                      fontSize: 11,
                      color: i === 0 ? "var(--accent)" : "var(--text-body)",
                      fontWeight: i === 0 ? 600 : 400,
                    }}
                    type="button"
                  >
                    {i === 0 && "→ "}{opt.label}
                    {opt.action === "next" && nextNode && (
                      <span style={{ fontSize: 9, color: "var(--text-muted)", marginLeft: 6 }}>
                        ({nextNode.file_path})
                      </span>
                    )}
                  </button>
                ))}
              </div>
            </div>
          )}

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
            onClick={() => {
              if (isLastNode) {
                onAdvance();
              } else {
                setShowGuidance(true);
              }
            }}
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
