import { describe, expect, it } from "vitest";
import { ApiError } from "./api";
import { failure, NOT_ANSWERING } from "./errorCopy";

describe("failure (QUI-G06)", () => {
  it("names what failed, what it affected and one next step, with the status as evidence", () => {
    const error = new ApiError(500, null, "boom");
    expect(failure("Stop was not sent", "The turn is still running.", "Try again.", error)).toBe(
      "Stop was not sent (HTTP 500). The turn is still running. Try again.",
    );
  });

  it("says Raiker did not answer when the request never reached it", () => {
    expect(failure("Stop was not sent", "The turn is still running.", "Try again.", new TypeError("fetch failed"))).toBe(
      `Stop was not sent. The turn is still running. ${NOT_ANSWERING}`,
    );
  });

  it("works without an error object", () => {
    expect(failure("Nothing was found", "No file was attached.", "Check the path.")).toBe(
      "Nothing was found. No file was attached. Check the path.",
    );
  });
});

describe("retired error copy (QUI-G06)", () => {
  it("no longer blames 'the local runtime' or reports a bare status", async () => {
    const { readdirSync, readFileSync, statSync } = await import("node:fs");
    const { join, resolve } = await import("node:path");
    const walk = (dir: string, out: string[] = []): string[] => {
      for (const name of readdirSync(dir)) {
        const path = join(dir, name);
        if (statSync(path).isDirectory()) walk(path, out);
        else if (/\.(svelte|ts)$/.test(name) && !name.includes(".test.")) out.push(path);
      }
      return out;
    };
    const retired = [/["`][^"`\n]*reach the local runtime/, /["`][^"`\n]*local runtime is unreachable/, /`(Stop|Steer) failed \(/];
    const found = walk(resolve(process.cwd(), "src")).flatMap((file) => {
      const text = readFileSync(file, "utf8");
      return retired.filter((pattern) => pattern.test(text)).map((pattern) => `${file}: ${pattern}`);
    });
    expect(found).toEqual([]);
  });
});
