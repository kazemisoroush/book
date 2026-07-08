"use client";

import { useEffect, useRef, useState } from "react";

import { startRun } from "@/lib/studio";

const EXAMPLE_URL = "https://www.gutenberg.org/cache/epub/2197/pg2197-images.zip";

type Status = "idle" | "submitting" | "started" | "error";

export function ImportModal({
  onClose,
  onStarted,
}: {
  onClose: () => void;
  onStarted: () => void;
}) {
  const [url, setUrl] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setStatus("submitting");
    try {
      await startRun({ workflow: "parse", url, startChapter: 1, refresh: false });
      setStatus("started");
      onStarted();
    } catch {
      setStatus("error");
    }
  }

  return (
    <div className="scrim" role="presentation" onClick={onClose}>
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="import-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal__top">
          <span className="modal__eyebrow">New title</span>
          <h2 className="modal__title" id="import-title">Import a book</h2>
          <p className="modal__sub">
            Bring a public-domain book into the studio to parse and cast.
          </p>
          <button
            className="modal__close"
            type="button"
            aria-label="Close"
            onClick={onClose}
          >
            ×
          </button>
        </div>

        {status === "started" ? (
          <>
            <div className="modal__body">
              <div className="notice">
                <h3>Parsing started</h3>
                <p className="muted-note">
                  The studio is downloading and parsing the book. It appears in the
                  list once its chapters are ready.
                </p>
              </div>
            </div>
            <div className="modal__foot">
              <button className="btn-primary" type="button" onClick={onClose}>
                Done
              </button>
            </div>
          </>
        ) : (
          <form onSubmit={onSubmit}>
            <div className="modal__body">
              <div>
                <div className="field-label">Source</div>
                <div className="sources">
                  <label className="source source--active">
                    <span className="source__dot" />
                    <span className="source__text">
                      <span className="source__name">Project Gutenberg</span>
                      <span className="source__desc">
                        Paste a book&rsquo;s Gutenberg download URL.
                      </span>
                    </span>
                  </label>
                  <div className="source source--disabled" aria-disabled="true">
                    <span className="source__dot" />
                    <span className="source__text">
                      <span className="source__name">Upload a file</span>
                      <span className="source__desc">EPUB or plain text from your machine.</span>
                    </span>
                    <span className="soon">Soon</span>
                  </div>
                  <div className="source source--disabled" aria-disabled="true">
                    <span className="source__dot" />
                    <span className="source__text">
                      <span className="source__name">Web URL</span>
                      <span className="source__desc">Any public plain-text book.</span>
                    </span>
                    <span className="soon">Soon</span>
                  </div>
                </div>
              </div>

              <div>
                <div className="field-label">Gutenberg URL</div>
                <input
                  ref={inputRef}
                  className="url-input"
                  type="url"
                  value={url}
                  onChange={(event) => setUrl(event.target.value)}
                  placeholder={EXAMPLE_URL}
                  required
                  aria-label="Gutenberg URL"
                />
                <p className="url-hint">
                  Paste the book&rsquo;s download file, e.g. its{" "}
                  <code>pg2197-images.zip</code>. The studio downloads and parses it
                  into chapters.
                </p>
                {status === "error" && (
                  <p className="muted-note muted-note--error">
                    Could not start the import. Check the URL and that the API is running.
                  </p>
                )}
              </div>
            </div>

            <div className="modal__foot">
              <button className="btn-ghost" type="button" onClick={onClose}>
                Cancel
              </button>
              <button className="btn-primary" type="submit" disabled={status === "submitting"}>
                {status === "submitting" ? "Starting…" : "Import book"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
