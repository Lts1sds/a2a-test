"""JSON-RPC protocol conformance probes (error codes, versioning, method style)."""

from __future__ import annotations

import json

from .checks import CheckSuite
from .client import A2AClient, error_code, error_reason

# A2A v1.0.0 error codes (spec spec 5.4)
A2A_ERROR_CODES = {
    -32001: "TaskNotFoundError",
    -32002: "TaskNotCancelableError",
    -32003: "PushNotificationNotSupportedError",
    -32004: "UnsupportedOperationError",
    -32005: "ContentTypeNotSupportedError",
    -32006: "InvalidAgentResponseError",
    -32007: "ExtendedAgentCardNotConfiguredError",
    -32008: "ExtensionSupportRequiredError",
    -32009: "VersionNotSupportedError",
}

JSONRPC_PARSE_ERROR = -32700
JSONRPC_INVALID_REQUEST = -32600
JSONRPC_METHOD_NOT_FOUND = -32601
JSONRPC_INVALID_PARAMS = -32602

# v0.3 method names (slash style) mapped to their v1.0 PascalCase replacements
LEGACY_METHOD_ALIASES = {
    "GetTask": "tasks/get",
    "CancelTask": "tasks/cancel",
    "SendMessage": "message/send",
    "SendStreamingMessage": "message/stream",
    "ListTasks": "tasks/list",
    "SubscribeToTask": "tasks/subscribeToTask",
}


def probe_protocol(suite: CheckSuite, client: A2AClient) -> None:
    """Run the full JSON-RPC conformance probe battery."""
    group = "protocol"
    _probe_method_style(suite, group, client)
    _probe_error_matrix(suite, group, client)
    _probe_version_negotiation(suite, group, client)


def _probe_method_style(suite: CheckSuite, group: str, client: A2AClient) -> None:
    """Detect whether the server uses v1.0 PascalCase or v0.3 slash method names."""
    status, resp, _body = client.rpc("GetTask", {"id": "a2a-test-nonexistent-id"})
    code = error_code(resp)

    if code == JSONRPC_METHOD_NOT_FOUND:
        # PascalCase GetTask not recognized; try the v0.3 alias
        _s2, resp2, _b2 = client.rpc("tasks/get", {"id": "a2a-test-nonexistent-id"})
        code2 = error_code(resp2)
        if code2 is not None and code2 != JSONRPC_METHOD_NOT_FOUND:
            suite.check(
                group,
                "method-style",
                False,
                "server rejects v1.0 PascalCase methods but answers v0.3 slash-style "
                "(`tasks/get`): pre-1.0 dialect (spec v1.0.0 spec 9.1 requires PascalCase)",
            )
        else:
            suite.check(
                group,
                "method-style",
                False,
                f"neither GetTask nor tasks/get answered (HTTP {status}, "
                f"code {code}/{code2}); server may not implement the JSON-RPC binding",
            )
    elif code is not None:
        suite.check(
            group, "method-style", True, "v1.0 PascalCase methods accepted (GetTask reachable)"
        )
    else:
        suite.check(
            group,
            "method-style",
            True,
            "GetTask answered without a JSON-RPC error (HTTP "
            f"{status}); assuming v1.0 method style",
        )


def _probe_error_matrix(suite: CheckSuite, group: str, client: A2AClient) -> None:
    """Fire malformed / edge-case requests and verify error codes."""
    # 1. GetTask with a nonexistent id -> expect -32001 TaskNotFoundError
    _status, resp, _body = client.rpc("GetTask", {"id": "a2a-test-nonexistent-id"})
    code = error_code(resp)
    suite.check(
        group,
        "error:task-not-found",
        code == -32001,
        f"expected -32001 TaskNotFoundError, got {code}"
        + (f" ({error_reason(resp)})" if code is not None else ""),
        warn=(code is not None and code not in (-32001,)),
    )

    # 2. CancelTask with a nonexistent id -> expect -32001
    _status, resp, _body = client.rpc("CancelTask", {"id": "a2a-test-nonexistent-id"})
    code = error_code(resp)
    suite.check(
        group,
        "error:cancel-not-found",
        code == -32001,
        f"expected -32001 TaskNotFoundError, got {code}"
        + (f" ({error_reason(resp)})" if code is not None else ""),
    )

    # 3. Unknown method -> expect -32601 MethodNotFoundError
    _status, resp, _body = client.rpc("A2aTestDefinitelyNotAMethod")
    code = error_code(resp)
    suite.check(
        group,
        "error:method-not-found",
        code == JSONRPC_METHOD_NOT_FOUND,
        f"expected -32601 MethodNotFoundError, got {code}"
        + (f" ({error_reason(resp)})" if code is not None else ""),
    )

    # 4. Malformed JSON body -> expect -32700 JSONParseError
    _status, resp, body = client.rpc_raw("{this is not json")
    code = error_code(resp)
    suite.check(
        group,
        "error:parse-error",
        code == JSONRPC_PARSE_ERROR,
        f"expected -32700 JSONParseError, got {code}"
        + (f" (body starts: {body[:80]!r})" if code is None else ""),
    )

    # 5. Valid JSON but not a JSON-RPC Request object -> expect -32600
    _status, resp, _body = client.rpc_raw(json.dumps({"hello": "world"}))
    code = error_code(resp)
    suite.check(
        group,
        "error:invalid-request",
        code == JSONRPC_INVALID_REQUEST,
        f"expected -32600 InvalidRequestError, got {code}"
        + (f" ({error_reason(resp)})" if code is not None else ""),
    )

    # 6. SendMessage without required `message` param -> expect -32602
    _status, resp, _body = client.rpc("SendMessage", {"metadata": {}})
    code = error_code(resp)
    suite.check(
        group,
        "error:invalid-params",
        code == JSONRPC_INVALID_PARAMS,
        f"expected -32602 InvalidParamsError for SendMessage without `message`, got {code}"
        + (f" ({error_reason(resp)})" if code is not None else ""),
    )

    # 7. ListTasks (new in v1.0): informational support probe
    _status, resp, _body = client.rpc("ListTasks", {"pageSize": 1})
    code = error_code(resp)
    if code is None:
        suite.info(group, "method:ListTasks", "supported")
    elif code == JSONRPC_METHOD_NOT_FOUND:
        suite.info(group, "method:ListTasks", "not implemented (optional in practice, v1.0 method)")
    else:
        suite.info(group, "method:ListTasks", f"answered with code {code}")


def _probe_version_negotiation(suite: CheckSuite, group: str, client: A2AClient) -> None:
    """Verify A2A-Version header handling (spec spec 3.6, spec 14.2.1)."""
    # Unsupported version -> expect -32009 VersionNotSupportedError
    _status, resp, _body = client.rpc(
        "GetTask", {"id": "a2a-test-nonexistent-id"}, a2a_version="9.9"
    )
    code = error_code(resp)
    version_rejected = code == -32009 or _status == 400
    suite.check(
        group,
        "version:negotiation",
        version_rejected,
        "server should reject A2A-Version: 9.9 with -32009 VersionNotSupportedError "
        f"(or HTTP 400), got JSON-RPC code {code} / HTTP {_status}",
        warn=(code is not None and code != -32009 and _status != 400),
    )

    # Empty header value must be interpreted as 0.3, not crash the server
    _status, resp, _body = client.rpc("GetTask", {"id": "a2a-test-nonexistent-id"}, a2a_version="")
    code = error_code(resp)
    suite.check(
        group,
        "version:empty-header",
        code is not None,
        f"empty A2A-Version must be treated as 0.3 (spec spec 3.6.2); "
        f"got HTTP {_status}, code {code}",
    )
