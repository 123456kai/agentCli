import { useCallback, useEffect, useRef, useState } from "react";
import type { TutorMessage } from "./types";
import { MessageBubble } from "./MessageBubble";
import { startTutorSession, sendTutorMessage } from "../../api/client";

type CodeTutorChatProps = {
  domainId: string;
  domainName: string;
  onOpenFile: (path: string, startLine: number, endLine: number) => void;
  onBack: () => void;
};

export function CodeTutorChat({ domainId, domainName, onOpenFile, onBack }: CodeTutorChatProps) {
  const [sessionId, setSessionId] = useState<string>("");
  const [messages, setMessages] = useState<TutorMessage[]>([]);
  const [breadcrumbs, setBreadcrumbs] = useState<string>("");
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const resp = await startTutorSession(domainId);
        if (!cancelled) {
          setSessionId(resp.session_id);
          setMessages([resp.message as TutorMessage]);
          setBreadcrumbs(resp.breadcrumbs);
        }
      } catch {
        if (!cancelled) {
          setMessages([{
            role: "tutor",
            content: `欢迎来到 **${domainName}**。暂时无法连接 AI 服务，请稍后重试。`,
            code_ref: null,
            branch_id: "main",
            parent_index: -1,
            active: true,
            timestamp: new Date().toISOString(),
          }]);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [domainId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const renderMessages = useCallback(() => {
    const elements: React.ReactNode[] = [];
    let lastWasInactive = false;

    for (let i = 0; i < messages.length; i++) {
      const msg = messages[i];

      if (!msg.active && !lastWasInactive && i > 0) {
        elements.push(
          <div key={`divider-${i}`} style={{
            textAlign: "center",
            margin: "12px 0",
            fontSize: 11,
            color: "var(--text-muted)",
            borderTop: "1px dashed var(--border)",
            paddingTop: 8,
          }}>
            {"──────── 你从这里换了方向 ────────"}
          </div>
        );
      }

      elements.push(
        <MessageBubble
          key={`msg-${i}`}
          message={msg}
          onCodeRefClick={(path, start, end) => onOpenFile(path, start, end)}
        />
      );

      lastWasInactive = !msg.active;
    }
    return elements;
  }, [messages, onOpenFile]);

  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (!text || !sessionId || sending) return;
    setInput("");
    setSending(true);

    const userMsg: TutorMessage = {
      role: "user",
      content: text,
      code_ref: null,
      branch_id: "main",
      parent_index: messages.length > 0 ? messages.length - 1 : -1,
      active: true,
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);

    try {
      const resp = await sendTutorMessage(sessionId, text);
      setMessages((prev) => [...prev, resp.message as TutorMessage]);
      setBreadcrumbs(resp.breadcrumbs);
    } catch {
      setMessages((prev) => [...prev, {
        role: "tutor",
        content: "抱歉，消息发送失败，请重试。",
        code_ref: null,
        branch_id: "main",
        parent_index: prev.length - 1,
        active: true,
        timestamp: new Date().toISOString(),
      }]);
    } finally {
      setSending(false);
    }
  }, [input, sessionId, sending, messages]);

  const handleBreadcrumbClick = useCallback((index: number) => {
    setMessages((prev) => {
      const activeMsgs = prev.filter((m) => m.active);
      if (index >= activeMsgs.length) return prev;
      return prev.map((m) => {
        const activeIdx = activeMsgs.indexOf(m);
        return activeIdx >= 0 && activeIdx > index ? { ...m, active: false } : m;
      });
    });
  }, []);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      {/* Header */}
      <div style={{
        padding: "8px 12px",
        borderBottom: "1px solid var(--border)",
        background: "#fafafa",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
          <button
            onClick={onBack}
            style={{
              fontSize: 11,
              padding: "2px 8px",
              border: "1px solid var(--border)",
              borderRadius: 4,
              background: "#fff",
              cursor: "pointer",
            }}
          >
            {"< 返回"}
          </button>
          <span style={{ fontSize: 12, fontWeight: 600 }}>CodeTutor</span>
        </div>
        {breadcrumbs && (
          <div style={{
            fontSize: 11,
            color: "var(--text-muted)",
            display: "flex",
            gap: 4,
            flexWrap: "wrap",
            alignItems: "center",
          }}>
            {breadcrumbs.split(" > ").map((crumb, i, arr) => (
              <span key={i} style={{ display: "flex", alignItems: "center", gap: 4 }}>
                <span
                  onClick={() => handleBreadcrumbClick(i)}
                  style={{
                    cursor: i < arr.length - 1 ? "pointer" : "default",
                    color: i < arr.length - 1 ? "var(--accent)" : "var(--text-muted)",
                    textDecoration: i < arr.length - 1 ? "underline" : "none",
                    maxWidth: 120,
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {crumb}
                </span>
                {i < arr.length - 1 && <span>{">"}</span>}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Messages */}
      <div style={{ flex: 1, overflow: "auto", padding: "12px" }}>
        {loading ? (
          <p className="muted">AI 导游正在准备...</p>
        ) : (
          <>
            {renderMessages()}
            <div ref={bottomRef} />
          </>
        )}
      </div>

      {/* Input */}
      <div style={{
        padding: "8px 12px",
        borderTop: "1px solid var(--border)",
        background: "#fafafa",
      }}>
        <div style={{ display: "flex", gap: 8 }}>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder={"输入你的问题，或说'好'继续..."}
            disabled={sending}
            style={{
              flex: 1,
              padding: "6px 10px",
              border: "1px solid var(--border)",
              borderRadius: 6,
              fontSize: 13,
              outline: "none",
            }}
          />
          <button
            onClick={handleSend}
            disabled={sending || !input.trim()}
            style={{
              padding: "6px 14px",
              background: sending ? "var(--border)" : "var(--accent)",
              color: "#fff",
              border: "none",
              borderRadius: 6,
              fontSize: 13,
              cursor: sending ? "default" : "pointer",
              whiteSpace: "nowrap",
            }}
          >
            {sending ? "..." : "发送"}
          </button>
        </div>
        <div style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 4 }}>
          Enter 发送，Shift+Enter 换行
        </div>
      </div>
    </div>
  );
}
