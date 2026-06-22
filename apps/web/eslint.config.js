import js from "@eslint/js";
import svelte from "eslint-plugin-svelte";
import globals from "globals";
import ts from "typescript-eslint";

export default [
  { ignores: ["dist/", "node_modules/", ".svelte-kit/"] },
  js.configs.recommended,
  ...ts.configs.recommended,
  ...svelte.configs["flat/recommended"],
  {
    languageOptions: {
      globals: { ...globals.browser, ...globals.node },
    },
  },
  {
    files: ["**/*.svelte"],
    languageOptions: {
      parserOptions: { parser: ts.parser },
    },
  },
  {
    files: ["**/*.test.ts", "src/test-setup.ts"],
    languageOptions: { globals: { ...globals.node } },
  },
];
