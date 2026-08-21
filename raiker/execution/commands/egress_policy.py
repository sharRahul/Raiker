"""Fail-closed domain/port and resolved-address policy for command egress."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import re
from collections.abc import Iterable
from dataclasses import dataclass

_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")


def normalize_domain(value: str) -> str:
    candidate = value.strip().rstrip(".").casefold()
    wildcard = candidate.startswith("*.")
    if wildcard:
        candidate = candidate[2:]
    if not candidate or ":" in candidate:
        raise ValueError("egress_domain_invalid")
    try:
        ascii_name = candidate.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise ValueError("egress_domain_invalid") from exc
    labels = ascii_name.split(".")
    if len(ascii_name) > 253 or len(labels) < 2 or any(
        not _LABEL.fullmatch(label) for label in labels
    ):
        raise ValueError("egress_domain_invalid")
    return f"*.{ascii_name}" if wildcard else ascii_name


def domain_matches(rule: str, host: str) -> bool:
    normalized_rule = normalize_domain(rule)
    normalized_host = normalize_domain(host)
    if not normalized_rule.startswith("*."):
        return normalized_rule == normalized_host
    suffix = normalized_rule[2:]
    return normalized_host.endswith("." + suffix) and normalized_host != suffix


def public_address(value: str) -> str:
    try:
        address = ipaddress.ip_address(value)
    except ValueError as exc:
        raise ValueError("egress_address_invalid") from exc
    if (
        not address.is_global
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    ):
        raise ValueError("egress_address_not_public")
    return address.compressed


@dataclass(frozen=True)
class EgressPolicy:
    domains: tuple[str, ...]
    ports: tuple[int, ...] = (443,)

    def __post_init__(self) -> None:
        normalized = tuple(sorted({normalize_domain(value) for value in self.domains}))
        ports = tuple(sorted(set(int(port) for port in self.ports)))
        if not normalized or not ports or any(not 1 <= port <= 65535 for port in ports):
            raise ValueError("egress_policy_invalid")
        object.__setattr__(self, "domains", normalized)
        object.__setattr__(self, "ports", ports)

    def permits(self, host: str, port: int, addresses: Iterable[str]) -> tuple[str, ...]:
        normalized_host = normalize_domain(host)
        if int(port) not in self.ports or not any(
            domain_matches(rule, normalized_host) for rule in self.domains
        ):
            raise ValueError("egress_destination_denied")
        selected = tuple(sorted({public_address(value) for value in addresses}))
        if not selected:
            raise ValueError("egress_dns_answer_empty")
        return selected

    @property
    def digest(self) -> str:
        payload = json.dumps(
            {"domains": self.domains, "ports": self.ports},
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode()).hexdigest()
