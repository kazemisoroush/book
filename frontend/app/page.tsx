"use client";

import { useEffect, useState } from "react";

import { BookList } from "@/components/BookList";
import { apiClient } from "@/lib/api/client";
import { parseBookId, type BookSummary } from "@/lib/books";

type State =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; books: BookSummary[] };

export default function HomePage() {
  const [state, setState] = useState<State>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    apiClient()
      .GET("/books")
      .then(({ data, error }) => {
        if (cancelled) return;
        if (error || !data) {
          setState({ status: "error", message: "Could not reach the studio API." });
          return;
        }
        setState({
          status: "ready",
          books: data.books.map(parseBookId),
        });
      })
      .catch(() => {
        if (!cancelled) {
          setState({ status: "error", message: "Could not reach the studio API." });
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <>
      <section className="hero">
        <span className="eyebrow">The Casting Room</span>
        <h1>
          Give every voice in <em>The Gambler</em> a face.
        </h1>
        <p>
          Parse a book, cast its characters against the ElevenLabs voice library,
          and produce it chapter by chapter. Pick a title to open its dossier.
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
