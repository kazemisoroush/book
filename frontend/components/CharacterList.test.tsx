import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { BookDetail } from "@/lib/studio";

import { CharacterList } from "./CharacterList";

function book(overrides: Partial<BookDetail> = {}): BookDetail {
  return {
    id: "the_gambler",
    title: "The Gambler",
    author: "Fyodor Dostoyevsky",
    chapters: [],
    characters: [],
    voice_assignments: {},
    ...overrides,
  };
}

describe("CharacterList", () => {
  it("shows traits and marks cast vs uncast characters", () => {
    render(
      <CharacterList
        book={book({
          characters: [
            { id: 1, name: "Narrator", gender: "male", age: "old", accent: "russian" },
            { id: 2, name: "Polina", gender: "female", age: "young", accent: "russian" },
          ],
          voice_assignments: { "1": "voice-a" },
        })}
      />,
    );

    expect(screen.getByText("Narrator")).toBeInTheDocument();
    expect(screen.getByText("Polina")).toBeInTheDocument();
    expect(screen.getAllByText("Cast")).toHaveLength(1);
    expect(screen.getAllByText("Uncast")).toHaveLength(1);
  });

  it("prompts to run ai when there are no characters", () => {
    render(<CharacterList book={book()} />);
    expect(screen.getByText(/Run the/i)).toBeInTheDocument();
  });
});
