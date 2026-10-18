"""A deliberately non-compliant, v0.3-dialect A2A server used as a fixture.

Every bug in here is something a2a-test must catch:
  * v0.3 top-level card fields (preferredTransport, supportsExtendedAgentCard, url)
  * slash-style method names (tasks/get instead of GetTask)
  * `kind` discriminators in parts and stream events
  * wrong error codes (-32603 instead of -32001 for missing tasks)
"""

from __future__ import annotations

import json
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

LEGACY_CARD: dict[str, Any] = {
    "name": "Legacy Fixture Agent",
    "description": "A v0.3-dialect fixture agent.",
    "url": "http://127.0.0.1:REPLACE",
    "preferredTransport": "JSONRPC",
    "version": "0.3.0",
    "capabilities": {"streaming": False, "pushNotifications": False},
    "supportsExtendedAgentCard": True,
    "defaultInputModes": ["text/plain"],
    "defaultOutputModes": ["text/plain"],
    "skills": [
        {
            "id": "echo",
            "name": "Echo",
            "description": "Echoes text.",
            "tags": ["echo"],
        }
    ],
}


class LegacyHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        pass

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/.well-known/agent-card.json":
            card = json.loads(json.dumps(LEGACY_CARD))
            card["url"] = f"http://127.0.0.1:{self.server.server_address[1]}/"
            body = json.dumps(card).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        try:
            req = json.loads(raw)
        except ValueError:
            body = json.dumps(
                {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}}
            ).encode()
            self._respond(body)
            return
        if not isinstance(req, dict) or "method" not in req:
            body = json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32600, "message": "invalid request"},
                }
            ).encode()
            self._respond(body)
            return

        method = req.get("method")
        rid = req.get("id")

        if method == "tasks/get":
            # BUG: wrong error code for a missing task
            body = json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": rid,
                    "error": {"code": -32603, "message": "internal error: no such task"},
                }
            ).encode()
            self._respond(body)
        elif method == "GetTask":
            # v1.0 PascalCase is not recognized at all
            body = json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": rid,
                    "error": {"code": -32601, "message": "Method not found"},
                }
            ).encode()
            self._respond(body)
        elif method == "message/send":
            # v0.3 method name; response parts carry the legacy `kind` discriminator
            params = req.get("params") or {}
            text = ""
            msg = params.get("message")
            if isinstance(msg, dict):
                for p in msg.get("parts", []):
                    if isinstance(p, dict) and p.get("kind") == "text":
                        text = p.get("text", "")
            message = {
                "messageId": str(uuid.uuid4()),
                "role": "ROLE_AGENT",
                "parts": [{"kind": "text", "text": text}],
            }
            body = json.dumps(
                {"jsonrpc": "2.0", "id": rid, "result": {"message": message}}
            ).encode()
            self._respond(body)
        else:
            body = json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": rid,
                    "error": {"code": -32601, "message": "Method not found"},
                }
            ).encode()
            self._respond(body)

    def _respond(self, body: bytes) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def start_legacy_server() -> tuple[ThreadingHTTPServer, str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), LegacyHandler)
    port = server.server_address[1]
    base_url = f"http://127.0.0.1:{port}"
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, base_url
