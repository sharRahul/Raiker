# Event catalog

Raiker emits structured audit metadata for governed work. Events must not carry
secrets, raw prompts, private reasoning, or unbounded tool output.

| Event | Meaning |
|---|---|
| `prompt_received` | A client submitted a turn |
| `conversation_history_replayed` | Prior turns of the session were sent to the model as context (message count and character total only — never the transcript) |
| `policy_decision` | Policy classified the requested action |
| `approval_requested` | A human decision is required |
| `approval_denied` | A human or policy denied the action |
| `tool_started` | A governed executor started work |
| `tool_completed` | A governed executor completed work |
| `tool_failed` | A governed executor failed safely |
| `code_repo_connected` | A repository reference was added to the Build workspace (workspace-relative subpath, or a GitHub `owner/repo` coordinate) |
| `code_repo_disconnected` | A repository reference was removed; the folder and the remote are untouched |
| `checkpoint_created` | The gateway recorded a turn checkpoint |
| `turn_closed` | The gateway finalised a turn |
| `phase3.external_channels_notifications.readiness.metadata_defined` | External-channel readiness metadata was defined; runtime dispatch events are introduced only with a governed executor |
| `phase3.remote_container_cloud_readiness.metadata_created` | Remote/container/cloud readiness metadata was created |
| `phase3.remote_container_cloud_readiness.summary_viewed` | A local readiness summary was viewed |
| `phase3.remote_container_cloud_readiness.exported` | A redacted readiness export was produced |

Event records are append-style local audit evidence, not tamper-proof logging.
Approval resolution alone does not emit execution events because it is
metadata-only.
