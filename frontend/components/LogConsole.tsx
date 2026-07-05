import type { RunStatus } from "@/lib/studio";

export function LogConsole({
  run,
  lines,
  finalStatus,
}: {
  run: RunStatus;
  lines: string[];
  finalStatus: RunStatus | null;
}) {
  const state = finalStatus?.state ?? "running";
  return (
    <div className="console">
      <div className="console__head">
        <span className={`run-state run-state--${stateKind(state)}`}>
          {state}
        </span>
        <span className="console__meta">
          {run.workflow} · {run.run_id.slice(0, 8)}
        </span>
      </div>
      <pre className="console__body">
        {lines.length === 0
          ? "Waiting for output…"
          : lines.map((line, i) => <div key={i}>{line}</div>)}
      </pre>
    </div>
  );
}

function stateKind(state: string): string {
  if (state === "succeeded") return "ok";
  if (state === "failed") return "fail";
  return "running";
}
