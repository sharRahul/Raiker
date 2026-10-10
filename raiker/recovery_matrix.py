"""How each subsystem recovers, said once and held to the code (DEC-24 step 3).

DEC-24 step 3 asks for a recovery matrix per subsystem: its source of truth,
how work is claimed, how a restart is reconciled, what is done about an effect
whose outcome is unknown, what is cleaned up, and what is left to the owner.
Without one, "what happens if Raiker stops in the middle of this?" had a
different answer in every module and none in one place — and writing this down
found that a scheduled run the host stopped in the middle of stayed ``running``
for ever (``TaskScheduler.settle_interrupted_runs``).

Each row names its ``anchors``: the functions that do what the row says.
``tests/test_recovery_matrix.py`` resolves every anchor, so a row cannot keep
describing a function that was renamed or removed. A clean-shutdown marker is
not part of any row: it would aid diagnosis, but it is not evidence that an
effect settled.

This is read by Observability's diagnostics and holds no owner content.
"""

from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import TypedDict


class RecoveryRowView(TypedDict):
    subsystem: str
    label: str
    source_of_truth: str
    claim: str
    after_restart: str
    uncertain_effects: str
    cleanup: str
    owner_action: str
    anchors: list[str]


class RecoveryMatrixView(TypedDict):
    rows: list[RecoveryRowView]


@dataclass(frozen=True)
class RecoveryRow:
    subsystem: str
    label: str
    source_of_truth: str
    claim: str
    after_restart: str
    uncertain_effects: str
    cleanup: str
    owner_action: str
    #: ``module:qualname`` of the code that does what the row says.
    anchors: tuple[str, ...]

    def to_view(self) -> RecoveryRowView:
        return {
            "subsystem": self.subsystem,
            "label": self.label,
            "source_of_truth": self.source_of_truth,
            "claim": self.claim,
            "after_restart": self.after_restart,
            "uncertain_effects": self.uncertain_effects,
            "cleanup": self.cleanup,
            "owner_action": self.owner_action,
            "anchors": list(self.anchors),
        }


RECOVERY_MATRIX: tuple[RecoveryRow, ...] = (
    RecoveryRow(
        subsystem="scheduled_tasks",
        label="Tasks and routines",
        source_of_truth="The task's row in the encrypted database, and its run history.",
        claim="A due task moves from queued to running in one conditional update, so two passes cannot both take it.",
        after_restart=(
            "A run the host stopped in the middle of is settled at start as one that did not "
            "complete; a routine moves to its next slot."
        ),
        uncertain_effects="Never run again on its own: what it did before stopping is not known.",
        cleanup="Three failed cycles in a row pause a routine and tell you.",
        owner_action="Read its conversation, then Run now or Continue.",
        anchors=(
            "raiker.storage.sqlite:SQLiteStore.claim_due_tasks",
            "raiker.tasks.scheduler:TaskScheduler.settle_interrupted_runs",
            "raiker.tasks.scheduler:TaskScheduler._rearm",
        ),
    ),
    RecoveryRow(
        subsystem="approval_continuations",
        label="Work waiting on an approval",
        source_of_truth="The parked turn, kept in the database while it waits.",
        claim="An approved turn is claimed once (suspended to resuming) before it continues.",
        after_restart="The host's next pass continues every approved turn nobody has claimed.",
        uncertain_effects="A turn already claimed elsewhere is not continued twice.",
        cleanup="Nothing is discarded on its own: a parked turn waits for your decision.",
        owner_action="Approve or refuse it where it is listed.",
        anchors=(
            "raiker.storage.sqlite:SQLiteStore.claim_suspended_turn",
            "raiker.storage.sqlite:SQLiteStore.list_resumable_suspended_turns",
        ),
    ),
    RecoveryRow(
        subsystem="background_commands",
        label="Commands running in the background",
        source_of_truth="The command run's record and its supervisor's lease.",
        claim="A run holds a lease its supervisor renews.",
        after_restart="A run whose supervisor still answers is taken back over before anything is declared lost.",
        uncertain_effects="A lost run gets a receipt saying it was lost — never a silent success, never a re-run.",
        cleanup="A lapsed lease is reclaimed and the run's sandbox grant taken back.",
        owner_action="Read its output and run it again if you want to.",
        anchors=(
            "raiker.execution.commands.service:CommandService.recover_owner",
            "raiker.execution.commands.service:CommandService.reconcile_leases",
        ),
    ),
    RecoveryRow(
        subsystem="model_operations",
        label="Model downloads and conversions",
        source_of_truth="The operation's row.",
        claim="One in-process worker drives each operation.",
        after_restart="An operation left running is marked failed as host_restarted before the first request.",
        uncertain_effects="Partial files are kept and listed, not trusted as complete.",
        cleanup="Partial files can be deleted from the operation.",
        owner_action="Retry, or delete the partial files.",
        anchors=("raiker.models.local_operations:ModelOperationService.recover_abandoned",),
    ),
    RecoveryRow(
        subsystem="channel_messages",
        label="Messaging channels",
        source_of_truth="Each message's receipt and audit event, written before any route runs.",
        claim="A message is handled inside the request that delivered it.",
        after_restart="A message whose request did not finish was not acknowledged, so the sender may send it again.",
        uncertain_effects=(
            "A resend is a new message; an echo of Raiker's own reply or a third repeat is refused "
            "before routing. A failed notice is recorded as Delivery failed, not re-sent."
        ),
        cleanup="Pause keeps receiving and recording, and starts and sends nothing.",
        owner_action="Pause or turn off the channel; read its receipts.",
        anchors=(
            "raiker.api.routes_channels:_loop_reason",
            "raiker.control.service:RuntimeControlService.set_channel_paused",
            "raiker.storage.sqlite:SQLiteStore.record_task_delivery",
        ),
    ),
    RecoveryRow(
        subsystem="notifications",
        label="Notices",
        source_of_truth="The notice's row, written whether or not it is shown.",
        claim="The same unread notice within the window is counted, not raised again.",
        after_restart="Every notice is still in the list; quiet hours' held notices end in one summary.",
        uncertain_effects="A notice is never marked delivered when delivery failed.",
        cleanup="Read notices stay as history.",
        owner_action="Open the bell.",
        anchors=(
            "raiker.storage.sqlite:SQLiteStore.insert_notification",
            "raiker.storage.sqlite:SQLiteStore.acknowledge_held_notifications",
        ),
    ),
    RecoveryRow(
        subsystem="search_indexes",
        label="Search and memory indexes",
        source_of_truth="The rows they are built from; the indexes are derived and can be rebuilt.",
        claim="The host checks every index on its own tick.",
        after_restart="A damaged index is named on the attention list and rebuilt from its source rows.",
        uncertain_effects="A damaged vector is removable; its memory reads as not yet indexed.",
        cleanup="Rebuilding replaces the damaged index.",
        owner_action="Rebuild from the attention list.",
        anchors=(
            "raiker.storage.sqlite:SQLiteStore.check_search_indexes",
            "raiker.storage.sqlite:SQLiteStore.reconcile_memory_projections",
        ),
    ),
    RecoveryRow(
        subsystem="database",
        label="The encrypted database",
        source_of_truth="The database file and this workspace's key.",
        claim="An older build refuses a database a newer one shaped, before writing anything.",
        after_restart=(
            "A database that will not open is never replaced by an empty one; the lock screen "
            "offers its verified backups."
        ),
        uncertain_effects="Restoring moves the unopenable copy to quarantine — nothing is deleted.",
        cleanup="Deletions made after a backup are replayed into any restore of it.",
        owner_action="Restore a verified backup, or keep the quarantined copy for diagnosis.",
        anchors=(
            "raiker.storage.backup:restore_in_place",
            "raiker.storage.backup:verify_backup",
            "raiker.storage.deletion_journal:read_deletions",
        ),
    ),
    RecoveryRow(
        subsystem="updates",
        label="Updates",
        source_of_truth="The installed tree and the recovery points kept beside it.",
        claim="An update is applied by a helper after the host stops, never by the running host.",
        after_restart="A failed swap puts the previous tree back; the database is backed up before it migrates.",
        uncertain_effects="A recovery point that cannot open this workspace's data says so.",
        cleanup="The previous tree is removed only once the new one is in place.",
        owner_action="Roll back to a recovery point that opens this data, or restore the pre-update backup.",
        anchors=(
            "raiker.app.update:roll_back",
            "raiker.app.update:recovery_points",
        ),
    ),
    RecoveryRow(
        subsystem="mcp_servers",
        label="MCP servers",
        source_of_truth="The server's profile and the tools you accepted, by declaration.",
        claim="Each call is checked against the accepted declarations.",
        after_restart="A paused or contained server stays so; Resume tests it again before trusting it.",
        uncertain_effects="A tool the server changed is held until you accept it as it reads now.",
        cleanup="Kill refuses every session for the server until you resume it.",
        owner_action="Resume, or accept the held tools.",
        anchors=("raiker.control.service:RuntimeControlService.resume_mcp_server",),
    ),
)


def recovery_matrix_view() -> list[RecoveryRowView]:
    return [row.to_view() for row in RECOVERY_MATRIX]
