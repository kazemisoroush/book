import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { BookSummary } from "@/lib/books";

import { BookList } from "./BookList";

const books: BookSummary[] = [
  {
    id: "the_gambler:fyodor_dostoyevsky",
    title: "The Gambler",
    author: "Fyodor Dostoyevsky",
    chapters: 1,
    characters: 2,
    cast: 0,
  },
  {
    id: "crime_and_punishment:fyodor_dostoyevsky",
    title: "Crime and Punishment",
    author: "Fyodor Dostoyevsky",
    chapters: 1,
    characters: 3,
    cast: 0,
  },
];

describe("BookList", () => {
  it("renders a card per book with title, author, and character count", () => {
    render(<BookList books={books} />);

    expect(screen.getByText("The Gambler")).toBeInTheDocument();
    expect(screen.getByText("Crime and Punishment")).toBeInTheDocument();
    expect(screen.getAllByText("Fyodor Dostoyevsky")).toHaveLength(2);
    expect(screen.getByText("2 characters")).toBeInTheDocument();
    expect(screen.getByText("3 characters")).toBeInTheDocument();
  });

  it("does not show a made-up run status", () => {
    render(<BookList books={books} />);

    expect(screen.queryByText(/not started/i)).not.toBeInTheDocument();
  });

  it("shows an empty state when there are no books", () => {
    render(<BookList books={[]} />);

    expect(screen.getByText(/No books on the table yet/i)).toBeInTheDocument();
  });
});
