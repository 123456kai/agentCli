import { useState } from "react";

type NarrativeCardsProps = {
  narrative: {
    summary: string;
    design_notes: string;
    warnings: string | null;
    next_teaser?: string | null;
  } | null;
  loading: boolean;
  lineStart: number;
  lineEnd: number;
  filePath: string;
  onAskSuggestion?: (question: string) => void;
  onFillInput?: (question: string) => void;
};

type CardSection = {
  key: string;
  label: string;
  content: string | null;
  color: string;
  bgColor: string;
};

function buildSuggestions(narrative: NarrativeCardsProps["narrative"]): string[] {
  if (!narrative) return [];
  const suggestions: string[] = [];
  if (narrative.next_teaser) {
    suggestions.push(narrative.next_teaser);
  }
  if (narrative.design_notes) {
    // Extract a follow-up question from design_notes
    const lines = narrative.design_notes.split(/[。？\n]/);
    for (const line of lines) {
      const trimmed = line.trim();
      if (trimmed.length > 10 && trimmed.length < 80 && !trimmed.startsWith("使用")) {
        suggestions.push(`为什么${trimmed}？`.slice(0, 80));
        break;
      }
    }
  }
  if (suggestions.length < 2) {
    suggestions.push("这段代码在整体架构中扮演什么角色？");
  }
  if (suggestions.length < 3) {
    suggestions.push("如果这部分出错了，会影响哪些功能？");
  }
  return suggestions.slice(0, 3);
}

export function NarrativeCards({ narrative, loading, lineStart, lineEnd, filePath, onAskSuggestion, onFillInput }: NarrativeCardsProps) {
  const [openSections, setOpenSections] = useState<Set<string>>(new Set(["summary"]));

  function toggle(key: string) {
    setOpenSections((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  if (loading) {
    return (
      <div style={{ padding: "12px 0" }}>
        <p className="muted" style={{ fontSize: 11, margin: 0 }}>AI 正在分析这段代码...</p>
        <div style={{ background: "#f3f4f6", borderRadius: 4, height: 3, overflow: "hidden", marginTop: 6 }}>
          <div style={{
            background: "var(--accent)",
            height: 3,
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

  const cards: CardSection[] = [
    {
      key: "summary",
      label: "做什么",
      content: narrative.summary,
      color: "var(--accent)",
      bgColor: "#eff6ff",
    },
    {
      key: "design_notes",
      label: "为什么这样设计",
      content: narrative.design_notes,
      color: "#d97706",
      bgColor: "#fffbeb",
    },
    {
      key: "warnings",
      label: "注意",
      content: narrative.warnings,
      color: "#dc2626",
      bgColor: "#fef2f2",
    },
  ].filter((c) => c.content);

  return (
    <div style={{ display: "grid", gap: 6 }}>
      {/* Location reference */}
      {filePath && lineStart > 0 ? (
        <div style={{
          fontSize: 10,
          color: "var(--text-muted)",
          display: "flex",
          alignItems: "center",
          gap: 6,
        }}>
          <span>{filePath}</span>
          <span style={{
            background: "#f3f4f6",
            padding: "1px 6px",
            borderRadius: 3,
            fontFamily: "monospace",
            fontSize: 9,
          }}>
            第 {lineStart}-{lineEnd} 行
          </span>
        </div>
      ) : null}

      {/* Accordion cards */}
      {cards.map((card) => {
        const isOpen = openSections.has(card.key);
        return (
          <div
            key={card.key}
            style={{
              border: `1px solid ${isOpen ? card.color : "var(--border)"}`,
              borderRadius: 6,
              overflow: "hidden",
              transition: "border-color 0.15s",
            }}
          >
            <button
              onClick={() => toggle(card.key)}
              style={{
                width: "100%",
                textAlign: "left",
                padding: "6px 10px",
                border: "none",
                background: isOpen ? card.bgColor : "transparent",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                fontSize: 11,
                fontWeight: 600,
                color: card.color,
              }}
              type="button"
            >
              <span>{card.label}</span>
              <span style={{ fontSize: 10, transition: "transform 0.15s", transform: isOpen ? "rotate(180deg)" : "" }}>
                ▾
              </span>
            </button>
            {isOpen && (
              <div style={{
                padding: "6px 10px 10px",
                fontSize: 11,
                lineHeight: 1.6,
                color: "var(--text-body)",
              }}>
                {card.content}
              </div>
            )}
          </div>
        );
      })}

      {/* Suggested follow-up questions */}
      {(onAskSuggestion || onFillInput) && (() => {
        const suggestions = buildSuggestions(narrative);
        if (suggestions.length === 0) return null;
        const handleClick = (q: string) => {
          if (onFillInput) {
            onFillInput(q);
          } else {
            onAskSuggestion?.(q);
          }
        };
        return (
          <div style={{ marginTop: 4 }}>
            <div style={{ fontSize: 10, color: "var(--text-muted)", marginBottom: 4 }}>
              追问建议 · 点击填入输入框
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              {suggestions.map((q, i) => (
                <button
                  key={i}
                  onClick={() => handleClick(q)}
                  style={{
                    textAlign: "left",
                    padding: "5px 8px",
                    border: "1px dashed var(--border)",
                    borderRadius: 4,
                    background: "transparent",
                    cursor: "pointer",
                    fontSize: 10,
                    color: "var(--text-muted)",
                    transition: "border-color 0.15s, color 0.15s",
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.borderColor = "var(--accent)";
                    e.currentTarget.style.color = "var(--accent)";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.borderColor = "var(--border)";
                    e.currentTarget.style.color = "var(--text-muted)";
                  }}
                  type="button"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        );
      })()}
    </div>
  );
}
