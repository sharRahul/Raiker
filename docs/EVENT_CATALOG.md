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
| `turn_suspended_for_approval` | A turn parked its working state against an approval so resolving it resumes the same turn (approval id, tool name, and counts only — the parked conversation stays in the encrypted store) |
| `turn_suspension_failed` | The working state could not be parked, so the turn is not resumable; the approval itself is unaffected |
| `turn_resumed_after_approval` | A parked turn picked up again with the resolved tool result appended (approval id and counts only) |
| `session_transcript_exported` | A conversation transcript was rendered to a file the owner keeps (format, message and file counts, byte size, and the redaction policy applied — never the transcript text) |
| `model_price_override_recorded` | An administrator set a model's price, with the exact provider and model id and their stated reason. The rate itself lives in the effective-dated price registry |
| `model_price_override_cleared` | An administrator withdrew a price override, returning the model to its published or documented rate |
| `model_price_synchronised` | A provider's prices were refreshed into the registry (provider and counts only) |
| `tool_started` | A governed executor started work |
| `tool_completed` | A governed executor completed work |
| `tool_failed` | A governed executor failed safely |
| `code_repo_connected` | A repository reference was added to the Build workspace (workspace-relative subpath, or a GitHub `owner/repo` coordinate) |
| `code_repo_disconnected` | A repository reference was removed; the folder and the remote are untouched |
| `attachment_downloaded` | A file this conversation holds was downloaded; metadata only — attachment id, filename, media type, byte size |
| `task_created` | A task or schedule was queued (title, objective, and status only) |
| `task_progress` | A running task reported a step and a percentage |
| `task_blocked` | A run stopped at an approval boundary — unfinished, not failed; the payload always states the reason |
| `task_resume_started` | A granted approval is being replayed into a run that parked on it; the payload names the tool the decision covered |
| `task_resume_blocked` | An automatic continuation could not proceed; the run stays parked and the payload states why |
| `task_completed` | A task finished; the payload carries its summary |
| `task_failed` | A task ended in failure; the payload always states a reason, substituting a stated one when the run left none |
| `task_cancelled` | A task was stopped at a safe boundary, with the reason it was stopped |
| `checkpoint_created` | The gateway recorded a turn checkpoint |
| `turn_closed` | The gateway finalised a turn |
| `phase3.external_channels_notifications.readiness.metadata_defined` | External-channel readiness metadata was defined; runtime dispatch events are introduced only with a governed executor |
| `phase3.remote_container_cloud_readiness.metadata_created` | Remote/container/cloud readiness metadata was created |
| `phase3.remote_container_cloud_readiness.summary_viewed` | A local readiness summary was viewed |
| `phase3.remote_container_cloud_readiness.exported` | A redacted readiness export was produced |

Event records are append-style local audit evidence, not tamper-proof logging.
Approval resolution alone does not emit execution events because it is
metadata-only.
