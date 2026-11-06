/** QUI-G06: keep refusal evidence and never infer a write's outcome from a lost response. */
import { ApiError } from "./api";
import { failure } from "./errorCopy";
import { endpointRefusal } from "./mcpEndpoint";

const guidance: Record<string, string> = {
  connector_auth_required: "Connect this account before turning it on.",
  connector_reauth_required: "This sign-in expired or was revoked. Connect the account again.",
  connector_oauth_refresh_failed: "Raiker could not refresh this sign-in. Connect the account again.",
  connector_oauth_refresh_invalid: "The provider returned an invalid refreshed sign-in. Connect the account again.",
  connector_not_enabled: "Turn this connection on for this session before using it.",
  disabled_by_capability_gate: "Enable the capability in Permissions to continue.",
};

export function connectionFailure(what: string, affected: string, next: string, error: unknown): string {
  if (error instanceof ApiError) {
    const detail = endpointRefusal(error.reasonCode) ?? guidance[error.reasonCode ?? ""];
    return failure(what, affected, detail ? `${detail} ${next}` : next, error);
  }
  // A transport error can happen after the server commits. Keep the action's
  // read-back instruction rather than replacing it with a blind retry.
  return failure(what, affected, `Raiker did not answer. Check that it is still running. ${next}`);
}
