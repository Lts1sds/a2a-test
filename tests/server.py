"""A minimal spec-v1.0.0-compliant A2A server used as a test fixture.

Implemented with the standard library only (http.server), speaking raw
JSON-RPC over HTTP plus SSE streaming, exactly like a real remote agent.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

AGENT_CARD: dict[str, Any] = {
    "name": "Fixture Echo Agent",
    "description": "A spec-compliant fixture agent that echoes text.",
    "supportedInterfaces": [
        {
            "url": "http://127.0.0.1:REPLACE/a2a",
            "protocolBinding": "JSONRPC",
            "protocolVersion": "1.0",
        }
    ],
    "provider": {"organization": "a2a-test fixtures", "url": "https://example.com"},
    "version": "1.0.0",
    "capabilities": {"streaming": True, "pushNotifications": False, "extendedAgentCard": False},
    "defaultInputModes": ["text/plain"],
    "defaultOutputModes": ["text/plain"],
    "skills": [
        {
            "id": "echo",
            "name": "Echo",
            "description": "Echoes the user text back.",
            "tags": ["echo", "test"],
            "examples": ["Reply with the single word: pong"],
        }
    ],
}

ERROR_DATA_TASK_NOT_FOUND = [
    {
        "@type": "type.googleapis.com/google.rpc.ErrorInfo",
        "reason": "TASK_NOT_FOUND",
        "domain": "a2a-protocol.org",
    }
]


def _error(request_id: Any, code: int, message: str, data: list | None = None) -> bytes:
    err: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return json.dumps({"jsonrpc": "2.0", "id": request_id, "error": err}).encode("utf-8")


def _result(request_id: Any, result: dict[str, Any]) -> bytes:
    return json.dumps({"jsonrpc": "2.0", "id": request_id, "result": result}).encode("utf-8")


class FixtureAgent:
    """In-memory task store shared across handler threads."""

    def __init__(self) -> None:
        self.tasks: dict[str, dict[str, Any]] = {}
        self.lock = threading.Lock()

    def create_task(self, text: str) -> dict[str, Any]:
        task_id = str(uuid.uuid4())
        context_id = str(uuid.uuid4())
        task = {
            "id": task_id,
            "contextId": context_id,
            "status": {"state": "TASK_STATE_WORKING", "message": None, "timestamp": _now()},
            "artifacts": [],
            "history": [],
            "metadata": {},
        }
        with self.lock:
            self.tasks[task_id] = task
        return task

    def complete_task(self, task_id: str, text: str) -> dict[str, Any]:
        with self.lock:
            task = self.tasks[task_id]
            task["status"] = {
                "state": "TASK_STATE_COMPLETED",
                "message": _agent_message(text, task_id),
                "timestamp": _now(),
            }
            return task

    def get(self, task_id: str) -> dict[str, Any] | None:
        with self.lock:
            return self.tasks.get(task_id)


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _agent_message(text: str, task_id: str) -> dict[str, Any]:
    return {
        "messageId": str(uuid.uuid4()),
        "taskId": task_id,
        "contextId": None,
        "role": "ROLE_AGENT",
        "parts": [{"text": text}],
        "metadata": {},
    }


def _user_text(params: dict[str, Any]) -> str | None:
    msg = params.get("message")
    if not isinstance(msg, dict):
        return None
    parts = msg.get("parts")
    if not isinstance(parts, list):
        return None
    for p in parts:
        if isinstance(p, dict) and isinstance(p.get("text"), str):
            return p["text"]
    return None


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    agent: FixtureAgent = FixtureAgent()
    base_url: str = ""

    def log_message(self, fmt: str, *args: Any) -> None:  # silence
        pass

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/.well-known/agent-card.json":
            card = json.loads(json.dumps(AGENT_CARD))
            card["supportedInterfaces"][0]["url"] = self.base_url + "/a2a"
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
        if self.path != "/a2a":
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""

        version = self.headers.get("A2A-Version", "")
        if version and not version.startswith(("0.", "1.")):
            self._respond(_error(None, -32009, "Protocol version not supported"))
            return

        try:
            req = json.loads(raw)
        except ValueError:
            self._respond(_error(None, -32700, "Invalid JSON payload"))
            return
        if not isinstance(req, dict) or req.get("jsonrpc") != "2.0" or "method" not in req:
            self._respond(_error(None, -32600, "Request payload validation error"))
            return

        method = req.get("method")
        params = req.get("params") or {}
        rid = req.get("id")

        if method == "GetTask":
            task = self.agent.get(str(params.get("id", "")))
            if task is None:
                self._respond(_error(rid, -32001, "Task not found", ERROR_DATA_TASK_NOT_FOUND))
            else:
                self._respond(_result(rid, task))
        elif method == "CancelTask":
            task = self.agent.get(str(params.get("id", "")))
            if task is None:
                self._respond(_error(rid, -32001, "Task not found", ERROR_DATA_TASK_NOT_FOUND))
            else:
                self._respond(_error(rid, -32002, "Task not cancelable"))
        elif method == "ListTasks":
            self._respond(
                _result(rid, {"tasks": [], "nextPageToken": "", "pageSize": 0, "totalSize": 0})
            )
        elif method == "SendMessage":
            if not isinstance(params.get("message"), dict):
                self._respond(_error(rid, -32602, "Invalid parameters"))
                return
            task_id = (params.get("message") or {}).get("taskId")
            if isinstance(task_id, str) and task_id:
                task = self.agent.get(task_id)
                if task is not None and task["status"]["state"] == "TASK_STATE_COMPLETED":
                    self._respond(_error(rid, -32004, "Unsupported operation"))
                    return
            text = _user_text(params)
            task = self.agent.create_task(text or "")
            self.agent.complete_task(task["id"], text or "")
            self._respond(_result(rid, {"task": task}))
        elif method == "SendStreamingMessage":
            self._stream(rid, params)
        else:
            self._respond(_error(rid, -32601, "Method not found"))

    def _stream(self, rid: Any, params: dict[str, Any]) -> None:
        text = _user_text(params) or ""
        task = self.agent.create_task(text)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Connection", "close")
        self.end_headers()
        for frame in (
            {"task": task},
            {
                "statusUpdate": {
                    "taskId": task["id"],
                    "contextId": task["contextId"],
                    "status": {"state": "TASK_STATE_WORKING"},
                }
            },
            {
                "statusUpdate": {
                    "taskId": task["id"],
                    "contextId": task["contextId"],
                    "status": {
                        "state": "TASK_STATE_COMPLETED",
                        "message": _agent_message(text, task["id"]),
                    },
                    "final": True,
                }
            },
        ):
            payload = json.dumps({"jsonrpc": "2.0", "id": rid, "result": frame})
            self.wfile.write(f"data: {payload}\n\n".encode())
            self.wfile.flush()
        self.close_connection = True

    def _respond(self, body: bytes) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def start_fixture_server() -> tuple[ThreadingHTTPServer, str, FixtureAgent]:
    """Start the compliant fixture server on an ephemeral port."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    base_url = f"http://127.0.0.1:{port}"
    Handler.base_url = base_url
    Handler.agent = FixtureAgent()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, base_url, Handler.agent
