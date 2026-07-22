# Self-Improvement Model

Status: specification (no runtime self-improvement is enabled in code today). This doc makes
self-improvement a first-class Raiker capability instead of a sub-section of
`docs/EIDETIC_MEMORY_AND_LEARNING_SPEC.md`. It defines what Raiker may learn, how learning is
proposed, reviewed, stored, and verified, and the safety boundaries that keep self-improvement
from becoming self-granted agency.

Reference inspiration: `obra/Superpowers` (composable, reusable skills that an agent accrues and
invokes), an external agent framework (closed learning loop / user modelling), and Claude Code skills
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
(`raiker/memory/`, `docs/MEMORY_GOVERNANCE_RULES.md`).

---

## 2. What Raiker may learn

| Artifact | Description | Becomes | First active phase |
|---|---|---|---|
| **Skill** | A named, reusable procedure distilled from a successful task trajectory (steps, tool sequence, checks). | A `/skill-name` invocable unit (see `docs/EXTENSIBILITY_MODEL.md`). | Phase 3+ |
| **Procedure note** | A shorter "how we do X here" entry tied to a project. | Procedural memory record. | Phase 2+ |
| **User model fact** | A confirmed preference/convention ("uses pytest", "prefers small PRs"). | Profile memory record. | Phase 2+ |
| **Gist** | Compressed recall of an episode for cheaper future context. | Episodic/gist memory. | Phase 2+ |
| **Heuristic** | A scored rule of thumb ("tests in `tests/` mirror `raiker/`"). | Project memory with confidence. | Phase 3+ |

Self-improvement does **not** include: editing policy, expanding tool permissions, enabling
disabled runtime capabilities, or rewriting its own system prompt.

---

## 3. The closed loop

```
observe (eidetic raw observation, verified)
   -> distill (propose skill/heuristic/user-fact CANDIDATE)
   -> review (user or managed policy gate; preview shown)
   -> store (provenance + confidence + sensitivity, candidate -> active)
   -> use (loaded on demand, like a skill)
   -> measure (success/failure feedback updates confidence)
   -> correct / forget (decay, contradiction, or explicit deletion)
```

Each transition emits an event (Section 6) and is rollback-able.

---

## 4. Skill distillation contract

A skill candidate is proposed only when a trajectory is **completed and verified** (the verifier
must pass — note: the verifier is currently a stub, `raiker/runtime/verifier.py`, so skill
distillation cannot be enabled until verification is real).

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
  (poisoning defence, see `docs/OWASP_GENAI_SECURITY_MAPPING.md`).
- **Confidence + decay.** New artifacts start at low confidence; repeated success raises it,
  contradiction or failure lowers it; stale artifacts decay.
- **Forgetting.** Users can correct or delete any learned artifact; eidetic raw observations are
  retention-bounded.
- **Managed override.** Enterprise/managed policy can disable self-improvement entirely.

---

## 6. Events (reserved; not yet emitted)

- `skill_candidate_proposed`
- `skill_candidate_reviewed`
- `skill_activated`
- `skill_used`
- `skill_confidence_updated`
- `skill_deactivated`
- `learned_artifact_forgotten`
- `self_improvement_policy_decision`

---

## 7. Tests required before enabling

- A verified trajectory produces exactly one skill candidate; an unverified one produces none.
- A skill candidate is inactive until approved.
- An activated skill executes only through the tool broker/policy path.
- A skill learned from untrusted content is quarantined and cannot self-activate.
- Confidence rises on success and falls on failure; stale artifacts decay.
- Deletion/forgetting removes the artifact and its activation.
- Managed policy can globally disable self-improvement.

---

## 8. Current code status

**specified_not_implemented.** There is no self-improvement runtime today. The prerequisites are:
a real verifier, memory writes enabled under governance (currently disabled,
`raiker/memory/readiness.py`), and the skills/extensibility surface
(`docs/EXTENSIBILITY_MODEL.md`). Until those exist, this doc is the contract to build against.
