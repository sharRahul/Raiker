import "@testing-library/jest-dom/vitest";
import { afterEach } from "vitest";
import { resetModels } from "./lib/models.svelte";

// The model-profiles store is a module-level singleton, so without an explicit
// reset it leaks the previous test's snapshot into the next case (a picker would
// briefly show a stale "selected" model until its own refresh resolves). Clear
// it after every test so each case starts from the empty default.
afterEach(() => resetModels());
