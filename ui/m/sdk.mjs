// Stand-in for the host-provided "@kirocrew/app-sdk" when Ghost Foreman runs as its own page (the phone app).
// Only what ui/dist/index.mjs uses: an API client that rides on the signed-in session cookie (renewing it once with
// the refresh cookie when it has expired), and no-op event hooks (the UI polls instead).
let refreshing = null;

export function refreshSession() {
  // One refresh at a time: the Gateway rotates the refresh cookie on every use.
  if (!refreshing) {
    refreshing = fetch("/api/auth/refresh", { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" }, body: "{}" })
      .then((r) => r.ok)
      .catch(() => false)
      .finally(() => setTimeout(() => (refreshing = null), 2000));
  }
  return refreshing;
}

async function request(method, path, body, retried = false) {
  const res = await fetch(path, {
    method,
    credentials: "same-origin",
    headers: body !== undefined ? { "Content-Type": "application/json" } : {},
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if ((res.status === 401 || res.status === 403) && !retried) {
    const text = await res.clone().text();
    // Only an authentication failure is worth a refresh (not e.g. an app-scope refusal).
    if (/token|unauthenticated|expired|signature|forbidden/i.test(text) && (await refreshSession())) {
      return request(method, path, body, true);
    }
  }
  const text = await res.text();
  let data;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }
  if (!res.ok) {
    const err = new Error((data && data.error) || res.statusText || "HTTP " + res.status);
    err.status = res.status;
    err.data = data;
    throw err;
  }
  return data;
}

const api = {
  get: (path) => request("GET", path),
  post: (path, body) => request("POST", path, body === undefined ? {} : body),
  put: (path, body) => request("PUT", path, body),
  patch: (path, body) => request("PATCH", path, body),
  del: (path) => request("DELETE", path),
};

export const useAppApi = () => api;
export const useAppEvents = () => {};
export const useAppInfo = () => ({ name: "ghost-foreman", version: "standalone" });
export const useNotify = () => () => {};
