"""What "low", "medium", "high" and "critical" actually mean.

Raiker validated risk bands against a four-name set and never said what any of
them meant. Every band was therefore whatever the literal at each call site
decided: `PolicyEngine` asserted `"high"` for anything that parked, the broker
asserted `"high"` in two more places, and a tool's own declared band — the one
field that looked authoritative — was read by nobody making a decision.

Three things go wrong when a vocabulary has no definitions. A new tool's band is
guessed, because there is nothing to check it against. Two call sites drift,
because neither is wrong about a rule that was never written. And the owner is
shown a word — "high risk" — that carries no promise, which is the worst of the
three: an approval queue works because its entries mean something, and a queue
where "high" means "this parks" rather than "this is dangerous" teaches people to
click through it.

## The bands are not a property of the tool

That is the mistake this module exists to avoid. `write_file` is not dangerous;
writing a file inside the workspace that a checkpoint captured is ordinary, and
writing one that no checkpoint can restore is not. The band belongs to the
**action in its context**, and it is derived from named, checkable properties of
that action — the signals below — rather than looked up by tool name.

A tool still *declares* a band in `raiker.models.tool_registry`. That declaration
is the floor: the band an action gets when no signal raises it. Signals can only
raise it, never lower it, so a tool that declares `high` cannot be talked down to
`low` by a context that happens to look safe.

## Built in, and not hard-coded

Everything here is data: the bands, their definitions, the signals, and which
band each signal floors an action at. `describe_risk_model()` renders the whole
thing, which is what the Settings surface shows and what a reviewer reads. The
owner can raise a tool's floor through their own settings and can never lower one
— the same rule hooks follow, for the same reason: a control that can only make
an action stricter cannot be turned into a way around governance.

## Where this came from

Both reference implementations were read rather than remembered, and they
disagree in a way that turned out to be useful.

**Claude Code** treats risk as a property of the action and checks it against
published rule lists — what the auto-mode classifier blocks and allows by
default, plus two path classes (*protected* paths that no mode auto-writes, and
*critical* paths that no allow rule and no hook may approve for removal). The
lists are data: `claude auto-mode defaults` prints them as JSON. The signals
below are the same idea, reduced to the questions that actually separate the
bands rather than to a list of cases.

**Codex** splits it differently and more sharply: a *sandbox mode*
(`read-only`, `workspace-write`, `danger-full-access`) sets the boundary, and an
*approval policy* (`untrusted`, `on-request`, `never`) says what happens when an
action needs to leave it. Risk, in that model, is not a property of the tool at
all — it is the single question *does this have to cross the boundary?*

Raiker takes Codex's question and can answer it better, because
`crosses_sandbox_boundary` is measured here rather than assumed: the OS boundary
is real and probed. It takes Claude Code's insistence that the rules are
published data an owner can read. And it keeps one thing neither has: a band is
recorded with the signals that produced it, so an assessment can be recomputed
from the audit trail months later instead of being trusted.

One control from Claude Code is deliberately **not** built here and is worth
naming so its absence is a decision rather than an oversight: a boundary the
owner states in conversation ("don't push until I've reviewed it") is treated by
the reference classifier as a block signal that stays in force until lifted.
Raiker has nowhere to put that today — it would need a stored, owner-visible
constraint rather than a model's recollection of a sentence — and a control that
depends on the model remembering is not a control.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

#: The terminal record of a refusal. It is not a band an action is assessed
#: into — nothing is "blocked risk" — it is what a decision writes down when the
#: action will not happen at all. Ranked above `critical` so an ordering
#: comparison never treats a refusal as milder than the worst band.
BLOCKED = "blocked"


@dataclass(frozen=True)
class RiskBand:
    """One band, and the promise it makes to the owner."""

    #: The name stored on an action and shown to the owner.
    name: str
    #: Ordering. Comparisons use this rather than the string, so adding a band
    #: does not mean finding every place two names were compared by hand.
    rank: int
    #: One line, in the owner's language, for the surfaces that list bands.
    summary: str
    #: What puts an action in this band. This is the definition a new tool's
    #: declaration is checked against, so it has to be decidable by reading it.
    definition: str
    #: What reverses an action in this band, or the honest statement that
    #: nothing does. This is the field that most often decides the band.
    undo: str
    #: What the runtime does with an action in this band before the owner's
    #: approval mode is consulted. A mode may make this stricter; nothing makes
    #: it looser.
    disposition: str
    #: Concrete actions, so the definition can be checked against cases rather
    #: than agreed with in the abstract.
    examples: tuple[str, ...]


#: The four bands, defined once.
#:
#: The order of the questions is the order they are asked in: an action that is
#: reversible, local, private and bounded is low, and each property it fails
#: raises it. Authority is last because it is the one that jumps straight to
#: critical regardless of everything above it.
RISK_BANDS: tuple[RiskBand, ...] = (
    RiskBand(
        name="low",
        rank=0,
        summary="Reads and reasoning. Nothing to undo, because nothing changed.",
        definition=(
            "The action changes no state the owner can observe afterwards, reaches nothing "
            "off this machine, and is bounded to what the turn named. Running it twice is "
            "the same as running it once."
        ),
        undo="Nothing to undo.",
        disposition="Runs. It is not offered to the owner as a decision, because there is no decision in it.",
        examples=(
            "Reading a file inside the workspace",
            "Searching the transcript or the code map",
            "Recording this conversation's plan",
        ),
    ),
    RiskBand(
        name="medium",
        rank=1,
        summary="Local changes a checkpoint can put back.",
        definition=(
            "The action changes state on this machine only, inside the workspace or the "
            "owner's own records, and a checkpoint written before it can restore what it "
            "replaced. Nobody outside this machine can observe that it happened."
        ),
        undo="A checkpoint restore returns the workspace to the state before it.",
        disposition="Runs under the owner's approval mode. `manual` parks it; `auto` may run it after the alignment check.",
        examples=(
            "Writing or editing a file inside the workspace",
            "Applying a patch the checkpoint captured",
            "Storing a memory the owner can later forget",
        ),
    ),
    RiskBand(
        name="high",
        rank=2,
        summary="Leaves the machine, or leaves a mark a checkpoint cannot lift.",
        definition=(
            "Any one of: the effect is visible to somebody other than the owner; the effect "
            "leaves this machine; or the change is not covered by a checkpoint, so undoing "
            "it means doing separate work rather than restoring. A single one of these is "
            "enough — they are not counted, they are checked."
        ),
        undo="Not by restoring. Undoing it is its own action, and may not be possible at all.",
        disposition="Parks for the owner's approval before anything runs.",
        examples=(
            "Pushing a branch, or opening a pull request",
            "Sending a message through a paired channel",
            "Running a shell command that reaches the network",
            "Spending against a provider credential",
        ),
    ),
    RiskBand(
        name="critical",
        rank=3,
        summary="Irreversible outside the workspace, or it changes who may act.",
        definition=(
            "The action destroys something no checkpoint holds and that exists outside the "
            "workspace, has a blast radius wider than what the turn named, or changes "
            "authority itself — who may act, what a capability permits, or the agent's own "
            "oversight. The last of these is critical however small the change looks."
        ),
        undo="Nothing in Raiker undoes it.",
        disposition=(
            "A live human decides, in person. `auto` never runs it, an approval rule never "
            "pre-approves it, and its resting state is denial."
        ),
        examples=(
            "Deleting a path outside the workspace, or a workspace parent",
            "Granting a role, or widening a capability gate",
            "Turning off the hooks that govern the agent, from inside a turn",
            "A command whose target the runtime cannot resolve, so its blast radius is unknown",
        ),
    ),
)

_BY_NAME: dict[str, RiskBand] = {band.name: band for band in RISK_BANDS}
#: Ranks including the terminal refusal record, so ordering is total.
_RANKS: dict[str, int] = {band.name: band.rank for band in RISK_BANDS} | {BLOCKED: 4}


@dataclass(frozen=True)
class RiskSignal:
    """One checkable property of an action, and the band it floors it at.

    A signal is not a heuristic about a tool name. It is a question with an
    answer the runtime can actually determine about *this* call — which is what
    makes an assessment reproducible months later from the audit record, and what
    keeps the model out of the authority path entirely.
    """

    #: Stable identifier, recorded in the decision's reasons.
    name: str
    #: The floor this signal imposes. The assessment takes the highest floor
    #: raised, so signals never argue with each other.
    band: str
    #: The question, in owner language, for the surface that explains a decision.
    question: str
    #: Why that answer means that band, tied back to a band's definition.
    why: str


#: The named properties that raise an action's band.
#:
#: Every one is derived from the action and the runtime's own knowledge. None is
#: derived from the model's description of what it is doing, because a signal the
#: model can phrase its way past is not a control.
RISK_SIGNALS: tuple[RiskSignal, ...] = (
    RiskSignal(
        name="changes_state",
        band="medium",
        question="Does anything on this machine differ afterwards?",
        why="A change the owner can observe afterwards is at least medium, because there is now something to undo.",
    ),
    RiskSignal(
        name="not_covered_by_checkpoint",
        band="high",
        question="Would a checkpoint restore put this back?",
        why=(
            "Medium's whole promise is that a restore undoes it. An action the checkpoint "
            "does not hold cannot make that promise, so it is high however local it looks."
        ),
    ),
    RiskSignal(
        name="leaves_this_machine",
        band="high",
        question="Does anything cross the network as a result?",
        why="Once bytes leave, no local control reaches them. That is high by definition, whatever they were.",
    ),
    RiskSignal(
        name="crosses_sandbox_boundary",
        band="high",
        question="Does it need to reach outside the boundary this turn is running in?",
        why=(
            "Codex's model, and the sharpest of the three: an action is risky exactly when it "
            "has to leave the boundary it was given. Raiker can ask this more honestly than "
            "the reference can, because its boundary is measured rather than asserted — so "
            "'outside the sandbox' is a fact here, not a policy guess."
        ),
    ),
    RiskSignal(
        name="observable_by_others",
        band="high",
        question="Can anybody but the owner see that this happened?",
        why=(
            "A push, a message, a comment: the effect is now somebody else's context. "
            "Withdrawing it is a new action and usually an incomplete one."
        ),
    ),
    RiskSignal(
        name="spends_owner_credential",
        band="high",
        question="Does it authenticate as the owner, or spend against their account?",
        why="Acting as the owner somewhere else is high because the record it leaves is theirs, not Raiker's.",
    ),
    RiskSignal(
        name="unbounded_target",
        band="critical",
        question="Can the runtime resolve exactly what this affects?",
        why=(
            "A target the runtime cannot resolve — a wildcard, an unassigned variable, a "
            "recursive delete rooted somewhere it cannot compute — has a blast radius nobody "
            "has measured. Unknown scope is treated as the widest scope, never the narrowest."
        ),
    ),
    RiskSignal(
        name="destroys_outside_workspace",
        band="critical",
        question="Does it remove something no checkpoint holds, outside the workspace?",
        why="There is no restore and no copy. This is the band's own definition.",
    ),
    RiskSignal(
        name="changes_authority",
        band="critical",
        question="Does it change who may act, or what a capability permits?",
        why=(
            "An action that widens authority is the one action whose blast radius is every "
            "action after it. Size is irrelevant: granting a role is critical."
        ),
    ),
    RiskSignal(
        name="changes_own_oversight",
        band="critical",
        question="Does it change the controls that govern the agent itself?",
        why=(
            "Turning off hooks, clearing an approval requirement, or editing the record of "
            "what happened is the agent editing its own supervision. It is critical even "
            "when the same edit made by hand would be routine, because the point of the "
            "control is that the agent is not the one who relaxes it."
        ),
    ),
)

_SIGNALS_BY_NAME: dict[str, RiskSignal] = {signal.name: signal for signal in RISK_SIGNALS}


class RiskModelError(ValueError):
    """A band or signal name that this build does not define."""


def band(name: str) -> RiskBand:
    """The definition behind a band name."""
    try:
        return _BY_NAME[name]
    except KeyError:
        raise RiskModelError(f"unknown_risk_band:{name}") from None


def rank(name: str) -> int:
    """Ordering for a band name, including the terminal refusal record."""
    try:
        return _RANKS[name]
    except KeyError:
        raise RiskModelError(f"unknown_risk_band:{name}") from None


def strictest(*names: str) -> str:
    """The highest band among *names*. The empty case is `low`, not an error.

    Assessment is a floor-raising operation, so "no signal raised anything" has
    to have an answer, and that answer is the mildest band rather than a
    failure — a tool that raises nothing is exactly what `low` describes.
    """
    chosen = "low"
    for name in names:
        if rank(name) > rank(chosen):
            chosen = name
    return chosen


@dataclass(frozen=True)
class RiskAssessment:
    """The band an action lands in, and every reason it landed there."""

    band: str
    #: Signal names that raised the floor, in registry order. Recorded in the
    #: decision's reasons so the assessment can be recomputed from the audit
    #: trail rather than taken on trust.
    signals: tuple[str, ...]
    #: The tool's own declared band, before any signal.
    declared: str
    #: The owner's floor for this tool, when they set one.
    owner_floor: str | None = None

    @property
    def reasons(self) -> list[str]:
        """Reason codes for the policy decision, in the order they applied."""
        codes = [f"risk_declared:{self.declared}"]
        codes.extend(f"risk_signal:{name}" for name in self.signals)
        if self.owner_floor is not None:
            codes.append(f"risk_owner_floor:{self.owner_floor}")
        codes.append(f"risk_band:{self.band}")
        return codes


def assess(
    *,
    declared: str,
    signals: Mapping[str, bool] | None = None,
    owner_floor: str | None = None,
) -> RiskAssessment:
    """Derive the band for one action.

    *declared* is the tool's registry band, which is the floor. *signals* answers
    the named questions for this call; only the true ones are considered, and an
    unknown name is an error rather than an ignored key, because a signal that
    is silently dropped is a control that silently stopped working.

    *owner_floor* may raise the result and can never lower it. That asymmetry is
    the whole reason it is safe to let an owner tune the model: the worst a
    setting can do is make Raiker ask more often.
    """
    raised: list[str] = []
    floors = [declared]
    for signal in RISK_SIGNALS:
        if signals is not None and signals.get(signal.name):
            raised.append(signal.name)
            floors.append(signal.band)
    if owner_floor is not None:
        floors.append(owner_floor)
    for name in signals or {}:
        if name not in _SIGNALS_BY_NAME:
            raise RiskModelError(f"unknown_risk_signal:{name}")
    return RiskAssessment(
        band=strictest(*floors),
        signals=tuple(raised),
        declared=declared,
        owner_floor=owner_floor,
    )


def describe_risk_model() -> dict[str, Any]:
    """The whole model as data, for the surface that shows it and the reviewer who checks it.

    This is the answer to "what does high mean" being a thing an owner can read
    rather than a thing they infer from which prompts they get.
    """
    return {
        "bands": [
            {
                "name": item.name,
                "rank": item.rank,
                "summary": item.summary,
                "definition": item.definition,
                "undo": item.undo,
                "disposition": item.disposition,
                "examples": list(item.examples),
            }
            for item in RISK_BANDS
        ],
        "signals": [
            {
                "name": item.name,
                "raises_to": item.band,
                "question": item.question,
                "why": item.why,
            }
            for item in RISK_SIGNALS
        ],
        "rules": [
            "A tool's declared band is the floor, never the answer.",
            "A signal can only raise an action's band. Nothing lowers it.",
            "The band is the highest floor raised, so signals never contradict each other.",
            "An owner setting may raise a tool's floor and can never lower one.",
            "Unknown scope is treated as the widest scope.",
        ],
    }


__all__ = [
    "BLOCKED",
    "RISK_BANDS",
    "RISK_SIGNALS",
    "RiskAssessment",
    "RiskBand",
    "RiskModelError",
    "RiskSignal",
    "assess",
    "band",
    "describe_risk_model",
    "rank",
    "strictest",
]
