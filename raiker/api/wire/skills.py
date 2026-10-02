# SPDX-License-Identifier: Apache-2.0
"""The Skills tab: listing, installing, verifying a link, and editing one skill."""

from __future__ import annotations

from typing_extensions import TypedDict

from raiker.skills.service import InstalledSkill


class SkillList(TypedDict):
    skills: list[InstalledSkill]


class SkillInstalled(TypedDict):
    """An upload, import or build that stored a skill, and the skill as stored."""

    ok: bool
    skill_id: str
    skill: InstalledSkill | None


class SkillVerification(TypedDict):
    """What a linked skill turned out to be, reported before anything is stored."""

    ok: bool
    verified: bool
    name: str
    description: str
    version: str | None
    checksum: str
    byte_size: int
    source_url: str
    already_installed: bool


class SkillRenamed(TypedDict):
    ok: bool
    skill_id: str
    name: str


class SkillActiveSet(TypedDict):
    ok: bool
    skill_id: str
    active: bool


class SkillCommandSet(TypedDict):
    ok: bool
    skill_id: str
    command_trigger: str | None


class SkillDeleted(TypedDict):
    ok: bool
    skill_id: str
    deleted: bool
