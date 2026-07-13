"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useCallback, useRef, useState } from "react";

import { speakerColor } from "@/lib/speakerColor";
import type { BeatView, CastMember } from "@/lib/studio";
import { type BeatEdit, type BeatSave, useChapterReview } from "@/lib/useChapterReview";
import { useDismissable } from "@/lib/useDismissable";
import { useRequireAuth } from "@/lib/useRequireAuth";

export function Review() {
  const ready = useRequireAuth();
  const params = useSearchParams();
  const bookId = params.get("id") ?? "";
  const number = Number(params.get("chapter") ?? "1");
  const { state, saves, saveBeat } = useChapterReview(bookId, number);

  if (!ready) return null;

  return (
    <>
      <div className="crumb">
        <Link href={`/book?id=${encodeURIComponent(bookId)}`} className="crumb__back">
          &larr; Chapters
        </Link>
      </div>

      <section className="book-head">
        <span className="eyebrow">Chapter {number} &middot; Attribution review</span>
        <h1>Who is speaking?</h1>
        <p className="book-head__author">
          The AI cast every line to a voice and guessed its feeling. Reassign the speaker, fix the
          wording, or retune the emotion &mdash; each edit saves the moment you click away.
        </p>
      </section>

      {state.status === "loading" && <p className="muted-note">Reading the beats…</p>}

      {state.status === "error" && (
        <div className="notice notice--error">
          <h3>The table is dark</h3>
          <p>{state.message} Start it with <code>make serve</code>.</p>
        </div>
      )}

      {state.status === "ready" && (
        <>
          <CastLegend cast={state.chapter.cast} />
          {state.chapter.beats.length === 0 ? (
            <p className="muted-note">
              This chapter is parsed but has no beats yet. Extract beats first.
            </p>
          ) : (
            <div className="ledger">
              <div className="ledger__head">
                <span>Parsed &mdash; source</span>
                <span>Beats &mdash; edit speaker, text, or emotion</span>
              </div>
              <div className="ledger__cols">
                <div className="ledger__src">
                  {state.chapter.sections.map((section, i) => (
                    <p key={i} className="src-para">
                      {section.text}
                    </p>
                  ))}
                </div>
                <div className="ledger__beats">
                  {state.chapter.beats.map((beat) => (
                    <BeatCard
                      key={beat.index}
                      beat={beat}
                      cast={state.chapter.cast}
                      save={saves[beat.index]}
                      onChange={(change) => saveBeat(beat.index, change)}
                    />
                  ))}
                </div>
              </div>
            </div>
          )}
          <p className="autosave-note">
            Every change saves on its own &middot; {state.chapter.beats.length} beats across{" "}
            {state.chapter.cast.length} voices
          </p>
        </>
      )}
    </>
  );
}

function CastLegend({ cast }: { cast: CastMember[] }) {
  if (cast.length === 0) return null;
  return (
    <div className="cast-legend">
      <span className="cast-legend__label">Cast</span>
      {cast.map((member) => (
        <span key={member.id ?? "narrator"} className="cast-chip">
          <span className="sw" style={{ background: speakerColor(member.id) }} />
          <b>{member.name}</b>
          <span className="ct">{member.count}</span>
        </span>
      ))}
    </div>
  );
}

function BeatCard({
  beat,
  cast,
  save,
  onChange,
}: {
  beat: BeatView;
  cast: CastMember[];
  save?: BeatSave;
  onChange: (change: BeatEdit) => void;
}) {
  const color = speakerColor(beat.character_id);
  return (
    <div className="beat" style={{ borderLeftColor: color }}>
      <div className="beat__top">
        <SpeakerMenu
          current={beat.character_name}
          color={color}
          cast={cast}
          disabled={save?.state === "saving"}
          onPick={(id) => onChange({ character_id: id })}
        />
        <span className="btype">{beat.beat_type.replace(/_/g, " ")}</span>
        <SaveChip save={save} onRetry={() => save?.state === "error" && onChange(save.change)} />
        <EditableField
          value={beat.emotion ?? ""}
          className="emotion"
          ariaLabel="Beat emotion"
          placeholder="add emotion"
          onCommit={(text) => onChange({ emotion: text })}
        />
      </div>
      <EditableField
        value={beat.text}
        className="beat__text"
        ariaLabel="Beat text"
        onCommit={(text) => onChange({ text })}
      />
    </div>
  );
}

function SpeakerMenu({
  current,
  color,
  cast,
  disabled,
  onPick,
}: {
  current: string;
  color: string;
  cast: CastMember[];
  disabled: boolean;
  onPick: (id: number | null) => void;
}) {
  const [open, setOpen] = useState(false);
  const close = useCallback(() => setOpen(false), []);
  const ref = useDismissable<HTMLDivElement>(open, close);

  return (
    <div className="who-wrap" ref={ref}>
      <button
        type="button"
        className={`who${open ? " who--open" : ""}`}
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <span className="sw" style={{ background: color }} />
        {current}
        <span className="caret">▾</span>
      </button>
      {open && (
        <div className="who-menu" role="listbox">
          <div className="who-menu__label">Reassign to</div>
          {cast.map((member) => (
            <button
              type="button"
              key={member.id ?? "narrator"}
              role="option"
              aria-selected={member.name === current}
              className={`who-menu__item${member.name === current ? " who-menu__item--on" : ""}`}
              onClick={() => {
                setOpen(false);
                if (member.name !== current) onPick(member.id ?? null);
              }}
            >
              <span className="sw" style={{ background: speakerColor(member.id) }} />
              {member.name}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function SaveChip({ save, onRetry }: { save?: BeatSave; onRetry: () => void }) {
  if (!save) return null;
  if (save.state === "saving") {
    return (
      <span className="save save--busy">
        <span className="spinner" />
        Saving…
      </span>
    );
  }
  if (save.state === "saved") {
    return <span className="save save--ok">✓ saved</span>;
  }
  return (
    <span className="save save--err">
      ⚠ Couldn’t save ·{" "}
      <button type="button" className="save__retry" onClick={onRetry}>
        Retry
      </button>
    </span>
  );
}

function EditableField({
  value,
  className,
  ariaLabel,
  placeholder,
  onCommit,
}: {
  value: string;
  className: string;
  ariaLabel: string;
  placeholder?: string;
  onCommit: (text: string) => void;
}) {
  const ref = useRef<HTMLSpanElement>(null);

  function commit() {
    const next = (ref.current?.textContent ?? "").trim();
    if (next !== value) onCommit(next);
  }
  function onKeyDown(event: React.KeyboardEvent<HTMLSpanElement>) {
    if (event.key === "Enter") {
      event.preventDefault();
      ref.current?.blur();
    }
    if (event.key === "Escape") {
      if (ref.current) ref.current.textContent = value;
      ref.current?.blur();
    }
  }

  return (
    <span
      // Remount when the committed value changes so contentEditable shows the reconciled text.
      key={value}
      ref={ref}
      className={`${className} editable`}
      role="textbox"
      tabIndex={0}
      aria-label={ariaLabel}
      data-placeholder={placeholder}
      contentEditable
      suppressContentEditableWarning
      onBlur={commit}
      onKeyDown={onKeyDown}
    >
      {value}
    </span>
  );
}
