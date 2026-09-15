"""What each capability would cost if it were reached without governance.

**Why this exists (BUG-293 / RR-AUTHORITY-01).**
[DEC-16](../../../docs/plans/RELEASE_READINESS_PRODUCT_UX_RUNTIME_REVIEW_2026-09-13.md)
step 8 asks for a mechanical check that every real side-effect capability carries
five things: *an executor, a threat model, a Permissions description, an authority
requirement and a negative bypass test.* Three of the five were already
mechanical and two had no home at all:

============================  ====================================================
Column                        Enforced by
============================  ====================================================
Executor                      ``REAL_EXECUTOR_CAPABILITIES`` and the registry
                              assertion in ``raiker/runtime/executors/__init__.py``
How it is reached             ``tests/test_governance_entry_paths.py`` against
                              :data:`~raiker.runtime.authority.entry_paths.CAPABILITY_ENTRY_PATHS`
Permissions description       ``tests/test_capability_permissions_copy.py``
**Threat model**              **this table's** :attr:`CapabilityAuthority.ungoverned`
**Authority requirement**     **this table's** :attr:`CapabilityAuthority.authority`
**Negative bypass test**      **this table's** :attr:`CapabilityAuthority.bypass_test`
============================  ====================================================

The bypass property used to be established *structurally*: ``route_action``'s
callers are enumerated and asserted, and the agent gateway is constructed only by
named surfaces. That is a genuine boundary and it is a different claim. It says
*no current path bypasses the chokepoint*; it does not say *each of the forty-eight
capabilities has a test proving its own gate refuses before its executor runs.*

So every row here names a test, ``tests/test_capability_authority.py`` asserts
that the named test exists and is the one that covers this capability, and the
generic proof is parameterised over the capability rather than over a set
intersection — a test id carrying the capability's own name is per-capability in
the way a shared assertion is not.

**What writing it out found.** ``image_generation`` had a real executor, an
owner-facing switch on Permissions, a docstring in
``RuntimeControlService.run_image_generation`` saying "the ``image_generation``
gate … appl[ies]", and **no entry in** :data:`~raiker.runtime.authority.router.CAPABILITY_GATE_MAP`
— so ``check_capability_gate`` found no gate for the action, returned ``None``,
and the owner's off switch decided nothing. It was approval-required by policy,
which is why nothing looked wrong. Recorded as FIXED-542.

The API serves this beside the gate, so Permissions can answer *what would this
cost if it ran without me* rather than only *is it on*.
"""
from __future__ import annotations

from dataclasses import dataclass

# ── How far the side effect reaches ─────────────────────────────────────────
#
# The classes are ordered by what an owner loses if the capability runs when
# they did not mean it to, which is the question the column exists to answer —
# not by implementation tier, and not by risk level, which is a per-action
# property the policy engine already carries.

#: Reads and derives. Nothing changes and nothing leaves the machine.
SIDE_EFFECT_READ = "read"
#: Changes local state that an inverse action, a checkpoint or a delete undoes.
SIDE_EFFECT_REVERSIBLE = "reversible"
#: Bytes leave the machine, or a third party is asked to do something. Nothing
#: Raiker can do afterwards un-sends them.
SIDE_EFFECT_EXTERNAL = "external"
#: Destroys or replaces state the owner cannot get back from inside Raiker.
SIDE_EFFECT_DESTRUCTIVE = "destructive"
#: Changes what Raiker itself may do next — authority, code it will run, or work
#: it will start without being asked.
SIDE_EFFECT_CRITICAL = "critical"

SIDE_EFFECT_CLASSES = (
    SIDE_EFFECT_READ,
    SIDE_EFFECT_REVERSIBLE,
    SIDE_EFFECT_EXTERNAL,
    SIDE_EFFECT_DESTRUCTIVE,
    SIDE_EFFECT_CRITICAL,
)

#: The generic per-capability negative proof. Parameterised over the capability,
#: so a row naming it names a test id that carries the capability's own name.
GENERIC_BYPASS_TEST = (
    "tests/test_capability_authority.py::test_the_gate_refuses_before_the_executor_runs"
)


@dataclass(frozen=True)
class CapabilityAuthority:
    """One capability's threat model, authority requirement and negative proof."""

    capability: str
    #: One of :data:`SIDE_EFFECT_CLASSES`.
    side_effect: str
    #: What goes wrong if this runs and the owner did not decide it should.
    #: Written for the owner, not the implementer, and never a restatement of
    #: the capability's own name — that is the bar
    #: ``test_an_inert_gate_says_what_really_governs_it`` already sets next door.
    ungoverned: str
    #: What has to be true before it may run at all.
    authority: str
    #: The test that proves the refusal, as a pytest node id.
    bypass_test: str = GENERIC_BYPASS_TEST

    def __post_init__(self) -> None:
        if self.side_effect not in SIDE_EFFECT_CLASSES:
            raise ValueError(f"capability_authority_side_effect_invalid:{self.capability}")
        if not self.ungoverned.strip():
            raise ValueError(f"capability_authority_threat_required:{self.capability}")
        if not self.authority.strip():
            raise ValueError(f"capability_authority_requirement_required:{self.capability}")
        if "::" not in self.bypass_test:
            raise ValueError(f"capability_authority_bypass_test_invalid:{self.capability}")


def _row(
    capability: str,
    side_effect: str,
    ungoverned: str,
    authority: str,
    bypass_test: str | None = None,
) -> CapabilityAuthority:
    """A row whose bypass test defaults to the generic proof for *capability*."""
    return CapabilityAuthority(
        capability=capability,
        side_effect=side_effect,
        ungoverned=ungoverned,
        authority=authority,
        bypass_test=bypass_test or f"{GENERIC_BYPASS_TEST}[{capability}]",
    )


_AUTHORITY: tuple[CapabilityAuthority, ...] = (
    # ── Reads: nothing changes, nothing leaves ─────────────────────────────
    _row(
        "language_intelligence",
        SIDE_EFFECT_READ,
        "A turn could parse any file the workspace confinement allows and quote "
        "its symbols back, so a repository the owner attached for one question "
        "answers a different one without being asked.",
        "An owner-enabled gate, and the same workspace confinement `read_file` "
        "obeys. It writes nothing, not even a derived index.",
    ),
    _row(
        "semantic_memory_runtime",
        SIDE_EFFECT_READ,
        "Recall could surface an approved fact into a conversation the owner "
        "never meant it to reach, which is a disclosure even though no record "
        "changes.",
        "The `vector_embedding_runtime` gate the retrieval path reads, under the "
        "owner's account scope — that is the gate the Memory page shows — and a "
        "memory belonging to another account is never a candidate.",
    ),
    _row(
        "vector_embedding_runtime",
        SIDE_EFFECT_READ,
        "Text the owner stored locally would be turned into vectors by whatever "
        "backend is configured, and a provider-backed backend sends that text "
        "off the machine to do it.",
        "An owner-enabled gate; the provider-backed path additionally re-checks "
        "the model egress allowlist and the hosted/private gate per call.",
    ),
    # ── Reversible local state ─────────────────────────────────────────────
    _row(
        "file_write_execution",
        SIDE_EFFECT_REVERSIBLE,
        "An agent turn could write anywhere the process can reach and the owner "
        "would learn about it by finding the file, rather than by deciding.",
        "An owner-enabled gate, workspace confinement, and — in the default Ask "
        "mode — an approval carrying the unified diff before a byte is written.",
    ),
    _row(
        "patch_apply_execution",
        SIDE_EFFECT_REVERSIBLE,
        "A patch could rewrite files the owner never opened, and a patch is "
        "harder to read after the fact than the diff that proposed it.",
        "An owner-enabled gate, workspace confinement, and an approval whose "
        "preview is the patch that will actually be applied.",
    ),
    _row(
        "git_write_execution",
        SIDE_EFFECT_REVERSIBLE,
        "A branch or commit could appear in the owner's repository history "
        "without them, and history is the record they use to review everything "
        "else the agent did.",
        "An owner-enabled gate and an approval. Repository hooks are disabled "
        "for the invocation, so an approved commit cannot run workspace code the "
        "agent may itself have written.",
    ),
    _row(
        "memory_write_execution",
        SIDE_EFFECT_REVERSIBLE,
        "A turn could write a durable fact about the owner that every later turn "
        "then reasons from, so one wrong sentence becomes the premise of every "
        "conversation after it.",
        "An owner-enabled gate and, in Ask mode, an approval naming the fact. "
        "Learned text is untrusted: it can never change a grant.",
    ),
    _row(
        "task_management_runtime",
        SIDE_EFFECT_REVERSIBLE,
        "A turn could create scheduled or background work that keeps running "
        "after the conversation that asked for it has ended.",
        "An owner-enabled gate, the owner's account scope, and the decision mode "
        "for the capability. Creating a task grants it nothing the owner has not "
        "granted separately.",
    ),
    _row(
        "project_assignment_runtime",
        SIDE_EFFECT_REVERSIBLE,
        "A session could be filed to a project it does not belong to, which "
        "silently changes which context later turns are given.",
        "An owner-enabled gate and account-scoped project ownership; a project "
        "belonging to another account is not a destination.",
    ),
    _row(
        "audit_export",
        SIDE_EFFECT_REVERSIBLE,
        "The owner's whole governed record could be written to a file on disk "
        "that nothing afterwards redacts, which is a copy of everything Raiker "
        "knows sitting outside its own store.",
        "An owner-enabled gate and their own account scope. The export is "
        "redacted and written locally; it reaches no network and grants nothing.",
    ),
    _row(
        "graph_indexing_runtime",
        SIDE_EFFECT_REVERSIBLE,
        "A derived graph of the owner's files and their relationships would be "
        "built and kept, so material they only meant Raiker to read once becomes "
        "material it has indexed.",
        "An owner-enabled gate and workspace confinement; the derived store is "
        "the owner's and is deletable.",
    ),
    _row(
        "code_map_indexing",
        SIDE_EFFECT_REVERSIBLE,
        "A symbol index of the repository would be written and kept, so a "
        "repository attached for one build is summarised into a cache that "
        "outlives it.",
        "An owner-enabled gate, the repository Build points at, and the "
        "repository's own exclusions. The cache is derived and removable.",
    ),
    _row(
        "mcp_builder_runtime",
        SIDE_EFFECT_REVERSIBLE,
        "A server template would be written into the workspace, and a file that "
        "looks like infrastructure is one an owner is likely to run later "
        "without re-reading it.",
        "An owner-enabled gate, a workspace-relative destination, and a reviewed "
        "dependency-free template. Writing one does not connect it.",
    ),
    _row(
        "plugin_revocation_cap",
        SIDE_EFFECT_REVERSIBLE,
        "An install could be revoked without the owner asking, which is the "
        "safe direction and still a change to what they believe is available.",
        "The plugin registry revokes an install directly when the owner asks; no "
        "governed action is constructed, so the gate has nothing to refuse. "
        "Revocation is the safe direction and is the owner's own act.",
    ),
    _row(
        "container_execution_cap",
        SIDE_EFFECT_REVERSIBLE,
        "Work would move into a container the owner did not choose, and a "
        "different execution destination is a different set of things that can "
        "go wrong with it.",
        "Choosing a container execution profile is the owner's act of "
        "authorisation, and every tool call inside it is still brokered under "
        "that tool's own gate. No network, no host mounts.",
    ),
    _row(
        "reminder_runtime",
        SIDE_EFFECT_REVERSIBLE,
        "Local reminder records would be created and read by later turns, so a "
        "store the owner never opened becomes context they did not supply.",
        "Nothing constructs a reminder action, so the gate has nothing to refuse "
        "yet. If a surface ever proposes one it meets an owner-enabled gate and "
        "their own account scope; the records are local and nothing delivers one.",
    ),
    _row(
        "calendar_runtime",
        SIDE_EFFECT_REVERSIBLE,
        "Local calendar entries would be created and read as though the owner "
        "had kept them, which makes invented appointments indistinguishable "
        "from real ones.",
        "Nothing constructs a calendar action, so the gate has nothing to refuse "
        "yet. A future surface meets an owner-enabled gate and their own account "
        "scope; the store is local and syncs with nothing.",
    ),
    _row(
        "email_runtime",
        SIDE_EFFECT_REVERSIBLE,
        "Drafts would be composed and stored under the owner's name, and a draft "
        "is one accidental action away from being a sent message.",
        "Nothing drafts and nothing has ever sent, so the gate has nothing to "
        "refuse yet. A future surface meets an owner-enabled gate and their own "
        "account scope, and sending would be a separate decision again.",
    ),
    # ── External: bytes leave, or a third party acts ───────────────────────
    _row(
        "web_fetch",
        SIDE_EFFECT_EXTERNAL,
        "A turn could ask any host on the internet for anything, and the request "
        "itself — the URL, the timing, the machine it came from — tells that host "
        "something about the owner whatever the answer is.",
        "An owner-enabled gate, the owner's web blocklist, the address guard "
        "that refuses private and loopback destinations, and the decision mode "
        "for the capability. Every answer is marked untrusted.",
    ),
    _row(
        "git_push_execution",
        SIDE_EFFECT_EXTERNAL,
        "Repository content would leave the machine under the owner's own "
        "credential, and a push is public the moment it lands — no later "
        "decision takes it back.",
        "Its own gate, separate from `git_write_execution`: an owner who let the "
        "agent commit has not thereby let it publish. Plus the connector egress "
        "allowlist, the owner's credential, and an approval. It never forces and "
        "never deletes a ref.",
    ),
    _row(
        "image_generation",
        SIDE_EFFECT_EXTERNAL,
        "The prompt — and, for an edit, the source image — would be sent to a "
        "hosted provider and the owner's credit spent, on a turn's initiative "
        "rather than theirs.",
        "An owner-enabled gate, a human principal, the model egress allowlist, "
        "the owner's saved provider credential, and an approval. An endpoint is "
        "built from the configured profile, never from the request.",
    ),
    _row(
        "telemetry_export",
        SIDE_EFFECT_EXTERNAL,
        "The governed record would be streamed to a collector over the network, "
        "so evidence that exists to be the owner's leaves the machine "
        "continuously rather than once.",
        "Its own gate, separate from `audit_export`, because it differs in the "
        "one way that matters: it leaves the machine. Plus the owner-named "
        "collector endpoint and the egress allowlist.",
    ),
    _row(
        "hosted_model_runtime",
        SIDE_EFFECT_EXTERNAL,
        "Conversation content would be sent to a hosted provider, which is the "
        "single largest disclosure Raiker can make and the one an owner most "
        "expects to have chosen.",
        "An owner-enabled gate, the model egress allowlist (process "
        "configuration, deliberately not editable from a browser session), and "
        "an owner credential supplied from the environment.",
    ),
    _row(
        "private_network_model_runtime",
        SIDE_EFFECT_EXTERNAL,
        "Conversation content would be sent to a host on the owner's own "
        "network, which is not the internet and is still not this machine.",
        "An owner-enabled gate and the model egress allowlist. The private "
        "destination is named by the owner, not derived from the request.",
    ),
    _row(
        "advisor_model_runtime",
        SIDE_EFFECT_EXTERNAL,
        "A local-model turn would quietly consult a second, hosted model, so an "
        "owner who chose a local runtime for privacy would be sending the same "
        "content to a provider anyway.",
        "An owner-enabled gate, default-Ask consult of the owner-picked advisor "
        "profile, and the provider policy — hosted/private gate, egress "
        "allowlist, environment-only key — re-checked per call.",
    ),
    _row(
        "model_provider_runtime",
        SIDE_EFFECT_EXTERNAL,
        "Text would be sent to an LLM provider to be embedded, which is the same "
        "disclosure as a chat turn wearing the clothes of an index build.",
        "An owner-enabled gate layered over the egress allowlist, the "
        "hosted/private gate and environment-only credentials.",
    ),
    _row(
        "connector_github_runtime",
        SIDE_EFFECT_EXTERNAL,
        "The owner's GitHub token would be used to read — and, through "
        "`github_write`, to change — repositories and issues under their name, "
        "so the account acts without the person.",
        "An owner-enabled gate, default-Ask decision mode, an environment-only "
        "credential (`RAIKER_GITHUB_TOKEN`), and `api.github.com` on the owner's "
        "connector egress allowlist.",
    ),
    _row(
        "connector_gmail_runtime",
        SIDE_EFFECT_EXTERNAL,
        "The owner's mail would be read with their own token, and mail is the "
        "store most likely to contain the credentials for everything else.",
        "An owner-enabled gate, default-Ask decision mode, an environment-only "
        "credential (`RAIKER_GMAIL_TOKEN`), and `gmail.googleapis.com` on the "
        "connector egress allowlist. Reads only.",
    ),
    _row(
        "connector_gcal_runtime",
        SIDE_EFFECT_EXTERNAL,
        "The owner's calendar would be read with their own token, which "
        "discloses where they are and who they meet as well as what they wrote.",
        "An owner-enabled gate, default-Ask decision mode, an environment-only "
        "credential (`RAIKER_GCAL_TOKEN`), and `www.googleapis.com` on the "
        "connector egress allowlist. Reads only.",
    ),
    _row(
        "connector_slack_runtime",
        SIDE_EFFECT_EXTERNAL,
        "A workspace's channel history would be read with the owner's token, "
        "which discloses other people's messages and not only theirs.",
        "An owner-enabled gate, default-Ask decision mode, an environment-only "
        "credential (`RAIKER_SLACK_TOKEN`), and `slack.com` on the connector "
        "egress allowlist. Reads only.",
    ),
    _row(
        "external_channel_runtime",
        SIDE_EFFECT_EXTERNAL,
        "Raiker would send a message to a paired destination in the owner's "
        "name, and a message that has been delivered cannot be recalled by "
        "revoking the channel afterwards.",
        "An owner-enabled gate, a paired channel whose destination is recorded "
        "rather than taken from the request, and a bounded metadata-only body.",
    ),
    _row(
        "channel_approval_relay",
        SIDE_EFFECT_EXTERNAL,
        "An approval decision could be taken over a channel, so whoever holds "
        "the channel holds the owner's authority to say yes.",
        "No approval is ever relayed to a channel, because an inbound message "
        "never becomes work, so the gate has nothing to refuse yet. A future "
        "relay meets a paired channel and the controls binding a decision to the "
        "request it answers.",
    ),
    _row(
        "mcp_connector_runtime",
        SIDE_EFFECT_EXTERNAL,
        "A tool on a server outside Raiker would be called with arguments a turn "
        "chose, and its answer would come back into the conversation as though "
        "Raiker had produced it.",
        "An owner-enabled gate, an owner-configured server whose interpreter is "
        "allowlisted and whose arguments are workspace-relative, a constructed "
        "environment rather than Raiker's own, and a result marked untrusted.",
    ),
    _row(
        "remote_execution_cap",
        SIDE_EFFECT_EXTERNAL,
        "Commands would run on another machine the owner has access to, so the "
        "blast radius stops being this workspace and becomes that host.",
        "An owner-enabled gate, an owner-configured remote target with a "
        "verified host key, and an approval. A failed remote adapter never "
        "silently falls back to running on this host.",
    ),
    _row(
        "cloud_execution_cap",
        SIDE_EFFECT_EXTERNAL,
        "Work would run in a cloud runtime under the owner's account, spending "
        "their money and leaving their data wherever that runtime keeps it.",
        "An owner-enabled gate, an owner-configured cloud target, and an "
        "approval. As with the remote target, there is no silent host fallback.",
    ),
    _row(
        "plugin_sandbox_image_pull_cap",
        SIDE_EFFECT_EXTERNAL,
        "A container image would be pulled from a registry, which is both an "
        "egress and the moment third-party code arrives on the machine.",
        "Nothing pulls a sandbox image, because nothing runs a sandboxed plugin "
        "yet. A pull would need an owner-enabled gate and a pinned, allowlisted "
        "image reference, and pulling one still does not run it.",
    ),
    # ── Destructive: the owner cannot get it back from inside Raiker ───────
    _row(
        "shell_execution",
        SIDE_EFFECT_DESTRUCTIVE,
        "An arbitrary command would run with the owner's own operating-system "
        "privileges, which is every other capability on this page at once and "
        "several that are not on it.",
        "An owner-enabled gate, the native sandbox's operating-system boundary, "
        "the command policy, and an approval carrying the exact argument vector. "
        "Containment pauses the tool after repeated failures.",
    ),
    _row(
        "process_execution",
        SIDE_EFFECT_DESTRUCTIVE,
        "A process would be started outside the turn that asked for it, so "
        "something keeps running after the conversation that produced it has "
        "been closed.",
        "No tool names it and no approval relays it, so it is an unused path "
        "rather than a weaker one: it enters the same `CommandService` "
        "lifecycle, sandbox boundary and approval `shell_execution` does.",
    ),
    _row(
        "memory_forget_execution",
        SIDE_EFFECT_DESTRUCTIVE,
        "An approved fact would be removed, and a memory Raiker has forgotten is "
        "one the owner cannot ask it to remember again from the record.",
        "An owner-enabled gate and, in Ask mode, an approval naming the record. "
        "A tombstone is written so the forgotten fact stays suppressed rather "
        "than being re-learned.",
    ),
    _row(
        "checkpoint_restore_execution",
        SIDE_EFFECT_DESTRUCTIVE,
        "The working tree would be replaced by an older snapshot, so every edit "
        "made since — the owner's own included — disappears from the files they "
        "are looking at.",
        "An owner-enabled gate and a live human confirmation: restore is floored "
        "to the critical path, so no decision mode, standing grant or subagent "
        "can resolve it. A pre-image is written first, so the restore is itself "
        "reversible.",
    ),
    # ── Critical: it changes what Raiker may do next ───────────────────────
    _row(
        "approval_execution_relay",
        SIDE_EFFECT_CRITICAL,
        "An approval would be turned into a real mutation without the owner's "
        "off switch applying, which makes every other approval in the product a "
        "decision about nothing.",
        "Its own gate, named in the router precisely so the owner's switch "
        "reaches the one executor that converts a decision into an effect, plus "
        "the self-approval refusal.",
    ),
    _row(
        "subagents",
        SIDE_EFFECT_CRITICAL,
        "A turn could spawn work that acts on its own reading of the "
        "conversation, and the owner would be reviewing a summary of what "
        "happened instead of a proposal of what should.",
        "An owner-enabled gate deciding whether delegation happens at all. Each "
        "subagent step is re-brokered individually against the read-only "
        "delegable set, so delegation never widens what may be touched.",
    ),
    _row(
        "multi_agent_teams",
        SIDE_EFFECT_CRITICAL,
        "Several delegated workers would act at once, multiplying one decision "
        "into an unbounded number of them.",
        "The `subagents` gate each member runs under, with every step brokered "
        "individually exactly as a single delegation is. No surface offers a "
        "team yet, so nothing constructs one.",
    ),
    _row(
        "scheduled_routines",
        SIDE_EFFECT_CRITICAL,
        "Work would start when nobody is watching, which is the one case where "
        "an approval the owner never sees is the same as no approval at all.",
        "Each run is one whole governed turn through the Agent Gateway, so every "
        "action inside it answers to that action's own gate and decision mode "
        "rather than to a second switch here. Pausing the host stops new work.",
    ),
    _row(
        "plugin_install",
        SIDE_EFFECT_CRITICAL,
        "Third-party contributions would be installed, and an install is the "
        "moment the owner's trust boundary moves to include somebody else's "
        "manifest.",
        "An owner-enabled gate, a validated signed manifest, a scope preview "
        "the owner sees before the install, and an approval. Imported policy is "
        "never automatically trusted.",
    ),
    _row(
        "plugin_execution_cap",
        SIDE_EFFECT_CRITICAL,
        "A plugin would invoke tools on the owner's behalf, so a manifest they "
        "read once decides what runs from then on.",
        "Each brokered call runs through the ordinary tool broker against the "
        "plugin's validated read-only set, so it answers to the gate of the tool "
        "it names rather than to one of its own. No plugin code runs in-process.",
    ),
    _row(
        "plugin_runtime_cap",
        SIDE_EFFECT_CRITICAL,
        "An installed plugin's own entrypoint would execute, which is "
        "third-party code running as the owner on the owner's machine.",
        "No owner surface runs an installed plugin's entrypoint, so the executor "
        "exists and nothing invokes it. Reaching it would need an owner-enabled "
        "gate, an allowlisted install and a bounded subprocess.",
    ),
    _row(
        "plugin_sandboxed_runtime_cap",
        SIDE_EFFECT_CRITICAL,
        "Third-party code would execute in a container, and a sandbox the owner "
        "did not choose is a boundary they cannot have reasoned about.",
        "No owner surface runs a sandboxed plugin, so nothing invokes this. "
        "Reaching it would need an owner-enabled gate and the network-isolated "
        "container with no host mounts that the executor builds.",
    ),
)

CAPABILITY_AUTHORITY: dict[str, CapabilityAuthority] = {
    row.capability: row for row in _AUTHORITY
}
if len(CAPABILITY_AUTHORITY) != len(_AUTHORITY):  # pragma: no cover - construction guard
    raise ValueError("capability_authority_duplicate")


def authority_for(capability: str) -> CapabilityAuthority | None:
    """The authority record for *capability*, or ``None`` if it has none."""
    return CAPABILITY_AUTHORITY.get(capability)


def side_effect_class(capability: str) -> str:
    """The side-effect class to show an owner, or ``""`` when unclassified.

    A capability with no real executor has nothing to classify: it cannot run,
    so there is no cost to state. Returning ``""`` rather than a fail-safe
    ``"critical"`` keeps the column honest — an empty cell says *not applicable*,
    and a filled one is always a claim somebody wrote.
    """
    row = CAPABILITY_AUTHORITY.get(capability)
    return row.side_effect if row is not None else ""


def ungoverned_consequence(capability: str) -> str:
    """What it would cost if it ran without governance (``""`` if none)."""
    row = CAPABILITY_AUTHORITY.get(capability)
    return row.ungoverned if row is not None else ""


def authority_requirement(capability: str) -> str:
    """What has to be true before it may run (``""`` if none)."""
    row = CAPABILITY_AUTHORITY.get(capability)
    return row.authority if row is not None else ""
