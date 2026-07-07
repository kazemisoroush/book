"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { CharacterList } from "@/components/CharacterList";
import { FileList } from "@/components/FileList";
import { RunPanel } from "@/components/RunPanel";
import { SummaryStrip } from "@/components/SummaryStrip";
import { parseBookId } from "@/lib/books";
import { castCount } from "@/lib/studio";
import { useBook } from "@/lib/useBook";
import { useRequireAuth } from "@/lib/useRequireAuth";

export function Workspace() {
  const ready = useRequireAuth();
  const id = useSearchParams().get("id") ?? "";
  const state = useBook(id);
  const display = parseBookId(id);

  if (!ready) return null;

  return (
    <>
      <div className="crumb">
        <Link href="/" className="crumb__back">
          &larr; All books
        </Link>
      </div>

      <section className="book-head">
        <span className="eyebrow">The Dossier</span>
        <h1>{display.title}</h1>
        <p className="book-head__author">{display.author}</p>
      </section>

      {state.status === "loading" && (
        <p className="muted-note">Opening the dossier…</p>
      )}

      {state.status === "error" && (
        <div className="notice notice--error">
          <h3>The table is dark</h3>
          <p>{state.message} Start it with <code>make serve</code>.</p>
        </div>
      )}

      {state.status === "ready" && (
        <>
          <SummaryStrip
            chapters={state.book.chapters.length}
            characters={state.book.characters.length}
            cast={castCount(state.book)}
          />

          <Section title="Run a workflow">
            <RunPanel />
          </Section>

          <Section title="Cast">
            <CharacterList book={state.book} />
          </Section>

          <Section title="Artifacts">
            <FileList files={state.files} />
          </Section>
        </>
      )}
    </>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section>
      <div className="section-head">
        <h2>{title}</h2>
      </div>
      {children}
    </section>
  );
}
