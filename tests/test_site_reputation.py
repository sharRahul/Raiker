"""Owner's decision, 2026-10-26: flag only sites registered as malicious; never a known one."""

from __future__ import annotations

from pathlib import Path

import pytest

from raiker.runtime.site_reputation import (
    FEEDS,
    SiteReputation,
    ThreatFeeds,
    parse_feed,
    trusted_domain,
)
from raiker.runtime.web_access import address_alerts, check_web_read
from raiker.runtime.web_policy import parse_rules

URLHAUS = "# URLhaus hostfile\n127.0.0.1\tmalware-drop.example.net\n127.0.0.1\tlocalhost\n"
OPENPHISH = "https://login-verify.example.org/account/\nhttps://sites.google.com/view/fake-login\n"


def _fetch(feed: object) -> str:
    return URLHAUS if feed.kind == "hosts" else OPENPHISH


@pytest.fixture
def reputation(tmp_path: Path) -> SiteReputation:
    ThreatFeeds(tmp_path).refresh(fetch=_fetch)
    return SiteReputation(tmp_path)


def test_known_and_authenticated_sites_are_trusted() -> None:
    assert trusted_domain("github.com") == "github.com"
    assert trusted_domain("raw.githubusercontent.com") == "githubusercontent.com"
    assert trusted_domain("api.github.com")
    assert trusted_domain("gmail.googleapis.com") == "googleapis.com"
    assert trusted_domain("evil-github.com") == ""
    assert trusted_domain("github.com.evil.net") == ""


def test_feeds_parse_hosts_and_pages() -> None:
    assert parse_feed("hosts", URLHAUS) == ["malware-drop.example.net"]
    assert parse_feed("urls", OPENPHISH) == ["login-verify.example.org/account", "sites.google.com/view/fake-login"]


def test_a_registered_site_alerts_and_a_known_site_does_not(reputation: SiteReputation) -> None:
    flagged = reputation.malicious("https://malware-drop.example.net/payload.exe")
    assert flagged and flagged[0]["feed"] == "URLhaus (abuse.ch)" and flagged[0]["scope"] == "site"
    assert reputation.malicious("https://github.com/anthropics") == []
    # One registered page on a known site is still flagged, as a page.
    page = reputation.malicious("https://sites.google.com/view/fake-login")
    assert page and page[0]["scope"] == "page"
    assert reputation.malicious("https://sites.google.com/view/a-real-site") == []


def test_owner_flags_never_alert_on_a_known_site(monkeypatch: pytest.MonkeyPatch, reputation: SiteReputation) -> None:
    monkeypatch.setattr("raiker.runtime.web_policy.resolve_public_addresses", lambda h, p=443: ["140.82.112.3"])
    rules = parse_rules(["github.com", "ads.example.com"])
    _decision, _url, alerts = check_web_read("https://github.com/x", rules, reputation)
    assert [a["kind"] for a in alerts] == []
    _decision, _url, alerts = check_web_read("https://ads.example.com/", rules, reputation)
    assert [a["kind"] for a in alerts] == ["flagged_site"]
    _decision, _url, alerts = check_web_read("https://malware-drop.example.net/", (), reputation)
    assert [a["kind"] for a in alerts] == ["malicious_site"]
    assert "registered as malicious by URLhaus" in alerts[0]["message"]
    assert [a["kind"] for a in address_alerts("https://github.com/x", rules, reputation)] == []


def test_a_feed_that_cannot_be_read_keeps_what_it_had(tmp_path: Path) -> None:
    feeds = ThreatFeeds(tmp_path)
    feeds.refresh(fetch=_fetch)

    def down(feed: object) -> str:
        raise OSError("connect refused")

    status = feeds.refresh(fetch=down)
    assert all(item["entries"] > 0 for item in status)
    assert all("connect refused" in item["last_error"] for item in status)
    assert {item["id"] for item in status} == {feed.id for feed in FEEDS}


def test_settings_refuses_to_flag_a_known_site(tmp_path: Path) -> None:
    from fastapi.testclient import TestClient

    from raiker.api.app import create_app
    from raiker.api.sessions import ApiSessionStore
    from raiker.cli.principal_resolver import bootstrap_owner

    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    client = TestClient(create_app(tmp_path))
    token, _session = ApiSessionStore(tmp_path).create_session("principal_owner")
    headers = {"Authorization": f"Bearer {token}"}
    refused = client.post("/api/web-access/blocklist", json={"rule": "github.com"}, headers=headers)
    assert refused.status_code == 422 and "never flagged" in refused.text
    assert refused.json()["detail"]["reason_code"] == "known_site_not_flaggable:github.com"
    invalid = client.post("/api/web-access/blocklist", json={"rule": "not a domain!"}, headers=headers)
    assert invalid.status_code == 422 and invalid.json()["detail"]["reason_code"].startswith("blocklist_")
    assert client.post("/api/web-access/blocklist", json={"rule": "*.githubusercontent.com"}, headers=headers).status_code == 422
    assert client.post("/api/web-access/blocklist", json={"rule": "ads.example.com"}, headers=headers).status_code == 201
    feeds = client.get("/api/web-access/threat-feeds", headers=headers).json()
    assert {item["id"] for item in feeds["feeds"]} == {"urlhaus", "openphish"}
    assert "github.com" in feeds["known_sites"] and "api.github.com" in feeds["authenticated_sites"]
