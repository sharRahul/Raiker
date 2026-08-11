# Cross-Platform Manual Release Design

**Status:** Approved for implementation on 2026-08-11

## Goal

Make `.github/workflows/release.yml` reliably build a complete Raiker release for
macOS, Windows, and Linux while preserving deliberate manual dispatch, explicit
signing gates, and a draft-release review step.

## Existing state and defects

The workflow already uses `workflow_dispatch`, reads its four-target matrix from
`raiker.app.release.TARGETS`, builds platform installers, and can create a draft
GitHub release. Four details keep that design from being dependable:

1. The Intel target still selects `macos-13`, a GitHub-hosted runner retired on
   2025-12-04. It must use the supported `macos-15-intel` label.
2. The Windows installer invokes the PyInstaller desktop build, but matrix jobs
   install only Raiker's runtime dependencies. PyInstaller is in the `dev` extra.
3. GitHub's Linux runner does not guarantee FUSE support for a downloaded
   `appimagetool` AppImage. The build must opt into AppImage extraction mode.
4. `actions/upload-artifact` and `actions/download-artifact` use mutable major
   tags, the open BUG-49 supply-chain gap.

## Release contract

The workflow remains `workflow_dispatch` only. No `push`, tag, schedule, or
`workflow_call` trigger may publish or build a release implicitly.

One manual run covers these targets:

| Target | Runner | Installer output |
|---|---|---|
| macOS Apple Silicon | `macos-14` | `.pkg` |
| macOS Intel | `macos-15-intel` | `.pkg` |
| Windows x86-64 | `windows-2022` | `.msi` |
| Linux x86-64 | `ubuntu-22.04` | `.deb` and `.AppImage` |

The workflow retains the existing inputs:

- `version`: required `X.Y.Z` release version;
- `channel`: `stable` or `beta`;
- `signing`: `require` by default or `skip` for explicitly unsigned test builds;
- `publish`: false by default.

When `publish=false`, successful target artifacts and the verified channel are
available as workflow artifacts. When `publish=true`, the workflow may create a
GitHub release only if `signing=require` and every target, manifest, signature,
and channel check succeeds. The resulting GitHub release remains a **draft** for
human review. The workflow never publishes a public release automatically.

## Build and signing flow

The plan job validates inputs, refuses unsigned publication, emits the target
matrix, and fixes `SOURCE_DATE_EPOCH` to the selected commit. The web job builds
the frontend once. Each matrix runner installs `.[dev]`, resolves native wheels,
builds the reproducible payload twice, performs the packaging smoke test, wraps
the payload in that operating system's installer, and applies the configured
platform signature.

The Linux installer step sets `APPIMAGE_EXTRACT_AND_RUN=1`, allowing the official
`appimagetool` AppImage to run without a FUSE mount. This does not alter the
generated application image.

The channel job refuses a missing target, signs the update index, and verifies it
using the same Raiker verifier used by installed clients. The publish job
downloads that complete verified directory and calls `gh release create --draft`.

All uses of `actions/upload-artifact` and `actions/download-artifact` are pinned
to resolved v4 commit digests. No mutable major tag remains in the workflow.

## Failure behavior

- A retired/unavailable runner fails its target and prevents the channel job.
- A missing platform identity fails when `signing=require`.
- `signing=skip` names artifacts as unsigned and cannot reach the publish job.
- Missing PyInstaller, WiX, `pkgbuild`, `dpkg-deb`, or `appimagetool` fails the
  owning target without allowing a partial release.
- A missing target artifact, non-reproducible payload, failed smoke test,
  invalid signature, or invalid channel prevents draft creation.
- Existing release tags continue to make `gh release create` fail rather than
  overwrite an existing release.

## Verification

Add workflow contract tests that parse `release.yml` and prove:

- `workflow_dispatch` is its only trigger;
- the publish job is gated by `publish` and required signing and creates a draft;
- the matrix covers macOS ARM64 and Intel, Windows x86-64, and Linux x86-64;
- the Intel runner is `macos-15-intel`;
- matrix jobs install the desktop build dependency;
- Linux installer execution uses AppImage extraction mode;
- artifact actions are pinned to 40-character commit digests.

Run the focused release tests, the full Python suite, Ruff, MyPy, compilation,
licensing, phase validation, and workflow YAML parsing. After pushing, require all
automatically triggered workflows for the final SHA to be green and confirm via
GitHub CLI that Release remains enabled and manually dispatchable. Do not invoke
the release workflow or create a GitHub release as part of this change.

## Documentation

Update `docs/DESKTOP_DISTRIBUTION_DESIGN.md` to use the supported Intel runner.
Move BUG-49 from `docs/plans/TO_BE_FIXED.md` to the existing format in
`docs/plans/FIXED_ITEMS.md`, recording the immutable action digests and workflow
contract evidence. README changes are unnecessary because the user-facing
installation and first-run behavior do not change.
