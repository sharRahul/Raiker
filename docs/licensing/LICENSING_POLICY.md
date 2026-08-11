# Licensing policy

Raiker distributions from the licensing-change commit onward are licensed under
the [Apache License 2.0](../../LICENSE). The root [NOTICE](../../NOTICE) carries
the project-level notice. Earlier versions released under MIT remain available
under their original terms.

## Source and contributions

New first-party Python scripts must begin with
`SPDX-License-Identifier: Apache-2.0` (after a shebang or encoding declaration
when present). Existing source files receive a header when materially modified;
headers are not added to JSON, lockfiles, generated outputs, snapshots,
fixtures, compiled assets, or third-party files. Do not remove third-party
notices or add ownership claims without evidence.

Contributions are submitted under Apache-2.0 as described in
[CONTRIBUTING.md](../../CONTRIBUTING.md); no sign-off trailer or Contributor
License Agreement is required. Raise licensing questions through a private
security report or a repository issue that contains no sensitive information.

## Dependencies and notices

Dependencies retain their own licences. Generated files and SBOMs are not
project copyright notices. Vendored or copied material must retain its licence
and attribution; the bundled fonts remain under the SIL OFL 1.1 with the
copyright notices and full licence text in
`apps/web/src/assets/fonts/OFL.txt`, summarised in
`apps/web/src/assets/fonts/LICENSE.md`.

`LICENSE_POLICY.json` is the machine-readable dependency policy. Permissive
licences in `permitted` pass. MPL and LGPL require review in context (for
example, optional tooling, dynamic linking, test-only use, and distribution);
they are not automatically prohibited. GPL, AGPL, proprietary, custom,
UNKNOWN, and NOASSERTION values fail unless a narrow, documented exception is
added. A dual-licensed dependency passes only when at least one offered licence
is permitted. The current exceptions cover unmodified transitive `certifi`
under MPL-2.0 (a CA bundle), development-only `pathspec` under MPL-2.0,
Lightning CSS's Vite 8/Rolldown build packages, the unmodified LGPL-3.0
`pystray` runtime (whose complete licence files remain in the frozen payload),
its unmodified LGPL-2.1-or-later `python-xlib` Linux backend, development-only
PyInstaller under its official bootloader distribution exception, and a
build-only setuptools release whose metadata reports `NOASSERTION`. Pillow's
MIT-CMU licence is accepted as permissive. None of the
reviewed dependency source is modified by Raiker. The zero-clause BSD licence
(`0BSD`) is accepted as permissive.

Run the checks after installing Python and web dependencies:

```bash
python scripts/licensing_check.py --sbom artifacts/licensing/raiker.spdx.json
python -m build
python scripts/licensing_check.py --dist-dir dist
```

The SPDX JSON SBOM is written to the path supplied with `--sbom`; `artifacts/`
and `dist/` are local build output and are not committed.
