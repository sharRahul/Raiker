from __future__ import annotations

from typing import Any

from raiker.contracts.ids import new_id
from raiker.contracts.models import OWNER_QUESTION_TOOL, ToolAction
from raiker.models.contracts import ToolCallProposal, ToolSpec
from raiker.models.tool_registry import (
    ARG_SCHEMAS,
    MODEL_EXPOSED_TOOLS,
    OPTIONAL_ARGS,
    REQUIRED_ARGS,
    REQUIRED_LIST_ARGS,
    TOOL_DESCRIPTIONS,
    TOOL_RISK,
    TOOL_RISK_BANDS,
    mcp_tool_risk_band,
)
from raiker.tools.mcp_tools import is_mcp_tool, parse_mcp_tool_name

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
_MCP_TOOL_RISK: tuple[str, bool] = (mcp_tool_risk_band(), False)


class ToolCallRejected(ValueError):
    """Raised when a model-proposed tool call fails validation (OWASP LLM05)."""

    def __init__(self, reason: str, *, tool_name: str) -> None:
        super().__init__(reason)
        self.reason = reason
        self.tool_name = tool_name


# ADD-22 — the shape a question has to have before it reaches the owner.
#
# The bounds match the reference contract (1-4 questions, 2-4 options each, a
# short header) because they are good bounds and because a Raiker skill an owner
# writes should port. They are enforced here rather than trusted: `question`,
# `header`, `label` and `description` are all model-authored text that a person
# is about to read and act on, so the count, the length and the type are checked
# before anything is stored, and the surface renders them as data.
MAX_OWNER_QUESTIONS = 4
MAX_OWNER_QUESTION_OPTIONS = 4
MIN_OWNER_QUESTION_OPTIONS = 2
MAX_OWNER_QUESTION_CHARS = 400
MAX_OWNER_HEADER_CHARS = 12
MAX_OWNER_OPTION_CHARS = 200


def _text(value: object, limit: int, field: str) -> str:
    if not isinstance(value, str):
        raise ToolCallRejected(f"question_{field}_not_text", tool_name=OWNER_QUESTION_TOOL)
    text = value.strip()
    if not text:
        raise ToolCallRejected(f"question_{field}_empty", tool_name=OWNER_QUESTION_TOOL)
    if len(text) > limit:
        raise ToolCallRejected(f"question_{field}_too_long", tool_name=OWNER_QUESTION_TOOL)
    return text


def _validate_owner_questions(value: object) -> None:
    """Refuse a malformed question before the owner is ever shown one."""
    if not isinstance(value, list) or not value:
        raise ToolCallRejected("questions_missing", tool_name=OWNER_QUESTION_TOOL)
    if len(value) > MAX_OWNER_QUESTIONS:
        raise ToolCallRejected("too_many_questions", tool_name=OWNER_QUESTION_TOOL)
    seen: set[str] = set()
    for entry in value:
        if not isinstance(entry, dict):
            raise ToolCallRejected("question_not_object", tool_name=OWNER_QUESTION_TOOL)
        question = _text(entry.get("question"), MAX_OWNER_QUESTION_CHARS, "text")
        # The answer comes back keyed by the question text, exactly as the
        # reference contract does it, so two identical questions would make one
        # answer ambiguous. Refused rather than silently merged.
        if question in seen:
            raise ToolCallRejected("duplicate_question", tool_name=OWNER_QUESTION_TOOL)
        seen.add(question)
        _text(entry.get("header"), MAX_OWNER_HEADER_CHARS, "header")
        options = entry.get("options")
        if not isinstance(options, list):
            raise ToolCallRejected("question_options_missing", tool_name=OWNER_QUESTION_TOOL)
        if not MIN_OWNER_QUESTION_OPTIONS <= len(options) <= MAX_OWNER_QUESTION_OPTIONS:
            raise ToolCallRejected("question_option_count", tool_name=OWNER_QUESTION_TOOL)
        labels: set[str] = set()
        for option in options:
            if not isinstance(option, dict):
                raise ToolCallRejected("question_option_not_object", tool_name=OWNER_QUESTION_TOOL)
            label = _text(option.get("label"), MAX_OWNER_OPTION_CHARS, "option_label")
            # The answer is returned as the chosen label, so labels have to be
            # distinguishable for the same reason questions do.
            if label in labels:
                raise ToolCallRejected("duplicate_option", tool_name=OWNER_QUESTION_TOOL)
            labels.add(label)
            _text(option.get("description"), MAX_OWNER_OPTION_CHARS, "option_description")
        if "multiSelect" in entry and not isinstance(entry["multiSelect"], bool):
            raise ToolCallRejected("question_multiselect_not_bool", tool_name=OWNER_QUESTION_TOOL)


def risk_for_tool(tool_name: str) -> str:
    """The band any proposal of *tool_name* carries, model-proposed or not.

    Three places built a `ToolAction` without going through the validator and
    each stamped a band of its own: the subagent runner wrote `low` for every
    step whatever the tool was, and the plugin runtime wrote `medium`. Both were
    right by coincidence at the time and neither would have noticed becoming
    wrong — a tool marked delegable, or a plugin reaching one that leaves the
    machine, would have been laundered into a milder band than it carries, and in
    `auto` decision mode `low` is the band that runs unprompted.

    A projected MCP tool has no registry entry by design, so it takes the band
    declared for the whole class. An unregistered name is an error rather than a
    default: guessing a band for a tool nobody declared is how the coincidences
    above happened.
    """
    if is_mcp_tool(tool_name):
        return _MCP_TOOL_RISK[0]
    try:
        # Every registered tool, not only the model-exposed ones: a subagent may
        # be delegated `vector_get`, which is deliberately absent from the
        # model's catalogue and still needs a band.
        return TOOL_RISK_BANDS[tool_name]
    except KeyError:
        raise ToolCallRejected(f"unknown_tool:{tool_name}", tool_name=tool_name) from None


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
    if tool_name == OWNER_QUESTION_TOOL:
        _validate_owner_questions(arguments.get("questions"))
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
