type FileTabsProps = {
  files: string[];
  activePath: string;
  onSelect: (path: string) => void;
  onClose: (path: string) => void;
};

export function FileTabs({ files, activePath, onSelect, onClose }: FileTabsProps) {
  if (files.length === 0) {
    return (
      <div className="fileTabs">
        <span className="muted">No file open</span>
      </div>
    );
  }

  return (
    <div className="fileTabs">
      {files.map((file) => (
        <button
          className={file === activePath ? "fileTab fileTabActive" : "fileTab"}
          key={file}
          onClick={() => onSelect(file)}
        >
          {file.split("/").at(-1)}
          <span
            className="fileTabClose"
            title="Close"
            onClick={(e) => {
              e.stopPropagation();
              onClose(file);
            }}
          >
            ×
          </span>
        </button>
      ))}
    </div>
  );
}
