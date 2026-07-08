import createClient from "openapi-fetch";

import { endSession, getIdToken } from "@/lib/auth";
import { loadConfig } from "@/lib/config";

import type { paths } from "./schema";

// The typed API client, generated from openapi.yaml. It targets the API url from config.json
// and attaches the Cognito id token, so the frontend never talks to the backend any other way.
// A 401 means the token expired or was revoked, so it ends the session (auth owns that).
export async function apiClient() {
  const { apiUrl } = await loadConfig();
  const token = getIdToken();
  const client = createClient<paths>({
    baseUrl: apiUrl,
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  client.use({
    onResponse({ response }) {
      if (response.status === 401) endSession();
      return undefined;
    },
  });
  return client;
}
