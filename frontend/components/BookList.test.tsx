import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { parseBookId } from "@/lib/books";

import { BookList } from "./BookList";

describe("BookList", () => {
  it("renders a card per book with title and author", () => {
    const books = [
      "the_gambler:fyodor_dostoyevsky",
      "crime_and_punishment:fyodor_dostoyevsky",
    ].map(parseBookId);

    render(<BookList books={books} />);

    expect(screen.getByText("The Gambler")).toBeInTheDocument();
    expect(screen.getByText("Crime And Punishment")).toBeInTheDocument();
    expect(screen.getAllByText("Fyodor Dostoyevsky")).toHaveLength(2);
  });

  it("shows an empty state when there are no books", () => {
    render(<BookList books={[]} />);

    expect(screen.getByText(/No books on the table yet/i)).toBeInTheDocument();
  });
});
