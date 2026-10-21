# 05 Raiker Browser

Part of the [Quiet UI redesign plan](README.md). Proposed, 2026-10-21.

## Starting point

The desktop app is an Electron 44 shell (`desktop/package.json`), and Electron
is Chromium. A built-in browser needs no new engine and no extra download. Today
the shell deliberately sends every outside link to the system browser
(`desktop/src/main.ts`, `shell.openExternal` in `route()`) and blocks embedded
web views (`will-attach-webview`). Web reads in the runtime go through
`raiker/runtime/web_access.py` (`WebAccessService`: HTTPS, private-address
guard, blocklist, checked redirects) via `tier2_web.py`.

The browser is a controlled browsing surface inside a task, not a second general
browser product and not an import of the owner's personal browser profile.

## Layout

* Opens as a **tab inside the task**, beside the conversation. The chat keeps
  running; the browser takes the work area. At 1,280 px the chat collapses to a
  360 px column.
* Top bar, always visible: site identity, **Temporary session** or **Signed in
  (kept)**, and who is in control: **Raiker is browsing** / **You are browsing**,
  with **Take over** / **Hand back**.
* Activity list beside the page: every step ("Opened search", "Typed …",
  "Waiting: sign-in needed"). It becomes part of the task's activity.
* Hand-off banner when Raiker must stop: "You need to sign in to booking.com.
  Raiker never sees your password. Sign in myself."

## How it works

* **One isolated session per site.** Each site gets its own Electron session
  partition: in memory by default, persisted only after "Keep me signed in on
  this site". Nothing is shared with or imported from the owner's Chrome, Edge
  or Safari: no cookies, passwords, history, extensions or profiles.
* **Same network rules as web reads.** Browser partitions route through the
  host's egress controls, so the browser cannot reach anything `web_fetch`
  cannot.
* **Driven by the shell, governed by the host.** The shell drives the page
  through Chromium's DevTools protocol (`webContents.debugger`). Each action is a
  governed action, so profiles, permissions and approval cards apply exactly as
  in chat. Reading, scrolling, searching and filling fields within limits
  proceed; submitting, buying, posting and sending ask first.
* **Hard limits, enforced in the shell.** No reading of password fields; no
  filling of payment details; stop and hand over at sign-in, multi-factor
  prompts, CAPTCHAs, account recovery and checkout. Third-party pages get no
  preload, no Node integration and no access to the app.
* **Take over** stops Raiker's actions at once. **Hand back** records what the
  owner changed.
* **Downloads** go to a per-task folder and are listed in the activity before
  Raiker opens them.
* **Site permissions** (camera, microphone, location, notifications) are refused
  unless the owner allows them for that site.

## Where the system browser stays

* **Connecting accounts** (Google, GitHub, ChatGPT sign-in). Google blocks OAuth
  in embedded browsers, and RFC 8252 (OAuth for native apps) requires the system
  browser so the app never handles the password. The sign-in returns to Raiker
  automatically.
* **The web app** (Raiker in the owner's own browser, or on a VPS) cannot show
  other sites inside its page, because most sites forbid embedding. There the
  browser runs on the host with a live view streamed into Raiker: an optional,
  heavier add-on (a host-side Chromium, roughly 150 MB), delivered after the
  desktop version.

## Delivery

| ID | Step | Scope |
|---|---|---|
| QUI-B01 | View only | Open a page inside a task and browse it yourself, in a temporary session. Links in answers open here instead of the system browser. |
| QUI-B02 | Raiker browses | Read, scroll, search and fill fields with limits; the activity list; Take over. Submit and send go through approval cards. |
| QUI-B03 | Kept sign-ins | Encrypted per-site sessions after explicit consent; "Clear this site" in Settings › Web access. |
| QUI-B04 | Web app and VPS | Host-side Chromium with a streamed view, as an optional add-on. |

A credential broker backed by the OS keychain comes only if a real need appears
after B03.

## Acceptance

* No browser session shares storage with another site or with the app's own
  session.
* Every browser action appears in the task activity with the approval that
  allowed it.
* The shell refuses any DOM read of a password field, whatever the request.
* Take over stops automation within one action.
