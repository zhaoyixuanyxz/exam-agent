const USER_HEADER = "X-User-Id";
const DEFAULT_USER = "00000000-0000-4000-8000-000000000001";

function headers(extra?: Record<string, string>) {
  return {
    "Content-Type": "application/json",
    [USER_HEADER]: localStorage.getItem("exam-agent-user-id") || DEFAULT_USER,
    ...extra,
  };
}

export async function apiGet<T = unknown>(path: string, params?: Record<string, string | number | undefined>) {
  const u = new URL(path, window.location.origin);
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v === undefined) continue;
      u.searchParams.set(k, String(v));
    }
  }
  const r = await fetch(u.toString(), { headers: { [USER_HEADER]: localStorage.getItem("exam-agent-user-id") || DEFAULT_USER } });
  if (!r.ok) {
    const t = await r.text();
    throw new Error(t || r.statusText);
  }
  return (await r.json()) as T;
}

export async function apiPost<T = unknown>(path: string, body?: unknown) {
  const r = await fetch(path, { method: "POST", headers: headers(), body: body ? JSON.stringify(body) : undefined });
  if (!r.ok) {
    const t = await r.text();
    throw new Error(t || r.statusText);
  }
  return (await r.json()) as T;
}

export { DEFAULT_USER, USER_HEADER };
