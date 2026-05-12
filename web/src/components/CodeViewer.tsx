type CodeViewerProps = {
  code: string;
  highlightedRange?: { startLine: number; endLine: number };
};

export function CodeViewer({ code, highlightedRange }: CodeViewerProps) {
  return (
    <section>
      <h2>CodeViewer</h2>
      {highlightedRange ? (
        <p className="muted">
          Highlighting lines {highlightedRange.startLine}-{highlightedRange.endLine}
        </p>
      ) : null}
      <pre>{code}</pre>
    </section>
  );
}
