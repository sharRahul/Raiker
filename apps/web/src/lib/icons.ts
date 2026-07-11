// Inline SVG icon set (24×24 viewBox, stroke-based). Self-contained — no icon
// font, no CDN — so the SPA works fully offline behind the loopback origin.
// Rendered by components/Icon.svelte.

export type IconName =
  | "chat"
  | "approvals"
  | "tasks"
  | "sessions"
  | "capabilities"
  | "connections"
  | "models"
  | "checkpoints"
  | "activity"
  | "diagnostics"
  | "settings"
  | "shield"
  | "stop"
  | "sun"
  | "moon"
  | "system"
  | "send"
  | "check"
  | "x"
  | "chevron-down"
  | "chevron-right"
  | "search"
  | "refresh"
  | "lock"
  | "warning"
  | "info"
  | "spark"
  | "mic"
  | "file";

// Each icon is one or more SVG path `d` strings (stroke, round caps).
export const ICON_PATHS: Record<IconName, string[]> = {
  chat: ["M21 12a8 8 0 0 1-8 8H4l2.4-2.9A8 8 0 1 1 21 12Z", "M9 11h6", "M9 14.5h4"],
  approvals: ["M9 11.5 11.3 14 15.5 9.5", "M12 3l7 3v5.5c0 4.4-3 7.6-7 9.5-4-1.9-7-5.1-7-9.5V6l7-3Z"],
  tasks: ["M4 6h10", "M4 12h10", "M4 18h6", "M17 15l2 2 3.5-3.5"],
  sessions: ["M5 4h14a1 1 0 0 1 1 1v11a1 1 0 0 1-1 1H8l-4 3.5V5a1 1 0 0 1 1-1Z", "M9 9h6"],
  capabilities: [
    "M12 3v3.5",
    "M12 17.5V21",
    "M3 12h3.5",
    "M17.5 12H21",
    "M12 8.5a3.5 3.5 0 1 1 0 7 3.5 3.5 0 0 1 0-7Z",
  ],
  connections: [
    "M9 15l-2.5 2.5a3.5 3.5 0 0 1-5-5L4 10",
    "M15 9l2.5-2.5a3.5 3.5 0 0 1 5 5L20 14",
    "M9.5 14.5 14.5 9.5",
  ],
  models: ["M12 3 4 7.5v9L12 21l8-4.5v-9L12 3Z", "M4 7.5 12 12l8-4.5", "M12 12v9"],
  checkpoints: ["M12 8v4l2.5 2.5", "M12 3a9 9 0 1 1-9 9", "M3 5v4h4"],
  activity: ["M3 12h4l2.5-6 4 12 2.5-6H21"],
  diagnostics: ["M12 3a9 9 0 1 1-9 9", "M12 7v5l3 3", "M3 5v4h4"],
  settings: [
    "M12 9.5a2.5 2.5 0 1 1 0 5 2.5 2.5 0 0 1 0-5Z",
    "M19 12a7 7 0 0 0-.15-1.4l2-1.55-2-3.45-2.35.95a7 7 0 0 0-2.4-1.4L13.75 2.7h-3.5L9.9 5.15a7 7 0 0 0-2.4 1.4L5.15 5.6l-2 3.45 2 1.55A7 7 0 0 0 5 12c0 .48.05.94.15 1.4l-2 1.55 2 3.45 2.35-.95a7 7 0 0 0 2.4 1.4l.35 2.45h3.5l.35-2.45a7 7 0 0 0 2.4-1.4l2.35.95 2-3.45-2-1.55c.1-.46.15-.92.15-1.4Z",
  ],
  shield: ["M12 3l7 3v5.5c0 4.4-3 7.6-7 9.5-4-1.9-7-5.1-7-9.5V6l7-3Z"],
  stop: ["M12 3a9 9 0 1 1 0 18 9 9 0 0 1 0-18Z", "M9.5 9.5h5v5h-5Z"],
  sun: [
    "M12 8.5a3.5 3.5 0 1 1 0 7 3.5 3.5 0 0 1 0-7Z",
    "M12 2.5v2",
    "M12 19.5v2",
    "M4.6 4.6l1.4 1.4",
    "M18 18l1.4 1.4",
    "M2.5 12h2",
    "M19.5 12h2",
    "M4.6 19.4 6 18",
    "M18 6l1.4-1.4",
  ],
  moon: ["M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5Z"],
  system: ["M4 5h16a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1Z", "M9 20h6", "M12 16v4"],
  send: ["M4 12 20 4l-4 16-4.5-6.5L4 12Z", "M20 4 11.5 13.5"],
  check: ["M5 12.5 10 17.5 19 7"],
  x: ["M6 6l12 12", "M18 6 6 18"],
  mic: [
    "M12 3a3 3 0 0 1 3 3v6a3 3 0 1 1-6 0V6a3 3 0 0 1 3-3Z",
    "M6 11.5a6 6 0 0 0 12 0",
    "M12 17.5V21",
    "M9 21h6",
  ],
  file: ["M7 3h7l4 4v13a1 1 0 0 1-1 1H8a1 1 0 0 1-1-1V4a1 1 0 0 1 0-1Z", "M14 3v4h4"],
  "chevron-down": ["M6 9.5 12 15.5 18 9.5"],
  "chevron-right": ["M9.5 6 15.5 12 9.5 18"],
  search: ["M10.5 4a6.5 6.5 0 1 1 0 13 6.5 6.5 0 0 1 0-13Z", "M15.5 15.5 21 21"],
  refresh: ["M20 8a8 8 0 1 0 1 6", "M21 3v5h-5"],
  lock: ["M6 11h12a1 1 0 0 1 1 1v8a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1v-8a1 1 0 0 1 1-1Z", "M8.5 11V8a3.5 3.5 0 0 1 7 0v3"],
  warning: ["M12 4 2.8 20h18.4L12 4Z", "M12 10v4.5", "M12 17.5v.5"],
  info: ["M12 3a9 9 0 1 1 0 18 9 9 0 0 1 0-18Z", "M12 11v5", "M12 7.5v.5"],
  spark: ["M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3Z"],
};
