# a2a-test

[![CI](https://github.com/Lts1sds/a2a-test/actions/workflows/ci.yml/badge.svg)](https://github.com/Lts1sds/a2a-test/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![Zero dependencies](https://img.shields.io/badge/dependencies-0-brightgreen.svg)](#design-principles)
[![A2A spec](https://img.shields.io/badge/spec-A2A%20v1.0.0-orange.svg)](https://a2a-protocol.org/latest/specification/)

**[English](README.md)** | [简体中文](README.zh-CN.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [Español](README.es.md) | [Français](README.fr.md) | [Deutsch](README.de.md) | [Italiano](README.it.md) | [Русский](README.ru.md) | [Português (BR)](README.pt-BR.md)

---

**A conformance test suite for A2A (Agent2Agent) protocol servers.**
One command produces a full compliance report against the A2A v1.0.0 specification — designed for agent developers, QA engineers, and CI pipelines.

```text
$ a2a-test all http://localhost:9999

[agent-card]
  PASS card-fetch - HTTP 200, 651 bytes
  PASS field:supportedInterfaces - present
  PASS legacy-field:preferredTransport - not present (v1.0 clean)
  ...
[protocol]
  PASS method-style - v1.0 PascalCase methods accepted (GetTask reachable)
  PASS error:task-not-found - expected -32001 TaskNotFoundError, got -32001
  PASS version:negotiation - rejected A2A-Version: 9.9 with -32009
  ...
[task]
  PASS lifecycle:terminal - reached terminal state TASK_STATE_COMPLETED
  PASS streaming:discriminator - no v0.3 `kind` discriminators

38 passed, 0 failed, 0 warned, 0 skipped
```

## Why this exists

The A2A protocol shipped **v1.0.0** with breaking changes: JSON-RPC methods were renamed to PascalCase (`message/send` → `SendMessage`), the `kind` discriminator was removed from Parts and stream events, and transport declaration moved into the ordered `supportedInterfaces` array. The ecosystem is mid-migration — many servers still emit v0.3 dialect without their authors knowing.

`a2a-test` answers one question precisely: **is this agent a clean v1.0 implementation, and if not, exactly which lines does it violate?**

| | a2a-test | official `a2a-cli` | `a2a-doctor` |
|---|---|---|---|
| Purpose | Conformance testing | Interactive client | Offline traffic audit |
| Mode | Active probing of a live server | Human chat / manual calls | Replay of recorded streams |
| CI-friendly exit codes | Yes | No | Yes |
| v0.3 legacy detection | Yes | — | Partial |

## Features

- **Three suites, one command** — Agent Card structure, JSON-RPC protocol behavior, and task-lifecycle semantics, all validated against the published specification.
- **v0.3 legacy detection** — flags `preferredTransport`, `supportsExtendedAgentCard`, slash-style method names, `kind` discriminators, and other pre-1.0 behaviors with the exact migration note for each.
- **Raw protocol, zero dependencies** — speaks plain JSON-RPC 2.0 over HTTP and parses SSE by hand using only the standard library. No official SDK is involved, because an SDK would silently normalize away the very bugs being tested for.
- **Spec-accurate endpoint discovery** — the JSON-RPC endpoint is read from the Agent Card's `supportedInterfaces[].url` (per spec §4.4.6), never assumed to be a fixed path.
- **Three output formats** — human-readable, TAP 14, and JSON — with an exit code (0/1) that gates CI.

## Installation

```bash
pip install a2a-test            # once published on PyPI
pip install git+https://github.com/Lts1sds/a2a-test   # from source
```

Requires Python 3.9 or later. No runtime dependencies.

## Quick start

```bash
a2a-test all http://localhost:9999
```

| Command | Scope |
|---|---|
| `a2a-test card <url>` | Agent Card: discovery, required fields, interfaces, skills, signatures, v0.3 legacy fields |
| `a2a-test probe <url>` | JSON-RPC: method style, error-code matrix, A2A-Version negotiation |
| `a2a-test task <url>` | Lifecycle: SendMessage → poll → terminal state → guards → SSE streaming |
| `a2a-test all <url>` | Everything above |

Options: `--format human|tap|json`, `--timeout <sec>`, `--task-timeout <sec>`, `--message <text>`.

### CI integration

```yaml
# .github/workflows/conformance.yml
name: A2A conformance
on: [push]
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - run: pip install a2a-test
      - run: a2a-test all https://staging.example.com --format tap
```

The exit code is `1` when any check FAILs (WARN does not fail), and TAP 14 output plugs into any standard CI test reporter.

## What gets checked

**`agent-card`** — *Agent Card, spec §4.4 / §8*

- Well-known URI `/.well-known/agent-card.json` reachable and parseable
- Required fields present: `name`, `description`, `supportedInterfaces`, `version`, `capabilities`, `defaultInputModes`, `defaultOutputModes`, `skills`
- Each interface declares `url`, `protocolBinding` (`JSONRPC` / `GRPC` / `HTTP+JSON`), and `protocolVersion`
- Skills carry required fields and unique ids
- JWS `signatures` structurally valid (base64url protected header with `alg`/`kid`)
- v0.3 legacy top-level fields: `preferredTransport`, `additionalInterfaces`, `supportsExtendedAgentCard`, `url`, `security`

**`protocol`** — *JSON-RPC binding, spec §9*

- Method style: v1.0 PascalCase (`GetTask`) vs v0.3 slash-style (`tasks/get`)
- Error-code matrix: `-32001` TaskNotFound, `-32601` MethodNotFound, `-32700` parse error, `-32600` invalid request, `-32602` invalid params
- `A2A-Version` negotiation: unsupported `9.9` must yield `-32009` VersionNotSupportedError; an empty header must be interpreted as 0.3, never crash the server

**`task`** — *Task lifecycle, spec §3.1 / §4.1*

- `SendMessage` returns a `Task` or a `Message`; ids are server-generated; `contextId` present; states within the `TASK_STATE_*` enum
- Polling reaches a terminal state (`TASK_STATE_COMPLETED` / `FAILED` / `CANCELED` / `REJECTED`)
- Terminal tasks reject `CancelTask` with `-32002` and further messages with `-32004`
- Streaming (when `capabilities.streaming`): SSE framing, first event is the Task, stream closes on terminal state, no `kind` discriminators

## Design principles

1. **No official SDK.** A conformance tool must speak the raw wire protocol; an SDK would paper over non-conformant responses.
2. **Follow the spec, not conventions.** Endpoint discovery, version negotiation, and error semantics are implemented from the v1.0.0 specification text.
3. **Zero dependencies.** `urllib`, `json`, and `http.server` (for in-process fixture servers) are sufficient. `pip install` and go, on any OS and Python 3.9+.

## Roadmap

- [ ] REST binding probes (`POST /message:send`, Google AIP style) and gRPC binding probes
- [ ] Full Agent Card signature verification (JWS + RFC 8785 canonicalization)
- [ ] Declarative YAML test cases for agent-specific scenarios
- [ ] pytest plugin
- [ ] GitHub Action with PR comments

## Development

```bash
pip install -e ".[dev]"
pytest                                   # 19 tests
ruff check src tests && ruff format --check src tests
mypy src/a2a_test
```

The test suite spins up two real HTTP servers in-process: a spec-compliant v1.0 fixture (must yield zero failures) and a deliberately v0.3-dialect fixture (must be caught with exactly the right findings). The tool is therefore tested both against the specification and against its own bug detector.

## License

[MIT](LICENSE)
