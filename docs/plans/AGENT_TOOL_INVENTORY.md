# Agent tool inventory — tools to bring into Raiker

**Proposed, 2026-10-25. Nothing in this document has shipped.** It records
every tool the coding agent that worked on Raiker on 2026-10-25 had in its
inventory (Claude Code in a cloud session), which of them it used, and what
each would become as a Raiker capability. It is a backlog of ideas, not a
decision: each item still needs its own design, threat model and approval in
the usual way ([THREAT_MODEL.md](../architecture/THREAT_MODEL.md),
[TOOLS_AND_PERMISSIONS_SPEC.md](../architecture/TOOLS_AND_PERMISSIONS_SPEC.md)).

Raiker's own model-facing tools are listed in
[RAIKER_TOOL_AND_PLUGIN_CATALOG.md](../architecture/RAIKER_TOOL_AND_PLUGIN_CATALOG.md).
Where a tool below already has a Raiker equivalent, the table names it and the
item is about the gap, not the whole tool.

## Rules every item inherits

These come from the existing posture and do not change per item:

* **Governed like any other tool.** A new tool registers a capability gate,
  a side-effect class (read, reversible, external, destructive, critical) and a
  risk level, and goes through the broker. Reading may run within permissions;
  anything that changes, sends, deletes or spends asks first.
* **Results are data, never instructions.** A web page, a CI log, a GitHub
  comment, an email or a connector answer is untrusted content.
* **Credentials stay in the vault.** No tool takes a key as an argument.
* **Owner-scoped and audited.** Every call is an event; every result is
  attributable to the turn and the approval that allowed it.

## Status

| Item | State |
|---|---|
| TOOL-01 – TOOL-12 (agent loop) | **Open** |
| TOOL-20 – TOOL-31 (GitHub) | **Open** |
| TOOL-40 – TOOL-47 (sessions, schedules, notifications) | **Open** |
| TOOL-60 – TOOL-66 (artifacts, documents, design) | **Open** |
| TOOL-70 – TOOL-75 (skills, plugins, connectors) | **Open** |
| TOOL-80 – TOOL-83 (third-party connector families) | **Open** |

## The agent loop

The built-in tools a coding agent uses on every task.

| Item | Tool (inventory name) | What it does | Used 2026-10-25 | Raiker today | Proposed Raiker capability | Side effect |
|---|---|---|---|---|---|---|
| TOOL-01 | `Bash` | Run a shell command; foreground with a timeout, or detached in the background with a completion notice | Yes | `run_command`, `shell`, `background_run` | A completion notice for a background command, delivered into the turn, instead of the model polling `background_run` | As today |
| TOOL-02 | `Read`, `Write`, `Edit`, `Glob`, `Grep` | Read a file (text, images, PDFs, notebooks), write or exact-replace in one, find files by pattern, search with regex | Yes | `read_file`, `write_file`, `edit_file`, `glob`, `grep` | `read_file` for images and PDF pages; regex and context lines in `grep`; `edit_file` with *replace all* | Read / reversible |
| TOOL-03 | `NotebookEdit` | Edit one Jupyter notebook cell | No | — | `notebook_edit`, a governed write like `edit_file` | Reversible |
| TOOL-04 | `TaskCreate`, `TaskUpdate`, `TaskGet`, `TaskList`, `TaskStop` | A structured to-do list for the session: create, update status, read, list, stop | Yes (19 items) | `update_plan` (one ordered checklist) | Task items with dependencies (*blocks* / *blocked by*), an owner, and stop for a running item | Model's own intent |
| TOOL-05 | `Monitor` | Stream events from a long-running script; each output line is a notice to the agent | Yes (CI jobs) | — | `watch`: a bounded, owner-visible watch on a background command or a feed, ending on a stated condition | Read |
| TOOL-06 | `ScheduleWakeup` | Resume the same loop after a delay | No | Tasks with `scheduled_at` | A self-scheduled continuation of a turn, shown in Tasks and stoppable | Reversible |
| TOOL-07 | `Agent`, `SendMessage`, `ListAgents` | Start a sub-agent (fresh or a fork of the current context), message it, list running agents | No | `spawn_subagent` (read-only) | Message a running subagent; list subagents; a fork that inherits the turn's context | Read |
| TOOL-08 | `AskUserQuestion` | Ask the user one to four multiple-choice questions, with a recommended option | Yes (the app mark, the profile) | `ask_owner_question` | A *recommended* marker on one option, and an optional preview per option | None |
| TOOL-09 | `EnterPlanMode`, `ExitPlanMode` | Switch to a read-only planning posture and back, with approval to leave it | No | Build's **Plan** posture | Leaving Plan by proposing the plan for approval, so the switch to acting is the owner's | None |
| TOOL-10 | `EnterWorktree`, `ExitWorktree` | Work in an isolated git worktree | No | BR-D02 worktrees for Build turns | Model-requested worktree for an experiment, discarded unless kept | Reversible |
| TOOL-11 | `WebFetch`, `WebSearch` | Read one page and answer a question about it; search the web (standard or extended) | Yes (`WebFetch`, blocked by DNS) | `web_fetch`, `web_search` | A question argument on `web_fetch` that returns the answer rather than the page; an *extended* search depth | Read |
| TOOL-12 | `ToolSearch` | Load the schema of a deferred tool by name or keyword | Yes | All tools advertised up front | Deferred tool loading, so a large connector catalogue does not fill every prompt | Read |

## GitHub

The GitHub MCP server's tools. Raiker today reads one issue or pull request
(`github_read`) and proposes a pull request or a comment (`github_write`).

| Item | Tools | What they do | Used 2026-10-25 | Proposed Raiker capability | Side effect |
|---|---|---|---|---|---|
| TOOL-20 | `actions_list`, `actions_get`, `get_job_logs` | List workflows, runs, jobs and artifacts; read one run, job or artifact; read a job's log, or only the failed jobs' | `actions_list` yes | Read CI status and failed-job logs, so Build can watch its own pushed change to green | Read |
| TOOL-21 | `actions_run_trigger` | Re-run, cancel or dispatch a workflow | No | Re-run a failed job once, asked first | External |
| TOOL-22 | `get_check_run` | Read one check run | No | Part of TOOL-20 | Read |
| TOOL-23 | `list_commits`, `get_commit`, `search_commits`, `list_branches`, `list_tags`, `get_tag`, `list_releases`, `get_latest_release`, `get_release_by_tag` | Repository history and releases | No | Read-only repository history beside the local `git_log` | Read |
| TOOL-24 | `get_file_contents`, `search_code`, `search_repositories` | Read a file at a ref; search code and repositories | No | Read a file from a remote ref without cloning | Read |
| TOOL-25 | `create_branch`, `create_or_update_file`, `push_files`, `delete_file` | Change a repository through the API | No | Covered by local `git_branch`, `git_commit`, `git_push`; an API path only for repositories with no local clone | External |
| TOOL-26 | `pull_request_read`, `list_pull_requests`, `search_pull_requests`, `create_pull_request`, `update_pull_request`, `update_pull_request_branch`, `merge_pull_request`, `enable_pr_auto_merge`, `disable_pr_auto_merge` | Read, open, update, merge pull requests | No | Update a pull request's title and body, and bring its branch up to date; merging stays the owner's, never the model's | External |
| TOOL-27 | `pull_request_review_write`, `add_comment_to_pending_review`, `add_reply_to_pull_request_comment`, `resolve_review_thread`, `unresolve_review_thread`, `request_copilot_review` | Reviews and review threads | No | Reply to a review thread and resolve it after a pushed fix | External |
| TOOL-28 | `issue_read`, `issue_write`, `list_issues`, `search_issues`, `add_issue_comment`, `update_issue_comment`, `sub_issue_write`, `list_issue_types`, `list_issue_fields`, `get_label` | Issues, comments, sub-issues, labels | No | Issue reads beyond one number; comments and sub-issues asked first | Read / external |
| TOOL-29 | `get_me`, `get_teams`, `get_team_members`, `list_repository_collaborators`, `search_users` | Who the account is, teams, collaborators | No | Read the connected account and its teams | Read |
| TOOL-30 | `run_secret_scanning` | Scan content for secrets | No | Already local (`scripts/scan_secrets.py`); offer it as a check Build runs before a push | Read |
| TOOL-31 | `create_repository`, `fork_repository` | New repositories and forks | No | Asked first, critical | External |

## Sessions, schedules and notifications

From the cloud session's own server (`claude-code-remote`) and the scheduling
tools. Raiker has sessions, tasks with schedules, and notifications; these are
the parts it does not have.

| Item | Tools | What they do | Used 2026-10-25 | Proposed Raiker capability | Side effect |
|---|---|---|---|---|---|
| TOOL-40 | `create_session`, `send_message`, `interrupt_session`, `archive_session`, `unarchive_session`, `get_session`, `list_sessions`, `list_events`, `get_event`, `set_session_title`, `set_session_tags` | Start another session with a task, message it, interrupt it, read its transcript, title and tag it | No | One conversation starting and steering another (a routine delegating to a fresh thread), owner-visible in Threads | Reversible |
| TOOL-41 | `create_trigger`, `update_trigger`, `delete_trigger`, `fire_trigger`, `get_trigger`, `list_triggers`, `CronCreate`, `CronDelete`, `CronList` | Scheduled tasks: create, change, run now, delete, list | No | Raiker has scheduled tasks; the model could propose one (asked first) instead of the owner filling the form | Reversible |
| TOOL-42 | `send_later` | One message back into this conversation at a set time | No | A reminder that continues the same conversation, shown in Tasks | Reversible |
| TOOL-43 | `subscribe_pr_activity`, `unsubscribe_pr_activity` | Wake the session on a pull request's comments, reviews and CI results | No | Build follows its own pull request and fixes CI or answers review, within its permissions | Read |
| TOOL-44 | `watch_url`, `unwatch_url` | An inbound webhook that wakes the session | No | Inbound webhooks for routines, signed and owner-approved per source | External |
| TOOL-45 | `PushNotification`, `ReadNotifications` | Push a notice to the owner's phone; read queued notices | `ReadNotifications` no | A mobile push channel for *Approval needed* and *Task failed*, under the same quiet hours (DEC-21a) | External |
| TOOL-46 | `list_environments`, `list_repos`, `add_repo`, `register_repo_root`, `confirm_repository_trust`, `read_documentation` | Environments, repositories in reach, trust for what a session holds, product documentation | No | `read_documentation` maps to the help panel (QUI-L05): the model reads Raiker's own help articles to answer *how do I…* | Read |
| TOOL-47 | `SendUserFile` | Send a file to the owner, rendered or as an attachment | No | `create_document` already attaches; a *render now* hint for images and HTML | Read |

## Artifacts, documents and design

| Item | Tools | What they do | Used 2026-10-25 | Proposed Raiker capability | Side effect |
|---|---|---|---|---|---|
| TOOL-60 | `Artifact` (publish, read, list, open, pin, delete, quickstart), `ArtifactComments`, `ArtifactData` | Publish an HTML page privately, read and list them, comments on them, and a small shared database a page can use | No | The Library (QUI-F15) as a place for pages Raiker makes, with comments, private by default | Reversible |
| TOOL-61 | `Claude_Docs` (`batch`, `create`, `read`, `update`, `query`, `export`, `delete`, `guide`) | Living documents created and edited by the agent | No | Documents in the Library that a turn can edit section by section, with history | Reversible |
| TOOL-62 | `pdf-viewer` (`display_pdf`, `interact`, `list_pdfs`) | Open a PDF, annotate, fill forms, place a signature | No | PDF annotation and form filling in Design or Chat, asked before a signed file leaves | Reversible / external |
| TOOL-63 | `Figma` (design context, screenshots, variables, Code Connect, `use_figma`, diagrams, …) | Read and write Figma files, design-to-code and code-to-design | No | A Figma connector for Design: read a frame as a reference, export a design | Read / external |
| TOOL-64 | `Canva` (create, edit, export, brand kits, …) | Generate and edit Canva designs | No | A Canva connector for Design exports | External |
| TOOL-65 | `DesignSync` | Sync a design system | No | Keep `app.css` tokens and an external design system in step | Reversible |
| TOOL-66 | `ReportFindings` | Report review findings as a typed list | No | Build's patch review (`review_patch`) as typed findings the transcript draws | Read |

## Skills, plugins and connectors

| Item | Tools | What they do | Used 2026-10-25 | Proposed Raiker capability | Side effect |
|---|---|---|---|---|---|
| TOOL-70 | `Skill`, `ListSkills`, `SearchSkills`, `SuggestSkills` | Load a skill; list, search and suggest skills | No | Raiker has `skill_load`; add search and a suggestion when a task matches an uninstalled skill | Read |
| TOOL-71 | `ListPlugins`, `SearchPlugins`, `SuggestPluginInstall` | Find and suggest plugins | No | Suggest a plugin from the catalogue; installing stays the owner's | Read |
| TOOL-72 | `ListConnectors`, `SuggestConnectors`, `SearchMcpRegistry` | List connectors, suggest one, search the MCP registry | No | The Add connection dialog (QUI-L07) offered from the conversation when a task needs a service | Read |
| TOOL-73 | `ListMcpResourcesTool`, `ReadMcpResourceTool`, `ReadMcpResourceDirTool` | Read MCP resources, not only tools | No | MCP resources in Connections › Advanced, read-only | Read |
| TOOL-74 | `ShowOnboardingRolePicker` | A role picker during setup | No | A role choice in the setup conversation (QUI-W02) that pre-selects starters and connectors | None |
| TOOL-75 | `Artifact` `quickstart` and types | Start from a ready-made page type (slides, documents, dashboards) | No | Templates in Design and the Library | Reversible |

## Third-party connector families

Every family below was in the inventory and none was used. Each is a candidate
for a manifest-driven connector (`connector_read` / `connector_write`), with
reads within permissions and every write asked first.

| Item | Family | Tools in the inventory |
|---|---|---|
| TOOL-80 | Google Workspace | Gmail (search, read threads and messages, drafts, labels, send, reply, forward, trash, spam); Google Calendar (list, search, read, create, update, delete, respond, suggest a time); Google Drive (search, read, download, create, copy, update, share, permissions, trash) |
| TOOL-81 | Messaging and work | Slack (read channels, threads, canvases, lists; send, schedule and draft messages; reactions; files); Asana, Linear, ClickUp, Atlassian, monday.com, Notion (most failed to connect in this session) |
| TOOL-82 | Sales, finance and commerce | Apollo.io (people and company search and enrichment, contacts, accounts, deals, sequences, tasks, calls, analytics); HubSpot, QuickBooks, Xero, Stripe, PayPal, Square, Shopify, Gusto, Ramp, Expensify, DocuSign (most failed to connect) |
| TOOL-83 | Consumer and travel | Indeed (job search, job and company details, résumé); Audible (audiobook recommendations); Booking.com (accommodation and attraction search, property questions); Kiwi.com (flight search) |

## Order

1. TOOL-20 and TOOL-43: Build reads its own CI and follows its own pull
   request. This is the loop that would have saved the most time this round.
2. TOOL-04, TOOL-05 and TOOL-01's completion notice: the agent loop for long
   work without polling.
3. TOOL-12: deferred tool loading, before the connector families grow the
   prompt.
4. TOOL-08 and TOOL-09: a recommended answer, and leaving Plan by approval.
5. TOOL-60 and TOOL-61 with the Library (QUI-F15).
6. The rest, each when a task needs it.
