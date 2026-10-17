// SPDX-License-Identifier: Apache-2.0
// The shell's own page: shown while the host starts, or when the window cannot
// show Raiker. The message is set with textContent, never as markup.
const params = new URLSearchParams(window.location.search);
const state = params.get("state") === "error" ? "error" : "starting";
document.body.dataset.state = state;
document.getElementById("title").textContent =
  state === "error" ? "Raiker is not available" : "Starting Raiker";
document.getElementById("message").textContent = params.get("message") ?? "";
document.getElementById("spinner").hidden = state !== "starting";
