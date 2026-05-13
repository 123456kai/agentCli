type FileExplorerProps = {
  files: string[];
  totalMatches: number;
  truncated: boolean;
  query: string;
  onQueryChange: (query: string) => void;
  onOpen: (path: string) => void;
};

export function FileExplorer({ files, totalMatches, truncated, query, onQueryChange, onOpen }: FileExplorerProps) {
  return (
    <div className="fileExplorer">
      <h3>Files</h3>
      <input
        className="filterInput"
        value={query}
        onChange={(event) => onQueryChange(event.target.value)}
        placeholder="Filter files..."
      />
      {truncated ? (
        <p className="muted">只显示部分文件（{files.length}/{totalMatches}），请使用搜索缩小范围。</p>
      ) : null}
      <div className="fileList">
        {files.map((file) => (
          <button className="fileRow" key={file} onClick={() => onOpen(file)}>
            <span className="fileIcon">›</span>
            {file}
          </button>
        ))}
      </div>
    </div>
  );
}
