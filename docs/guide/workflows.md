# Example Workflows

## For Developers: Git Automation
Raiker provides a deterministic code-review workflow.
- **Review**: Use `/review` to analyze diffs.
- **Lifecycle**: Proposal $\rightarrow$ Review $\rightarrow$ Approval $\rightarrow$ Commit.

## For Home-lab Operators: Local State
- **Scheduled Tasks**: Create stored-only schedules via the dashboard.
- **Workspace Isolation**: Run multiple instances with different `--workspace` paths.

## For Enterprise: Governed Automation
- **Policy Gating**: Every mutation must pass the static policy engine.
- **Auditability**: Every turn is recorded in append-only JSONL and SQLite.
- **Risk Acceptance**: High-risk actions require explicit threat-model acknowledgment.
