import type { ReactNode } from "react";

/**
 * Lightweight markdown renderer for chat bubbles.
 * Handles: code blocks, inline code, bold, headers, lists, horizontal rules, links,
 * and inline code references (path/to/file.ext:line-line → clickable link).
 *
 * Code references ALWAYS take precedence over inline markdown — a file:line
 * inside backticks still renders as a clickable link.
 */

type CodeRefHandler = (path: string, startLine: number, endLine: number) => void;

/** Detect path/to/file.ext:123 or path/to/file.ext:123-456 */
const CODE_REF_RE = /([\w][\w/\-.]*\.(?:py|tsx?|jsx?|json|toml|ya?ml|html|css|java|go|rs|md)):(\d+)(?:-(\d+))?/g;

function parseInline(text: string, onCodeRefClick?: CodeRefHandler): ReactNode[] {
  if (!onCodeRefClick) {
    return _parseInlineMarkdown(text);
  }

  // Phase 1: find all code references and split text into segments
  const codeRefs: { start: number; end: number; path: string; startLine: number; endLine: number }[] = [];
  let m: RegExpExecArray | null;
  while ((m = CODE_REF_RE.exec(text)) !== null) {
    codeRefs.push({
      start: m.index,
      end: m.index + m[0].length,
      path: m[1],
      startLine: parseInt(m[2], 10),
      endLine: m[3] ? parseInt(m[3], 10) : parseInt(m[2], 10),
    });
  }

  if (codeRefs.length === 0) {
    return _parseInlineMarkdown(text);
  }

  // Phase 2: build nodes — segments between code refs get markdown-parsed,
  // code refs themselves become clickable links
  const nodes: ReactNode[] = [];
  let cursor = 0;

  for (let i = 0; i < codeRefs.length; i++) {
    const ref = codeRefs[i];

    // Avoid overlapping refs
    if (ref.start < cursor) continue;

    // Check if this code ref is wrapped in backticks — if so, consume them
    let refStart = ref.start;
    let refEnd = ref.end;
    if (onCodeRefClick && text[refStart - 1] === "`" && text[refEnd] === "`") {
      refStart -= 1;
      refEnd += 1;
    }

    // Text before this code ref → parse as markdown
    if (refStart > cursor) {
      const before = text.slice(cursor, refStart);
      nodes.push(..._parseInlineMarkdown(before));
    }

    // The code ref itself → clickable link (show only path:line, not backticks)
    const label = text.slice(ref.start, ref.end);
    nodes.push(
      <a
        key={`cr-${ref.start}`}
        onClick={(e) => { e.preventDefault(); onCodeRefClick(ref.path, ref.startLine, ref.endLine); }}
        style={{
          color: "var(--accent)",
          textDecoration: "underline",
          cursor: "pointer",
          fontWeight: 500,
        }}
        title={`打开 ${ref.path}:${ref.startLine}-${ref.endLine}`}
      >
        {label}
      </a>,
    );

    cursor = refEnd;
  }

  // Remaining text after last code ref
  if (cursor < text.length) {
    nodes.push(..._parseInlineMarkdown(text.slice(cursor)));
  }

  return nodes;
}

/** Parse inline markdown within a plain-text segment (no code refs). */
function _parseInlineMarkdown(text: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  const pattern = /(`[^`]+`|\*\*[^*]+\*\*|\[([^\]]+)\]\(([^)]+)\))/g;
  let last = 0;
  let match: RegExpExecArray | null;

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > last) {
      nodes.push(text.slice(last, match.index));
    }
    const raw = match[1];
    if (raw.startsWith("`") && raw.endsWith("`")) {
      nodes.push(
        <code
          key={`ic-${match.index}`}
          style={{
            background: "#e5e7eb",
            padding: "1px 4px",
            borderRadius: 3,
            fontSize: "0.92em",
            fontFamily: "monospace",
          }}
        >
          {raw.slice(1, -1)}
        </code>,
      );
    } else if (raw.startsWith("**") && raw.endsWith("**")) {
      nodes.push(<strong key={`b-${match.index}`}>{raw.slice(2, -2)}</strong>);
    } else if (raw.startsWith("[")) {
      const linkMatch = raw.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
      if (linkMatch) {
        nodes.push(
          <a
            key={`l-${match.index}`}
            href={linkMatch[2]}
            target="_blank"
            rel="noopener noreferrer"
            style={{ color: "var(--accent)", textDecoration: "underline" }}
          >
            {linkMatch[1]}
          </a>,
        );
      } else {
        nodes.push(raw);
      }
    }
    last = match.index + raw.length;
  }
  if (last < text.length) {
    nodes.push(text.slice(last));
  }
  return nodes;
}

export function renderMarkdown(content: string, onCodeRefClick?: CodeRefHandler): ReactNode[] {
  const lines = content.split("\n");
  const elements: ReactNode[] = [];
  let i = 0;
  let inCodeBlock = false;
  let codeLines: string[] = [];
  let codeLang = "";

  while (i < lines.length) {
    const line = lines[i];

    // Code block start/end
    if (line.trimStart().startsWith("```")) {
      if (inCodeBlock) {
        // End code block
        elements.push(
          <pre
            key={`cb-${i}`}
            style={{
              background: "#1e1e2e",
              color: "#e2e8f0",
              padding: "8px 10px",
              borderRadius: 6,
              fontSize: 10,
              fontFamily: "monospace",
              lineHeight: 1.5,
              overflow: "auto",
              maxHeight: 240,
              margin: "4px 0",
            }}
          >
            <code>{codeLines.join("\n")}</code>
          </pre>,
        );
        codeLines = [];
        inCodeBlock = false;
      } else {
        // Start code block
        inCodeBlock = true;
        codeLang = line.trimStart().slice(3).trim();
      }
      i++;
      continue;
    }

    if (inCodeBlock) {
      codeLines.push(line);
      i++;
      continue;
    }

    // Empty line
    if (line.trim() === "") {
      elements.push(<div key={`br-${i}`} style={{ height: 4 }} />);
      i++;
      continue;
    }

    // Horizontal rule
    if (/^[-*_]{3,}\s*$/.test(line.trim())) {
      elements.push(
        <hr
          key={`hr-${i}`}
          style={{
            border: "none",
            borderTop: "1px solid var(--border)",
            margin: "6px 0",
          }}
        />,
      );
      i++;
      continue;
    }

    // Header
    const headerMatch = line.match(/^(#{1,4})\s+(.+)/);
    if (headerMatch) {
      const level = headerMatch[1].length;
      const sizes = [15, 13, 12, 11] as const;
      elements.push(
        <div
          key={`h-${i}`}
          style={{
            fontSize: sizes[level - 1] ?? 11,
            fontWeight: 700,
            marginTop: level === 1 ? 6 : 4,
            marginBottom: 2,
            lineHeight: 1.4,
          }}
        >
          {parseInline(headerMatch[2], onCodeRefClick)}
        </div>,
      );
      i++;
      continue;
    }

    // Unordered list
    const listMatch = line.match(/^(\s*)[-*]\s+(.+)/);
    if (listMatch) {
      const indent = Math.floor((listMatch[1]?.length ?? 0) / 2) * 12;
      elements.push(
        <div
          key={`li-${i}`}
          style={{
            display: "flex",
            paddingLeft: 8 + indent,
            fontSize: 11,
            lineHeight: 1.6,
          }}
        >
          <span style={{ marginRight: 6, flexShrink: 0 }}>•</span>
          <span>{parseInline(listMatch[2], onCodeRefClick)}</span>
        </div>,
      );
      i++;
      continue;
    }

    // Numbered list
    const numMatch = line.match(/^(\s*)\d+\.\s+(.+)/);
    if (numMatch) {
      const indent = Math.floor((numMatch[1]?.length ?? 0) / 2) * 12;
      elements.push(
        <div
          key={`ol-${i}`}
          style={{
            display: "flex",
            paddingLeft: 8 + indent,
            fontSize: 11,
            lineHeight: 1.6,
          }}
        >
          <span style={{ marginRight: 6, flexShrink: 0, minWidth: 14 }}>{numMatch[0].trimStart().split(".")[0]}.</span>
          <span>{parseInline(numMatch[2], onCodeRefClick)}</span>
        </div>,
      );
      i++;
      continue;
    }

    // Regular paragraph
    elements.push(
      <div key={`p-${i}`} style={{ fontSize: 11, lineHeight: 1.6 }}>
        {parseInline(line, onCodeRefClick)}
      </div>,
    );
    i++;
  }

  // Unclosed code block
  if (inCodeBlock && codeLines.length > 0) {
    elements.push(
      <pre
        key="cb-end"
        style={{
          background: "#1e1e2e",
          color: "#e2e8f0",
          padding: "8px 10px",
          borderRadius: 6,
          fontSize: 10,
          fontFamily: "monospace",
          lineHeight: 1.5,
          overflow: "auto",
          maxHeight: 240,
          margin: "4px 0",
        }}
      >
        <code>{codeLines.join("\n")}</code>
      </pre>,
    );
  }

  return elements;
}
