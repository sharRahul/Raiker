// SPDX-License-Identifier: Apache-2.0
// The Setup page (src/setup.ts). It only draws what the shell reports through
// `window.raikerSetup`; every value is set with textContent, never as markup.
//
// Opened in an ordinary browser (no bridge), `?fake=install` or `?fake=failure`
// plays a recorded run, so the screens can be reviewed without packaging.
"use strict";

const params = new URLSearchParams(window.location.search);
const mode = ["install", "update", "repair"].includes(params.get("mode")) ? params.get("mode") : "install";
const bridge = window.raikerSetup ?? fakeBridge(params.get("fake"));

const $ = (id) => document.getElementById(id);
const SCREENS = ["welcome", "progress", "ready", "failed"];
const TITLES = { install: "Setting up Raiker", update: "Updating Raiker", repair: "Checking Raiker" };
const ICONS = {
  done: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M5 10.5l3.2 3.2L15 7"/></svg>',
  failed: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M6 6l8 8M14 6l-8 8"/></svg>',
};
const LOG_LIMIT = 2000;

let stages = [];
const started = new Map();
const finished = new Map();
let lastChecks = [];
let ticker = null;

function show(screen) {
  document.body.dataset.screen = screen;
  for (const name of SCREENS) $(name).hidden = name !== screen;
  const focus = { welcome: "begin", ready: "open", failed: "retry" }[screen];
  if (focus) $(focus).focus();
}

function elapsed(ms) {
  const seconds = Math.max(0, Math.round(ms / 1000));
  if (seconds < 60) return `${seconds}s`;
  return `${Math.floor(seconds / 60)}m ${String(seconds % 60).padStart(2, "0")}s`;
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function renderStages() {
  const list = $("stages");
  list.replaceChildren();
  for (const stage of stages) {
    const item = el("li", "stage");
    item.id = `stage-${stage.id}`;
    item.dataset.state = "pending";
    const row = el("div", "stage-row");
    const icon = el("span", "icon pending");
    icon.append(el("span", "dot"));
    row.append(icon, el("span", "stage-title", stage.title), el("span", "stage-time", ""));
    const detail = el("div", "stage-detail");
    detail.hidden = true;
    row.append(detail);
    item.append(row);
    list.append(item);
  }
  updateCount();
}

function setStage(id, state, detail) {
  const item = $(`stage-${id}`);
  if (!item) return;
  item.dataset.state = state;
  const icon = item.querySelector(".icon");
  icon.className = `icon ${state}`;
  if (state === "running") {
    started.set(id, Date.now());
    icon.replaceChildren(el("span", "spinner"));
    item.setAttribute("aria-current", "step");
    item.scrollIntoView({ block: "nearest", behavior: "smooth" });
  } else {
    item.removeAttribute("aria-current");
    if (state === "done" || state === "failed") {
      finished.set(id, Date.now());
      icon.innerHTML = ICONS[state]; // fixed markup from this file, never data
    }
  }
  const line = item.querySelector(".stage-detail");
  line.hidden = !detail;
  line.textContent = detail ?? "";
  tick();
  updateCount();
}

function showChecks(checks, container) {
  container.replaceChildren();
  for (const check of checks) {
    const row = el("li", "check");
    row.dataset.state = check.state;
    const line = el("span", "check-line");
    line.title = `${check.label}: ${check.detail}`;
    line.append(el("span", "check-label", check.label), el("span", "check-detail", check.detail));
    row.append(line);
    if (check.remedy && (check.state === "warn" || check.state === "fail")) {
      row.append(el("span", "check-remedy", check.remedy));
    }
    container.append(row);
  }
  container.hidden = checks.length === 0;
}

function updateCount() {
  const done = stages.filter((stage) => $(`stage-${stage.id}`)?.dataset.state === "done").length;
  const percent = stages.length ? Math.round((done / stages.length) * 100) : 0;
  $("progress-count").textContent = `${done} of ${stages.length} steps complete · ${percent}%`;
  $("bar-fill").style.width = `${percent}%`;
  document.querySelector(".bar").setAttribute("aria-valuenow", String(percent));
}

// A long step shows its clock moving, so it never looks frozen.
function tick() {
  for (const stage of stages) {
    const item = $(`stage-${stage.id}`);
    if (!item || !started.has(stage.id)) continue;
    const end = finished.get(stage.id) ?? Date.now();
    item.querySelector(".stage-time").textContent = elapsed(end - started.get(stage.id));
  }
}

function appendLog(line) {
  const log = $("log");
  const atBottom = log.scrollTop + log.clientHeight >= log.scrollHeight - 4;
  const lines = (log.textContent ? `${log.textContent}\n${line}` : line).split("\n");
  log.textContent = lines.slice(-LOG_LIMIT).join("\n");
  if (atBottom) log.scrollTop = log.scrollHeight;
}

function begin() {
  started.clear();
  finished.clear();
  lastChecks = [];
  $("log").textContent = "";
  $("progress-title").textContent = TITLES[mode];
  show("progress");
  clearInterval(ticker);
  ticker = setInterval(tick, 1000);
}

bridge.onEvent((event) => {
  if (typeof event !== "object" || event === null) return;
  switch (event.type) {
    case "manifest":
      begin();
      stages = Array.isArray(event.stages) ? event.stages : [];
      renderStages();
      break;
    case "stage":
      setStage(event.id, event.state, event.detail);
      break;
    case "checks": {
      lastChecks = Array.isArray(event.checks) ? event.checks : [];
      const item = $("stage-check");
      if (!item) break;
      let list = item.querySelector(".checks");
      if (!list) {
        list = el("ul", "checks");
        list.setAttribute("aria-label", "This computer");
        item.append(list);
      }
      showChecks(lastChecks.filter((check) => check.state !== "info" || check.id === "gpu"), list);
      break;
    }
    case "log":
      appendLog(String(event.line ?? ""));
      break;
    case "complete": {
      clearInterval(ticker);
      const notes = $("ready-notes");
      notes.replaceChildren();
      for (const check of lastChecks.filter((item) => item.state === "warn")) {
        const note = el("li");
        note.append(el("strong", "", `${check.label}: `), document.createTextNode(check.remedy || check.detail));
        notes.append(note);
      }
      notes.hidden = notes.childElementCount === 0;
      if (mode !== "install") {
        $("ready-lead").textContent = "Every part of Raiker was checked and it is running on this computer.";
      }
      show("ready");
      break;
    }
    case "failed":
      clearInterval(ticker);
      {
        const failedChecks = event.stage === "check" ? lastChecks.filter((check) => check.state === "fail") : [];
        // A failed requirement is listed with its remedy; the headline only frames it.
        $("failed-cause").textContent = failedChecks.length
          ? "This computer doesn't meet Raiker's requirements yet. Fix what's listed below, then try again."
          : String(event.cause ?? "");
        $("failed-detail").textContent = String(event.detail ?? "");
        showChecks(failedChecks, $("failed-checks"));
      }
      show("failed");
      break;
    default:
      break;
  }
});

$("begin").addEventListener("click", () => bridge.send("start"));
$("retry").addEventListener("click", () => bridge.send("retry"));
$("open").addEventListener("click", () => {
  $("open").disabled = true;
  $("open").textContent = "Opening…";
  bridge.send("open");
});
$("logs").addEventListener("click", () => bridge.send("logs"));
$("quit").addEventListener("click", () => bridge.send("quit"));
$("cancel").addEventListener("click", () => bridge.send("quit"));
$("toggle-log").addEventListener("click", () => {
  const pane = $("log-pane");
  pane.hidden = !pane.hidden;
  $("toggle-log").setAttribute("aria-expanded", String(!pane.hidden));
  $("toggle-log").textContent = pane.hidden ? "Show details" : "Hide details";
});

// An update or a repair has nothing to welcome anyone to: it begins at once.
if (mode === "install") show("welcome");
else bridge.send("start");

/** A recorded run, for reviewing the screens in a browser. */
function fakeBridge(kind) {
  let listener = () => {};
  const checks = [
    { id: "os", label: "Operating system", state: "pass", detail: "Windows 11 Pro 23H2" },
    { id: "arch", label: "Architecture", state: "pass", detail: "x86-64" },
    { id: "memory", label: "Memory", state: kind === "failure" ? "fail" : "pass", detail: kind === "failure" ? "3.2 GB" : "16.0 GB", remedy: "Raiker needs at least 4 GB of memory." },
    { id: "cpu", label: "Processor", state: "pass", detail: "8 logical cores" },
    { id: "storage", label: "Free storage", state: "warn", detail: "14.2 GB free where Raiker keeps data", remedy: "Enough for Raiker; local models need 20 GB or more." },
    { id: "network", label: "Network", state: "pass", detail: "A network route is available" },
    { id: "credentials", label: "Credential protection", state: "pass", detail: "Windows data protection (DPAPI)" },
    { id: "gpu", label: "Graphics acceleration", state: "info", detail: "NVIDIA GeForce RTX 3060" },
  ];
  const script = [
    [300, { type: "manifest", stages: [
      { id: "check", title: "Checking this computer" },
      { id: "start", title: "Preparing encrypted storage and starting Raiker" },
      { id: "verify", title: "Verifying the installation" },
    ] }],
    [100, { type: "stage", id: "check", state: "running" }],
    [200, { type: "log", line: "Checking this computer…" }],
    [1400, { type: "checks", checks }],
    ...(kind === "failure"
      ? [[300, { type: "stage", id: "check", state: "failed", detail: "1 requirement is not met" }],
         [200, { type: "failed", stage: "check", cause: "Raiker needs at least 4 GB of memory.", detail: "blocking: memory" }]]
      : [[300, { type: "stage", id: "check", state: "done", detail: "Ready · 1 note" }],
         [100, { type: "stage", id: "start", state: "running" }],
         [2600, { type: "stage", id: "start", state: "done", detail: "Running on this computer only" }],
         [100, { type: "stage", id: "verify", state: "running" }],
         [900, { type: "stage", id: "verify", state: "done", detail: "Encrypted store open, fts5 search ready, interface served." }],
         [400, { type: "complete" }]]),
  ];
  return {
    onEvent(next) {
      listener = next;
    },
    send(action) {
      if (action !== "start" && action !== "retry") return;
      let at = 0;
      for (const [delay, event] of script) {
        at += delay;
        setTimeout(() => listener(event), at);
      }
    },
  };
}
