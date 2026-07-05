import { apiClient } from "@/lib/api/client";

// A book id from the API is a "title:author" slug, for example
// "the_gambler:fyodor_dostoyevsky". These helpers turn it into something readable.
export type BookSummary = {
  id: string;
  title: string;
  author: string;
};

// Fetch and shape the book list. This is the single place the studio reads books.
// Interim: the API returns bare ids, so the display title and author are decoded from
// the slug here. The proper fix is for the API to return display fields (SOR-30).
export async function fetchBooks(): Promise<BookSummary[]> {
  const { data, error } = await apiClient().GET("/books");
  if (error || !data) {
    throw new Error("Could not reach the studio API.");
  }
  return data.books.map(parseBookId);
}

export function parseBookId(id: string): BookSummary {
  const [titleSlug, authorSlug] = id.split(":");
  return {
    id,
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
