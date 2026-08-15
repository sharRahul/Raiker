from __future__ import annotations

from typing import Any

from raiker.contracts.ids import new_id
from raiker.contracts.models import ToolAction
from raiker.models.contracts import ToolCallProposal, ToolSpec
from raiker.models.tool_registry import (
    ARG_SCHEMAS,
    MODEL_EXPOSED_TOOLS,
    OPTIONAL_ARGS,
    REQUIRED_ARGS,
    REQUIRED_LIST_ARGS,
    TOOL_DESCRIPTIONS,
    TOOL_RISK,
)
from raiker.tools.mcp_tools import parse_mcp_tool_name

# Every table this module used to own now lives in one declaration per tool.
# Registering `conversation_search` and `code_map_references` cost twelve edits
# across seven files, none of which failed loudly when one was missed — so the
# requirement moved somewhere it cannot be forgotten. See
# `raiker.models.tool_registry`.
_TOOL_RISK = TOOL_RISK
_MODEL_EXPOSED_TOOLS = MODEL_EXPOSED_TOOLS
_REQUIRED_ARGS = REQUIRED_ARGS
_REQUIRED_LIST_ARGS = REQUIRED_LIST_ARGS
_ARG_SCHEMAS = ARG_SCHEMAS
_OPTIONAL_ARGS = OPTIONAL_ARGS
_TOOL_DESCRIPTIONS = TOOL_DESCRIPTIONS

# A projected MCP tool (``mcp__<server>__<tool>``) is deliberately *not* in the
# registry: the tools a turn may call depend on which servers the owner
# connected (BUG-12), so the set is dynamic and validation checks the *shape*
# and stays store-free. Whether that server and tool actually exist is answered
# at execution, where the capability gate, the decision mode, containment, and
# the advertised tool list all apply. Reaching a registered server runs code
# Raiker does not own, so a call carries the same risk band as a connector read:
# `ask`/`auto` withhold it by default.
_MCP_TOOL_RISK: tuple[str, bool] = ("medium", False)


class ToolCallRejected(ValueError):
    """Raised when a model-proposed tool call fails validation (OWASP LLM05)."""

    def __init__(self, reason: str, *, tool_name: str) -> None:
        super().__init__(reason)
        self.reason = reason
        self.tool_name = tool_name


def default_tool_specs() -> list[ToolSpec]:
    """Tool schemas advertised to the model. Only registered, brokered tools are offered."""

    specs: list[ToolSpec] = []
    for name in sorted(_MODEL_EXPOSED_TOOLS):
        required = [*_REQUIRED_ARGS.get(name, ()), *_REQUIRED_LIST_ARGS.get(name, ())]
        schemas = _ARG_SCHEMAS.get(name, {})
        properties: dict[str, Any] = {
            arg: schemas.get(arg, {"type": "string"})
            for arg in (*required, *_OPTIONAL_ARGS.get(name, ()))
        }
        specs.append(
            ToolSpec(
                name=name,
                description=_TOOL_DESCRIPTIONS.get(name, name),
                parameters={
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            )
        )
    return specs


def validate_tool_call(proposal: ToolCallProposal) -> ToolAction:
    """Validate an untrusted model tool call and convert it into a ToolAction.

    Raises ToolCallRejected for unknown tools, non-object arguments, or missing required
    fields. Only validated calls become ToolActions; they still flow through the policy
    engine and approval path unchanged.
    """

    tool_name = proposal.tool_name
    mcp_tool = parse_mcp_tool_name(tool_name)
    if mcp_tool is None and tool_name not in _MODEL_EXPOSED_TOOLS:
        raise ToolCallRejected(f"unknown_tool:{tool_name}", tool_name=tool_name)
    arguments: dict[str, Any] = proposal.arguments
    if not isinstance(arguments, dict):
        raise ToolCallRejected("arguments_not_object", tool_name=tool_name)
    if mcp_tool is not None:
        nested = arguments.get("arguments", {})
        if not isinstance(nested, dict):
            raise ToolCallRejected("arguments_not_object", tool_name=tool_name)
        risk_level, requires_approval = _MCP_TOOL_RISK
        return ToolAction(
            action_id=new_id("act_"),
            tool_name=tool_name,
            arguments=arguments,
            risk_level=risk_level,
            requires_approval=requires_approval,
            proposed_by="model",
        )
    for required in _REQUIRED_ARGS.get(tool_name, ()):
        value = arguments.get(required)
        if not isinstance(value, str) or value == "":
            raise ToolCallRejected(f"missing_argument:{required}", tool_name=tool_name)
    for required in _REQUIRED_LIST_ARGS.get(tool_name, ()):
        listed = arguments.get(required)
        if not isinstance(listed, list) or not listed:
            raise ToolCallRejected(f"missing_argument:{required}", tool_name=tool_name)
    if tool_name == "create_document" and not str(arguments["path"]).lower().endswith(
        (".md", ".markdown", ".docx", ".xlsx", ".pdf")
    ):
        raise ToolCallRejected("document_path_must_be_markdown", tool_name=tool_name)
    risk_level, requires_approval = _TOOL_RISK[tool_name]
    return ToolAction(
        action_id=new_id("act_"),
        tool_name=tool_name,
        arguments=arguments,
        risk_level=risk_level,
        requires_approval=requires_approval,
        proposed_by="model",
    )
