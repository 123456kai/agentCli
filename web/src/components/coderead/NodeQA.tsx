import { useState } from "react";

type Message = {
  role: "user" | "ai";
  content: string;
};

type NodeQAProps = {
  onAsk: (question: string) => Promise<string>;
};

export function NodeQA({ onAsk }: NodeQAProps) {
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
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      {messages.length > 0 && (
        <div style={{ maxHeight: 160, overflowY: "auto", display: "grid", gap: 4 }}>
          {messages.map((m, i) => (
            <div
              key={i}
              style={{
                fontSize: 10,
                lineHeight: 1.5,
                padding: "4px 8px",
                borderRadius: 6,
                background: m.role === "user" ? "#f9fafb" : "#eff6ff",
                color: m.role === "user" ? "#6b7280" : "#374151",
              }}
            >
              <span style={{ fontWeight: 600, fontSize: 9 }}>
                {m.role === "user" ? "你" : "AI"}
              </span>
              <div>{m.content}</div>
            </div>
          ))}
        </div>
      )}

      <div style={{ display: "flex", gap: 4 }}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") handleSend(); }}
          placeholder="问这段代码..."
          className="filterInput"
          style={{ flex: 1, fontSize: 11, padding: "5px 8px" }}
          disabled={loading}
        />
        <button
          className="toolbar-btn"
          onClick={handleSend}
          disabled={loading}
          style={{ fontSize: 11, whiteSpace: "nowrap" }}
          type="button"
        >
          {loading ? "..." : "发送"}
        </button>
      </div>
    </div>
  );
}
