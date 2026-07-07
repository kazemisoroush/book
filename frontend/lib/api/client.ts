import createClient from "openapi-fetch";

import { getIdToken } from "@/lib/auth";
import { loadConfig } from "@/lib/config";

import type { paths } from "./schema";

// The typed API client, generated from openapi.yaml. It targets the API url from config.json
// and attaches the Cognito id token, so the frontend never talks to the backend any other way.
export async function apiClient() {
  const { apiUrl } = await loadConfig();
  const token = getIdToken();
  return createClient<paths>({
    baseUrl: apiUrl,
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
}
