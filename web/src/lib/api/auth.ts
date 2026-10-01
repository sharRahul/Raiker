// Signing in, restoring a session after a reload, and the account routes that
// adopt or drop the session they answer with (OPT-02).
import type {
  AuthSession,
  InstanceLaunchResult,
  PasswordRecoveryBeginResult,
} from "../apiTypes";
import { csrfFromCookie, hasToken, postJson, request, setCsrfToken, setToken } from "./core";

/** Mint a bearer token for the local owner principal and hold it in memory. */
export async function connect(): Promise<AuthSession> {
  const session = await postJson<AuthSession & { csrf_token?: string | null }>(
    "/api/auth/session",
    { as_principal: null },
  );
  setToken(session.token);
  setCsrfToken(session.csrf_token ?? null);
  return session;
}

// ── Lock screen: local-account auth ─────────────────────────────────────────

export type HealthView = {
  status: string;
  /** "ok" when the encrypted store opens and reads; "unavailable" otherwise. */
  store?: string;
  /** Stable code for an unavailable store, e.g. store_memory_lock_unavailable. */
  reason?: string;
  detail?: string;
  cipher_memory_security?: string;
  memory_security_mode?: "auto" | "on" | "off";
  memory_security_probe?: "supported" | "failed" | "not_run";
  memory_security_reason?: string;
  memory_security_checked_at?: string | null;
  sqlcipher_version?: string | null;
};

/**
 * Privacy-safe pre-auth reachability probe. `/api/health` is the only
 * unauthenticated read: it names whether the server answers and whether the
 * encrypted store opens, and nothing else about the workspace. Both facts are
 * needed pre-auth, because a store that will not open is exactly what makes
 * every sign-in fail (BUG-86) — reporting only reachability let the lock
 * screen call the runtime operational while refusing every attempt.
 */
export function health(): Promise<HealthView> {
  return request<HealthView>("/api/health");
}

export function createInstance(
  name: string,
  username: string,
  password: string,
): Promise<InstanceLaunchResult> {
  return postJson<InstanceLaunchResult>("/api/instances", {
    name,
    username,
    password,
  });
}

export interface LoginResult {
  stage: "session" | "mfa_required";
  principal_id: string;
  token: string | null;
  ticket: string | null;
  /** Pairs with the session cookie on every write (BUG-253). */
  csrf_token?: string | null;
}

/**
 * On a full 'session' result the bearer token is stored in memory, and the CSRF
 * token that guards the reload-surviving cookie is stored beside it.
 */
function adoptSession(result: LoginResult): LoginResult {
  if (result.stage === "session" && result.token) {
    setToken(result.token);
    setCsrfToken(result.csrf_token ?? null);
  }
  return result;
}

/**
 * Whether this browser is already signed in, from the server's point of view
 * (BUG-253).
 *
 * After a reload there is no bearer token in memory and the session cookie is
 * `HttpOnly`, so the only honest way to answer is to ask. "Nobody" is one of the
 * two expected answers, and it is what puts the lock screen up.
 *
 * It asks `/api/auth/session-state` rather than `/api/auth/whoami` (BUG-267). Both
 * answer the same question; only one answers "nobody" with a `200`. Asking the
 * governed route made the browser log a failed request on every locked load —
 * routine noise in the one place a real fault is supposed to stand out.
 */
export async function restoreSession(): Promise<string | null> {
  if (!hasToken()) return null;
  try {
    const who = await request<{ principal_id: string | null }>("/api/auth/session-state");
    if (who.principal_id === null) {
      // The server has already cleared the cookie that said otherwise; drop the
      // half this page was holding so the next load has nothing to ask with.
      setToken(null);
      setCsrfToken(null);
      return null;
    }
    setCsrfToken(csrfFromCookie());
    return who.principal_id;
  } catch {
    // A cookie that no longer authenticates is worse than none: it would make
    // every later call fail with the owner looking at a workspace. Forget it.
    setToken(null);
    setCsrfToken(null);
    return null;
  }
}

export const auth = {
  register: (username: string, password: string) =>
    postJson<LoginResult>("/api/auth/register", { username, password }).then(
      adoptSession,
    ),
  login: (username: string, password: string) =>
    postJson<LoginResult>("/api/auth/login", { username, password }).then(
      adoptSession,
    ),
  verifyMfa: (ticket: string, code: string) =>
    postJson<LoginResult>("/api/auth/mfa/verify", { ticket, code }).then(
      adoptSession,
    ),
  bootstrapStatus: () =>
    request<{ can_register: boolean }>("/api/auth/bootstrap-status"),
  beginPasswordRecovery: (username: string) =>
    postJson<PasswordRecoveryBeginResult>("/api/auth/password-recovery/begin", {
      username,
    }),
  completePasswordRecovery: (
    ticket: string,
    code: string,
    newPassword: string,
  ) =>
    postJson<{ ok: boolean }>("/api/auth/password-recovery/complete", {
      ticket,
      code,
      new_password: newPassword,
    }),
  logout: async () => {
    try {
      await postJson<{ ok: boolean }>("/api/auth/logout", {});
    } finally {
      setToken(null);
      setCsrfToken(null);
    }
  },
  elevate: (password?: string, mfaCode?: string) =>
    postJson<{ token: string }>("/api/auth/elevate", {
      password,
      mfa_code: mfaCode,
    }),
  enrollMfa: () =>
    postJson<{
      secret: string;
      provisioning_uri: string;
      backup_codes: string[];
    }>("/api/auth/mfa/enroll", {}),
  activateMfa: (code: string) =>
    postJson<{ ok: boolean }>("/api/auth/mfa/activate", { code }),
  changePassword: (oldPassword: string, newPassword: string) =>
    postJson<{ ok: boolean }>("/api/auth/password", {
      old_password: oldPassword,
      new_password: newPassword,
    }),
  listDeviceSessions: () =>
    request<
      Array<{
        session_id: string;
        created_at: string;
        last_seen_at: string | null;
        device_label: string | null;
        revoked: boolean;
        scope: string;
        current: boolean;
      }>
    >("/api/auth/sessions"),
  revokeDeviceSession: (sessionId: string) =>
    postJson<{ ok: boolean }>(
      `/api/auth/sessions/${encodeURIComponent(sessionId)}/revoke`,
      {},
    ),
  deleteAccount: () =>
    request<{ ok: boolean }>("/api/account", { method: "DELETE" }),
};
