import createClient from "openapi-fetch";

import { getApiBaseUrl } from "@/lib/config";

import type { paths } from "./schema";

// The typed API client, generated from openapi.yaml. The frontend never talks to the
// backend any other way.
export function apiClient() {
  return createClient<paths>({ baseUrl: getApiBaseUrl() });
}
