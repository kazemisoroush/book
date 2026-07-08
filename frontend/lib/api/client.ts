import createClient from "openapi-fetch";

import { getIdToken, signOut } from "@/lib/auth";
import { loadConfig } from "@/lib/config";

import type { paths } from "./schema";

// A 401 means the id token expired or was revoked. Clear it and send the user back to the
// login page, unless they are already there (nothing on /login calls the API, so no loop).
function onUnauthorized(): void {
  signOut();
  if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
    window.location.assign("/login");
  }
}

// The typed API client, generated from openapi.yaml. It targets the API url from config.json
// and attaches the Cognito id token, so the frontend never talks to the backend any other way.
export async function apiClient() {
  const { apiUrl } = await loadConfig();
  const token = getIdToken();
  const client = createClient<paths>({
    baseUrl: apiUrl,
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  client.use({
    onResponse({ response }) {
      if (response.status === 401) onUnauthorized();
      return undefined;
    },
  });
  return client;
}
