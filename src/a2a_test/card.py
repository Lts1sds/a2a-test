"""Agent Card discovery and structural conformance checks (spec v1.0.0)."""

from __future__ import annotations

import json
from typing import Any

from .checks import CheckSuite
from .client import A2AClient

REQUIRED_TOP_LEVEL = [
    "name",
    "description",
    "supportedInterfaces",
    "version",
    "capabilities",
    "defaultInputModes",
    "defaultOutputModes",
    "skills",
]

CORE_PROTOCOL_BINDINGS = {"JSONRPC", "GRPC", "HTTP+JSON"}

# v0.3 top-level fields removed in v1.0 (migration Appendix A)
LEGACY_TOP_LEVEL_FIELDS = {
    "preferredTransport": "v0.3: replaced by the ordered `supportedInterfaces` array",
    "additionalInterfaces": "v0.3: merged into `supportedInterfaces`",
    "supportsExtendedAgentCard": "v0.3: moved into `capabilities.extendedAgentCard`",
    "security": "v0.3: split into `securitySchemes` + `securityRequirements`",
    "url": "v0.3: moved into `supportedInterfaces[].url`",
}

LEGACY_CAPABILITY_FIELDS = {
    "stateTransitionHistory": "v0.3 capability field, not part of v1.0",
}


def fetch_agent_card(client: A2AClient) -> tuple[dict[str, Any] | None, str]:
    """Fetch and parse the agent card. Returns (card_or_None, error_detail)."""
    status, _ctype, body = client.fetch_card()
    if status == 0:
        return None, f"cannot connect to {client.card_url()} (network error)"
    if status != 200:
        return None, f"GET {client.card_url()} returned HTTP {status}"
    try:
        card = json.loads(body)
    except ValueError as e:
        return None, f"agent card is not valid JSON: {e}"
    if not isinstance(card, dict):
        return None, "agent card is not a JSON object"
    return card, ""


def check_agent_card(suite: CheckSuite, client: A2AClient) -> dict[str, Any] | None:
    """Run all agent-card checks. Returns the parsed card (None on fetch failure)."""
    group = "agent-card"
    card, err = fetch_agent_card(client)
    if card is None:
        suite.check(group, "card-fetch", False, err)
        return None
    suite.check(group, "card-fetch", True, f"HTTP 200, {len(json.dumps(card))} bytes")

    # --- required top-level fields -------------------------------------
    for field_name in REQUIRED_TOP_LEVEL:
        present = field_name in card and card[field_name] is not None
        if field_name in (
            "supportedInterfaces",
            "defaultInputModes",
            "defaultOutputModes",
            "skills",
        ):
            present = present and isinstance(card[field_name], list) and len(card[field_name]) > 0
        suite.check(
            group,
            f"field:{field_name}",
            present,
            "present" if present else "missing or empty (required by spec v1.0.0 spec 4.4.1)",
        )

    # --- v0.3 legacy field detection ------------------------------------
    for legacy_name, note in LEGACY_TOP_LEVEL_FIELDS.items():
        if legacy_name in card:
            suite.check(group, f"legacy-field:{legacy_name}", False, note, warn=False)
        else:
            suite.check(group, f"legacy-field:{legacy_name}", True, "not present (v1.0 clean)")

    # --- supportedInterfaces ---------------------------------------------
    interfaces = card.get("supportedInterfaces")
    if isinstance(interfaces, list) and interfaces:
        _check_interfaces(suite, group, interfaces)
    else:
        suite.skip(group, "interfaces-detail", "no usable supportedInterfaces array")

    # --- capabilities -----------------------------------------------------
    caps = card.get("capabilities")
    if isinstance(caps, dict):
        for cap in ("streaming", "pushNotifications", "extendedAgentCard"):
            if cap in caps:
                suite.info(group, f"capability:{cap}", str(caps[cap]).lower())
            else:
                suite.info(group, f"capability:{cap}", "absent (treated as false)")
        for legacy_name, note in LEGACY_CAPABILITY_FIELDS.items():
            if legacy_name in caps:
                suite.check(group, f"legacy-capability:{legacy_name}", False, note)
    else:
        suite.skip(group, "capabilities-detail", "capabilities missing or not an object")

    # --- skills -----------------------------------------------------------
    skills = card.get("skills")
    if isinstance(skills, list) and skills:
        _check_skills(suite, group, skills)
    else:
        suite.skip(group, "skills-detail", "no usable skills array")

    # --- signatures (structural only) --------------------------------------
    sigs = card.get("signatures")
    if isinstance(sigs, list) and sigs:
        _check_signatures(suite, group, sigs)
    else:
        suite.info(group, "signatures", "absent (optional)")

    # --- version string -----------------------------------------------------
    version = card.get("version")
    if isinstance(version, str) and version:
        suite.check(group, "version-format", True, f"agent version {version!r}")

    return card


def _check_interfaces(suite: CheckSuite, group: str, interfaces: list[Any]) -> None:
    ok_all = True
    details: list[str] = []
    for i, iface in enumerate(interfaces):
        if not isinstance(iface, dict):
            ok_all = False
            details.append(f"entry[{i}] is not an object")
            continue
        url = iface.get("url")
        binding = iface.get("protocolBinding")
        pv = iface.get("protocolVersion")
        if not isinstance(url, str) or not url:
            ok_all = False
            details.append(f"entry[{i}].url missing")
        if not isinstance(binding, str) or not binding:
            ok_all = False
            details.append(f"entry[{i}].protocolBinding missing")
        elif binding not in CORE_PROTOCOL_BINDINGS:
            suite.check(
                group,
                f"interface[{i}]:binding-known",
                False,
                f"protocolBinding {binding!r} is not a core binding "
                f"({', '.join(sorted(CORE_PROTOCOL_BINDINGS))}); custom bindings are allowed "
                "but interop is not guaranteed",
                warn=True,
            )
        if not isinstance(pv, str) or not pv:
            ok_all = False
            details.append(f"entry[{i}].protocolVersion missing")
        elif pv.startswith("1."):
            pass  # v1.x
        elif pv.startswith("0."):
            suite.check(
                group,
                f"interface[{i}]:version-current",
                False,
                f"protocolVersion {pv!r} is pre-1.0; server speaks a legacy dialect",
                warn=False,
            )
    suite.check(
        group,
        "interfaces-valid",
        ok_all,
        "; ".join(details) if details else f"{len(interfaces)} interface(s), first is preferred",
    )


def _check_skills(suite: CheckSuite, group: str, skills: list[Any]) -> None:
    ok_all = True
    details: list[str] = []
    ids: list[str] = []
    for i, skill in enumerate(skills):
        if not isinstance(skill, dict):
            ok_all = False
            details.append(f"skill[{i}] is not an object")
            continue
        sid = skill.get("id")
        if isinstance(sid, str) and sid:
            ids.append(sid)
        for req in ("id", "name", "description", "tags"):
            val = skill.get(req)
            if req == "tags":
                if not isinstance(val, list) or not val:
                    ok_all = False
                    details.append(f"skill[{i}].tags missing or empty")
            elif not isinstance(val, str) or not val:
                ok_all = False
                details.append(f"skill[{i}].{req} missing")
    suite.check(
        group, "skills-valid", ok_all, "; ".join(details) if details else f"{len(skills)} skill(s)"
    )
    if len(ids) != len(set(ids)):
        dupes = sorted({s for s in ids if ids.count(s) > 1})
        suite.check(group, "skill-ids-unique", False, f"duplicate skill ids: {dupes}")
    else:
        suite.check(group, "skill-ids-unique", True, "all skill ids unique")


def _check_signatures(suite: CheckSuite, group: str, sigs: list[Any]) -> None:
    import base64
    import re

    ok_all = True
    details: list[str] = []
    for i, sig in enumerate(sigs):
        if not isinstance(sig, dict):
            ok_all = False
            details.append(f"signature[{i}] is not an object")
            continue
        protected = sig.get("protected")
        signature = sig.get("signature")
        if not isinstance(protected, str) or not protected:
            ok_all = False
            details.append(f"signature[{i}].protected missing")
            continue
        try:
            decoded = base64.urlsafe_b64decode(protected + "=" * (-len(protected) % 4))
            header = json.loads(decoded)
            if "alg" not in header or "kid" not in header:
                ok_all = False
                details.append(f"signature[{i}].protected header lacks alg/kid")
        except (ValueError, TypeError):
            ok_all = False
            details.append(f"signature[{i}].protected is not base64url-encoded JSON")
            continue
        if not isinstance(signature, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", signature or ""):
            ok_all = False
            details.append(f"signature[{i}].signature is not base64url")
    suite.check(
        group,
        "signatures-valid",
        ok_all,
        "; ".join(details) if details else f"{len(sigs)} signature(s) structurally valid (JWS)",
    )
