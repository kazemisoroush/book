export function FileList({ files }: { files: string[] }) {
  if (files.length === 0) {
    return <p className="muted-note">No artifacts yet.</p>;
  }

  return (
    <ul className="files">
      {files.map((file) => (
        <li className="files__row" key={file}>
          <span className="files__path">{file}</span>
        </li>
      ))}
    </ul>
  );
}
