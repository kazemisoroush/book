"use client";

import { useEffect, useState } from "react";

import { BookList } from "@/components/BookList";
import { fetchBooks, type BookSummary } from "@/lib/books";
import { useRequireAuth } from "@/lib/useRequireAuth";

type State =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; books: BookSummary[] };

export default function HomePage() {
  const ready = useRequireAuth();
  const [state, setState] = useState<State>({ status: "loading" });

  useEffect(() => {
    if (!ready) return;
    let cancelled = false;
    fetchBooks()
      .then((books) => {
        if (!cancelled) setState({ status: "ready", books });
      })
      .catch(() => {
        if (!cancelled) {
          setState({ status: "error", message: "Could not reach the studio API." });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [ready]);

  if (!ready) return null;

  return (
    <>
      <section className="hero">
        <span className="eyebrow">The Casting Room</span>
        <h1>
          Give every voice <em>a face</em>.
        </h1>
        <p>
          Parse a book, cast its characters against the voice library, and
          produce it chapter by chapter. Pick a title to open its dossier.
        </p>
      </section>

      <section>
        <div className="section-head">
          <h2>Books</h2>
          {state.status === "ready" && (
            <span className="count">
              {state.books.length}{" "}
              {state.books.length === 1 ? "title" : "titles"}
            </span>
          )}
        </div>

        {state.status === "loading" && (
          <div className="grid" aria-busy="true" aria-label="Loading books">
            {Array.from({ length: 6 }).map((_, i) => (
              <div className="skeleton" key={i} />
            ))}
          </div>
        )}

        {state.status === "error" && (
          <div className="notice notice--error">
            <h3>The table is dark</h3>
            <p>{state.message} Start it with <code>make serve</code>.</p>
          </div>
        )}

        {state.status === "ready" && <BookList books={state.books} />}
      </section>
    </>
  );
}
