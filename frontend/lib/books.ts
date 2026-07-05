// A book id from the API is a "title:author" slug, for example
// "the_gambler:fyodor_dostoyevsky". These helpers turn it into something readable.
export type BookSummary = {
  id: string;
  title: string;
  author: string;
};

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
