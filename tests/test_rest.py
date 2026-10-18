"""REST (HTTP+JSON) binding probes against live fixture servers."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from a2a_test.checks import CheckSuite, Status
from a2a_test.client import A2AClient
from a2a_test.rest import discover_rest_interface, probe_rest


def _run(base_url: str, rest_base: str, caps: dict[str, Any] | None = None) -> CheckSuite:
    suite = CheckSuite()
    probe_rest(suite, A2AClient(base_url), rest_base, capabilities=caps)
    return suite


def _by_name(suite: CheckSuite, name: str):
    for r in suite.results:
        if r.name == name:
            return r
    return None


def _good_caps() -> dict[str, Any]:
    return {"streaming": True}


def test_discover_rest_interface(good_server):
    client = A2AClient(good_server)
    _status, _ctype, body = client.fetch_card()
    card = json.loads(body)
    rest_base = discover_rest_interface(card)
    assert rest_base is not None
    assert rest_base.endswith("/rest")


def test_discover_rest_interface_none_without_binding():
    assert discover_rest_interface({"supportedInterfaces": []}) is None
    assert (
        discover_rest_interface(
            {"supportedInterfaces": [{"protocolBinding": "JSONRPC", "url": "http://x/a2a"}]}
        )
        is None
    )
    assert discover_rest_interface(None) is None


def test_good_server_rest_probe_all_pass(good_server):
    rest_base = good_server + "/rest"
    suite = _run(good_server, rest_base, caps=_good_caps())
    fails = [r for r in suite.results if r.status == Status.FAIL]
    warns = [r for r in suite.results if r.status == Status.WARN]
    assert not fails, "; ".join(f"{r.name}: {r.detail}" for r in fails)
    assert not warns, "; ".join(f"{r.name}: {r.detail}" for r in warns)
    for name in (
        "message:send",
        "content-type",
        "error:task-not-found",
        "error:cancel-not-found",
        "list-tasks",
        "list-tasks:pagination",
        "version:negotiation",
        "stream:frames",
        "stream:first-event",
    ):
        r = _by_name(suite, name)
        assert r is not None, name
        assert r.status == Status.PASS, f"{name}: {r.detail}"


def test_good_server_rest_stream_skipped_without_capability(good_server):
    suite = _run(good_server, good_server + "/rest", caps={})
    r = _by_name(suite, "stream")
    assert r is not None and r.status == Status.SKIP


# ---------------------------------------------------------------------------
# A deliberately broken REST server: right paths, wrong error dialect.
# ---------------------------------------------------------------------------


class BrokenRestHandler(BaseHTTPRequestHandler):
    """Serves /rest/* endpoints with non-compliant error bodies."""

    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: N802
        pass

    def _send(self, status: int, ctype: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path.startswith("/rest/tasks/"):
            # wrong: plain text 404, no google.rpc.Status
            self._send(404, "text/plain", b"task not found")
        elif self.path == "/rest/tasks":
            # wrong: bare array instead of the ListTasksResponse envelope
            self._send(200, "application/json", b"[]")
        else:
            self._send(404, "text/plain", b"")

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        if length:
            self.rfile.read(length)
        if self.path == "/rest/message:send":
            # wrong: 200 but Content-Type is not a2a+json and body is a bare string
            self._send(200, "text/plain", b"ok")
        elif self.path.endswith(":cancel"):
            # wrong: 500 instead of 404
            self._send(500, "application/json", b'{"error": "boom"}')
        else:
            self._send(404, "text/plain", b"")


def _start_broken_rest() -> tuple[ThreadingHTTPServer, str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), BrokenRestHandler)
    base_url = f"http://127.0.0.1:{server.server_address[1]}"
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, base_url


def test_broken_rest_server_is_caught():
    server, base_url = _start_broken_rest()
    try:
        suite = _run(base_url, base_url + "/rest", caps={})
        assert suite.exit_code == 1
        # message:send must fail (non-JSON body)
        r = _by_name(suite, "message:send")
        assert r is not None and r.status == Status.FAIL
        # content-type must fail (text/plain)
        r = _by_name(suite, "content-type")
        assert r is not None and r.status == Status.FAIL
        # 404 without google.rpc.Status -> WARN (tolerated but flagged)
        r = _by_name(suite, "error:task-not-found")
        assert r is not None and r.status == Status.WARN
        # cancel answered 500 instead of 404 -> FAIL
        r = _by_name(suite, "error:cancel-not-found")
        assert r is not None and r.status == Status.FAIL
        # list-tasks bare array -> FAIL
        r = _by_name(suite, "list-tasks")
        assert r is not None and r.status == Status.FAIL
    finally:
        server.shutdown()
        server.server_close()
