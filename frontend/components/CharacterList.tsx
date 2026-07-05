import type { BookDetail, CharacterInfo } from "@/lib/studio";

export function CharacterList({ book }: { book: BookDetail }) {
  if (book.characters.length === 0) {
    return (
      <p className="muted-note">
        No characters yet. Run the <code>ai</code> workflow to discover them.
      </p>
    );
  }

  return (
    <ul className="cast-list">
      {book.characters.map((character) => (
        <CharacterRow
          key={character.id}
          character={character}
          voice={book.voice_assignments[String(character.id)]}
        />
      ))}
    </ul>
  );
}

function CharacterRow({
  character,
  voice,
}: {
  character: CharacterInfo;
  voice?: string;
}) {
  const traits = [character.gender, character.age, character.accent].filter(
    Boolean,
  ) as string[];

  return (
    <li className="cast-row">
      <div className="cast-row__who">
        <span className="cast-row__name">{character.name}</span>
        <span className="cast-row__traits">
          {traits.map((trait) => (
            <span className="chip" key={trait}>
              {trait.replace(/_/g, " ")}
            </span>
          ))}
        </span>
      </div>
      {voice ? (
        <span className="cast-badge cast-badge--cast">Cast</span>
      ) : (
        <span className="cast-badge">Uncast</span>
      )}
    </li>
  );
}
