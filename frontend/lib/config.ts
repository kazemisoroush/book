// Where the frontend finds the API, the only link to the backend. It uses an optional
// runtime override (window.__API_URL__), else the build-time NEXT_PUBLIC_API_URL, else the
// local FastAPI default.
export function getApiBaseUrl(): string {
  if (typeof window !== "undefined") {
    const injected = (window as unknown as { __API_URL__?: string }).__API_URL__;
    if (injected) return injected;
  }
  return process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
}
