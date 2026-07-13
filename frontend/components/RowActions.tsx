"use client";

import Link from "next/link";
import { useCallback, useState } from "react";

import { useDismissable } from "@/lib/useDismissable";

// The per-chapter actions, collapsed into one ⋯ menu so the row stays calm: open the attribution
// review, or kick off a run. Replaces the always-visible Extract/Narrate buttons.
export function RowActions({
  reviewHref,
  canRun,
  hasBeats,
  running,
  onExtract,
  onNarrate,
  failed,
}: {
  reviewHref: string;
  canRun: boolean;
  hasBeats: boolean;
  running: boolean;
  failed: boolean;
  onExtract: () => void;
  onNarrate: () => void;
}) {
  const [open, setOpen] = useState(false);
  const close = useCallback(() => setOpen(false), []);
  const ref = useDismissable<HTMLDivElement>(open, close);

  function run(action: () => void) {
    setOpen(false);
    action();
  }

  return (
    <div className="rowmenu" ref={ref}>
      <button
        type="button"
        className={`rowmenu__trigger${open ? " rowmenu__trigger--open" : ""}`}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="Chapter actions"
        onClick={() => setOpen((v) => !v)}
      >
        ⋯
      </button>
      {open && (
        <div className="rowmenu__menu" role="menu">
          <Link
            href={reviewHref}
            role="menuitem"
            className="rowmenu__item rowmenu__item--primary"
            onClick={() => setOpen(false)}
          >
            Review attribution
          </Link>
          <button
            type="button"
            role="menuitem"
            className="rowmenu__item"
            disabled={!canRun || running}
            onClick={() => run(onExtract)}
          >
            {failed ? "Retry extract beats" : hasBeats ? "Re-extract beats" : "Extract beats"}
          </button>
          <button
            type="button"
            role="menuitem"
            className="rowmenu__item"
            disabled={!canRun || running || !hasBeats}
            onClick={() => run(onNarrate)}
          >
            Narrate
          </button>
          {!canRun && (
            <p className="rowmenu__hint">Re-import this book to run its chapters.</p>
          )}
        </div>
      )}
    </div>
  );
}
