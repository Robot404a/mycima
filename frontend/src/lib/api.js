export const TOKEN_KEY = "mycima.token";
export const USER_KEY = "mycima.user";

export class ApiError extends Error {
  constructor(message, status = 0, detail = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export function getStoredUser() {
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function setStoredUser(user) {
  if (user) localStorage.setItem(USER_KEY, JSON.stringify(user));
  else localStorage.removeItem(USER_KEY);
}

export function clearAuthStorage() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

function detailMessage(detail) {
  if (!detail) return null;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const first = detail[0];
    if (first?.msg) return first.msg.replace(/^Value error,\s*/i, "");
    return "Please check the information you entered.";
  }
  if (detail.message) return detail.message;
  if (detail.detail) return detail.detail;
  return null;
}

function buildUrl(path, params) {
  const base = path.startsWith("/api") ? path : `/api${path}`;
  if (!params) return base;
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") return;
    search.append(key, String(value));
  });
  const query = search.toString();
  return query ? `${base}${base.includes("?") ? "&" : "?"}${query}` : base;
}

export async function api(path, options = {}) {
  const {
    method = "GET",
    body,
    params,
    auth = true,
    timeout = 60000,
    signal,
    headers: extraHeaders = {},
  } = options;
  const headers = { Accept: "application/json", ...extraHeaders };
  if (auth) {
    const token = getToken();
    if (token) headers.Authorization = `Bearer ${token}`;
  }
  if (body !== undefined) headers["Content-Type"] = "application/json";

  const controller = new AbortController();
  const timer = timeout ? setTimeout(() => controller.abort(), timeout) : null;
  if (signal) {
    signal.addEventListener("abort", () => controller.abort(), { once: true });
  }

  let response;
  try {
    response = await fetch(buildUrl(path, params), {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });
  } catch (error) {
    if (timer) clearTimeout(timer);
    if (error.name === "AbortError") {
      throw new ApiError("The request took too long. Please try again.", 0);
    }
    throw new ApiError("Unable to reach MyCima. Check your connection and try again.", 0);
  }
  if (timer) clearTimeout(timer);

  if (response.status === 204) return null;

  let payload = null;
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    payload = await response.json().catch(() => null);
  } else {
    payload = await response.text().catch(() => null);
  }

  if (!response.ok) {
    if (response.status === 401) {
      window.dispatchEvent(new CustomEvent("mycima:unauthorized"));
    }
    const message =
      detailMessage(payload?.detail) ||
      (response.status === 403
        ? "You do not have access to this."
        : response.status === 404
          ? "We couldn't find what you were looking for."
          : response.status === 503
            ? "That service is temporarily unavailable. Please try again shortly."
            : "Something went wrong. Please try again.");
    throw new ApiError(message, response.status, payload?.detail ?? payload);
  }
  return payload;
}

export function apiErrorMessage(error) {
  if (error instanceof ApiError) return error.message;
  if (error?.message) return error.message;
  return "Something went wrong. Please try again.";
}
