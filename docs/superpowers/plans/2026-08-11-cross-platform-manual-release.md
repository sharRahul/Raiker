# Cross-Platform Manual Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the manually dispatched Release workflow reliably build signed or explicitly unsigned artifacts for macOS, Windows, and Linux and create only a signed draft GitHub release.

**Architecture:** Keep `raiker.app.release.TARGETS` as the target source of truth and `.github/workflows/release.yml` as the manual runner/signing wrapper. Add a parsed-YAML contract test for trigger, publication, build-tool, Linux AppImage, and immutable-action invariants; update the retired runner and workflow defects without changing release payload semantics.

**Tech Stack:** GitHub Actions YAML, Python 3.11, PyYAML, pytest, PyInstaller, WiX, pkgbuild/productsign/notarytool, dpkg-deb, appimagetool, GitHub CLI.

## Global Constraints

- `.github/workflows/release.yml` must contain `workflow_dispatch` as its only trigger.
- A GitHub release must remain a draft and require `publish=true` plus `signing=require`.
- `signing=skip` may build explicitly unsigned workflow artifacts but must never create a GitHub release.
- Targets remain macOS ARM64, macOS Intel, Windows x86-64, and Linux x86-64.
- Use `macos-15-intel` for macOS Intel; retain `macos-14`, `windows-2022`, and `ubuntu-22.04` for the other targets.
- Artifact actions must be pinned to resolved 40-character commit digests.
- Do not dispatch the Release workflow or create a GitHub release during verification.

---

### Task 1: Encode the release workflow contract

**Files:**
- Create: `tests/test_release_workflow.py`
- Modify: `tests/test_release_pipeline.py`

**Interfaces:**
- Consumes: `.github/workflows/release.yml` as YAML and `raiker.app.release.TARGETS_BY_ID`.
- Produces: regression assertions for manual dispatch, draft-only publishing, all four targets, build dependencies, AppImage extraction, and immutable artifact actions.

- [ ] **Step 1: Write the failing workflow contract tests**

Create a test module that loads the workflow with `yaml.BaseLoader`, flattens all job steps, and asserts:

```python
assert set(workflow["on"]) == {"workflow_dispatch"}
assert "inputs.publish" in workflow["jobs"]["publish"]["if"]
assert "inputs.signing == 'require'" in workflow["jobs"]["publish"]["if"]
assert "--draft" in create_release_step["run"]
assert TARGETS_BY_ID["macos-x86_64"].runner == "macos-15-intel"
assert 'python -m pip install -e ".[dev]"' in install_step["run"]
assert native_installer_step["env"]["APPIMAGE_EXTRACT_AND_RUN"] == "1"
assert all(re.fullmatch(r"actions/(upload|download)-artifact@[0-9a-f]{40}", use) for use in artifact_uses)
```

Extend the existing matrix test to assert the exact runner mapping for all four targets.

- [ ] **Step 2: Run the tests and verify the intended failures**

Run: `python -m pytest tests/test_release_workflow.py tests/test_release_pipeline.py -q`

Expected: failures for `macos-13`, runtime-only installation, missing AppImage extraction mode, and mutable `@v4` artifact action references.

- [ ] **Step 3: Keep the red tests local**

Do not push a red commit. Inline execution keeps the tests uncommitted until Task 2 is green.

---

### Task 2: Repair the cross-platform workflow

**Files:**
- Modify: `raiker/app/release.py`
- Modify: `.github/workflows/release.yml`
- Modify: `docs/DESKTOP_DISTRIBUTION_DESIGN.md`
- Test: `tests/test_release_workflow.py`
- Test: `tests/test_release_pipeline.py`

**Interfaces:**
- Consumes: the Task 1 workflow contract.
- Produces: a manual workflow whose matrix can build `.pkg`, `.msi`, `.deb`, and `.AppImage` artifacts and whose draft job receives the complete verified channel.

- [ ] **Step 1: Replace the retired Intel runner**

Change only the `macos-x86_64` target runner from `macos-13` to `macos-15-intel` in `TARGETS`; update the desktop distribution table to match.

- [ ] **Step 2: Install the desktop build dependency**

In the matrix build job, use:

```yaml
- name: Install package and desktop build tool
  run: python -m pip install -e ".[dev]"
```

Keep the plan and channel jobs on runtime-only installation because they do not invoke PyInstaller.

- [ ] **Step 3: Make AppImage tooling runner-safe**

Set the native-installer step environment without changing non-Linux behavior:

```yaml
env:
  APPIMAGE_EXTRACT_AND_RUN: ${{ matrix.os == 'linux' && '1' || '0' }}
```

The existing `scripts/build_installer.py` subprocess inherits the value when it launches `appimagetool`.

- [ ] **Step 4: Pin artifact actions immutably and close the stale warning**

Replace every upload reference with:

```yaml
uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02
```

Replace every download reference with:

```yaml
uses: actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093
```

Update comments to identify the v4 major line and remove the top-of-file BUG-49 deviation note.

- [ ] **Step 5: Run focused workflow and release tests**

Run: `python -m pytest tests/test_release_workflow.py tests/test_release_pipeline.py tests/test_desktop_build.py -q`

Expected: all pass.

- [ ] **Step 6: Validate YAML and Python quality**

Run:

```powershell
python -c "from pathlib import Path; import yaml; data=yaml.load(Path('.github/workflows/release.yml').read_text(encoding='utf-8'), Loader=yaml.BaseLoader); assert set(data['on']) == {'workflow_dispatch'}"
python -m ruff check raiker/app/release.py tests/test_release_workflow.py tests/test_release_pipeline.py
python -m mypy raiker/app/release.py
```

Expected: all exit zero.

- [ ] **Step 7: Commit the green workflow implementation**

```powershell
git add -- .github/workflows/release.yml raiker/app/release.py tests/test_release_workflow.py tests/test_release_pipeline.py docs/DESKTOP_DISTRIBUTION_DESIGN.md
git commit -m "fix: make manual releases cross-platform"
```

---

### Task 3: Record BUG-49 resolution and acceptance

**Files:**
- Modify: `docs/plans/TO_BE_FIXED.md`
- Modify: `docs/plans/FIXED_ITEMS.md`

**Interfaces:**
- Consumes: immutable artifact action pins and passing workflow contract tests from Task 2.
- Produces: issue ledgers consistent with the repository's existing table and detailed-section format.

- [ ] **Step 1: Move BUG-49 to the fixed ledger**

Remove the BUG-49 summary row and full open section from `TO_BE_FIXED.md`. Add FIXED-179 to the fixed summary table and a detailed section stating the mutable references, resolved v4 commit digests, and regression evidence.

- [ ] **Step 2: Run documentation and repository hygiene checks**

Run:

```powershell
git diff --check
python scripts/validate_phase_status.py
python scripts/licensing_check.py --sbom artifacts/licensing/raiker.spdx.json
```

Expected: all exit zero and BUG-49 appears only as a resolved historical reference.

- [ ] **Step 3: Commit the acceptance documentation**

```powershell
git add -- docs/plans/TO_BE_FIXED.md docs/plans/FIXED_ITEMS.md
git commit -m "docs: close release action pinning gap"
```

---

### Task 4: Final verification and publication

**Files:**
- Force-add: `docs/superpowers/plans/2026-08-11-cross-platform-manual-release.md`

**Interfaces:**
- Consumes: the complete implementation and documentation commits.
- Produces: a clean `origin/main`, green required workflows, and a registered manual Release workflow.

- [ ] **Step 1: Run the complete local release gate**

Run the full Python suite with a short external Windows temp path, then Ruff, MyPy, compileall, phase validation, licensing, web lint/check/test/build, and the mocked Playwright suite. Expected: every command exits zero.

- [ ] **Step 2: Audit and commit the implementation plan**

Force-add this intentionally ignored plan only. Run `git diff --cached --check`, verify no credential patterns or generated build directories are staged, and commit any remaining plan-only change.

- [ ] **Step 3: Push and monitor**

Push `main` to `origin/main`. Monitor every automatically triggered workflow for the final SHA; diagnose and repair any failure before completion. Also verify the immediately preceding implementation SHA's path-filtered Web UI run when the final documentation-only or Python-only commit does not trigger it.

- [ ] **Step 4: Confirm manual Release registration without dispatching it**

Run `gh workflow view release.yml --yaml` and `gh workflow list` to prove GitHub recognizes the workflow and it remains active with only `workflow_dispatch`. Do not call `gh workflow run`.
