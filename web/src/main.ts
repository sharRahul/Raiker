import { mount } from "svelte";
import App from "./App.svelte";
import { applyTheme, loadThemeChoice } from "./lib/theme";
import { startDesktopShell } from "./lib/desktopShell";
import "./app.css";

// Apply the stored theme before mounting so there is no flash of the wrong theme.
applyTheme(loadThemeChoice());
// In Raiker's desktop window, mark the document before the first frame so the
// window chrome is right from the start; in a browser this does nothing.
startDesktopShell();

const target = document.getElementById("app");
if (!target) {
  throw new Error("Root element #app not found");
}

const app = mount(App, { target });

export default app;
