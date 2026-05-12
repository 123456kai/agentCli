type FileTabsProps = {
  files: string[];
  activePath: string;
  onSelect: (path: string) => void;
};

export function FileTabs({ files, activePath, onSelect }: FileTabsProps) {
  return (
    <div className="fileTabs">
      {files.length === 0 ? <span className="muted">No file open</span> : null}
      {files.map((file) => (
        <button
          className={file === activePath ? "fileTab fileTabActive" : "fileTab"}
          key={file}
          onClick={() => onSelect(file)}
        >
          {file.split("/").at(-1)}
        </button>
      ))}
    </div>
  );
}
