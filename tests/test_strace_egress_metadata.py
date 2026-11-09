# SPDX-License-Identifier: Apache-2.0
from scripts.strace_egress_metadata import observations


def test_extraction_keeps_failed_attempts_and_ipv6_but_discards_payloads() -> None:
    records = observations('''123 1794232149.390001 connect(3, {sa_family=AF_INET, sin_addr=inet_addr("10.0.12.212")}, 16) = -1 ENETUNREACH
[pid 124] 1794232150.100000 sendto(3, "private payload", 15, 0, {sin6_addr=inet_pton(AF_INET6, "::1", &address)}, 28) = 15
123 1794232149.100000 connect(3, {sa_family=AF_UNIX, sun_path="/private/socket"}, 110) = 0
''')
    assert [record["host"] for record in records] == ["10.0.12.212", "::1"]
    assert all(set(record) == {"timestamp", "host"} for record in records)
    assert "private" not in str(records)
    assert all(record["timestamp"].endswith("Z") for record in records)


def test_no_synthetic_observations_are_added_for_an_idle_or_empty_trace() -> None:
    assert observations('123 1794232149.390001 +++ exited with 0 +++') == []
    assert observations("") == []
