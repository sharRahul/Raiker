from __future__ import annotations

from raiker.graph.governance import graph_governance_status


def graph_registry_status() -> dict[str, object]:
    status = graph_governance_status()
    status["durable_graph_records_written"] = 0
    return status
