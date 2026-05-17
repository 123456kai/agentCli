import { useEffect, useRef, useState } from "react";
import { renderMarkdown } from "./Markdown";

type SourceRef = {
  path: string;
  line_start: number;
  line_end: number;
};

type AskResult = {
  answer: string;
  sourceRefs: SourceRef[];
};

type Message = {
  role: "user" | "ai";
  content: string;
  sourceRefs: SourceRef[];
};

type NodeQAProps = {
  onAsk: (question: string) => Promise<AskResult>;
  onOpenFile: (path: string, startLine: number, endLine: number) => void;
  nodeContext: string;
  prefillQuestion?: string;
  onPrefillConsumed?: () => void;
  currentFilePath?: string;
  currentLineStart?: number;
  currentLineEnd?: number;
};

export function NodeQA({
  onAsk,
  onOpenFile,
  nodeContext,
  prefillQuestion,
  onPrefillConsumed,
  currentFilePath,
  currentLineStart,
  currentLineEnd,
}: NodeQAProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (prefillQuestion) {
      setInput(prefillQuestion);
      onPrefillConsumed?.();
      setTimeout(() => inputRef.current?.focus(), 0);
    }
  }, [prefillQuestion, onPrefillConsumed]);

  async function handleSend() {
    const q = input.trim();
    if (!q || loading) return;
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: q, sourceRefs: [] }]);
    setLoading(true);
    try {
      const result = await onAsk(q);
      setMessages((prev) => [
        ...prev,
        { role: "ai", content: result.answer, sourceRefs: result.sourceRefs },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "ai", content: "提问失败，请重试。", sourceRefs: [] },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function refLabel(ref: SourceRef): string {
    const fname = ref.path.split("/").pop() || ref.path;
    if (ref.line_start === ref.line_end) {
      return `${fname}:${ref.line_start}`;
    }
    return `${fname}:${ref.line_start}-${ref.line_end}`;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <div style={{ fontSize: 10, fontWeight: 600, color: "#6b7280" }}>
        追问
      </div>

      {/* Current code quick-jump chip */}
      {currentFilePath && (
        <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
          <button
            onClick={() =>
              onOpenFile(
                currentFilePath,
                currentLineStart || 1,
                currentLineEnd || 1,
              )
            }
            style={{
              fontSize: 10,
              padding: "3px 8px",
              border: "1px solid #c7d2fe",
              borderRadius: 4,
              background: "#eef2ff",
              color: "var(--accent)",
              cursor: "pointer",
              whiteSpace: "nowrap",
            }}
            type="button"
          >
            查看当前代码
          </button>
        </div>
      )}

      {messages.length > 0 && (
        <div
          style={{
            maxHeight: 400,
            overflowY: "auto",
            display: "flex",
            flexDirection: "column",
            gap: 6,
          }}
        >
          {messages.map((m, i) => (
            <div
              key={i}
              style={{
                display: "flex",
                justifyContent: m.role === "user" ? "flex-end" : "flex-start",
              }}
            >
              <div
                style={{
                  maxWidth: "90%",
                  padding: "8px 12px",
                  borderRadius:
                    m.role === "user"
                      ? "12px 12px 4px 12px"
                      : "4px 12px 12px 12px",
                  background: m.role === "user" ? "var(--accent)" : "#f3f4f6",
                  color: m.role === "user" ? "#fff" : "var(--text-body)",
                  fontSize: 11,
                  lineHeight: 1.6,
                  wordBreak: "break-word",
                }}
              >
                <div
                  style={{
                    fontSize: 9,
                    fontWeight: 600,
                    marginBottom: 2,
                    opacity: 0.7,
                  }}
                >
                  {m.role === "user" ? "你" : "AI"}
                </div>
                {m.role === "ai" ? (
                  <div>{renderMarkdown(m.content, onOpenFile)}</div>
                ) : (
                  <div>{m.content}</div>
                )}

                {/* Clickable code reference chips */}
                {m.role === "ai" && m.sourceRefs.length > 0 && (
                  <div
                    style={{
                      display: "flex",
                      gap: 4,
                      flexWrap: "wrap",
                      marginTop: 8,
                      paddingTop: 8,
                      borderTop: "1px solid var(--border)",
                    }}
                  >
                    {m.sourceRefs.map((ref, ri) => (
                      <button
                        key={ri}
                        onClick={() =>
                          onOpenFile(ref.path, ref.line_start, ref.line_end)
                        }
                        style={{
                          fontSize: 10,
                          padding: "3px 8px",
                          border: "1px solid #c7d2fe",
                          borderRadius: 4,
                          background: "#eef2ff",
                          color: "var(--accent)",
                          cursor: "pointer",
                          whiteSpace: "nowrap",
                          fontWeight: 500,
                        }}
                        type="button"
                        title={`打开 ${ref.path}:${ref.line_start}-${ref.line_end}`}
                      >
                        {refLabel(ref)}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
          {loading && (
            <div style={{ display: "flex", justifyContent: "flex-start" }}>
              <div
                style={{
                  padding: "6px 10px",
                  borderRadius: "4px 12px 12px 12px",
                  background: "#f3f4f6",
                  fontSize: 11,
                  color: "#9ca3af",
                  fontStyle: "italic",
                }}
              >
                思考中...
              </div>
            </div>
          )}
        </div>
      )}

      <div style={{ display: "flex", gap: 6 }}>
        <input
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") handleSend();
          }}
          placeholder={`对"${nodeContext}"提问...`}
          style={{
            flex: 1,
            fontSize: 11,
            padding: "6px 10px",
            border: "1px solid var(--border)",
            borderRadius: 8,
            outline: "none",
            background: "#fff",
          }}
          disabled={loading}
          onFocus={(e) => {
            e.currentTarget.style.borderColor = "var(--accent)";
          }}
          onBlur={(e) => {
            e.currentTarget.style.borderColor = "var(--border)";
          }}
        />
        <button
          onClick={handleSend}
          disabled={loading || !input.trim()}
          style={{
            fontSize: 11,
            padding: "6px 14px",
            border: "none",
            borderRadius: 8,
            background: loading || !input.trim() ? "var(--border)" : "var(--accent)",
            color: "#fff",
            cursor: loading || !input.trim() ? "default" : "pointer",
            fontWeight: 500,
            whiteSpace: "nowrap",
            transition: "background 0.15s",
          }}
          type="button"
        >
          {loading ? "..." : "发送"}
        </button>
      </div>
    </div>
  );
}
