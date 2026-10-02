// The transport every API call shares: the in-memory bearer token, the CSRF
// echo, the instance path prefix, and one way a failed response becomes an
// `ApiError`. Nothing here names an endpoint (OPT-02).

// Bearer token held in memory only — never localStorage/sessionStorage (security requirement).
let token: string | null = null;

/**
 * The CSRF token that pairs with the session cookie (BUG-253).
 *
 * The cookie is what makes a reload keep the session; it is also what creates a
 * CSRF surface, because a browser attaches a cookie by itself and never
 * attaches an `Authorization` header by itself. This value — handed back by the
 * sign-in, and readable from Raiker's own cookie after a reload — is echoed in a
 * header on every state-changing request, which is the half a cross-site page
 * cannot produce. Holding it in a variable is not a secrecy claim: it is a
 * convenience over re-reading the readable cookie on every call.
 */
let csrfToken: string | null = null;

export function setToken(value: string | null): void {
  token = value;
}

export function setCsrfToken(value: string | null): void {
  csrfToken = value;
}

/**
 * Raiker's own readable CSRF cookie, for the case where a reload dropped it.
 *
 * Wrapped because reading `document.cookie` can throw — a document with an
 * opaque origin, a browser configured to block site data, an embedding context
 * with no cookie access. None of those are reasons to fail the request that was
 * about to be sent: the correct answer to "can this be read?" is "no", and the
 * server's own refusal is what governs the outcome.
 */
export function csrfFromCookie(): string | null {
  try {
    if (typeof document === "undefined") return null;
    const match = document.cookie.match(/(?:^|;\s*)raiker_csrf=([^;]*)/);
    return match ? decodeURIComponent(match[1]) : null;
  } catch {
    return null;
  }
}

/**
 * Whether this browser holds something that can authenticate.
 *
 * After a reload the in-memory bearer token is gone and the session cookie is
 * `HttpOnly`, so it cannot be seen from here at all. The readable CSRF cookie is
 * the observable half of the same sign-in, which is what makes it the right
 * question to ask: the *authoritative* answer is still the server's, asked
 * once on boot through `/api/auth/session-state`.
 */
export function hasToken(): boolean {
  return token !== null || csrfToken !== null || csrfFromCookie() !== null;
}

export function getToken(): string | null {
  return token;
}

/** The auth headers for one request, whichever way this browser is signed in. */
export function authHeaders(headers: Headers, method: string | undefined): Headers {
  if (token !== null) headers.set("Authorization", `Bearer ${token}`);
  const verb = (method ?? "GET").toUpperCase();
  if (verb !== "GET" && verb !== "HEAD" && verb !== "OPTIONS") {
    const csrf = csrfToken ?? csrfFromCookie();
    if (csrf !== null) headers.set("X-Raiker-CSRF", csrf);
  }
  return headers;
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly reasonCode: string | null,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/**
 * Read the machine-readable reason out of a failed response.
 *
 * Every governed refusal answers with `{"detail": {"reason_code": …}}`, and that
 * code is the only part of a failure the interface can reason about — the status
 * number alone cannot tell a lost race from a broken turn. Shared by the plain
 * and the streaming paths, because BUG-196 was exactly the streaming path
 * throwing the code away and leaving the UI to guess from `409`.
 */
export function reasonCodeFrom(body: unknown): string | null {
  const envelope = body as { detail?: { reason_code?: unknown }; reason_code?: unknown } | null;
  const detail = envelope?.detail ?? envelope;
  const code = (detail as { reason_code?: unknown } | null)?.reason_code;
  return typeof code === "string" ? code : null;
}

/** The `ApiError` a failed response stands for, with its reason code when it sent one. */
async function failure(resp: Response, path: string): Promise<ApiError> {
  let reasonCode: string | null = null;
  try {
    reasonCode = reasonCodeFrom(await resp.json());
  } catch {
    /* Non-JSON error response */
  }
  return new ApiError(resp.status, reasonCode, `Request failed: ${resp.status} ${path}`);
}

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = authHeaders(new Headers(init.headers), init.method);
  // `same-origin` so the session cookie rides along after a reload. It is not
  // `include`: Raiker never calls another origin, and a cookie should not be
  // offered to one.
  const resp = await fetch(instancePath(path), { ...init, headers, credentials: "same-origin" });
  if (!resp.ok) throw await failure(resp, path);
  return (await resp.json()) as T;
}

export async function requestBlob(
  path: string,
  init: RequestInit = {},
): Promise<Blob> {
  const headers = authHeaders(new Headers(init.headers), init.method);
  const resp = await fetch(instancePath(path), { ...init, headers, credentials: "same-origin" });
  if (!resp.ok) throw await failure(resp, path);
  return resp.blob();
}

export function instancePath(path: string): string {
  if (typeof window === "undefined") return path;
  const match = window.location.pathname.match(/^(\/instances\/[^/]+)/);
  return match ? `${match[1]}${path}` : path;
}

export function withQuery(
  path: string,
  params: Record<string, string | number | boolean | undefined>,
): string {
  const q = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") q.set(key, String(value));
  }
  const suffix = q.toString();
  return suffix ? `${path}?${suffix}` : path;
}

export function postJson<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

/** A JSON body sent with a method other than POST (PUT, PATCH, DELETE). */
export function sendJson<T>(method: string, path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}
