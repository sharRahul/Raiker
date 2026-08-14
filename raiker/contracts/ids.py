from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

_PREFIXES = {
    "req_",
    "sess_",
    "turn_",
    "evt_",
    "act_",
    "tool_",
    "pol_",
    "ckpt_",
    # Checkpoint pre-image capture manifest entry (Workstream B / B1).
    "ckcap_",
    "task_",
    # One row of per-turn token accounting in the model usage ledger.
    "usage_",
    # One durable conversation-context compaction attempt.
    "cmp_",
    # Append-only cloud execution budget ledger event.
    "cost_",
    # Administrator context-capacity registry history row.
    "mcap_",
    # Owner-confirmed local runtime/model install, download, conversion, or deployment.
    "mop_",
    "appr_",
    "memcand_",
    "ver_",
    "graphplan_",
    "ctxb_",
    "ctxi_",
    "ctxs_",
    "vres_",
    "vchk_",
    "rap_",
    "apv_",
    "mem_",
    "obs_",
    "pur_",
    "mev_",
    "ent_",
    "rel_",
    "mjob_",
    "mla_",
    "mng_",
    "usr_",
    "rl_",
    "ura_",
    "aex_",
    "plr_",
    "htr_",
    "bud_",
    "ret_",
    "bkm_",
    "chn_",
    "chr_",
    "sba_",
    "team_",
    "rex_",
    "exb_",
    "dsk_",
    "web_",
    "mob_",
    "plgex_",
    "plgrt_",
    "rem_",
    "cal_",
    "eml_",
    "gix_",
    "smw_",
    "ide_",
    "vec_",
    "sym_",
    "dep_",
    "pg_",
    "skc_",
    # An installed skill: a validated SKILL.md document, or a *.skill bundle.
    "skl_",
    "ra_",
    "rm_",
    "rtn_",
    "att_",
    "proj_",
    "cwi_",
    "cinv_",
    "mcp_",
    # Monitored MCP connections (Phase B): a redacted per-session monitoring row
    # and a redacted security finding.
    "mses_",
    "find_",
    "cred_",
    # Monitored MCP connections (Phase C): an owner-facing notification.
    "ntf_",
    # Scoped standing approval grants (Workstream F / F3).
    "grn_",
    # Build workspace repository references: a workspace-contained local folder
    # or a GitHub `owner/repo` coordinate. A reference holds no credential and
    # grants no capability.
    "repo_",
    # Capability-agnostic behaviour monitoring (BUG-76/77): one redacted
    # activity row per governed capability invocation.
    "cact_",
    # RAIKER-2021: one owner rule on the web egress blocklist. Holds a domain,
    # address, network or pattern — never a credential.
    "wbl_",
    # RAIKER-2022: one owner decision to lend the git credential, scoped to a
    # single command or to a session. Holds the decision, never the token.
    "grant_",
    # Immutable command credential-delta resolution receipt.
    "dres_",
    # One durable governed command invocation.
    "cmd_",
}


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def new_id(prefix: str) -> str:
    if prefix not in _PREFIXES:
        raise ValueError(f"unsupported_id_prefix:{prefix}")
    return f"{prefix}{uuid4().hex}"


def require_prefix(value: str, prefix: str) -> None:
    if not value.startswith(prefix):
        raise ValueError(f"expected_prefix:{prefix}")
