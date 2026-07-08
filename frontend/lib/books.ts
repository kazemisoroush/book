import { apiClient } from "@/lib/api/client";

// A book as the studio shows it: real metadata from the API plus the casting counts.
export type BookSummary = {
  id: string;
  title: string;
  author: string;
  language?: string;
  releaseDate?: string;
  chapters: number;
  characters: number;
  cast: number;
};

// Fetch the book list. This is the single place the studio reads books. The API returns the
// real title, author, and counts, so nothing here decodes the id.
export async function fetchBooks(): Promise<BookSummary[]> {
  const { data, error } = await (await apiClient()).GET("/books");
  if (error || !data) {
    throw new Error("Could not reach the studio API.");
  }
  return data.books.map((book) => ({
    id: book.id,
    title: book.title,
    author: book.author ?? "Unknown",
    language: book.language ?? undefined,
    releaseDate: book.release_date ?? undefined,
    chapters: book.chapters,
    characters: book.characters,
    cast: book.cast,
  }));
}

// A readable title and author decoded from a "title:author" slug id, for the workspace header
// where the full metadata is not loaded yet. The list uses the API metadata instead.
export function parseBookId(id: string): { title: string; author: string } {
  const [titleSlug, authorSlug] = id.split(":");
  return {
    title: humanize(titleSlug),
    author: authorSlug ? humanize(authorSlug) : "Unknown",
  };
}

function humanize(slug: string): string {
  return slug
    .replace(/_/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
