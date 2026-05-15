import { useState } from "react";

type Message = {
  role: "user" | "ai";
  content: string;
};

type NodeQAProps = {
  onAsk: (question: string) => Promise<string>;
  nodeContext: string;
};

export function NodeQA({ onAsk, nodeContext }: NodeQAProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSend() {
    const q = input.trim();
    if (!q || loading) return;
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: q }]);
    setLoading(true);
    try {
      const answer = await onAsk(q);
      setMessages((prev) => [...prev, { role: "ai", content: answer }]);
    } catch {
      setMessages((prev) => [...prev, { role: "ai", content: "提问失败，请重试。" }]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <div style={{ fontSize: 10, fontWeight: 600, color: "#6b7280" }}>
        追问
      </div>

      {messages.length > 0 && (
        <div style={{
          maxHeight: 200,
          overflowY: "auto",
          display: "flex",
          flexDirection: "column",
          gap: 6,
        }}>
          {messages.map((m, i) => (
            <div
              key={i}
              style={{
                display: "flex",
                justifyContent: m.role === "user" ? "flex-end" : "flex-start",
              }}
            >
              <div style={{
                maxWidth: "85%",
                padding: "6px 10px",
                borderRadius: m.role === "user" ? "12px 12px 4px 12px" : "4px 12px 12px 12px",
                background: m.role === "user" ? "var(--accent)" : "#f3f4f6",
                color: m.role === "user" ? "#fff" : "var(--text-body)",
                fontSize: 11,
                lineHeight: 1.5,
                wordBreak: "break-word",
              }}>
                <div style={{ fontSize: 9, fontWeight: 600, marginBottom: 2, opacity: 0.7 }}>
                  {m.role === "user" ? "你" : "AI"}
                </div>
                <div>{m.content}</div>
              </div>
            </div>
          ))}
          {loading && (
            <div style={{ display: "flex", justifyContent: "flex-start" }}>
              <div style={{
                padding: "6px 10px",
                borderRadius: "4px 12px 12px 12px",
                background: "#f3f4f6",
                fontSize: 11,
                color: "#9ca3af",
                fontStyle: "italic",
              }}>
                思考中...
              </div>
            </div>
          )}
        </div>
      )}

      <div style={{ display: "flex", gap: 6 }}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") handleSend(); }}
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
          onFocus={(e) => { e.currentTarget.style.borderColor = "var(--accent)"; }}
          onBlur={(e) => { e.currentTarget.style.borderColor = "var(--border)"; }}
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
