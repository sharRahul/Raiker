// Response shapes from the governed read API (see raiker/control/dashboard.py and
// raiker/control/dtos.py). These mirror the backend DTOs; the backend remains the source of truth.

export interface CapabilityGate {
  capability: string;
  phase: number;
  state: string;
  default_state: string;
  source: string;
  runtime_enabled: boolean;
  allowed_transitions: string[];
  can_current_principal_change: boolean;
  blocked_reason_code: string | null;
  readiness: Record<string, boolean>;
}

export interface RuntimeMode {
  mode_name: string;
  status: string;
  activated_by: string;
  activated_at: string;
  reason: string;
  allowed_modes: string[];
}

export interface RuntimeReadiness {
  mode: RuntimeMode;
  gates: CapabilityGate[];
  summary: Record<string, unknown>;
}

export interface Diagnostics {
  runtime_mode: string;
  production_ready_local_single_user_runtime: boolean;
  summary: Record<string, unknown>;
  disabled_capabilities: string[];
  counts: Record<string, number>;
  scope_note: string;
}

export interface ModelProfile {
  profile_id: string;
  provider: string;
  model: string;
  default_state: string;
  local_only: boolean;
  requires_network: boolean;
  endpoint_kind: string;
  selected: boolean;
}

export interface ModelsView {
  profiles: ModelProfile[];
  current_profile_id: string | null;
  no_silent_hosted_fallback: boolean;
}

export interface EventEntry {
  event_id: string;
  session_id: string;
  turn_id: string | null;
  event_type: string;
  actor: string;
  timestamp: string;
  risk_level: string | null;
  summary: string | null;
}

export interface Checkpoint {
  checkpoint_id: string;
  session_id: string;
  turn_id: string | null;
  task_id: string | null;
  checkpoint_type: string;
  created_at: string;
  summary: string | null;
  last_event_id: string | null;
  can_restore_state: boolean;
  can_restore_files: boolean;
}

export interface SessionSummary {
  session_id: string;
  title: string | null;
  status: string;
  created_at: string;
  updated_at: string;
  turn_count: number;
}

export interface AuthSession {
  token: string;
  session_id: string;
  principal_id: string;
  expires_at: string | null;
}
