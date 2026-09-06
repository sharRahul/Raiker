// Inline SVG icon set (24×24 viewBox, stroke-based). Self-contained — no icon
// font, no CDN — so the SPA works fully offline behind the loopback origin.
// Rendered by components/Icon.svelte.
//
// BUG-37 — three things the set was missing:
//
// 1. **One optical size per role.** `ICON_SIZE` names the four sizes this app
//    actually needs. Call sites passed 14, 15, 16, 17, 18, 20 and 22 more or
//    less interchangeably, which is why an icon in a button and an icon in a nav
//    row were different sizes that both looked almost right.
// 2. **A filled/outline pair for selected states.** These are stroke icons, so
//    the "filled" partner is the same geometry with a soft fill behind it
//    (`Icon`'s `filled` prop) rather than a second hand-drawn path set that
//    could drift from the outline it belongs to.
// 3. **No repeats across unrelated meanings.** `diagnostics` was the same
//    clock-with-rewind as `checkpoints`, `capabilities` was the same ringed
//    circle as `sun`, and `projects` was the same folder as `folder`. At 16px
//    each pair was indistinguishable while meaning entirely different things.

/** The optical size scale. `sm` sits inside dense text, `md` inside a control,
 *  `lg` beside a heading or in a nav row, `xl` in an empty state. */
export const ICON_SIZE = { sm: 14, md: 16, lg: 20, xl: 24 } as const;

export type IconSize = keyof typeof ICON_SIZE;

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
  | "license"
  | "warning"
  | "hand"
  | "fast-forward"
  | "info"
  | "spark"
  | "mic"
  | "volume"
  | "file"
  | "code"
  | "branch"
  | "folder"
  | "panel"
  | "clock"
  | "play"
  | "projects"
  | "user"
  | "user-plus"
  | "eye"
  | "eye-off"
  | "bell"
  // BUG-26 — the image inspection controls.
  | "zoom-in"
  | "zoom-out"
  | "fit"
  | "rotate"
  // BUG-28 — taking a generated artifact away with you.
  | "download"
  // BUG-23 — the code-block copy action, as a glyph rather than a word.
  | "copy"
  // BUG-27 — opening the exact passage a memory or a file came from.
  | "quote"
  // An unstarted plan step: an empty ring, deliberately the quietest glyph in
  // the set so a checklist reads by its *completed* marks rather than its gaps.
  | "circle"
  // BUG-206 slice C — one glyph per tool family, so a transcript row tells you
  // the *kind* of work before you read the words. Four families reuse a glyph
  // the set already had, and that already means the same thing there: `file`
  // for a read, `branch` for the repository, `connections` for a connector,
  // `tasks` for the turn's own plan. These five are the ones nothing meant.
  | "file-edit"
  | "terminal"
  | "globe"
  | "memory"
  | "agent"
  // B18 — the overflow handle. Three dots is the one glyph a reader already
  // knows means "the rest of the actions", and it earns its place because the
  // alternative was six labelled buttons under every message.
  | "more"
  // The neutral fallback. A tool with no family still renders as a tool, which
  // is the difference between "Raiker did something you cannot name" and the
  // silence BUG-206 was filed about.
  | "tool"
  // BUG-251 — "go up one folder" in the path picker. Its own glyph rather than a
  // rotated `chevron-right`: a bare chevron beside a path reads as "expand this",
  // and the folder is the half that says which direction is meant.
  | "folder-up"
  // VIS2-09 — three permanent destinations drew the same spark. A rail whose
  // rows are only told apart by their labels is not an icon set, and the spark
  // is Raiker's mark for agent action: spending it on "Home" spends the one
  // glyph that should mean the agent did something.
  | "home"
  | "design"
  | "map";

// Each icon is one or more SVG path `d` strings (stroke, round caps).
export const ICON_PATHS: Record<IconName, string[]> = {
  chat: ["M21 12a8 8 0 0 1-8 8H4l2.4-2.9A8 8 0 1 1 21 12Z", "M9 11h6", "M9 14.5h4"],
  approvals: ["M9 11.5 11.3 14 15.5 9.5", "M12 3l7 3v5.5c0 4.4-3 7.6-7 9.5-4-1.9-7-5.1-7-9.5V6l7-3Z"],
  tasks: ["M4 6h10", "M4 12h10", "M4 18h6", "M17 15l2 2 3.5-3.5"],
  sessions: ["M5 4h14a1 1 0 0 1 1 1v11a1 1 0 0 1-1 1H8l-4 3.5V5a1 1 0 0 1 1-1Z", "M9 9h6"],
  // A key: what Raiker may do. The ringed circle it used to be was the sun icon
  // with four rays instead of eight — indistinguishable at 16px.
  capabilities: [
    "M15.5 4a4.5 4.5 0 1 1-4.2 6.1L4 17.4V20h2.6l.9-.9v-1.9h1.9l1.3-1.3",
    "M16.5 8.2h.01",
  ],
  connections: [
    "M9 15l-2.5 2.5a3.5 3.5 0 0 1-5-5L4 10",
    "M15 9l2.5-2.5a3.5 3.5 0 0 1 5 5L20 14",
    "M9.5 14.5 14.5 9.5",
  ],
  models: ["M12 3 4 7.5v9L12 21l8-4.5v-9L12 3Z", "M4 7.5 12 12l8-4.5", "M12 12v9"],
  checkpoints: ["M12 8v4l2.5 2.5", "M12 3a9 9 0 1 1-9 9", "M3 5v4h4"],
  activity: ["M3 12h4l2.5-6 4 12 2.5-6H21"],
  // A gauge: how healthy is this, right now. It used to be the same
  // clock-with-a-rewind-arrow as `checkpoints`, which is genuinely that glyph's
  // meaning — rewinding — and is not this one's.
  diagnostics: ["M3.5 17.5a9 9 0 1 1 17 0", "M12 17.5 16 11", "M12 20.2h.01"],
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
  volume: [
    "M4 10v4h4l5 4V6l-5 4H4Z",
    "M16 9a4 4 0 0 1 0 6",
    "M18.5 6.5a8 8 0 0 1 0 11",
  ],
  file: ["M7 3h7l4 4v13a1 1 0 0 1-1 1H8a1 1 0 0 1-1-1V4a1 1 0 0 1 0-1Z", "M14 3v4h4"],
  // Stacked boards: a project groups conversations, files and instructions. It
  // used to be the same folder outline as `folder`, which means a directory on
  // disk — a different thing that appears on the same screens.
  projects: [
    "M4 8.5a1.5 1.5 0 0 1 1.5-1.5h13A1.5 1.5 0 0 1 20 8.5v9a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 17.5v-9Z",
    "M6.5 4.5h11",
    "M9.5 11.5h5",
  ],
  "chevron-down": ["M6 9.5 12 15.5 18 9.5"],
  "chevron-right": ["M9.5 6 15.5 12 9.5 18"],
  search: ["M10.5 4a6.5 6.5 0 1 1 0 13 6.5 6.5 0 0 1 0-13Z", "M15.5 15.5 21 21"],
  refresh: ["M20 8a8 8 0 1 0 1 6", "M21 3v5h-5"],
  lock: ["M6 11h12a1 1 0 0 1 1 1v8a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1v-8a1 1 0 0 1 1-1Z", "M8.5 11V8a3.5 3.5 0 0 1 7 0v3"],
  license: ["M12 3v18", "M5 6h14", "M7.5 6 4 13h7L7.5 6Z", "M16.5 6 13 13h7l-3.5-7Z", "M8 21h8"],
  warning: ["M12 4 2.8 20h18.4L12 4Z", "M12 10v4.5", "M12 17.5v.5"],
  hand: [
    "M7.5 12V6.5a1.5 1.5 0 0 1 3 0V11",
    "M10.5 11V5a1.5 1.5 0 0 1 3 0v6",
    "M13.5 11V6.5a1.5 1.5 0 0 1 3 0V12",
    "M16.5 11.5a1.5 1.5 0 0 1 3 0v3c0 3.6-2.5 6.5-6.5 6.5h-1.2c-2.6 0-4.5-1.6-5.7-3.9L4.5 14a1.5 1.5 0 0 1 2.6-1.5L8.5 15",
  ],
  "fast-forward": ["M5 5.5 12 12 5 18.5V5.5Z", "M12 5.5 19 12l-7 6.5V5.5Z"],
  info: ["M12 3a9 9 0 1 1 0 18 9 9 0 0 1 0-18Z", "M12 11v5", "M12 7.5v.5"],
  spark: ["M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3Z"],
  bell: ["M18 16H6c1.2-1.4 2-2.8 2-6a4 4 0 0 1 8 0c0 3.2.8 4.6 2 6Z", "M10.4 19a1.8 1.8 0 0 0 3.2 0"],
  user: ["M12 11a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z", "M4.5 20c1.6-3.2 4.3-5 7.5-5s5.9 1.8 7.5 5"],
  "user-plus": [
    "M10 11a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z",
    "M3 20c1.4-3 4-4.7 7-4.7 1.1 0 2.2.2 3.2.7",
    "M18.5 13v6",
    "M15.5 16h6",
  ],
  code: ["M9 7 4 12l5 5", "M15 7l5 5-5 5"],
  branch: [
    "M6.5 6.5a2 2 0 1 0 0-.1Z",
    "M6.5 17.5a2 2 0 1 0 0-.1Z",
    "M17.5 8.5a2 2 0 1 0 0-.1Z",
    "M6.5 8.5v7",
    "M17.5 10.5a5 5 0 0 1-5 5H6.5",
  ],
  folder: ["M3 6.5a1 1 0 0 1 1-1h4.5l2 2.5H20a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1v-11Z"],
  "folder-up": [
    "M3 6.5a1 1 0 0 1 1-1h4.5l2 2.5H20a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1v-11Z",
    "M12 17.5v-5",
    "M9.5 14.5 12 12l2.5 2.5",
  ],
  panel: ["M4 5h16a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1Z", "M15 5v14"],
  clock: ["M12 3.5a8.5 8.5 0 1 1 0 17 8.5 8.5 0 0 1 0-17Z", "M12 7.5V12l3 2"],
  circle: ["M12 4.5a7.5 7.5 0 1 1 0 15 7.5 7.5 0 0 1 0-15Z"],
  play: ["M8 5.5 18 12 8 18.5V5.5Z"],
  eye: [
    "M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12Z",
    "M12 14.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Z",
  ],
  "eye-off": [
    "M4 4l16 16",
    "M9.9 5.9A9 9 0 0 1 12 5.5c6 0 9.5 6.5 9.5 6.5a17.4 17.4 0 0 1-3.3 3.9",
    "M6.1 8.2A17 17 0 0 0 2.5 12S6 18.5 12 18.5c1 0 2-.2 2.9-.5",
    "M10.2 10.3a2.5 2.5 0 0 0 3.5 3.5",
  ],
  "zoom-in": [
    "M10.5 4a6.5 6.5 0 1 1 0 13 6.5 6.5 0 0 1 0-13Z",
    "M15.5 15.5 21 21",
    "M10.5 7.8v5.4",
    "M7.8 10.5h5.4",
  ],
  "zoom-out": [
    "M10.5 4a6.5 6.5 0 1 1 0 13 6.5 6.5 0 0 1 0-13Z",
    "M15.5 15.5 21 21",
    "M7.8 10.5h5.4",
  ],
  fit: [
    "M4 9V5a1 1 0 0 1 1-1h4",
    "M15 4h4a1 1 0 0 1 1 1v4",
    "M20 15v4a1 1 0 0 1-1 1h-4",
    "M9 20H5a1 1 0 0 1-1-1v-4",
  ],
  rotate: ["M20 12a8 8 0 1 1-2.3-5.6", "M20 3.5v5h-5"],
  download: ["M12 4v10.5", "M8 11l4 4 4-4", "M5 19h14"],
  copy: [
    "M9 9.5A1.5 1.5 0 0 1 10.5 8h7A1.5 1.5 0 0 1 19 9.5v7a1.5 1.5 0 0 1-1.5 1.5h-7A1.5 1.5 0 0 1 9 16.5v-7Z",
    "M15 8V6.5A1.5 1.5 0 0 0 13.5 5h-7A1.5 1.5 0 0 0 5 6.5v7A1.5 1.5 0 0 0 6.5 15H8",
  ],
  quote: [
    "M9.5 6.5C7 7.6 5.5 9.8 5.5 12.5v5h5v-5h-3c0-1.8.8-3.2 2.6-4.1Z",
    "M18.5 6.5c-2.5 1.1-4 3.3-4 6v5h5v-5h-3c0-1.8.8-3.2 2.6-4.1Z",
  ],
  // BUG-206 slice C. A page with a nib over its lower corner: the file family
  // that *changes* something, deliberately different at 16px from plain `file`.
  "file-edit": [
    "M13 3H7a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1v-8",
    "M13 3v4h4",
    "M20.5 6.5 15 12l-2.5.5.5-2.5 5.5-5.5a1.4 1.4 0 0 1 2 2Z",
  ],
  // A prompt inside a window: something ran.
  terminal: [
    "M3.5 5h17a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1h-17a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1Z",
    "M7 9.5 10 12l-3 2.5",
    "M12.5 15h5",
  ],
  // Meridians: the call left this machine for the open web.
  globe: [
    "M12 3.5a8.5 8.5 0 1 1 0 17 8.5 8.5 0 0 1 0-17Z",
    "M3.5 12h17",
    "M12 3.5c2.3 2.3 3.5 5.3 3.5 8.5s-1.2 6.2-3.5 8.5c-2.3-2.3-3.5-5.3-3.5-8.5s1.2-6.2 3.5-8.5Z",
  ],
  // Stacked bands with a mark on the top one: what Raiker kept, rather than
  // what it read once. Distinct from `checkpoints`, which is rewinding.
  memory: [
    "M4 7.5c0-1.4 3.6-2.5 8-2.5s8 1.1 8 2.5-3.6 2.5-8 2.5-8-1.1-8-2.5Z",
    "M4 7.5v9c0 1.4 3.6 2.5 8 2.5s8-1.1 8-2.5v-9",
    "M4 12c0 1.4 3.6 2.5 8 2.5s8-1.1 8-2.5",
  ],
  // A second, smaller figure behind the first: work delegated to another model.
  agent: [
    "M9.5 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z",
    "M3 19.5c1.2-2.7 3.6-4.2 6.5-4.2s5.3 1.5 6.5 4.2",
    "M16 6.2a2.6 2.6 0 0 1 0 5",
    "M17.5 15.6c1.4.7 2.5 1.9 3.2 3.4",
  ],
  // The neutral fallback: a spanner. Not a gear — `settings` is a gear, and an
  // unnamed tool row is not a settings row.
  more: ["M6 12h.01", "M12 12h.01", "M18 12h.01"],
  tool: [
    "M14.8 3.6a5 5 0 0 0-6 6.6l-5.2 5.2a2 2 0 0 0 0 2.8l2.2 2.2a2 2 0 0 0 2.8 0l5.2-5.2a5 5 0 0 0 6.6-6l-3.1 3.1-3-.6-.6-3 3.1-3.1Z",
  ],
  // A roof and a doorway. Home is where you land, and every product the owner
  // already uses draws that as a house.
  home: [
    "M3.6 10.8 12 4l8.4 6.8",
    "M6 9.6V19a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1V9.6",
  ],
  // A framed picture: the object Design works on is an image, and the frame is
  // the canvas boundary the mode is about. Deliberately not the spark — Design
  // is a place, not an agent action.
  design: [
    "M4 5h16a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1Z",
    "M10 10.2a1.6 1.6 0 1 1-3.2 0 1.6 1.6 0 0 1 3.2 0Z",
    "M3.4 16.6 9 12l3.8 3.4 3.2-2.7 4.6 4.3",
  ],
  // Three nodes and the edges between them. The Knowledge Map is a graph, and
  // the glyph says graph rather than "something clever happens here".
  map: [
    "M6 5.4a2.1 2.1 0 1 1 0 4.2 2.1 2.1 0 0 1 0-4.2Z",
    "M18 4.4a2.1 2.1 0 1 1 0 4.2 2.1 2.1 0 0 1 0-4.2Z",
    "M12 15.4a2.1 2.1 0 1 1 0 4.2 2.1 2.1 0 0 1 0-4.2Z",
    "M7.7 9.2 10.8 14.4",
    "M16.5 8.2 13.3 14.4",
  ],
};
