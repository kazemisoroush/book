export function SummaryStrip({
  chapters,
  characters,
  cast,
}: {
  chapters: number;
  characters: number;
  cast: number;
}) {
  return (
    <div className="stats">
      <Stat label="Chapters" value={chapters} />
      <Stat label="Characters" value={characters} />
      <Stat label="Cast" value={`${cast} / ${characters}`} accent={cast > 0} />
    </div>
  );
}

function Stat({
  label,
  value,
  accent,
}: {
  label: string;
  value: number | string;
  accent?: boolean;
}) {
  return (
    <div className="stat">
      <div className={accent ? "stat__value stat__value--cast" : "stat__value"}>
        {value}
      </div>
      <div className="stat__label">{label}</div>
    </div>
  );
}
