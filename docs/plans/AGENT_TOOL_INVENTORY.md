# Agent tool inventory — tools to bring into Raiker

**Proposed, 2026-10-25.** It is the
input to the planned refactor of Raiker's tools and capabilities. **First
round shipped 2026-10-25** ([FIXED-1189](FIXED_ITEMS.md#fixed-1189--grep-searched-literal-text-only-with-no-context-lines-tool-02) to
[FIXED-1204](FIXED_ITEMS.md#fixed-1204--the-live-work-line-counted-a-routine-queued-for-later-as-running-found-live); live cases RT-TOOL-01 to RT-TOOL-10 in
[WEB_APP_LIVE_TEST.md](../architecture/WEB_APP_LIVE_TEST.md)): the owner chose
this document for the round and that the *Proposed Raiker capability* column
is the decision for the items taken. Everything not named in the status table
below is still a backlog idea. It records
the tools of three agents, so the refactor can see the whole field before it
reshapes Raiker's own set:

* **Claude** — every tool the coding agent that worked on Raiker on
  2026-10-25 had in its inventory (Claude Code in a cloud session, TOOL-01 –
  TOOL-83), which of them it used, plus the tools Anthropic provides on the
  Claude API and the features of the Claude apps (TOOL-90 – TOOL-109).
* **Hermes Agent** — Nous Research's open-source agent (MIT), from its
  `toolsets.py` on `main` (TOOL-110 – TOOL-131).
* **Muse** — Meta's personal agent (launched 2026-09-08) and its terminal
  sibling Muse Code (TOOL-140 – TOOL-153).

The [capability matrix](#capability-matrix) puts the three side by side with
Raiker today. Each item not taken in a round is a backlog idea, not a
decision: it still needs its own design, threat model and approval in the usual way
([THREAT_MODEL.md](../architecture/THREAT_MODEL.md),
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
| TOOL-02 | **Partly done.** `grep` takes `regex`, `ignore_case`, `context`, `path`, `include` and `max_results` ([FIXED-1189](FIXED_ITEMS.md#fixed-1189--grep-searched-literal-text-only-with-no-context-lines-tool-02)); `edit_file` takes `replace_all` ([FIXED-1190](FIXED_ITEMS.md#fixed-1190--edit_file-could-replace-exactly-one-occurrence-tool-02)); `read_file` reads a line range and a PDF's pages ([FIXED-1192](FIXED_ITEMS.md#fixed-1192--read_file-read-the-first-200-kb-of-a-text-file-and-nothing-else-tool-02)). Open: images in `read_file`. |
| TOOL-04 | **Partly done.** Plan steps carry `blocked_by` ([FIXED-1202](FIXED_ITEMS.md#fixed-1202--plan-steps-could-not-say-what-they-waited-on-tool-04)). Open: an owner per item and stopping a running item. |
| TOOL-08 | **Done.** A recommended option and a preview per option ([FIXED-1193](FIXED_ITEMS.md#fixed-1193--a-question-could-not-say-which-option-raiker-would-choose-tool-08)). |
| TOOL-20, TOOL-22 | **Partly done.** `github_read` `checks`, `workflow_runs` and `run_jobs`, with failure annotations and failed steps ([FIXED-1197](FIXED_ITEMS.md#fixed-1197--build-could-not-read-its-own-ci-tool-20-tool-22)). Open: raw job logs, served from a host outside the connector egress rule. |
| TOOL-23, TOOL-24 | **Partly done.** `github_read` `commits` and `file` at a ref ([FIXED-1198](FIXED_ITEMS.md#fixed-1198--a-remote-file-or-the-repositorys-history-needed-a-clone-tool-23-tool-24)). Open: branches, tags, releases and code search. |
| TOOL-26 | **Partly done.** `github_write` `update_pull_request`, title and body only ([FIXED-1199](FIXED_ITEMS.md#fixed-1199--a-pull-request-raiker-opened-could-not-be-corrected-tool-26)). Open: bringing a pull request's branch up to date. Merging stays the owner's. |
| TOOL-30 | **Done.** A push whose outgoing commits add a credential is refused before the owner is asked ([FIXED-1196](FIXED_ITEMS.md#fixed-1196--a-push-could-publish-a-committed-credential-tool-30)). |
| TOOL-46 | **Done** for `read_documentation`: `help_read` reads Raiker's own help articles ([FIXED-1200](FIXED_ITEMS.md#fixed-1200--a-how-do-i-question-about-raiker-was-answered-from-memory-tool-46)). The rest of TOOL-46 is about the cloud session and does not apply. |
| TOOL-90 | **Partly done.** `allowed_domains` and `blocked_domains` on `web_search`, filtered before the turn ([FIXED-1194](FIXED_ITEMS.md#fixed-1194--web_search-could-not-be-kept-to-sources-the-turn-trusted-tool-90)). |
| TOOL-91 | **Partly done.** `max_chars` on `web_fetch` ([FIXED-1195](FIXED_ITEMS.md#fixed-1195--every-web_fetch-cost-up-to-20000-characters-of-context-tool-91)). Open: the provenance rule (a URL from the owner or an earlier result) and PDF pages. |
| TOOL-99 | **Partly done.** `insert_line` on `edit_file` ([FIXED-1191](FIXED_ITEMS.md#fixed-1191--edit_file-could-not-insert-at-a-line-tool-99)). Open: merging the editor tools into one, which waits for the refactor. |
| TOOL-124 | **Done.** A task's prompt is scanned for injected instructions when it is saved ([FIXED-1201](FIXED_ITEMS.md#fixed-1201--a-tasks-prompt-was-never-checked-for-injected-instructions-tool-124)). |
| TOOL-131 | **Partly done.** `/compress` and `/insights` in Chat ([FIXED-1203](FIXED_ITEMS.md#fixed-1203--a-conversation-could-not-be-summarised-or-measured-from-the-composer-tool-131)). Open: Build's composer. |
| Every other item | **Open** |
| Capability matrix | **Input to the tools refactor** |

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

## Claude API tools and Claude app features

The tools Anthropic provides on the Messages API (from the Claude Platform
[tool reference](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-reference),
read 2026-10-25) and the features of the Claude apps. *Server* tools run on
Anthropic's side; *client* tools have an Anthropic schema and the caller runs
them. Raiker calls Claude as a provider, so a server tool is something Raiker
could switch on per request rather than build.

| Item | Tool (`type`) | What it does | Raiker today | Proposed Raiker capability | Side effect |
|---|---|---|---|---|---|
| TOOL-90 | Web search (`web_search_20260318`, `_20260209`, `_20250305`), server | Search with citations; allowed and blocked domains, a use cap, user location; the 2026 versions filter results in code before they reach the context, and control what the response includes | `web_search` (Raiker's own backend) | Domain allow and block lists on `web_search`; filter results before they enter the turn, so a long result page does not cost the context | Read |
| TOOL-91 | Web fetch (`web_fetch_20260318`, `_20260309`, `_20260209`, `_20250910`), server | Fetch a page or PDF with citations; only URLs the user gave or a search returned; a content-token cap; a cache bypass | `web_fetch` | The same provenance rule on `web_fetch` (a URL must come from the owner or an earlier result), PDF support and a token cap | Read |
| TOOL-92 | Code execution (`code_execution_20260521`, `_20260120`, `_20250825`), server | A sandbox with Python, Bash and file operations; the newest states its per-cell time limit | `cloud_execute`, `remote_execute` | A disposable analysis sandbox that takes the owner's attached files and returns files, not only output | Reversible |
| TOOL-93 | Programmatic tool calling (`allowed_callers`) | Code in the sandbox calls other tools, so a many-step pipeline is one turn; a tool can be limited to code callers | — | Let a sandboxed script call read-only Raiker tools through the broker, each call still gated and audited | As the tool called |
| TOOL-94 | Advisor (`advisor_20260301`, beta), server | A stronger model consulted mid-task for a second opinion | `consult_advisor` | Align `consult_advisor` with the provider tool where the provider offers it | Read |
| TOOL-95 | Tool search (`tool_search_tool_regex_20251119`, `_bm25_20251119`), server | Find deferred tools by regex or BM25; `defer_loading` keeps them out of the prompt and the cache | — | Same as TOOL-12; the refactor should make every connector tool deferrable | Read |
| TOOL-96 | MCP connector (`mcp_toolset`, beta), server | Call a remote MCP server's tools from the API, with per-tool allow and defer settings | MCP connections (local broker) | Keep MCP in the broker; adopt the per-tool allow and defer settings in each connection's manifest | As the tool called |
| TOOL-97 | Memory (`memory_20250818`), client | A `/memories` directory the model views, creates, edits, inserts into, renames and deletes; Managed Agents add a between-session consolidation that merges duplicates and drops stale entries | `memory_write`, `memory_search`, `memory_get`, `memory_list`, `memory_forget` | A scheduled consolidation pass over Memory (merge duplicates, retire stale facts) that proposes its changes in Suggestions | Reversible |
| TOOL-98 | Bash (`bash_20250124`), client | A persistent shell session | `run_command`, `shell` | Already covered; keep one shell tool in the refactor, not two | As today |
| TOOL-99 | Text editor (`text_editor_20250728`, `_20250124`), client | `view`, `str_replace`, `create`, `insert` | `read_file`, `write_file`, `edit_file`, `apply_patch` | `insert` at a line; merge the four into one editor tool with commands if the refactor favours fewer tools | Reversible |
| TOOL-100 | Computer use (`computer_toolset_20260801`; betas `computer_20251124`, `computer_20250124`), client | Screenshot, mouse, keyboard, scroll, drag, zoom; several calls in one turn run as a batch | — | A governed desktop-control toolset for the desktop shell, every action shown live and stoppable, off unless the owner turns it on | External |
| TOOL-101 | Browser use (`browser_toolset_20260801`), client | Navigate, read, click, type and screenshot in a browser; JavaScript execution switchable per member | — | A governed browser toolset (see the matrix: all three agents have one) | External |
| TOOL-102 | Tool definition properties | `strict` schema validation, `input_examples`, `defer_loading`, `allowed_callers`, `eager_input_streaming`, `cache_control` | Tools advertised in full | The refactor's tool manifest carries these: strict schemas, examples, deferral and caller limits per tool | — |
| TOOL-103 | Artifacts (Claude apps) | A side panel for documents, code and interactive apps; edit in place by highlighting; AI-powered artifacts; up to 20 MB of storage per artifact | `create_document` | See TOOL-60 and the Library (QUI-F15) | Reversible |
| TOOL-104 | Search and reference past chats, memory (Claude apps) | Find and cite earlier conversations; a memory of the person across chats | `conversation_search`, Memory | Cite the conversation a recalled fact came from | Read |
| TOOL-105 | Research (Claude apps) | Many searches and fetches gathered into a cited report | `web_search`, `web_fetch` | A *research* mode in Chat: a bounded plan of searches, shown as it runs, ending in a cited document | Read |
| TOOL-106 | File creation (Claude apps) | Make Word, Excel, PowerPoint and PDF files through code execution | `create_document` | Office formats from `create_document` | Reversible |
| TOOL-107 | Inline visualizations (Claude apps) | Charts and diagrams drawn in the answer | — | A chart block in `answerBlocks` from a data table | None |
| TOOL-108 | Claude in Chrome, Cowork (Claude apps) | Act in the user's own browser; long tasks in a cloud sandbox or a local VM | — | The browser toolset (TOOL-101) first in the desktop shell's own window, not the owner's profile | External |
| TOOL-109 | Skills, connectors, projects (Claude apps) | Agent Skills; MCP connectors from a directory; projects with their own files and instructions | `skill_load`, Connections, Projects | Covered by TOOL-70 – TOOL-72 | Read |

## Hermes Agent

Nous Research's agent, from
[`toolsets.py`](https://github.com/NousResearch/hermes-agent/blob/main/toolsets.py)
and the README on `main`, read 2026-10-25. Hermes groups tools into named
**toolsets** and gives each surface (CLI, API server, each messaging platform)
its own composition of them; its shared core is 46 tools.

| Item | Toolset: tools | What they do | Raiker today | Proposed Raiker capability | Side effect |
|---|---|---|---|---|---|
| TOOL-110 | `terminal`: `terminal`, `process_manage` | Run commands and manage background processes, on six backends (local, Docker, SSH, Modal, Daytona, Vercel Sandbox) plus plugin backends | `run_command`, `background_run`, `remote_execute`, `cloud_execute` | One execution tool with a *where* argument chosen from the owner's configured backends | As today |
| TOOL-111 | `file`: `read_file`, `write_file`, `patch`, `search_files` | Read, write, patch and search files | `read_file`, `write_file`, `edit_file`, `apply_patch`, `glob`, `grep` | Hermes does it with four tools; a reference point for consolidating Raiker's six | Read / reversible |
| TOOL-112 | `web`: `web_search`, `web_extract`; `x_search` | Search, extract a page's content; search X | `web_search`, `web_fetch` | Source-specific search as connector tools, not core | Read |
| TOOL-113 | `browser`: `browser_exec`, `browser_cdp`, `browser_dialog`, `browser_vault` | Drive a browser (local, cloud, sandboxed or the real profile), raw DevTools Protocol, answer dialogs, fill stored credentials; a URL policy | — | Browser toolset (matrix row); credentials from the vault filled by the broker, never shown to the model | External |
| TOOL-114 | `computer_use`: `computer_use` | Desktop control | — | See TOOL-100 | External |
| TOOL-115 | `vision`: `vision_analyze`; `video`: `video_analyze` | Describe an image or a video | Image attachments to a vision model | `video_analyze` for an attached clip | Read |
| TOOL-116 | `image_gen`: `image_generate`; `video_gen`: `video_generate`, `xai_video_edit`, `xai_video_extend` | Generate images and video; edit and extend video | Design (layouts, not images) | Image generation in Design through a provider connector, each image a saved revision | Reversible |
| TOOL-117 | `tts`: `text_to_speech`; voice-memo transcription | Speak an answer; transcribe incoming voice notes | — | Read an answer aloud, and dictate into the composer (desktop) | None |
| TOOL-118 | `todo`: `todo_list` | The agent's task list | `update_plan` | See TOOL-04 | Model's own intent |
| TOOL-119 | `memory`: `memory`; `session_search`: `session_search`; `context_engine` | Agent-curated memory with nudges to save (`MEMORY.md`, `USER.md`); full-text search over past sessions with model summaries; a pluggable context engine; Honcho user modelling as a plugin | Memory tools, `conversation_search` | A *save this?* nudge after a long task, landing in Suggestions; summaries on `conversation_search` hits | Reversible |
| TOOL-120 | `skills`: `skills_list`, `skill_view`, `skill_manage` | List, read and create or improve skills; skills written by the agent after a complex task (agentskills.io format, a Skills Hub) | `skill_load` | The model drafts a skill from a finished task, proposed to the owner, never installed by itself | Reversible |
| TOOL-121 | `clarify`: `clarify` | Ask the user a question, batched across platforms | `ask_owner_question` | Covered; see TOOL-08 | None |
| TOOL-122 | `code_execution`: `execute_code` | Python that calls Hermes tools over RPC, many steps in one turn | — | See TOOL-93 | As the tool called |
| TOOL-123 | `delegation`: `delegate_task` | Isolated subagents, synchronous or asynchronous, each with its own provider, model, limits and toolset; live logs; a result schema; redaction | `spawn_subagent` (read-only) | Asynchronous subagents with a toolset chosen per task and a typed result | As the toolset given |
| TOOL-124 | `cronjob`: `cronjob_manage` | Natural-language scheduled jobs, delivered to any platform; prompts scanned before they run | Scheduled tasks | See TOOL-41; scan a scheduled prompt for injected instructions when it is saved | Reversible |
| TOOL-125 | `kanban`: `kanban_show`, `kanban_list`, `kanban_create`, `kanban_complete`, `kanban_block`, `kanban_unblock`, `kanban_link`, `kanban_comment`, `kanban_heartbeat`, `kanban_request_review`, `kanban_request_changes`, `kanban_attach`, `kanban_attach_url`, `kanban_attachments` | A shared board of cards between agents and people: block, link, comment, attach, request review, heartbeat | Tasks, Goals, Projects | Task tools for the model: comment, block on another task, attach a file, ask for review; a heartbeat on a long task | Reversible |
| TOOL-126 | `connections`: `manage_connections`; `catalog`: `manage_catalog` | Add and change MCP connections and the tool catalogue from the conversation | Connections (owner only) | The model proposes a connection or a catalogue change; the owner confirms in Connections | Reversible |
| TOOL-127 | Messaging toolsets: `discord`, `discord_admin`, `feishu_doc_read`, `feishu_drive_*` (4), `yb_*` (5), `react_to_message` | Platform-specific reads, comments, DMs and reactions | `slack_read` | Per-platform tools as connector manifests, not core tools | Read / external |
| TOOL-128 | Messaging gateway | One process serving Telegram, Discord, Slack, WhatsApp, Signal, Email, SMS, Matrix, Mattermost, DingTalk, Feishu, WeCom, Weixin, QQ, BlueBubbles, Home Assistant and webhooks; DM pairing; one conversation continuing across platforms | Web and desktop only | Talk to Raiker from one paired messaging channel, the same approvals and quiet hours applying | External |
| TOOL-129 | `desktop_ui`: `read_terminal`, `close_terminal`, `desktop_preview`, `drive_preview`, `annotate_preview`, `read_window_below`, `focus_pane`, `gui_tour`, `show_tip`, `set_theme`; `onboarding`: `setup_beat`; `project`: `desktop_project` | The agent drives its own desktop app: previews, annotations, a guided tour, tips, theme, onboarding steps, projects | — | `show_tip` and `gui_tour` map to the help panel (QUI-L05); `annotate_preview` to Design review | None |
| TOOL-130 | Approvals, checkpoints, toolset profiles | Approval modes (smart, YOLO, floors, waiting on a gateway or a person); file checkpoints with pruning; named toolsets (`safe`, `coding`, `debugging`) and one composition per surface | Approvals, Checkpoints, runtime modes | **Named toolsets per surface and posture** as the refactor's unit: Chat, Build, Design, a routine and a subagent each get a declared set | — |
| TOOL-131 | Commands and training | `/undo`, `/retry`, `/compress`, `/insights`, `/usage`, `/personality`; batch trajectory generation and compression for training tool-calling models; importers from other agents | Composer commands | `/compress` (summarise the thread so far) and `/insights` (what this thread cost and used) | None |

## Muse

Meta's personal agent and Muse Code. Meta has not published Muse's tool
names, so these rows are **capabilities, not tool names**. Sources, read
2026-10-25: Meta's product page and help pages, Meta's safety and Muse Code
launch posts, and third-party reviews; rows that rest only on third-party
write-ups say so.

| Item | Capability | What it does | Raiker today | Proposed Raiker capability |
|---|---|---|---|---|
| TOOL-140 | Secure VM | A persistent, isolated Linux computer per person with a browser, file system and terminal that the person and the agent share | Local host, sandboxed commands | A per-owner workspace the owner can open and watch, the same one the agent works in |
| TOOL-141 | Browser subagent | A dedicated browser agent; DevTools access behind a broker with a narrow interface; fills forms; asks before important actions such as a purchase | — | The browser toolset as its own subagent, the main turn seeing only its summary |
| TOOL-142 | Sentinel | A separate policy agent that is the only authority over connector actions and network traffic: allow, deny or ask | Broker, permissions, network policy | A second, model-free policy check on every egress and connector write, outside the agent's process |
| TOOL-143 | Approval scopes | Once, for the session, for the task, for a time window, or always | Approvals (once; standing rules) | *For this task* and *for the next hour* as approval scopes |
| TOOL-144 | Surrogate credentials | Code in the VM sees a stand-in token; the real one is swapped in at the network boundary (third-party write-ups) | Vault; keys never in arguments | Surrogate tokens for sandboxed code, swapped by the broker |
| TOOL-145 | Purchases | Payments through Link by Stripe; Shop Pay and 1Password announced | — | Out of scope until a payments threat model exists; critical, asked every time |
| TOOL-146 | Connectors and skills | Connectors with read and write shown separately per service; about 68 bundled skills (Google Workspace, Outlook, Meta's apps, travel, shopping, health, home devices, media generation; third-party count) | Connections, skills | Show each connection's read and write grants separately |
| TOOL-147 | Memory and observers | A `MEMORY.md` sheet of facts, preferences and commitments, with dated daily files (third-party); four observer agents beside the session for memory recall, skill suggestion, goal tracking and verification of claimed work | Memory, Goals | A *verifier* that checks a turn's claimed result (tests run, file written) before the turn reports done |
| TOOL-148 | Subagent fan-out | Persistent background agents, each in its own git worktree, default eight at once (1 – 64); every model call, tool run, approval and edit in an append-only event log | `spawn_subagent`, BR-D02 worktrees, events | Parallel Build subagents, each in a worktree, under one approval budget |
| TOOL-149 | Custom tools, documents, images | Builds its own tools; creates documents and interactive artifacts; generates images | `create_document`, Design | Model-written tools proposed as skills (TOOL-120) |
| TOOL-150 | Proactive work | Scheduled work, reacting to events, messaging the person first | Scheduled tasks, notifications | See TOOL-41, TOOL-44, TOOL-45 |
| TOOL-151 | Built-in skills (Muse Code) | `/plan`, `/grill` (question the plan), `/taste`, `/threejs` | Build's Plan posture | A *grill* step: the model questions its own plan before asking for approval |
| TOOL-152 | Audit and export | An audit trail of what the agent did; the person can export the VM's files | Events, Diagnostics export | An export of everything a workspace holds, from Settings |
| TOOL-153 | Surfaces | iOS, Android, web, WhatsApp; glasses announced | Web, desktop | See TOOL-128 |

## Capability matrix

The refactor's starting point: each row is one capability family, with how
each agent provides it and what Raiker has. **Gap** means none of Raiker's
tools covers it.

| Capability | Claude | Hermes Agent | Muse | Raiker today |
|---|---|---|---|---|
| Shell and processes | `Bash` (background, notices), `bash` | `terminal`, `process_manage`, six backends | Terminal in the VM | `run_command`, `shell`, `background_run`, `remote_execute`, `cloud_execute` |
| Files | `Read`, `Write`, `Edit`, `Glob`, `Grep`, `NotebookEdit`; `text_editor` | `read_file`, `write_file`, `patch`, `search_files` | VM file system | `read_file`, `write_file`, `edit_file`, `apply_patch`, `glob`, `grep`, `list_directory`, `stat_path`, `diff_files` |
| Code search | `Grep`, `Glob` | `search_files` | — | `code_map_search`, `code_map_references` |
| Sandboxed code | `code_execution`, programmatic calling | `execute_code` (RPC) | VM | `cloud_execute` — no programmatic calling (**gap**) |
| Web search and fetch | `web_search`, `web_fetch`, Research | `web_search`, `web_extract`, `x_search` | Browsing | `web_search`, `web_fetch` |
| Browser | Browser use, Claude in Chrome | `browser_exec`, `browser_cdp`, `browser_dialog`, `browser_vault` | Browser subagent | **Gap** |
| Desktop control | Computer use | `computer_use` | — | **Gap** |
| Vision and media | Image input | `vision_analyze`, `video_analyze`, `image_generate`, `video_generate` | Image generation | Image input only |
| Voice | — | `text_to_speech`, transcription | — | **Gap** |
| Plan and to-dos | `TaskCreate` … `TaskStop`, plan mode | `todo_list` | `/plan`, `/grill` | `update_plan`, Plan posture |
| Ask the person | `AskUserQuestion` | `clarify` | Approvals | `ask_owner_question` |
| Memory | `memory` tool, past-chat search | `memory`, `session_search`, Honcho | `MEMORY.md`, observers | `memory_*`, `conversation_search`, `knowledge_graph`, `vector_get` |
| Skills | `Skill`, Agent Skills | `skills_list`, `skill_view`, `skill_manage` | Bundled skills | `skill_load` |
| Subagents | `Agent`, `SendMessage`, forks | `delegate_task` (async) | Fan-out in worktrees | `spawn_subagent` (read-only) |
| Second opinion | Advisor | — | Verifier observer | `consult_advisor` |
| Schedules and wake-ups | Scheduled tasks, `send_later`, `ScheduleWakeup` | `cronjob_manage` | Scheduled work, events | `create_task` with a schedule |
| Work tracking | — | `kanban_*` | Goals | `create_task`, `assign_session_project` |
| Git and GitHub | GitHub MCP (TOOL-20 – TOOL-31) | Through the terminal | Through the terminal | `git_*`, `github_read`, `github_write` |
| Connectors | MCP, connector directory, deferred loading | MCP, `manage_connections`, plugins | Connectors with read and write grants | `connector_read`, `connector_write`, `gmail_read`, `gcal_read`, `slack_read` |
| Messaging surfaces | Slack (Claude Tag) | Gateway for 17 platforms | WhatsApp | **Gap** |
| Documents and artifacts | Artifacts, Docs, file creation | `desktop_preview`, `annotate_preview` | Documents, interactive artifacts | `create_document` |
| Policy and approvals | Permission modes, hooks | Approval modes, DM pairing, toolset profiles | Sentinel, approval scopes, surrogate credentials | Broker, approvals, standing rules, vault |
| Audit and recovery | Transcript | Checkpoints | Event log, export | Events, checkpoints, Diagnostics |

### What the matrix suggests for the refactor

* **Toolsets as the unit.** Hermes composes named toolsets per surface;
  Claude declares toolsets with members switched on or off. Raiker can declare
  one set per surface and posture (Chat, Build, Design, a routine, a subagent)
  instead of filtering one flat list (TOOL-130, TOOL-102).
* **Fewer, broader core tools; everything else deferred.** All three keep a
  small core and load the rest on demand (TOOL-12, TOOL-95). Raiker's file
  tools (nine) and execution tools (five) are the first to consolidate
  (TOOL-99, TOOL-110, TOOL-111).
* **The shared gaps are browser, desktop control, programmatic calling and a
  messaging surface.** Each is in at least two of the three agents.
* **Policy outside the agent.** Muse's Sentinel and surrogate credentials, and
  Hermes's approval floors, keep the decision out of the model's process
  (TOOL-142, TOOL-144); Raiker's broker is the place for both.

## Order

1. **The refactor's shape first:** named toolsets per surface and posture
   (TOOL-130), the manifest properties (TOOL-102) and deferred loading
   (TOOL-12, TOOL-95), with the file and execution tools consolidated
   (TOOL-99, TOOL-110, TOOL-111).
2. TOOL-20 and TOOL-43: Build reads its own CI and follows its own pull
   request. This is the loop that would have saved the most time this round.
3. TOOL-04, TOOL-05 and TOOL-01's completion notice: the agent loop for long
   work without polling.
4. TOOL-142 and TOOL-143: a model-free policy check on egress and connector
   writes, and task- and time-scoped approvals, before any new external tool.
5. TOOL-101 / TOOL-113 / TOOL-141: the browser toolset, behind (4).
6. TOOL-93 / TOOL-122: programmatic tool calling from the sandbox.
7. TOOL-08 and TOOL-09: a recommended answer, and leaving Plan by approval.
8. TOOL-60 and TOOL-61 with the Library (QUI-F15).
9. The rest, each when a task needs it.
