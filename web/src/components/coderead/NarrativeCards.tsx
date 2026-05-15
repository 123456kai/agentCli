import { useState } from "react";

type NarrativeCardsProps = {
  narrative: {
    summary: string;
    design_notes: string;
    warnings: string | null;
  } | null;
  loading: boolean;
  lineStart: number;
  lineEnd: number;
  filePath: string;
};

type CardSection = {
  key: string;
  label: string;
  content: string | null;
  color: string;
  bgColor: string;
};

export function NarrativeCards({ narrative, loading, lineStart, lineEnd, filePath }: NarrativeCardsProps) {
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
    </div>
  );
}
