"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { isAuthenticated, signOut } from "@/lib/auth";

// Shows a sign-out control only once signed in, so it stays hidden in local dev and on /login.
export function SignOut() {
  const router = useRouter();
  const [authed, setAuthed] = useState(false);

  useEffect(() => {
    setAuthed(isAuthenticated());
  }, []);

  if (!authed) return null;

  return (
    <button
      className="signout"
      type="button"
      onClick={() => {
        signOut();
        router.replace("/login");
      }}
    >
      Sign out
    </button>
  );
}
