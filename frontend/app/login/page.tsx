"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { NEW_PASSWORD_REQUIRED, signIn } from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [needsNewPassword, setNeedsNewPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await signIn(email, password, needsNewPassword ? newPassword : undefined);
      router.replace("/");
    } catch (err) {
      if (err instanceof Error && err.message === NEW_PASSWORD_REQUIRED) {
        setNeedsNewPassword(true);
        setError("First sign-in: choose a new password.");
      } else {
        setError("Sign-in failed. Check your email and password.");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login">
      <section className="book-head">
        <span className="eyebrow">The Casting Room</span>
        <h1>Sign in</h1>
        <p className="book-head__author">Enter the studio.</p>
      </section>

      <form className="login-form" onSubmit={onSubmit}>
        <label className="field">
          <span className="field__label">Email</span>
          <input
            className="field__input"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoComplete="username"
          />
        </label>
        <label className="field">
          <span className="field__label">Password</span>
          <input
            className="field__input"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            autoComplete="current-password"
          />
        </label>
        {needsNewPassword && (
          <label className="field">
            <span className="field__label">New password</span>
            <input
              className="field__input"
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
              autoComplete="new-password"
            />
          </label>
        )}
        {error && <p className="muted-note muted-note--error">{error}</p>}
        <button className="btn" type="submit" disabled={busy}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}
