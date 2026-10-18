"""Zero-dependency HTTP + JSON-RPC + SSE client for A2A servers.

Deliberately does NOT use an official A2A SDK: a conformance tool must speak
the raw protocol so that server-side bugs are not silently papered over by
SDK-side fixups.
"""

from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request
from collections.abc import Iterator
from typing import Any

CARD_WELL_KNOWN = "/.well-known/agent-card.json"
JSONRPC_CONTENT_TYPE = "application/json"
SSE_CONTENT_TYPE = "text/event-stream"
DEFAULT_TIMEOUT = 30.0


class A2AClient:
    """Minimal raw-protocol client for one A2A server (JSON-RPC binding).

    The JSON-RPC endpoint is *not* a fixed path: per spec v1.0.0 搂4.4.6 it is
    declared by the Agent Card's ``supportedInterfaces[].url``. The client
    resolves the endpoint from the card on first RPC (falling back to the
    base URL when no card is available).
    """

    def __init__(self, base_url: str, timeout: float = DEFAULT_TIMEOUT) -> None:
        # base_url: scheme://host[:port] with optional path prefix, no trailing slash
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._ssl_context: ssl.SSLContext | None = None
        self._endpoint: str | None = None
        self.last_http_status: int | None = None
        self.last_content_type: str | None = None

    def card_url(self) -> str:
        return self.base_url + CARD_WELL_KNOWN

    def set_endpoint(self, url: str) -> None:
        """Explicitly pin the JSON-RPC endpoint (skips card discovery)."""
        self._endpoint = url.rstrip("/")

    def endpoint_url(self) -> str:
        """Resolve the JSON-RPC endpoint, discovering it from the card if needed."""
        if self._endpoint is not None:
            return self._endpoint
        resolved = self._discover_endpoint()
        self._endpoint = resolved
        return resolved

    def _discover_endpoint(self) -> str:
        """Find the first JSONRPC interface URL in the agent card; fallback to base."""
        fallback = self.base_url + "/"
        try:
            status, _ctype, body = self.get(self.card_url())
            if status != 200:
                return fallback
            card = json.loads(body)
            if not isinstance(card, dict):
                return fallback
            interfaces = card.get("supportedInterfaces")
            if isinstance(interfaces, list):
                for iface in interfaces:
                    if (
                        isinstance(iface, dict)
                        and iface.get("protocolBinding") == "JSONRPC"
                        and isinstance(iface.get("url"), str)
                        and iface["url"]
                    ):
                        return iface["url"]
                    if (
                        isinstance(iface, dict)
                        and isinstance(iface.get("url"), str)
                        and iface["url"]
                        and "protocolBinding" not in iface
                    ):
                        # tolerate cards that omit protocolBinding but expose a URL
                        return iface["url"]
        except (ValueError, OSError):
            return fallback
        return fallback

    def _request(
        self,
        url: str,
        data: bytes | None,
        headers: dict[str, str],
        method: str | None = None,
    ) -> tuple[int, str, str]:
        """Return (http_status, content_type, body_text).

        Network-level failures return status 0 with an empty body instead of
        raising, so conformance checks can report them uniformly.
        """
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            resp = urllib.request.urlopen(req, timeout=self.timeout, context=self._ssl_context)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            ctype = e.headers.get("Content-Type", "")
            return int(e.code), ctype, body
        except (urllib.error.URLError, OSError, ConnectionError):
            return 0, "", ""
        with resp:
            body = resp.read().decode("utf-8", "replace")
            ctype = resp.headers.get("Content-Type", "")
            return int(resp.status), ctype, body

    def get(self, url: str, headers: dict[str, str] | None = None) -> tuple[int, str, str]:
        h = {"Accept": "application/json"}
        if headers:
            h.update(headers)
        return self._request(url, None, h, method="GET")

    def post_json(
        self,
        url: str,
        payload: Any,
        headers: dict[str, str] | None = None,
        raw_body: str | None = None,
    ) -> tuple[int, str, str]:
        h = {"Content-Type": JSONRPC_CONTENT_TYPE, "Accept": "application/json"}
        if headers:
            h.update(headers)
        if raw_body is not None:
            data = raw_body.encode("utf-8")
        else:
            data = json.dumps(payload).encode("utf-8")
        return self._request(url, data, h, method="POST")

    # ------------------------------------------------------------------
    # Agent card
    # ------------------------------------------------------------------
    def fetch_card(self) -> tuple[int, str, str]:
        status, ctype, body = self.get(self.card_url())
        self.last_http_status = status
        self.last_content_type = ctype
        return status, ctype, body

    # ------------------------------------------------------------------
    # JSON-RPC
    # ------------------------------------------------------------------
    def rpc(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        a2a_version: str = "1.0",
        request_id: Any = 1,
        extra_headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, Any] | None, str]:
        """Send a JSON-RPC request. Returns (http_status, parsed_json_or_None, raw_body)."""
        payload: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id, "method": method}
        if params is not None:
            payload["params"] = params
        headers = {"A2A-Version": a2a_version}
        if extra_headers:
            headers.update(extra_headers)
        status, _ctype, body = self.post_json(self.endpoint_url(), payload, headers=headers)
        parsed: dict[str, Any] | None = None
        try:
            obj = json.loads(body)
            if isinstance(obj, dict):
                parsed = obj
        except (ValueError, TypeError):
            parsed = None
        return status, parsed, body

    def rpc_raw(
        self,
        raw_body: str,
        a2a_version: str = "1.0",
        content_type: str | None = None,
    ) -> tuple[int, dict[str, Any] | None, str]:
        """Send a raw string body (for malformed-payload probes).

        Returns (http_status, parsed_json_or_None, raw_body) like ``rpc``.
        """
        headers = {"A2A-Version": a2a_version}
        if content_type is not None:
            headers["Content-Type"] = content_type
        status, _ctype, body = self.post_json(
            self.endpoint_url(), None, headers=headers, raw_body=raw_body
        )
        parsed: dict[str, Any] | None = None
        try:
            obj = json.loads(body)
            if isinstance(obj, dict):
                parsed = obj
        except (ValueError, TypeError):
            parsed = None
        return status, parsed, body

    # ------------------------------------------------------------------
    # SSE streaming
    # ------------------------------------------------------------------
    def post_stream(
        self,
        url: str,
        payload: Any,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, str, Iterator[str]]:
        """POST a JSON payload and read the answer as an SSE stream.

        Returns (http_status, content_type, iterator_of_data_payloads).
        The iterator yields the decoded ``data:`` payload of each SSE frame.
        """
        import socket

        data = json.dumps(payload).encode("utf-8")
        h = {
            "Content-Type": JSONRPC_CONTENT_TYPE,
            "Accept": SSE_CONTENT_TYPE + ", application/json",
        }
        if headers:
            h.update(headers)
        req = urllib.request.Request(url, data=data, headers=h, method="POST")
        try:
            resp = urllib.request.urlopen(req, timeout=self.timeout, context=self._ssl_context)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            return int(e.code), e.headers.get("Content-Type", ""), iter([body] if body else [])

        status = int(resp.status)
        ctype = resp.headers.get("Content-Type", "")
        if SSE_CONTENT_TYPE not in ctype:
            # Not a stream: read whole body, yield once
            body = resp.read().decode("utf-8", "replace")
            return status, ctype, iter([body] if body else [])

        def frames() -> Iterator[str]:
            try:
                buffer = b""
                while True:
                    chunk = resp.read(1024)
                    if not chunk:
                        break
                    buffer += chunk
                    while b"\n" in buffer:
                        line, buffer = buffer.split(b"\n", 1)
                        text = line.decode("utf-8", "replace").rstrip("\r")
                        if text.startswith("data:"):
                            yield text[5:].strip()
            except (socket.timeout, OSError):
                return
            finally:
                resp.close()

        return status, ctype, frames()

    def rpc_stream(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        a2a_version: str = "1.0",
        request_id: Any = 1,
    ) -> tuple[int, str, Iterator[str]]:
        """Send a JSON-RPC request expected to answer with an SSE stream.

        Returns (http_status, content_type, iterator_of_data_payloads).
        The iterator yields the decoded ``data:`` payload of each SSE frame.
        """
        payload: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id, "method": method}
        if params is not None:
            payload["params"] = params
        return self.post_stream(self.endpoint_url(), payload, headers={"A2A-Version": a2a_version})


def error_code(response: dict[str, Any] | None) -> int | None:
    """Extract the JSON-RPC error code from a response, if any."""
    if not isinstance(response, dict):
        return None
    err = response.get("error")
    if isinstance(err, dict):
        code = err.get("code")
        if isinstance(code, int):
            return code
    return None


def error_reason(response: dict[str, Any] | None) -> str:
    """Extract a human-readable reason string from an A2A error response."""
    if not isinstance(response, dict):
        return ""
    err = response.get("error")
    if not isinstance(err, dict):
        return ""
    parts = [str(err.get("message", ""))]
    data = err.get("data")
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                reason = item.get("reason")
                if isinstance(reason, str):
                    parts.append(reason)
                domain = item.get("domain")
                if isinstance(domain, str):
                    parts.append(domain)
    elif isinstance(data, dict):
        reason = data.get("reason")
        if isinstance(reason, str):
            parts.append(reason)
    return " | ".join(p for p in parts if p)
