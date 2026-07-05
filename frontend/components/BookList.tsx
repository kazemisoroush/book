import type { BookSummary } from "@/lib/books";

export function BookList({ books }: { books: BookSummary[] }) {
  if (books.length === 0) {
    return (
      <div className="notice">
        <h3>No books on the table yet</h3>
        <p>
          Parse one first, for example{" "}
          <code>make read GUTENBERG_URL=&hellip;</code>, then it appears here to
          cast and produce.
        </p>
      </div>
    );
  }

  return (
    <ul className="grid" style={{ listStyle: "none", margin: 0, padding: 0 }}>
      {books.map((book, i) => (
        <li key={book.id}>
          <a className="dossier" href={`/books/${encodeURIComponent(book.id)}/`}>
            <div className="dossier__top">
              <div>
                <div className="dossier__title">{book.title}</div>
                <div className="dossier__author">{book.author}</div>
              </div>
              <span className="dossier__index">
                {String(i + 1).padStart(2, "0")}
              </span>
            </div>
            <div className="dossier__foot">
              <span className="pill">
                <span className="pill__dot" />
                Not started
              </span>
              <span className="open">Open the dossier &rarr;</span>
            </div>
          </a>
        </li>
      ))}
    </ul>
  );
}
