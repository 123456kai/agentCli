import { useEffect, useRef } from "react";
import Editor, { OnMount } from "@monaco-editor/react";

import { HighlightedRange, SourceFile } from "../../api/events";
import { FileTabs } from "./FileTabs";

type CodeEditorProps = {
  openFiles: string[];
  activeFile: SourceFile | null;
  highlightedRange?: HighlightedRange;
  onSelectFile: (path: string) => void;
};

function languageFor(path: string): string {
  if (path.endsWith(".py")) return "python";
  if (path.endsWith(".ts")) return "typescript";
  if (path.endsWith(".tsx")) return "typescript";
  if (path.endsWith(".js")) return "javascript";
  if (path.endsWith(".json")) return "json";
  if (path.endsWith(".toml")) return "toml";
  if (path.endsWith(".md")) return "markdown";
  return "plaintext";
}

export function CodeEditor({ openFiles, activeFile, highlightedRange, onSelectFile }: CodeEditorProps) {
  const editorRef = useRef<Parameters<OnMount>[0] | null>(null);
  const monacoRef = useRef<Parameters<OnMount>[1] | null>(null);
  const decorationIds = useRef<string[]>([]);
  const rangeLabel =
    highlightedRange && activeFile?.path === highlightedRange.path
      ? `lines ${highlightedRange.startLine}-${highlightedRange.endLine}`
      : "no active highlight";

  useEffect(() => {
    const editor = editorRef.current;
    const monaco = monacoRef.current;
    if (!editor || !monaco) return;
    decorationIds.current = editor.deltaDecorations(decorationIds.current, []);
    if (!highlightedRange || activeFile?.path !== highlightedRange.path) return;
    decorationIds.current = editor.deltaDecorations(decorationIds.current, [
      {
        range: new monaco.Range(highlightedRange.startLine, 1, highlightedRange.endLine, 1),
        options: {
          isWholeLine: true,
          className: "agentLineHighlight",
          glyphMarginClassName: "agentLineGlyph",
        },
      },
    ]);
    editor.revealLineInCenter(highlightedRange.startLine);
  }, [activeFile?.path, highlightedRange]);

  const handleMount: OnMount = (editor, monaco) => {
    editorRef.current = editor;
    monacoRef.current = monaco;
  };

  return (
    <div className="codeEditor">
      <FileTabs files={openFiles} activePath={activeFile?.path ?? ""} onSelect={onSelectFile} />
      <div className="breadcrumb">
        <span>{activeFile?.path ?? "No file selected"}</span>
        <span className="muted">{rangeLabel}</span>
      </div>
      <div className="monacoFrame">
        <Editor
          height="100%"
          theme="vs-dark"
          onMount={handleMount}
          language={activeFile ? languageFor(activeFile.path) : "plaintext"}
          path={activeFile?.path ?? "empty.txt"}
          value={activeFile?.content ?? "// Source files open here as the agent reads."}
          options={{
            readOnly: true,
            minimap: { enabled: false },
            fontSize: 13,
            lineNumbers: "on",
            scrollBeyondLastLine: false,
            wordWrap: "on",
          }}
        />
      </div>
    </div>
  );
}
