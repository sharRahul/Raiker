import { mount } from "svelte";
import App from "./App.svelte";
import { applyTheme, loadThemeChoice } from "./lib/theme";
import "./app.css";

// Apply the stored theme before mounting so there is no flash of the wrong theme.
applyTheme(loadThemeChoice());

const target = document.getElementById("app");
if (!target) {
  throw new Error("Root element #app not found");
}

const app = mount(App, { target });

export default app;
