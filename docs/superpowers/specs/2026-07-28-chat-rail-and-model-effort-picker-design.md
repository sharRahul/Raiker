# Chat rail and model-effort picker

## Goal

Give Chat its own right-hand Background Work rail, matching Build's visual hierarchy without moving or changing Build's rail, and give each composer a model picker that exposes a thinking-effort choice only when the selected provider/model supports it.

## Layout

Chat uses a local two-column grid at the same desktop breakpoint as Build: conversation/composer on the left and `BuildSidePanel` on the right. The existing Chat panel is removed from below the composer. At narrow widths the layout becomes one column and the panel follows the conversation, preserving access without overlap. Build is unchanged.

## Model and thinking selection

The composer displays the previously selected provider/model when one exists, otherwise **Not selected**. Its model picker groups available profiles by provider. A per-turn effort control is rendered only when the resolved selected profile declares both `supports_reasoning` and `supports_reasoning_effort`, and it offers exactly that profile's `reasoning_effort_values`. A model without those declarations never shows or sends an effort value.

The UI sends model profile, concrete model where applicable, and an optional reasoning effort with the prompt. The backend validates the effort against the resolved profile before constructing the provider request. An invalid or unavailable effort is rejected; it is never silently substituted. Per-turn choices do not overwrite the user's persisted global model selection.

## Safety and testing

Provider policy, credential checks, egress policy, model binding, and all approval/runtime protections remain server-enforced. Tests cover the responsive Chat rail, no duplicate below-composer panel, selected/unselected model presentation, exact provider capability-driven effort choices, omission for unsupported models, rejection of invalid effort, and provider request propagation. Live testing uses only process-scoped credentials; no secret is stored in source, test data, logs, or documentation.
