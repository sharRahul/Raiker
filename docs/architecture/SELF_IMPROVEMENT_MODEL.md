# Self-Improvement Model

Status: specification (no runtime self-improvement is enabled in code today). This doc makes
self-improvement a first-class Raiker capability instead of a sub-section of
`docs/architecture/EIDETIC_MEMORY_AND_LEARNING_SPEC.md`. It defines what Raiker may learn, how learning is
proposed, reviewed, stored, and verified, and the safety boundaries that keep self-improvement
from becoming self-granted agency.

Reference inspiration: `obra/Superpowers` (composable, reusable skills that an agent accrues and
invokes), Hermes-Agent (closed learning loop / user modelling), and Claude Code skills
(`SKILL.md` units that load on demand). Raiker's source of truth remains this repository.

---

## 1. Principle

Raiker improves by turning **verified experience** into **reusable, governed artifacts** —
never by silently changing its own policy, permissions, or behaviour. Every learned artifact is:

1. derived from a real, completed, verified trajectory;
2. created first as a **candidate** (never auto-active);
3. reviewed (user or managed policy) before it becomes active;
4. stored with provenance, confidence, and a sensitivity label;
5. revocable, correctable, and forgettable;
6. unable to override policy, approvals, or trust boundaries.

This mirrors the memory-candidate model already implemented for memory
(`raiker/memory/`, `docs/architecture/MEMORY_GOVERNANCE_RULES.md`).

---

## 2. What Raiker may learn

| Artifact | Description | Becomes | First active phase |
|---|---|---|---|
| **Skill** | A named, reusable procedure distilled from a successful task trajectory (steps, tool sequence, checks). | A `/skill-name` invocable unit (see `docs/architecture/EXTENSIBILITY_MODEL.md`). | Phase 3+ |
| **Procedure note** | A shorter "how we do X here" entry tied to a project. | Procedural memory record. | Phase 2+ |
| **User model fact** | A confirmed preference/convention ("uses pytest", "prefers small PRs"). | Profile memory record. | Phase 2+ |
| **Gist** | Compressed recall of an episode for cheaper future context. | Episodic/gist memory. | Phase 2+ |
| **Heuristic** | A scored rule of thumb ("tests in `tests/` mirror `raiker/`"). | Project memory with confidence. | Phase 3+ |
| **Failure pattern** | An approach that failed in a recognisable context, plus the verified resolution if one exists (Section 8). | Advisory project memory with confidence. | Phase 2+ |

Self-improvement does **not** include: editing policy, expanding tool permissions, enabling
disabled runtime capabilities, or rewriting its own system prompt.

---

## 3. The closed loop

```
observe (eidetic raw observation, verified)
   -> distill (propose skill/heuristic/user-fact/failure-pattern CANDIDATE)
   -> evaluate (fresh fixtures + regression replay, Section 6)
   -> review (user or managed policy gate; preview shows the evaluation)
   -> store (provenance + confidence + sensitivity, candidate -> active version)
   -> use (loaded on demand, like a skill)
   -> measure (verified outcomes update confidence and metrics, Section 9)
   -> quarantine / restore (on regression or safety trigger, Section 7)
   -> correct / forget (decay, contradiction, or explicit deletion)
```

Each transition emits an event (Section 10) and is rollback-able.

---

## 4. Skill distillation contract

A skill candidate is proposed only when a trajectory is **completed and verified**. The
deterministic verifier (`raiker/verification/verifier.py`, re-exported from
`raiker/runtime/verifier.py`) checks tool-call schema, that denied or approval-required actions
did not execute, and result shape. It is explicitly not a semantic-correctness proof, so it is
necessary but not sufficient: skill distillation cannot be enabled until an independent
outcome validator (PA-D01 final outcome assessment, PA-D11 validators) confirms the task's
result. A model's own statement that it succeeded never counts as verification.

```json
{
  "schema_version": "1.0",
  "skill_candidate_id": "skc_01H...",
  "name": "add-pytest-for-module",
  "summary": "Create a mirrored test file and a failing-then-passing test for a Python module.",
  "source_trajectory_id": "turn_01H...",
  "steps": ["locate module", "create tests/<mirror>", "write failing test", "implement", "run pytest"],
  "tools_used": ["read_file", "glob", "write_file", "shell:pytest"],
  "preconditions": ["python project", "pytest available"],
  "confidence": 0.0,
  "provenance": {"derived_from": "verified_trajectory", "actor": "agent_runtime"},
  "sensitivity": "normal",
  "status": "candidate",
  "active": false
}
```

Activation requires an approval preview (reuse `raiker/approval_previews.py` patterns) and may
not auto-enable.

---

## 5. Safety boundaries

- **No self-granted permission.** A learned skill runs through the same tool broker + policy
  path as everything else; it cannot widen its own scope.
- **No policy authorship.** Learned artifacts cannot create/modify policy rules.
- **Provenance required.** Anything learned from channel/web content is isolated and lower-trust
  (poisoning defence, see `docs/architecture/OWASP_GENAI_SECURITY_MAPPING.md`).
- **Confidence + decay.** New artifacts start at low confidence; repeated success raises it,
  contradiction or failure lowers it; stale artifacts decay.
- **Forgetting.** Users can correct or delete any learned artifact; eidetic raw observations are
  retention-bounded.
- **Owner-controlled disablement.** The owner can disable skill learning or
  self-improvement through their governed policy; an agent or plugin cannot
  turn it back on or grant itself a higher role.

---

## 6. Regression replay

Before a candidate becomes active — as a new skill or as a new version replacing an active
one — it is evaluated against two sets on the same execution profile:

1. **Fresh fixtures** (PAA-09): declared inputs with independent validators, unseen during
   distillation.
2. **Replay set**: historical verified tasks that used the current active version (or, for a
   new skill, tasks matching its preconditions that ran without it), found through the
   `skill_trace` retrieval mode of `EIDETIC_MEMORY_AND_LEARNING_SPEC.md`.

**Replay eligibility.** A historical task is replayed only when every recorded tool call was
read-only or confined to a disposable workspace (Build sandbox or governed container).
Tasks with outside effects — sends, publishes, connector writes, purchases, anything with a
provider receipt — are never replayed; they are represented by fixtures with stubbed effects or
left out. Replay runs through the normal broker and policy path under the original task's
execution profile or a stricter one, never a broader one. An approval the original task
needed is recorded as "would require approval" and is not granted.

**Comparison.** Baseline (the current active version, or no skill) and candidate run the same
items with the same profile and model, each repeated *k* times (initial default 3) to account
for model variance. Results are recorded per item and per repeat.

**Hard gates** — any failure blocks the candidate:

- no replay or fixture item that the baseline passed in a majority of repeats is failed by the
  candidate in a majority of repeats;
- no new denied or approval-required tool attempts;
- the tool/permission diff is empty or explicitly owner-reviewed;
- no verifier safety check fails.

**Improvement criteria.** The candidate's verified success rate is at least the baseline's,
and it beats the baseline by a declared margin on at least one Section 9 cost metric (tool
calls, tokens, time) or on known-failure recurrence. A candidate that passes the hard gates
but not the improvement criteria is marked `not_better`, kept for reference and not offered
for review.

**Thin evidence.** When fewer than *m* replay items exist (initial default 5), the
evaluation is labelled *fixture-only evidence* in the review preview rather than presented as
a regression result.

The evaluation is stored as a record linked to the candidate: item ids, per-repeat outcomes,
profile, model and metrics. Passing it does **not** activate the candidate; owner approval is
still required (Section 4).

---

## 7. Quarantine and restore

**Versions.** Each skill keeps immutable version rows and one active pointer. Promotion moves
the pointer and keeps the previously active version; promotion never deletes a version.

**Watch period.** For the first *w* uses (initial default 10) or *d* days after promotion,
whichever ends later, live verified outcomes are compared with the version's replay baseline.

**Triggers.** A version is quarantined when either:

- its verified-failure rate in the watch period exceeds the baseline by the declared
  threshold; or
- any safety trigger fires while it is loaded: a denied or approval-bypass tool attempt, a
  call outside its reviewed permission diff, a poisoning flag on its provenance, or an owner
  report.

**Effect.** The version moves to `quarantined` and is no longer loaded into turns. The active
pointer returns to the previous version if that version is still owner-approved and not
revoked; otherwise the skill is deactivated. The change applies from the next turn boundary;
an in-flight step is not rewritten mid-call.

Restore is automatic because it only returns the skill to a state the owner already approved
or to no skill at all. It never activates anything new, so it does not conflict with "never
auto-active" (Section 1). Releasing a quarantined version needs a fresh owner approval.

**Evidence.** The triggering task ids, outcomes, metrics, and the diff between the
quarantined and restored versions are kept and shown to the owner in Approvals/Activity.
Quarantine affects only that skill; it does not touch memory or other skills.

---

## 8. Failure recall

A **failure pattern** records an approach that failed in a recognisable context so a later
task does not repeat it.

**Source.** A pattern is proposed from a verifier-failed or owner-corrected outcome, or from a
tool error that recurs at least twice with the same signature. When a later verified
trajectory in the same context succeeds, its approach is attached as the resolution.

**Content.** A context signature (tool, normalised error class, project, relevant
environment such as tool or dependency version), a short redacted summary of the failed
approach and, if known, the resolution. Raw tool output is never stored, following the
eidetic capture rule "never the material". Error text from outside, connector or MCP sources
keeps its provenance trust level and is treated as data, never as instructions.

**Lifecycle.** A failure pattern is a candidate and is reviewed like a procedure note
(Section 1). The owner may approve several at once.

**Use.** A matching pattern is retrieved as advisory context ("previously failed: …; resolved
by: …") with its provenance. It never blocks a tool call, changes policy or alters approvals.
The agent may retry the approach when the context has changed; a retry that fails again
counts toward known-failure recurrence (Section 9).

**Invalidation.** Confidence falls, and the pattern is eventually retired, when the context
signature changes (for example a tool or dependency upgrade) or when a verified success uses
the approach that previously failed.

---

## 9. Improvement metrics

Measured per skill version and per evaluation, and rolled up for the Learning views in the
existing Memory, Skills and Observability surfaces:

| Metric | Definition |
|---|---|
| Verified success rate | Share of tasks whose outcome passed the verifier and outcome validator. Model self-report is excluded. |
| Tool calls per task | Governed tool calls through the broker. |
| Tokens per task | Input and output tokens across the task's model calls. |
| Time and cost per task | Wall time and provider cost under the task's profile. |
| Known-failure recurrence | Tasks that repeated an approach matching an active failure pattern and failed again. |
| Regression rate | Share of promoted versions later quarantined (Section 7). |
| Safety events | Denied or approval-required attempts and permission-diff violations. Must be zero to promote. |
| Owner corrections | Corrections or invalidations of learned artifacts attributed to the version. |

**Measurement rules.** Compare only runs on the same fixtures and profile; report the median
and spread across repeats; label small samples; never compare across a profile or model
change without a fresh baseline. A claim that Raiker improves over time, or matches another
agent, is made only through PA-D11 and the Testing protocol, not from these dashboards alone.

---

## 10. Events (reserved; not yet emitted)

- `skill_candidate_proposed`
- `skill_candidate_reviewed`
- `skill_evaluation_completed`
- `skill_activated`
- `skill_used`
- `skill_confidence_updated`
- `skill_quarantined`
- `skill_version_restored`
- `skill_deactivated`
- `failure_pattern_proposed`
- `failure_pattern_recalled`
- `learned_artifact_forgotten`
- `self_improvement_policy_decision`

---

## 11. Tests required before enabling

- A verified trajectory produces exactly one skill candidate; an unverified one produces none.
- A task the model reports as successful but the outcome validator fails produces no candidate.
- A skill candidate is inactive until approved.
- An activated skill executes only through the tool broker/policy path.
- A skill learned from untrusted content is quarantined and cannot self-activate.
- Confidence rises on success and falls on failure; stale artifacts decay.
- Deletion/forgetting removes the artifact and its activation.
- Managed policy can globally disable self-improvement.
- A historical task with outside effects is never replayed; replay cannot run on a broader
  profile than the original task.
- A candidate that fails a baseline-passing replay item is not offered for review.
- A candidate that passes evaluation stays inactive until approved.
- A safety trigger quarantines the version and restores the previous approved version; a
  revoked previous version is not restored; evidence is retained.
- A failure pattern learned in one session is recalled in a fresh session, does not block a
  tool call or change policy, and is retired after its context signature changes.
- Metrics are computed from verifier and validator outcomes; model self-report is ignored.

---

## 12. Current code status

**specified_not_implemented.** There is no self-improvement runtime today. The prerequisites
are:

- an independent outcome validator on top of the deterministic verifier (Section 4);
- memory writes enabled under governance (`raiker/memory/readiness.py`);
- skill versions with an active pointer and retained previous version — `SkillsService`
  (`raiker/skills/service.py`) has install, activate and delete but no versions;
- persisted skill candidates fed from verified trajectories — the `skill_candidates` table
  exists, but `SkillCandidateStore` (`raiker/skills/__init__.py`) is in-memory and builds
  candidates from project-graph patterns only;
- the skills/extensibility surface (`docs/architecture/EXTENSIBILITY_MODEL.md`).

Until those exist, this doc is the contract to build against.

## Personal-agent workflow learning

PAA-09 in the [delivery plan](../plans/PERSONAL_AUTONOMOUS_AGENT_SPEC.md)
adopts reusable procedural learning inspired by Hermes and Claude skills. It
begins with an independently verified outcome, proposes a versioned
instruction-only skill, measures it on fresh fixtures and regression replay
(Section 6), and requires owner review/activation of its dependencies and
permission diff. Quarantine and restore (Section 7), failure recall (Section 8)
and the improvement metrics (Section 9) are part of its contract. ADD-05/06/21
retain their own work; this target enables no runtime self-improvement, code
installation or self-granted permission.
