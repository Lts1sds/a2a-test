"""HTTP+JSON (REST) binding conformance probes (spec v1.0.0 section 11).

The REST binding is *not* JSON-RPC: it uses Google AIP-style resource paths
(``POST /message:send``, ``GET /tasks/{id}``, custom methods with ``:``),
``application/a2a+json`` content type, and ``google.rpc.Status`` error
bodies instead of JSON-RPC error objects. These probes verify that a server
which *declares* an HTTP+JSON interface in its Agent Card actually speaks
that dialect.
"""

from __future__ import annotations

import json
from typing import Any

from .checks import CheckSuite
from .client import SSE_CONTENT_TYPE, A2AClient

# REST binding paths relative to the interface URL (spec 11.3)
PATH_MESSAGE_SEND = "/message:send"
PATH_MESSAGE_STREAM = "/message:stream"
PATH_TASKS = "/tasks"
PATH_TASK_CANCEL_SUFFIX = ":cancel"

# gRPC status codes used by google.rpc.Status error bodies (spec 11.6)
GRPC_NOT_FOUND = 5

REST_BINDINGS = ("HTTP+JSON", "HTTPJSON", "REST")

NONEXISTENT_TASK_ID = "a2a-test-nonexistent-id"


def discover_rest_interface(card: dict[str, Any] | None) -> str | None:
    """Return the HTTP+JSON interface base URL declared by the Agent Card."""
    if not isinstance(card, dict):
        return None
    interfaces = card.get("supportedInterfaces")
    if not isinstance(interfaces, list):
        return None
    for iface in interfaces:
        if (
            isinstance(iface, dict)
            and iface.get("protocolBinding") in REST_BINDINGS
            and isinstance(iface.get("url"), str)
            and iface["url"]
        ):
            return iface["url"].rstrip("/")
    return None


def probe_rest(
    suite: CheckSuite,
    client: A2AClient,
    rest_base: str,
    capabilities: dict[str, Any] | None = None,
) -> None:
    """Run the REST (HTTP+JSON) binding conformance probe battery."""
    group = "rest"
    caps = capabilities or {}

    _probe_message_send(suite, group, client, rest_base)
    _probe_task_not_found(suite, group, client, rest_base)
    _probe_cancel_not_found(suite, group, client, rest_base)
    _probe_list_tasks(suite, group, client, rest_base)
    _probe_version_negotiation(suite, group, client, rest_base)
    if caps.get("streaming") is True:
        _probe_message_stream(suite, group, client, rest_base)
    else:
        suite.skip(group, "stream", "capabilities.streaming not declared; skipping SSE probe")


def _message_payload(text: str) -> dict[str, Any]:
    return {
        "message": {
            "messageId": "a2a-test-rest-msg-001",
            "role": "ROLE_USER",
            "parts": [{"text": text}],
        }
    }


def _parse_json(body: str) -> dict[str, Any] | None:
    try:
        obj = json.loads(body)
    except ValueError:
        return None
    return obj if isinstance(obj, dict) else None


def _grpc_reason(obj: dict[str, Any] | None) -> str | None:
    """Extract the ErrorInfo reason from a google.rpc.Status body, if present."""
    if not isinstance(obj, dict):
        return None
    details = obj.get("details")
    if not isinstance(details, list):
        return None
    for item in details:
        if isinstance(item, dict) and isinstance(item.get("reason"), str):
            return item["reason"]
    return None


def _grpc_code(obj: dict[str, Any] | None) -> int | None:
    if isinstance(obj, dict) and isinstance(obj.get("code"), int):
        return obj["code"]
    return None


def _probe_message_send(suite: CheckSuite, group: str, client: A2AClient, rest_base: str) -> None:
    """POST /message:send must return 200 with a Task or Message result."""
    status, ctype, body = client.post_json(
        rest_base + PATH_MESSAGE_SEND,
        _message_payload("Reply with the single word: pong"),
        headers={"A2A-Version": "1.0"},
    )
    if status != 200:
        suite.check(
            group,
            "message:send",
            False,
            f"POST /message:send returned HTTP {status} (expected 200); body: {body[:120]!r}",
        )
        suite.skip(group, "content-type", "no successful response to inspect")
        return

    result = _parse_json(body)
    has_result = result is not None and (
        isinstance(result.get("task"), dict) or isinstance(result.get("message"), dict)
    )
    suite.check(
        group,
        "message:send",
        has_result,
        "200 response body should contain a `task` or `message` object (spec 11.4); "
        f"got: {body[:120]!r}",
    )

    # Content type: spec 11.2 says responses SHOULD use application/a2a+json
    if "a2a+json" in ctype:
        suite.check(group, "content-type", True, "response Content-Type is application/a2a+json")
    elif "json" in ctype:
        suite.check(
            group,
            "content-type",
            False,
            f"response Content-Type is {ctype!r}; spec 11.2 says responses SHOULD use "
            "application/a2a+json",
            warn=True,
        )
    else:
        suite.check(
            group,
            "content-type",
            False,
            f"response Content-Type is {ctype!r}; expected application/a2a+json",
        )


def _check_rest_not_found(
    suite: CheckSuite,
    group: str,
    name: str,
    status: int,
    ctype: str,
    body: str,
) -> None:
    """Shared expectations for 404s: google.rpc.Status with TASK_NOT_FOUND."""
    if status != 404:
        suite.check(
            group,
            name,
            False,
            f"expected HTTP 404, got {status} (ctype {ctype!r}); body: {body[:100]!r}",
        )
        return
    obj = _parse_json(body)
    reason = _grpc_reason(obj)
    code = _grpc_code(obj)
    if reason == "TASK_NOT_FOUND" or code == GRPC_NOT_FOUND:
        suite.check(
            group,
            name,
            True,
            "404 with google.rpc.Status reason TASK_NOT_FOUND (spec 11.6)",
        )
    elif obj is not None:
        suite.check(
            group,
            name,
            False,
            "404 body is JSON but not a recognizable google.rpc.Status "
            f"(reason {reason!r}, code {code!r}); spec 11.6 requires "
            '{"code": 5, "details": [{"reason": "TASK_NOT_FOUND", ...}]}',
            warn=True,
        )
    else:
        suite.check(
            group,
            name,
            False,
            f"404 body is not JSON ({ctype!r}): {body[:100]!r}; spec 11.6 requires "
            "google.rpc.Status",
            warn=True,
        )


def _probe_task_not_found(suite: CheckSuite, group: str, client: A2AClient, rest_base: str) -> None:
    """GET /tasks/{unknown} must 404 with a google.rpc.Status body."""
    status, ctype, body = client.get(
        rest_base + PATH_TASKS + "/" + NONEXISTENT_TASK_ID,
        headers={"A2A-Version": "1.0"},
    )
    _check_rest_not_found(suite, group, "error:task-not-found", status, ctype, body)


def _probe_cancel_not_found(
    suite: CheckSuite, group: str, client: A2AClient, rest_base: str
) -> None:
    """POST /tasks/{unknown}:cancel must 404 with a google.rpc.Status body."""
    status, ctype, body = client.post_json(
        rest_base + PATH_TASKS + "/" + NONEXISTENT_TASK_ID + PATH_TASK_CANCEL_SUFFIX,
        {},
        headers={"A2A-Version": "1.0"},
    )
    _check_rest_not_found(suite, group, "error:cancel-not-found", status, ctype, body)


def _probe_list_tasks(suite: CheckSuite, group: str, client: A2AClient, rest_base: str) -> None:
    """GET /tasks must return 200 with the ListTasks pagination envelope."""
    status, _ctype, body = client.get(
        rest_base + PATH_TASKS,
        headers={"A2A-Version": "1.0"},
    )
    obj = _parse_json(body)
    if status != 200 or obj is None:
        suite.check(
            group,
            "list-tasks",
            False,
            f"GET /tasks returned HTTP {status}; expected 200 with the ListTasksResponse "
            f"object (spec 11.4); body: {body[:100]!r}",
        )
        return
    tasks = obj.get("tasks")
    if not isinstance(tasks, list):
        suite.check(
            group,
            "list-tasks",
            False,
            f"ListTasksResponse.tasks must be an array (spec 11.4); got: {body[:120]!r}",
        )
        return
    suite.check(group, "list-tasks", True, f"200 with {len(tasks)} task(s) in the envelope")

    # Pagination fields are required members of ListTasksResponse (spec 11.4)
    missing = [f for f in ("nextPageToken", "pageSize", "totalSize") if f not in obj]
    suite.check(
        group,
        "list-tasks:pagination",
        not missing,
        "ListTasksResponse should carry nextPageToken/pageSize/totalSize (spec 11.4); "
        f"missing: {', '.join(missing)}"
        if missing
        else "pagination envelope complete",
        warn=bool(missing),
    )


def _probe_version_negotiation(
    suite: CheckSuite, group: str, client: A2AClient, rest_base: str
) -> None:
    """An unsupported A2A-Version must be rejected with HTTP 400 (spec 6.4)."""
    status, _ctype, body = client.post_json(
        rest_base + PATH_MESSAGE_SEND,
        _message_payload("version probe"),
        headers={"A2A-Version": "9.9"},
    )
    if status == 400:
        suite.check(
            group,
            "version:negotiation",
            True,
            "A2A-Version: 9.9 rejected with HTTP 400 (spec 6.4)",
        )
    elif 400 <= status < 500:
        suite.check(
            group,
            "version:negotiation",
            False,
            f"A2A-Version: 9.9 answered HTTP {status}; spec 6.4 example uses 400 "
            f"problem+json; body: {body[:100]!r}",
            warn=True,
        )
    else:
        suite.check(
            group,
            "version:negotiation",
            False,
            f"A2A-Version: 9.9 was accepted (HTTP {status}); server must reject "
            "unsupported versions",
        )


def _probe_message_stream(suite: CheckSuite, group: str, client: A2AClient, rest_base: str) -> None:
    """POST /message:stream must answer with an SSE stream of REST events."""
    status, ctype, frames = client.post_stream(
        rest_base + PATH_MESSAGE_STREAM,
        _message_payload("stream probe"),
        headers={"A2A-Version": "1.0"},
    )
    if status != 200:
        suite.check(
            group,
            "stream",
            False,
            f"POST /message:stream returned HTTP {status} (capabilities.streaming "
            "declares support)",
        )
        return
    if SSE_CONTENT_TYPE not in ctype:
        suite.check(
            group,
            "stream",
            False,
            f"expected Content-Type text/event-stream, got {ctype!r}",
        )
        return

    events: list[dict[str, Any]] = []
    raw_frames = 0
    for payload in frames:
        raw_frames += 1
        obj = _parse_json(payload)
        if obj is not None:
            events.append(obj)
    suite.check(
        group,
        "stream:frames",
        raw_frames > 0,
        f"received {raw_frames} SSE frame(s), {len(events)} parsed object(s)",
    )
    if not events:
        return

    # REST stream events are unwrapped Task / TaskStatusUpdateEvent objects
    # (no JSON-RPC envelope), spec 11.4
    first = events[0]
    first_ok = isinstance(first.get("task"), dict) or isinstance(first.get("statusUpdate"), dict)
    suite.check(
        group,
        "stream:first-event",
        first_ok,
        "first stream event should be the Task object or a statusUpdate on it (spec 11.4); "
        f"got: {json.dumps(first)[:120]}",
    )
