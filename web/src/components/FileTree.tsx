type FileTreeProps = {
  files: string[];
  onOpen: (path: string) => void;
};

export function FileTree({ files, onOpen }: FileTreeProps) {
  return (
    <div>
      <h3>Recent Files</h3>
      {files.length === 0 ? <p className="muted">No files opened yet.</p> : null}
      {files.map((file) => (
        <button key={file} onClick={() => onOpen(file)}>
          {file}
        </button>
      ))}
    </div>
  );
}
