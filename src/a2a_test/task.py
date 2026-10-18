"""Task lifecycle smoke tests: SendMessage -> poll -> terminal state -> guards."""

from __future__ import annotations

import json
import time
from typing import Any

from .checks import CheckSuite
from .client import A2AClient, error_code, error_reason

TERMINAL_STATES = {
    "TASK_STATE_COMPLETED",
    "TASK_STATE_FAILED",
    "TASK_STATE_CANCELED",
    "TASK_STATE_REJECTED",
}
INTERRUPTED_STATES = {"TASK_STATE_INPUT_REQUIRED", "TASK_STATE_AUTH_REQUIRED"}
KNOWN_STATES = (
    TERMINAL_STATES
    | INTERRUPTED_STATES
    | {
        "TASK_STATE_UNSPECIFIED",
        "TASK_STATE_SUBMITTED",
        "TASK_STATE_WORKING",
    }
)

DEFAULT_POLL_INTERVAL = 0.5
DEFAULT_TASK_TIMEOUT = 60.0


def smoke_task(
    suite: CheckSuite,
    client: A2AClient,
    message_text: str = "Reply with the single word: pong",
    capabilities: dict[str, Any] | None = None,
    poll_interval: float = DEFAULT_POLL_INTERVAL,
    task_timeout: float = DEFAULT_TASK_TIMEOUT,
) -> None:
    """Exercise the happy-path task lifecycle and its invariants."""
    group = "task"
    caps = capabilities or {}

    status, resp, body = client.rpc("SendMessage", _message_params(message_text))
    if error_code(resp) is not None:
        suite.check(
            group,
            "send-message",
            False,
            f"SendMessage failed: {error_code(resp)} ({error_reason(resp)})",
        )
        suite.skip(group, "lifecycle", "no task/message to follow")
        return
    result = (resp or {}).get("result") if isinstance(resp, dict) else None
    if not isinstance(result, dict):
        suite.check(
            group, "send-message", False, f"SendMessage result is not an object: {body[:120]!r}"
        )
        return

    if "task" in result and isinstance(result["task"], dict):
        suite.check(group, "send-message", True, "returned a Task")
        task = result["task"]
        _run_task_lifecycle(suite, group, client, task, poll_interval, task_timeout)
    elif "message" in result and isinstance(result["message"], dict):
        suite.check(group, "send-message", True, "returned a direct Message (no task)")
        _check_message_shape(suite, group, result["message"])
        suite.skip(group, "lifecycle", "direct-message flow has no task lifecycle")
    else:
        suite.check(
            group,
            "send-message",
            False,
            "result contains neither `task` nor `message` (spec spec 3.1.1)",
        )

    # Streaming smoke only when the card declares it
    if caps.get("streaming") is True:
        _smoke_streaming(suite, group, client, message_text)
    else:
        suite.skip(group, "streaming", "capabilities.streaming is not true")


def _message_params(text: str) -> dict[str, Any]:
    return {
        "message": {
            "messageId": "a2a-test-msg-001",
            "role": "ROLE_USER",
            "parts": [{"text": text}],
        }
    }


def _run_task_lifecycle(
    suite: CheckSuite,
    group: str,
    client: A2AClient,
    task: dict[str, Any],
    poll_interval: float,
    task_timeout: float,
) -> None:
    task_id = task.get("id")
    suite.check(
        group,
        "task:id",
        isinstance(task_id, str) and bool(task_id),
        "task.id must be a server-generated string (spec spec 4.1.1)",
    )
    if not isinstance(task_id, str) or not task_id:
        suite.skip(group, "lifecycle", "unusable task id")
        return

    state = _state_of(task)
    suite.check(
        group,
        "task:initial-state",
        state in KNOWN_STATES,
        f"initial state {state!r} is not a known TaskState (spec spec 4.1.3)",
    )
    suite.check(
        group,
        "task:context-id",
        isinstance(task.get("contextId"), str) and bool(task.get("contextId")),
        "task.contextId should be provided for multi-turn correlation",
    )

    deadline = time.monotonic() + task_timeout
    seen: list[str] = [state] if state else []
    while state not in TERMINAL_STATES and time.monotonic() < deadline:
        time.sleep(poll_interval)
        _s, resp, _b = client.rpc("GetTask", {"id": task_id})
        if error_code(resp) is not None:
            suite.check(
                group,
                "lifecycle:poll",
                False,
                f"GetTask failed mid-lifecycle: {error_code(resp)} ({error_reason(resp)})",
            )
            return
        result = (resp or {}).get("result")
        if not isinstance(result, dict):
            suite.check(group, "lifecycle:poll", False, "GetTask result is not an object")
            return
        new_state = _state_of(result)
        if new_state and new_state != seen[-1]:
            seen.append(new_state)
        state = new_state or state

    if state in TERMINAL_STATES:
        suite.check(
            group,
            "lifecycle:terminal",
            True,
            f"reached terminal state {state} via {' -> '.join(seen)}",
        )
    else:
        suite.check(
            group,
            "lifecycle:terminal",
            False,
            f"task did not reach a terminal state within {task_timeout}s (last state {state!r})",
        )
        return

    # Terminal task must reject cancellation with -32002 TaskNotCancelableError
    _s, resp, _b = client.rpc("CancelTask", {"id": task_id})
    code = error_code(resp)
    suite.check(
        group,
        "lifecycle:cancel-terminal",
        code == -32002,
        f"expected -32002 TaskNotCancelableError on terminal task, got {code}"
        + (f" ({error_reason(resp)})" if code is not None else ""),
        warn=(code is not None and code != -32002),
    )

    # Terminal task must reject further messages with -32004 UnsupportedOperationError
    _s, resp, _b = client.rpc("SendMessage", _message_params_after(task_id))
    code = error_code(resp)
    suite.check(
        group,
        "lifecycle:message-terminal",
        code == -32004,
        f"expected -32004 UnsupportedOperationError on terminal task, got {code}"
        + (f" ({error_reason(resp)})" if code is not None else ""),
        warn=(code is not None and code != -32004),
    )


def _message_params_after(task_id: str) -> dict[str, Any]:
    return {
        "message": {
            "messageId": "a2a-test-msg-002",
            "role": "ROLE_USER",
            "taskId": task_id,
            "parts": [{"text": "follow-up after terminal state"}],
        }
    }


def _smoke_streaming(suite: CheckSuite, group: str, client: A2AClient, text: str) -> None:
    status, ctype, frames = client.rpc_stream("SendStreamingMessage", _message_params(text))
    if status != 200:
        suite.check(
            group,
            "streaming",
            False,
            f"SendStreamingMessage returned HTTP {status} "
            "(capabilities.streaming declares support)",
        )
        return
    if "text/event-stream" not in ctype:
        suite.check(
            group, "streaming", False, f"expected Content-Type text/event-stream, got {ctype!r}"
        )
        return

    events: list[dict[str, Any]] = []
    raw_frames = 0
    for payload in frames:
        raw_frames += 1
        try:
            obj = json.loads(payload)
        except ValueError:
            continue
        if isinstance(obj, dict) and isinstance(obj.get("result"), dict):
            events.append(obj["result"])
    suite.check(
        group,
        "streaming:frames",
        raw_frames > 0,
        f"received {raw_frames} SSE frame(s), {len(events)} parsed result object(s)",
    )
    if not events:
        return

    first = events[0]
    first_is_task = "task" in first or "taskId" in first or "statusUpdate" in first
    suite.check(
        group,
        "streaming:first-event",
        first_is_task,
        "first stream event should be the Task (or a status update on it)",
    )

    # v1.0: events are wrapped as {"statusUpdate": {...}} / {"artifactUpdate": {...}}
    # v0.3: events carried a "kind" discriminator at top level.
    legacy_kind = any("kind" in e for e in events)
    suite.check(
        group,
        "streaming:discriminator",
        not legacy_kind,
        "stream events use the v0.3 `kind` discriminator; v1.0 wraps events as "
        "`statusUpdate`/`artifactUpdate` members (spec Appendix A.2.1)",
    )

    last_state = None
    for e in events:
        su = e.get("statusUpdate")
        if isinstance(su, dict):
            st = su.get("status")
            if isinstance(st, dict):
                s = st.get("state")
                if isinstance(s, str):
                    last_state = s
    if last_state is not None:
        suite.check(
            group,
            "streaming:terminal-close",
            last_state in TERMINAL_STATES,
            f"stream ended on state {last_state!r} "
            "(should close on terminal state, spec spec 3.1.2)",
        )


def _check_message_shape(suite: CheckSuite, group: str, message: dict[str, Any]) -> None:
    suite.check(
        group,
        "message:messageId",
        isinstance(message.get("messageId"), str) and bool(message.get("messageId")),
        "message.messageId is required (field name is messageId, not id; spec spec 4.1.4)",
    )
    suite.check(
        group,
        "message:role",
        message.get("role") == "ROLE_AGENT",
        f"server message role should be ROLE_AGENT, got {message.get('role')!r}",
    )
    parts = message.get("parts")
    suite.check(
        group,
        "message:parts",
        isinstance(parts, list) and len(parts) > 0,
        "message.parts must be a non-empty array (spec spec 4.1.4)",
    )
    if isinstance(parts, list):
        legacy_kind = any(isinstance(p, dict) and "kind" in p for p in parts)
        suite.check(
            group,
            "message:part-discriminator",
            not legacy_kind,
            "parts use the v0.3 `kind` discriminator; v1.0 discriminates by member "
            "name (text/raw/url/data), spec Appendix A.2.1",
        )


def _state_of(task: dict[str, Any]) -> str | None:
    status = task.get("status")
    if isinstance(status, dict):
        state = status.get("state")
        if isinstance(state, str):
            return state
    return None
