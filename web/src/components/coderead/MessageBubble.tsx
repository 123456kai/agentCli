import type { TutorMessage } from "./types";
import { renderMarkdown } from "./Markdown";

type MessageBubbleProps = {
  message: TutorMessage;
  onCodeRefClick?: (filePath: string, lineStart: number, lineEnd: number) => void;
};

export function MessageBubble({ message, onCodeRefClick }: MessageBubbleProps) {
  const isTutor = message.role === "tutor";
  const isInactive = !message.active;

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: isTutor ? "flex-start" : "flex-end",
        marginBottom: 12,
        opacity: isInactive ? 0.45 : 1,
        transition: "opacity 0.2s",
      }}
    >
      <span style={{
        fontSize: 10,
        color: isTutor ? "var(--accent)" : "var(--text-muted)",
        marginBottom: 2,
        fontWeight: 600,
      }}>
        {isTutor ? "CodeTutor" : "你"}
      </span>

      <div
        style={{
          maxWidth: "90%",
          padding: "10px 14px",
          borderRadius: 12,
          background: isTutor ? "#f8faff" : "var(--accent)",
          color: isTutor ? "var(--text-body)" : "#fff",
          border: isTutor ? "1px solid var(--border)" : "none",
          fontSize: 13,
          lineHeight: 1.6,
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
        }}
      >
        {isTutor && onCodeRefClick
          ? renderMarkdown(message.content, onCodeRefClick)
          : message.content}

        {message.code_ref && (
          <button
            onClick={() => {
              if (onCodeRefClick && message.code_ref) {
                const cr = message.code_ref;
                onCodeRefClick(cr.file_path, cr.line_start, cr.line_end);
              }
            }}
            style={{
              display: "block",
              marginTop: 8,
              padding: "4px 10px",
              fontSize: 11,
              color: "var(--accent)",
              background: "#eef2ff",
              border: "1px solid #c7d2fe",
              borderRadius: 6,
              cursor: "pointer",
              textAlign: "left",
              width: "100%",
            }}
          >
            {message.code_ref.file_path}:{message.code_ref.line_start}-{message.code_ref.line_end}
          </button>
        )}
      </div>
    </div>
  );
}
