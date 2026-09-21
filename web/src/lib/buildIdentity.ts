/**
 * Which Raiker this page is, and which Raiker is answering it.
 *
 * GCR-16 — there were four independent version numbers: the Python package's
 * `0.0.0`, the FastAPI application's `0.1.0`, the `0.0.0` every recorded turn
 * carried as its client version, and this package's own `0.0.0`. A support
 * question as ordinary as *what are you running* had four answers, and which
 * one you got depended on which surface you read.
 *
 * The host now reports one identity, resolved from the record the release build
 * wrote inside the artifact. This module carries the other half: the identity of
 * the bundle the browser is actually executing, stamped in at build time by
 * `vite.config.ts`. They are separate on purpose — a browser holding a cached
 * bundle from before an update is the one case neither number can describe
 * alone.
 */

declare const __RAIKER_CLIENT_BUILD__: string;

/** The placeholder a tree that has never been released reports, everywhere. */
export const UNRELEASED = "0.0.0";

/** The version of the bundle this page is running. */
export const clientBuild: string =
  typeof __RAIKER_CLIENT_BUILD__ === "string" ? __RAIKER_CLIENT_BUILD__ : UNRELEASED;

/** How a build identity is written wherever one is shown. */
export function describeBuild(version: string, commit: string | null): string {
  if (version === UNRELEASED) return commit ? `Unreleased build (${commit.slice(0, 7)})` : "Unreleased build";
  return commit ? `${version} (${commit.slice(0, 7)})` : version;
}

/**
 * Whether the page and the host are running different releases.
 *
 * Only ever true once both have a release to name: two unreleased builds are
 * two development checkouts, and saying they disagree would put a warning on
 * every developer's screen for ever.
 *
 * `page` is the build of the bundle being judged; it defaults to this one and
 * is a parameter so the rule can be proved for a released client, which a
 * development test build can never be.
 */
export function clientIsStale(hostVersion: string, page: string = clientBuild): boolean {
  if (hostVersion === UNRELEASED || page === UNRELEASED) return false;
  return hostVersion !== page;
}
