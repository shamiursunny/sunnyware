import { LibraryFile } from '../api';

interface Props { files: LibraryFile[]; }

export default function Library({ files }: Props) {
  const download = (f: LibraryFile) => {
    if (!f.content) return;
    const a = document.createElement('a');
    a.href = f.content;
    a.download = f.name;
    a.click();
  };
  return (
    <div className="library-view">
      <h2>Library ({files.length})</h2>
      {files.length === 0 && <p className="library-empty">No files uploaded yet.</p>}
      <div className="library-list">
        {files.map((f) => (
          <div key={f.id} className="library-item">
            <div className="library-icon">DOC</div>
            <div className="library-info">
              <div className="library-name">{f.name}</div>
              <div className="library-meta">{f.type} / {(f.size / 1024).toFixed(1)} KB / {f.kind}</div>
            </div>
            <button className="library-download" onClick={() => download(f)} disabled={!f.content}>
              Download
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
