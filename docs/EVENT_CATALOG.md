# Event catalog

Raiker emits structured audit metadata for governed work. Events must not carry
secrets, raw prompts, private reasoning, or unbounded tool output.

The event envelope's `actor` is always the principal that literally emitted the
event. For agentic work, APIs and Activity may additionally resolve and display
the signed turn identity as context; that contextual identity never replaces a
human authorizer, runtime authority, or other literal actor.

| Event | Meaning |
|---|---|
| `machine_identity_issued` | A signed machine identity was minted for a turn (public IDs, audience, timestamps, and parent principal only) |
| `machine_identity_rotated` | A resumed turn received a fresh token ID while retaining its machine subject |
| `machine_identity_refused` | Broker verification failed closed with a stable reason code before policy, credentials, hooks, or tools |
| `machine_identity_deactivated` | A terminal turn's machine principal was made inactive |
| `prompt_received` | A client submitted a turn (client type, prompt length, input provenance and the composer surface — never the prompt text) |
| `conversation_history_replayed` | Prior turns of the session were sent to the model as context (message count and character total only — never the transcript) |
| `hook_matched` | A configured hook rule matched this event (event, matcher and scope only) |
| `hook_executed` | One hook handler ran, with the decision it returned and whether it held authority |
| `hook_decision` | The aggregated decision hooks reached for one event |
| `hook_timeout` | A command handler exceeded its bounded timeout; the action falls through to normal policy |
| `hook_failed` | A handler errored — a missing program, or a builtin name this build does not have |
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
| `agent_plan_updated` | The agent recorded or revised its plan for a conversation with `update_plan` — the ordered steps and their statuses, which are the model's own short statements of intent, never workspace content |
| `agent_plan_replayed` | A conversation's standing plan was carried into a later turn as context (character count only) |
| `subagent_completed` | A bounded, read-only subagent finished — its name, contract id, steps run, and the read-only tools it used. The findings reach the calling model and nothing else |
| `model_tool_calls_dropped` | Tool calls a turn proposed but did not run, with proposed/accepted/dropped counts and the boundary that stopped them (budget, approval, or policy) |
| `model_tool_calls_queued` | Tool calls held behind an approval boundary rather than dropped, with proposed/queued counts and the parked call's place in its batch. The calls are parked with the turn and drained one decision at a time on resume |
| `turn_stopped` | A turn the owner ended early was honoured at a safe boundary — the reason, the boundary it stopped at, and how many tool calls it had made |
| `turn_steered` | The owner's own instruction entered a running turn at a safe boundary (character count only; the instruction itself is a user message in the conversation) |
| `tool_started` | A governed executor started work |
| `tool_completed` | A governed executor completed work |
| `tool_failed` | A governed executor failed safely |
| `eidetic_observation_skipped` | An eidetic observation could not be recorded for a completed tool result — the action id, the tool, and the reason. The tool result itself is unaffected: an observation is a record *about* work, and a bookkeeping failure never fails the work. An observation the runtime deliberately refused on sensitivity is **not** this event; it is a row in `eidetic_observations` carrying its own reason, so the owner sees it in Memory rather than only in the audit log |
| `code_repo_connected` | A repository reference was added to the Build workspace (workspace-relative subpath, or a GitHub `owner/repo` coordinate) |
| `code_repo_disconnected` | A repository reference was removed; the folder and the remote are untouched |
| `code_map_indexed` | A repository's code map was built — file, symbol and edge totals, what the scan skipped and why, and which bound it hit if it stopped short. Counts and reasons only; never a path's content and never a symbol's text |
| `code_map_refreshed` | The code map was re-parsed for exactly the paths an approved write touched — how many files were re-read and how many rows went away |
| `attachment_downloaded` | A file this conversation holds was downloaded; metadata only — attachment id, filename, media type, byte size |
| `task_created` | A task or schedule was queued (title, objective, and status only) |
| `task_progress` | A running task reported a step and a percentage |
| `task_blocked` | A run stopped at an approval boundary — unfinished, not failed; the payload always states the reason |
| `task_resume_started` | A granted approval is being replayed into a run that parked on it; the payload names the tool the decision covered |
| `task_resume_blocked` | An automatic continuation could not proceed; the run stays parked and the payload states why |
| `task_completed` | A task finished; the payload carries its summary |
| `task_failed` | A task ended in failure; the payload always states a reason, substituting a stated one when the run left none |
| `task_cancelled` | A task was stopped at a safe boundary, with the reason it was stopped |
| `skill_installed` | A skill was uploaded and stored (name, source, checksum, byte size, file count — never the document) |
| `skill_imported` | A skill was fetched from a verified link and stored; the payload names the raw URL it came from |
| `skill_built` | A skill was authored in Raiker and stored, held to the same validation as an upload |
| `skill_renamed` | An installed skill's name — its prompt handle — was changed |
| `skill_activated` | A skill was turned on, so its index entry reaches turns again |
| `skill_deactivated` | A skill was turned off; it stays stored and is withheld from every turn |
| `skill_deleted` | A skill's stored document was removed from the workspace |
| `skills_indexed` | A turn advertised the owner's active skills to the model (count and names only — bodies are loaded on demand by `skill_load`) |
| `brain_source_folder_granted` | The owner gave the Knowledge Map access to one folder on this machine; the payload carries the path, because what was opened is the whole point of the record |
| `brain_source_folder_revoked` | That access was withdrawn; every source indexed under the folder is removed with it |
| `checkpoint_created` | The gateway recorded a turn checkpoint |
| `turn_closed` | The gateway finalised a turn |
| `phase3.external_channels_notifications.readiness.metadata_defined` | External-channel readiness metadata was defined; runtime dispatch events are introduced only with a governed executor |
| `phase3.remote_container_cloud_readiness.metadata_created` | Remote/container/cloud readiness metadata was created |
| `phase3.remote_container_cloud_readiness.summary_viewed` | A local readiness summary was viewed |
| `phase3.remote_container_cloud_readiness.exported` | A redacted readiness export was produced |

## The live stream, and how it relates to this catalogue

The events above are the **durable** record: append-style local audit evidence,
written by the writer and read afterwards in **Observability → Audit log**.
Beside them, a streamed turn carries a second, strictly smaller channel —
`raiker/contracts/streaming.py::StreamEvent` — which is what a client can watch
while the turn is still running. It grants no authority and adds no record.

| Stream kind | Carries |
|---|---|
| `lifecycle` | A runtime state or event transition, mirroring the durable event beside it |
| `text_delta` | One incremental chunk of the model's answer |
| `reasoning_delta` | One incremental chunk of the model's *own* reasoning, kept apart from the answer so a client can render it as reasoning or not at all (BUG-207) |
| `tool` | One tool call opening, settling, waiting on a decision, or refused — `tool_proposed`, `tool_started`, `tool_completed`, `tool_failed`, `tool_waiting`, `tool_refused` (BUG-206) |
| `final` | The terminal event, carrying the complete `AgentResponse` |
| `error` | A safe error surfaced to the client |

**A `tool` stream event carries strictly less than the durable event beside it.**
Its payload is the action id, an icon family, the tool's name in the owner's
language, and one short action phrase — never arguments, never a result, never
output. All of it is resolved in `raiker/tools/presentation.py`, through the same
redaction the durable event passes, and two arguments are narrowed further than
the event narrows them: a URL to its host and a command to its program name. A
tool whose argument *values* are dropped from the durable event derives no phrase
from them either. The transcript can therefore never say more than the audit
trail does.

**`reasoning_delta` is never merged into `text_delta`.** The answer is what the
owner asked for and the reasoning is how the model got there; a surface that
cannot tell them apart cannot honestly label either.

Every event type a runtime component emits must be declared in
`raiker/contracts/models.py::EVENT_TYPES`. `AgentEvent` validates against that
set and raises inside the turn otherwise, which surfaces as a failed turn rather
than a missing log line — so an undeclared event is a live defect, not a
documentation gap. `tests/test_agent_plan_and_subagents.py` scans every emitted
literal against the declared set.

Event records are append-style local audit evidence, not tamper-proof logging.

**Approval resolution does emit execution events.** For the twelve capabilities
in `EXECUTABLE_ON_APPROVAL` (`raiker/approvals/execution.py`) the relay records
`approval_executed` on success and `approval_execution_denied` when governance
refused at execution time; a turn resolving its own eligible call under the
`auto` approval mode records `approval_auto_executed`. For every other
capability the resolution is a decision and emits no execution event, which is
the distinction this paragraph used to collapse.

**This catalogue is a reader's guide, not the registry.** The registry is
`raiker/contracts/models.py::EVENT_TYPES`, which declares 268 event types; the
tables above cover the ones a person reading the audit log most often needs
explained. An event type that exists in the registry and not here is documented
by its emitting call site, not missing from the product.
