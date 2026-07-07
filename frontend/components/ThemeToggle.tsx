"use client";

import { useEffect, useState } from "react";

type Theme = "dark" | "light";

// Toggle the ground between the baize-black night and the aged-paper day, persisting the choice.
export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>("dark");

  useEffect(() => {
    const current = document.documentElement.dataset.theme;
    setTheme(current === "light" ? "light" : "dark");
  }, []);

  function toggle() {
    const next: Theme = theme === "dark" ? "light" : "dark";
    setTheme(next);
    if (next === "light") {
      document.documentElement.dataset.theme = "light";
    } else {
      delete document.documentElement.dataset.theme;
    }
    try {
      localStorage.setItem("theme", next);
    } catch {
      // Storage may be unavailable; the toggle still works for the session.
    }
  }

  const nextLabel = theme === "dark" ? "light" : "dark";
  return (
    <button
      className="theme-toggle"
      onClick={toggle}
      type="button"
      aria-label={`Switch to ${nextLabel} mode`}
      title={`Switch to ${nextLabel} mode`}
    >
      {theme === "dark" ? "☀" : "☾"}
    </button>
  );
}
