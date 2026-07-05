// Where the frontend finds the API. In production infra injects window.__API_URL__;
// in local dev it falls back to the FastAPI default. This is the only link to the backend.
export function getApiBaseUrl(): string {
  if (typeof window !== "undefined") {
    const injected = (window as unknown as { __API_URL__?: string }).__API_URL__;
    if (injected) return injected;
  }
  return process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
}
