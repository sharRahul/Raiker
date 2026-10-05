// Signing in, restoring a session after a reload, and the account routes that
// adopt or drop the session they answer with (OPT-02).
import type { InstanceLaunchResult } from "../apiTypes";
import { contract } from "../generated/apiContract";
import type { HealthView, IssuedSessionView, LoginResultView } from "../generated/apiContract";
import { csrfFromCookie, hasToken, setCsrfToken, setToken } from "./core";

/** Mint a bearer token for the local owner principal and hold it in memory. */
export async function connect(): Promise<IssuedSessionView> {
  const session = await contract.mintSession({ as_principal: null });
  setToken(session.token);
  setCsrfToken(session.csrf_token);
  return session;
}

// ── Lock screen: local-account auth ─────────────────────────────────────────

export type { HealthView };

/**
 * Privacy-safe pre-auth reachability probe. `/api/health` is the only
 * unauthenticated read: it names whether the server answers and whether the
 * encrypted store opens, and nothing else about the workspace. Both facts are
 * needed pre-auth, because a store that will not open is exactly what makes
 * every sign-in fail (BUG-86) — reporting only reachability let the lock
 * screen call the runtime operational while refusing every attempt.
 */
export function health(): Promise<HealthView> {
  return contract.health();
}

export function createInstance(
  name: string,
  username: string,
  password: string,
): Promise<InstanceLaunchResult> {
  return contract.createInstance({ name, username, password });
}

export type LoginResult = LoginResultView;

/**
 * On a full 'session' result the bearer token is stored in memory, and the CSRF
 * token that guards the reload-surviving cookie is stored beside it.
 */
function adoptSession(result: LoginResult): LoginResult {
  if (result.stage === "session" && result.token) {
    setToken(result.token);
    setCsrfToken(result.csrf_token);
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
    const who = await contract.sessionState();
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
    contract.register({ username, password }).then(adoptSession),
  login: (username: string, password: string) =>
    contract.login({ username, password }).then(adoptSession),
  verifyMfa: (ticket: string, code: string) =>
    contract.mfaVerify({ ticket, code }).then(adoptSession),
  bootstrapStatus: () => contract.bootstrapStatus(),
  beginPasswordRecovery: (username: string) => contract.beginPasswordRecovery({ username }),
  completePasswordRecovery: (ticket: string, code: string, newPassword: string) =>
    contract.completePasswordRecovery({ ticket, code, new_password: newPassword }),
  logout: async () => {
    try {
      await contract.logout();
    } finally {
      setToken(null);
      setCsrfToken(null);
    }
  },
  elevate: (password?: string, mfaCode?: string) =>
    contract.elevate({ password, mfa_code: mfaCode }),
  enrollMfa: () => contract.mfaEnroll(),
  activateMfa: (code: string) => contract.mfaActivate({ code }),
  changePassword: (oldPassword: string, newPassword: string) =>
    contract.changePassword({ old_password: oldPassword, new_password: newPassword }),
  listDeviceSessions: () => contract.listDeviceSessions(),
  revokeDeviceSession: (sessionId: string) => contract.revokeDeviceSession(sessionId),
  // DEC-10 step 8 — the username typed as confirmation travels with the
  // request, so the server refuses a delete nobody spelled out.
  deleteAccount: (confirm: string) => contract.deleteAccount({ confirm }),
  deletionPreview: () => contract.accountDeletionPreview(),
  sessionState: () => contract.sessionState(),
};
