// AppConfig is the runtime config the SPA needs, served as /config.json and written into the
// bucket at deploy. In local dev no config.json is served, so it falls back to the local API.
export type AppConfig = {
  apiUrl: string;
  cognitoUserPoolId?: string;
  cognitoClientId?: string;
};

let cached: AppConfig | null = null;

function fallbackConfig(): AppConfig {
  const injected =
    typeof window !== "undefined"
      ? (window as unknown as { __API_URL__?: string }).__API_URL__
      : undefined;
  const apiUrl = injected || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  return { apiUrl };
}

// Load and memoize /config.json, falling back to the local API when it is not served.
export async function loadConfig(): Promise<AppConfig> {
  if (cached) return cached;
  try {
    const response = await fetch("/config.json", { cache: "no-store" });
    if (response.ok) {
      cached = (await response.json()) as AppConfig;
      return cached;
    }
  } catch {
    // No config.json (local dev); use the fallback.
  }
  cached = fallbackConfig();
  return cached;
}
