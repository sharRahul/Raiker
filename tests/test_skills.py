"""Skill packaging and the owner-scoped skill store.

The package reader is the trust boundary for an uploaded file, so its refusals
matter as much as its successes: a zip that escapes its own directory, a
document with no description, and an oversized archive all have to fail closed
before anything is written.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.skills.package import (
    SkillValidationError,
    build_bundle,
    bundle_from_directory,
    parse_frontmatter,
    read_bundle_member,
    read_package,
    read_skill_bundle,
    read_skill_md,
)
from raiker.skills.service import SkillsService, normalize_import_url

VALID_DOCUMENT = """---
name: tidy-imports
description: Sort and dedupe imports. Use when asked to tidy imports.
version: 1.2.0
---

# Tidy imports

Sort them.
"""


def _bundle(members: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    return buffer.getvalue()


class TestFrontmatter:
    def test_reads_flat_scalar_fields(self) -> None:
        fields = parse_frontmatter(VALID_DOCUMENT)
        assert fields["name"] == "tidy-imports"
        assert fields["version"] == "1.2.0"

    def test_document_without_frontmatter_has_no_fields(self) -> None:
        assert parse_frontmatter("# Just a heading\n") == {}

    def test_quotes_are_stripped(self) -> None:
        fields = parse_frontmatter('---\nname: "quoted"\ndescription: \'also\'\n---\n')
        assert fields["name"] == "quoted"
        assert fields["description"] == "also"


class TestReadSkillMd:
    def test_valid_document_becomes_a_package(self) -> None:
        package = read_skill_md(VALID_DOCUMENT)
        assert package.name == "tidy-imports"
        assert package.version == "1.2.0"
        assert package.description.startswith("Sort and dedupe")
        assert package.checksum
        assert package.bundle is None

    def test_missing_description_is_refused(self) -> None:
        with pytest.raises(SkillValidationError) as exc:
            read_skill_md("---\nname: nameless\n---\nbody\n")
        assert exc.value.reason == "skill_missing_description"

    def test_invalid_name_is_refused(self) -> None:
        with pytest.raises(SkillValidationError) as exc:
            read_skill_md("---\nname: Not A Slug\ndescription: x\n---\nbody\n")
        assert exc.value.reason == "skill_invalid_name"

    def test_filename_supplies_a_name_only_when_frontmatter_omits_one(self) -> None:
        package = read_package("my-skill.md", b"---\ndescription: does a thing\n---\nbody\n")
        assert package.name == "my-skill"

    def test_document_named_skill_md_cannot_borrow_its_filename(self) -> None:
        with pytest.raises(SkillValidationError) as exc:
            read_package("SKILL.md", b"---\ndescription: does a thing\n---\nbody\n")
        assert exc.value.reason == "skill_invalid_name"

    def test_empty_document_is_refused(self) -> None:
        with pytest.raises(SkillValidationError) as exc:
            read_skill_md("   \n")
        assert exc.value.reason == "skill_empty"


class TestReadSkillBundle:
    def test_archive_with_skill_md_is_accepted(self) -> None:
        package = read_skill_bundle(
            _bundle({"tidy-imports/SKILL.md": VALID_DOCUMENT, "tidy-imports/notes.md": "x"})
        )
        assert package.name == "tidy-imports"
        assert set(package.files) == {"tidy-imports/SKILL.md", "tidy-imports/notes.md"}
        assert package.bundle is not None

    def test_archive_without_skill_md_is_refused(self) -> None:
        with pytest.raises(SkillValidationError) as exc:
            read_skill_bundle(_bundle({"thing/README.md": "hello"}))
        assert exc.value.reason == "skill_missing_skill_md"

    def test_non_archive_is_refused(self) -> None:
        with pytest.raises(SkillValidationError) as exc:
            read_skill_bundle(b"not a zip at all")
        assert exc.value.reason == "skill_not_an_archive"

    def test_parent_directory_escape_is_refused(self) -> None:
        with pytest.raises(SkillValidationError) as exc:
            read_skill_bundle(_bundle({"../escape/SKILL.md": VALID_DOCUMENT}))
        assert exc.value.reason == "skill_unsafe_member_path"

    def test_absolute_member_is_refused(self) -> None:
        with pytest.raises(SkillValidationError) as exc:
            read_skill_bundle(_bundle({"/etc/passwd": "root"}))
        assert exc.value.reason == "skill_unsafe_member_path"

    def test_oversized_archive_is_refused_before_reading(self) -> None:
        with pytest.raises(SkillValidationError) as exc:
            read_skill_bundle(b"\x00" * (2 * 1024 * 1024 + 1))
        assert exc.value.reason == "skill_too_large"

    def test_unsupported_extension_is_refused(self) -> None:
        with pytest.raises(SkillValidationError) as exc:
            read_package("payload.exe", b"MZ")
        assert exc.value.reason == "skill_unsupported_file_type"


class TestBuildBundle:
    def test_uploaded_archive_comes_back_byte_for_byte(self) -> None:
        raw = _bundle({"tidy-imports/SKILL.md": VALID_DOCUMENT})
        assert build_bundle(read_skill_bundle(raw)) == raw

    def test_bare_document_is_packed_on_demand(self) -> None:
        packed = build_bundle(read_skill_md(VALID_DOCUMENT))
        with zipfile.ZipFile(io.BytesIO(packed)) as archive:
            assert archive.namelist() == ["tidy-imports/SKILL.md"]


class TestBundleMembers:
    def test_a_member_is_readable_by_its_full_name(self) -> None:
        raw = _bundle({"tidy/SKILL.md": VALID_DOCUMENT, "tidy/references/x.md": "detail"})
        assert read_bundle_member(raw, "tidy/references/x.md") == "detail"

    def test_a_member_is_readable_by_its_path_within_the_skill(self) -> None:
        raw = _bundle({"tidy/SKILL.md": VALID_DOCUMENT, "tidy/references/x.md": "detail"})
        assert read_bundle_member(raw, "references/x.md") == "detail"

    def test_a_missing_member_is_refused_by_name(self) -> None:
        raw = _bundle({"tidy/SKILL.md": VALID_DOCUMENT})
        with pytest.raises(SkillValidationError) as exc:
            read_bundle_member(raw, "references/nope.md")
        assert exc.value.reason == "skill_member_not_found"

    def test_a_traversal_request_cannot_escape_the_bundle(self) -> None:
        raw = _bundle({"tidy/SKILL.md": VALID_DOCUMENT})
        with pytest.raises(SkillValidationError) as exc:
            read_bundle_member(raw, "../../etc/passwd")
        assert exc.value.reason == "skill_unsafe_member_path"


class TestBundleFromDirectory:
    def test_build_artifacts_are_left_out(self, tmp_path: Path) -> None:
        # Running a bundled script leaves a __pycache__ beside it. Shipping that
        # would put machine-specific bytes in the archive and move the checksum.
        folder = tmp_path / "tidy-imports"
        (folder / "scripts" / "__pycache__").mkdir(parents=True)
        (folder / "SKILL.md").write_text(VALID_DOCUMENT, encoding="utf-8")
        (folder / "scripts" / "helper.py").write_text("x = 1\n", encoding="utf-8")
        (folder / "scripts" / "__pycache__" / "helper.cpython-313.pyc").write_bytes(b"\x00")
        (folder / ".DS_Store").write_bytes(b"\x00")
        package = read_skill_bundle(bundle_from_directory(folder))
        assert set(package.files) == {
            "tidy-imports/SKILL.md",
            "tidy-imports/scripts/helper.py",
        }

    def test_a_folder_packs_into_a_readable_skill(self, tmp_path: Path) -> None:
        folder = tmp_path / "tidy-imports"
        (folder / "references").mkdir(parents=True)
        (folder / "SKILL.md").write_text(VALID_DOCUMENT, encoding="utf-8")
        (folder / "references" / "detail.md").write_text("more", encoding="utf-8")
        package = read_skill_bundle(bundle_from_directory(folder))
        assert package.name == "tidy-imports"
        assert set(package.files) == {
            "tidy-imports/SKILL.md",
            "tidy-imports/references/detail.md",
        }

    def test_packing_the_same_folder_twice_gives_the_same_bytes(self, tmp_path: Path) -> None:
        # The checksum has to mean "this content", not "this moment".
        folder = tmp_path / "tidy-imports"
        folder.mkdir()
        (folder / "SKILL.md").write_text(VALID_DOCUMENT, encoding="utf-8")
        assert bundle_from_directory(folder) == bundle_from_directory(folder)


class TestShippedSkills:
    """The skills Raiker ships have to satisfy the contract they teach."""

    def test_every_shipped_skill_is_a_valid_package(self) -> None:
        from raiker.skills.service import BUILTIN_ROOT

        folders = sorted(p for p in BUILTIN_ROOT.iterdir() if p.is_dir())
        assert {p.name for p in folders} == {
            "algorithm-creator",
            "mcp-builder",
            "skill-creator",
        }
        for folder in folders:
            package = read_skill_bundle(bundle_from_directory(folder))
            assert package.name == folder.name
            # The description is the whole triggering mechanism, so a shipped
            # skill must say when to use it, in a user's own words.
            assert "use th" in package.description.lower()
            assert len(package.description) > 200

    def test_bundled_files_are_linked_from_the_body(self) -> None:
        """Every file shipped inside a skill must be reachable from its body.

        BUG-56: build output is not a bundled file. Running `compileall` — which
        CI itself runs over the same trees — leaves `__pycache__` beside a
        skill's `scripts/`, and walking it blindly turned "you shipped a file
        nothing loads" into a failure that depended on the order two commands
        were run in. The rule is unchanged for *sources*: an unreferenced source
        file in a skill bundle is still a defect.
        """
        from raiker.skills.service import BUILTIN_ROOT

        generated_dirs = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
        generated_suffixes = {".pyc", ".pyo"}
        for folder in sorted(p for p in BUILTIN_ROOT.iterdir() if p.is_dir()):
            body = (folder / "SKILL.md").read_text(encoding="utf-8")
            for extra in sorted(folder.rglob("*")):
                if not extra.is_file() or extra.name == "SKILL.md":
                    continue
                parts = extra.relative_to(folder).parts
                if generated_dirs.intersection(parts) or extra.suffix in generated_suffixes:
                    continue
                relative = extra.relative_to(folder).as_posix()
                # A bundled file nothing points at is a file that never loads.
                assert relative in body, f"{folder.name} never references {relative}"

    def test_no_shipped_skill_body_exceeds_the_size_it_teaches(self) -> None:
        from raiker.skills.service import BUILTIN_ROOT

        for folder in sorted(p for p in BUILTIN_ROOT.iterdir() if p.is_dir()):
            lines = (folder / "SKILL.md").read_text(encoding="utf-8").splitlines()
            assert len(lines) < 500, f"{folder.name}/SKILL.md is {len(lines)} lines"


class TestNormalizeImportUrl:
    def test_raw_github_url_passes_through(self) -> None:
        url = "https://raw.githubusercontent.com/o/r/main/skills/x/SKILL.md"
        assert normalize_import_url(url) == url

    def test_blob_url_is_rewritten_to_raw(self) -> None:
        assert normalize_import_url(
            "https://github.com/o/r/blob/main/skills/x/SKILL.md"
        ) == "https://raw.githubusercontent.com/o/r/main/skills/x/SKILL.md"

    def test_other_host_is_refused(self) -> None:
        assert normalize_import_url("https://example.com/SKILL.md") is None

    def test_plain_http_is_refused(self) -> None:
        assert normalize_import_url("http://raw.githubusercontent.com/o/r/m/SKILL.md") is None


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    return ws


class TestSkillsService:
    def test_built_in_skills_are_seeded_once(self, workspace: Path) -> None:
        service = SkillsService(workspace)
        names = {skill.name for skill in service.list_skills("principal_owner")}
        assert {"algorithm-creator", "mcp-builder", "skill-creator"} <= names
        before = len(service.list_skills("principal_owner"))
        assert len(service.list_skills("principal_owner")) == before

    def test_a_deleted_built_in_is_not_restored(self, workspace: Path) -> None:
        service = SkillsService(workspace)
        skills = service.list_skills("principal_owner")
        target = next(s for s in skills if s.name == "mcp-builder")
        assert service.delete("principal_owner", target.skill_id).ok
        assert "mcp-builder" not in {s.name for s in service.list_skills("principal_owner")}

    def test_upload_rename_deactivate_download_delete(self, workspace: Path) -> None:
        service = SkillsService(workspace)
        installed = service.install_upload(
            "principal_owner", "tidy.md", VALID_DOCUMENT.encode("utf-8")
        )
        assert installed.ok, installed.reason_code
        skill_id = installed.data["skill_id"]

        assert service.rename("principal_owner", skill_id, "tidy-up").ok
        assert service.set_active("principal_owner", skill_id, False).ok
        assert [name for name, _ in service.active_skill_documents("principal_owner")].count(
            "tidy-up"
        ) == 0

        found = service.get_download("principal_owner", skill_id)
        assert found is not None
        filename, payload = found
        assert filename == "tidy-up.skill"
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            assert any(name.endswith("SKILL.md") for name in archive.namelist())

        assert service.delete("principal_owner", skill_id).ok
        assert service.get_download("principal_owner", skill_id) is None

    def test_reinstalling_keeps_the_owners_inactive_choice(self, workspace: Path) -> None:
        service = SkillsService(workspace)
        first = service.install_upload(
            "principal_owner", "tidy.md", VALID_DOCUMENT.encode("utf-8")
        )
        skill_id = first.data["skill_id"]
        assert service.set_active("principal_owner", skill_id, False).ok
        again = service.install_upload(
            "principal_owner", "tidy.md", VALID_DOCUMENT.encode("utf-8")
        )
        assert again.data["skill_id"] == skill_id
        assert again.data["skill"]["active"] is False

    def test_rename_onto_an_existing_name_is_refused(self, workspace: Path) -> None:
        service = SkillsService(workspace)
        skills = service.list_skills("principal_owner")
        target = next(s for s in skills if s.name == "skill-creator")
        result = service.rename("principal_owner", target.skill_id, "mcp-builder")
        assert not result.ok
        assert result.reason_code == "skill_rename_failed"

    def test_invalid_document_is_refused_with_its_reason(self, workspace: Path) -> None:
        result = SkillsService(workspace).install_upload(
            "principal_owner", "bad.md", b"---\nname: x\n---\nno description\n"
        )
        assert not result.ok
        assert result.reason_code == "skill_missing_description"

    def test_build_skill_assembles_a_valid_document(self, workspace: Path) -> None:
        service = SkillsService(workspace)
        result = service.build_skill(
            "principal_owner",
            "Release-Notes",
            "Draft release notes.  Use when cutting a release.",
            "# Release notes\n\nSummarise the diff.",
        )
        assert result.ok, result.reason_code
        assert result.data["skill"]["name"] == "release-notes"
        assert result.data["skill"]["source"] == "built"

    def test_another_owner_cannot_touch_a_skill(self, workspace: Path) -> None:
        service = SkillsService(workspace)
        skill_id = service.list_skills("principal_owner")[0].skill_id
        assert service.get_download("principal_other", skill_id) is None

    def test_import_from_an_unsupported_host_is_refused(self, workspace: Path) -> None:
        result = SkillsService(workspace).import_from_url(
            "principal_owner", "https://example.com/SKILL.md"
        )
        assert not result.ok
        assert result.reason_code == "skill_unsupported_source"


class TestSkillLoadTool:
    def test_active_skill_returns_its_instructions(self, workspace: Path) -> None:
        from raiker.tools.skill_tools import skill_load

        SkillsService(workspace).list_skills("principal_owner")
        result = skill_load(workspace, "mcp-builder", owner_principal_id="principal_owner")
        assert result["status"] == "success"
        assert "MCP" in result["instructions"]
        # The index of bundled files is what makes a follow-up read possible.
        assert "mcp-builder/references/python.md" in result["files"]

    def test_a_bundled_reference_is_read_only_when_asked_for(self, workspace: Path) -> None:
        from raiker.tools.skill_tools import skill_load

        SkillsService(workspace).list_skills("principal_owner")
        # The body points at the reference rather than inlining it — that split
        # is the whole point, so the detail must not already be in the body.
        body = skill_load(workspace, "mcp-builder", owner_principal_id="principal_owner")
        assert "references/python.md" in body["instructions"]
        assert "mcp.run(transport=" not in body["instructions"]
        reference = skill_load(
            workspace,
            "mcp-builder",
            file="references/python.md",
            owner_principal_id="principal_owner",
        )
        assert reference["status"] == "success"
        assert "FastMCP" in reference["content"]

    def test_a_file_outside_the_bundle_is_refused(self, workspace: Path) -> None:
        from raiker.tools.skill_tools import skill_load

        SkillsService(workspace).list_skills("principal_owner")
        result = skill_load(
            workspace,
            "mcp-builder",
            file="../../../etc/passwd",
            owner_principal_id="principal_owner",
        )
        assert result["status"] == "failed"

    def test_deactivated_skill_is_withheld(self, workspace: Path) -> None:
        from raiker.tools.skill_tools import skill_load

        service = SkillsService(workspace)
        target = next(s for s in service.list_skills("principal_owner") if s.name == "mcp-builder")
        service.set_active("principal_owner", target.skill_id, False)
        result = skill_load(workspace, "mcp-builder", owner_principal_id="principal_owner")
        assert result["status"] == "failed"
        assert result["error"]["type"] == "not_found"

    def test_unknown_skill_is_a_clean_failure(self, workspace: Path) -> None:
        from raiker.tools.skill_tools import skill_load

        result = skill_load(workspace, "nope", owner_principal_id="principal_owner")
        assert result["status"] == "failed"

    def test_another_owner_cannot_load_it(self, workspace: Path) -> None:
        from raiker.tools.skill_tools import skill_load

        SkillsService(workspace).list_skills("principal_owner")
        result = skill_load(workspace, "mcp-builder", owner_principal_id="principal_other")
        assert result["status"] == "failed"
