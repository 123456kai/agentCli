type FileExplorerProps = {
  files: string[];
  query: string;
  onQueryChange: (query: string) => void;
  onOpen: (path: string) => void;
};

export function FileExplorer({ files, query, onQueryChange, onOpen }: FileExplorerProps) {
  return (
    <div className="fileExplorer">
      <h3>Files</h3>
      <input
        className="filterInput"
        value={query}
        onChange={(event) => onQueryChange(event.target.value)}
        placeholder="Filter files..."
      />
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
