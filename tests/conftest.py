"""Shared fixtures: live in-process A2A servers (compliant and legacy)."""

from __future__ import annotations

import pytest

from tests.bad_server import start_legacy_server
from tests.server import start_fixture_server


@pytest.fixture(scope="session")
def good_server():
    server, base_url, agent = start_fixture_server()
    yield base_url
    server.shutdown()
    server.server_close()


@pytest.fixture(scope="session")
def bad_server():
    server, base_url = start_legacy_server()
    yield base_url
    server.shutdown()
    server.server_close()
