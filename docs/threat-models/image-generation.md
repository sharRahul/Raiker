# Threat model — image generation (`image_generation`)

`image_generation` sends one prompt to a hosted image model and stores the image
it returns in the workspace. It is the Design surface's whole runtime.

It has its own gate rather than living inside `hosted_model_runtime` for the
reason every separated capability here does: an owner who connected OpenAI to
answer questions has not thereby asked Raiker to spend their credit generating
pictures. The two are refused separately and turned on separately.

## What the capability does

`raiker/runtime/executors/tier2_image.py` → `ImageGenerationExecutor`:

1. validates the prompt (non-empty, under 4,000 characters) and the size against
   a fixed list — a free-text size would be a string this runtime forwards to a
   provider without understanding it;
2. resolves the model profile the action names, from the registry the owner
   configured on the Models page, and refuses a provider with no governed image
   endpoint by name;
3. requires the owner's saved connection for that profile
   (`model_connection_required`), refuses when the owner has turned hosted models
   off (`hosted_provider_requires_explicit_policy`), and requires the connection
   to be bound to the provider's own image origin — `https://api.openai.com` or
   `https://generativelanguage.googleapis.com` — so a key saved for another
   endpoint is never sent here (`image_connection_origin_mismatch`);
4. resolves the credential from that connection, or from the provider's
   environment variable when the owner saved the connection to use it — never
   from the action;
5. builds the provider's endpoint **itself** and POSTs through
   `sandbox.post_json` / `post_multipart`, held to that one host and refusing
   any redirect (`redirect_refused:<status>`);
6. decodes the response's base64 image, bounded at 8 MB;
7. stores the bytes in `attachments` (owner-scoped, sha256-addressed) and the
   attempt in `image_generations`.

## What an attacker would try

**Redirect the generation at a host they choose.** The endpoint is constructed
from the provider, never taken from the request. An action argument is a thing a
model can propose, and a proposed URL plus an owner's API key is a credential
exfiltration primitive. The prompt cannot reach the URL.

**Reach the network on an environment key alone.** They cannot: an API key is
not authorisation to reach a host. The owner's saved connection is, and it must
be bound to the provider's image origin. The transport is held to that one host
and does not follow a redirect, so the key in the header can only reach it.

**Read the credential out of the record.** Artifacts carry ids, provider, model,
size and byte count. Never the prompt, never the key, never the bytes. The
provider's URL is not recorded either.

**Read somebody else's images.** Both reads are owner-scoped at the store, and
the list route returns metadata only — the bytes are a separate request naming
one generation. The response is `Cache-Control: no-store`.

**Fill the workspace.** A response over 8 MB is refused before storage, and a
prompt over 4,000 characters is refused before the call.

**Make a refusal invisible.** A refused generation is recorded with its reason
code, so an owner who pressed Generate and got nothing finds out why from the
page rather than the audit log.

## What is deliberately not defended

**The provider sees the prompt.** That is what generating an image off-machine
means. An owner who does not want a prompt to leave the machine leaves this
capability off, which is its shipped state.

**Raiker does not moderate the prompt.** The provider's own policy applies, and a
policy refusal is surfaced as `image_refused_by_provider` rather than being
dressed up as a transport failure.

## Residual risk

The provider hosts are fixed in code, so there is no owner-widenable host
pattern any more. DNS for those hosts is resolved by the operating system at
send time; dial-time address checks are tracked in
[`MODEL_TRANSPORT_SECURITY_HARDENING.md`](../plans/MODEL_TRANSPORT_SECURITY_HARDENING.md).
