"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { isAuthenticated } from "@/lib/auth";
import { loadConfig } from "@/lib/config";

// Gate a page behind Cognito when auth is configured (the deployed studio), and let it through
// untouched in local dev where no Cognito is set. Returns whether the page may render.
export function useRequireAuth(): boolean {
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    loadConfig().then((config) => {
      if (cancelled) return;
      const authRequired = Boolean(config.cognitoClientId);
      if (authRequired && !isAuthenticated()) {
        router.replace("/login");
      } else {
        setReady(true);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [router]);

  return ready;
}
