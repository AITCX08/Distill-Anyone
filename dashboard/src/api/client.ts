export async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path, { credentials: "same-origin" });
  if (!response.ok) throw new Error(`Dashboard request failed: ${response.status}`);
  return response.json() as Promise<T>;
}
