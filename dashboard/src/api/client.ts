export async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path, { credentials: "same-origin" });
  if (!response.ok) throw new Error(`Dashboard request failed: ${response.status}`);
  return response.json() as Promise<T>;
}

export class DashboardRequestError extends Error {
  constructor(readonly status: number, readonly code: string) {
    super(`Dashboard request failed: ${code}`);
  }
}

function cookieValue(name: string): string {
  const prefix = `${name}=`;
  const encoded = document.cookie.split("; ").find((cookie) => cookie.startsWith(prefix))?.slice(prefix.length);
  return encoded ? decodeURIComponent(encoded) : "";
}

export async function postJson<T>(path: string, body: unknown): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-Distill-CSRF": cookieValue("distill_csrf"),
      },
      body: JSON.stringify(body),
    });
  } catch {
    throw new DashboardRequestError(0, "offline");
  }

  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const code = typeof payload === "object" && payload !== null
      && "error" in payload && typeof payload.error === "object" && payload.error !== null
      && "code" in payload.error && typeof payload.error.code === "string"
      ? payload.error.code
      : "request_failed";
    throw new DashboardRequestError(response.status, code);
  }
  return payload as T;
}
