# a2a-test

**Compliance test suite for A2A (Agent2Agent) protocol servers.**
One command, a full v1.0 conformance report.

```
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

The A2A protocol just shipped its **v1.0** release with breaking changes
(PascalCase method names, removal of the `kind` discriminator, the new
`supportedInterfaces` array). The ecosystem is mid-migration: many servers
still speak the v0.3 dialect without knowing it. `a2a-test` tells you, in one
command, whether your agent is a clean v1.0 citizen — and exactly which
legacy behaviors it still emits.

## Why

- **The spec moved.** v1.0.0 renamed every JSON-RPC method, reworked Agent
  Card transport declaration, and changed how polymorphic objects are
  discriminated. Old servers fail silently against new clients.
- **SDKs hide bugs.** Official SDKs are lenient and paper over non-conformant
  responses. `a2a-test` speaks the raw protocol (zero dependencies, standard
  library only) so server-side bugs surface exactly as a real client would
  see them.
- **CI needs a gate.** Exit code 0/1 plus TAP/JSON output makes conformance a
  merge-blocking check.

## Install

```bash
pip install a2a-test          # once published
# or from source
pip install git+https://github.com/Lts1sds/a2a-test
```

Python 3.9+, zero runtime dependencies.

## Usage

```bash
a2a-test card  <url>   # Agent Card: structure, required fields, v0.3 legacy fields
a2a-test probe <url>   # JSON-RPC: error-code matrix, method style, version negotiation
a2a-test task  <url>   # Lifecycle: SendMessage -> poll -> terminal state -> guards -> SSE
a2a-test all   <url>   # everything
```

```bash
a2a-test all http://localhost:9999 --format tap   # TAP 14 for CI
a2a-test all http://localhost:9999 --format json  # machine-readable
a2a-test all https://agent.example.com --timeout 60
```

Exit code is `1` when any check FAILs (WARN does not fail), so it can gate CI:

```yaml
# .github/workflows/conformance.yml
- run: pip install a2a-test
- run: a2a-test all https://staging.example.com --format tap
```

## What it checks

**agent-card** — discovery and structure per spec v1.0.0 §4.4/§8:
- well-known URI `/.well-known/agent-card.json` reachable and parseable
- all required fields (`name`, `description`, `supportedInterfaces`,
  `version`, `capabilities`, `defaultInputModes`, `defaultOutputModes`,
  `skills`)
- `supportedInterfaces` entries: `url` / `protocolBinding` / `protocolVersion`
- skills: required fields, unique ids
- JWS `signatures` structural validity
- **v0.3 legacy fields**: `preferredTransport`, `additionalInterfaces`,
  `supportsExtendedAgentCard`, top-level `url`/`security`

**protocol** — JSON-RPC binding per spec v1.0.0 §9:
- method style: v1.0 PascalCase vs v0.3 slash-style (`tasks/get`)
- error-code matrix: `-32001` TaskNotFound, `-32601` MethodNotFound,
  `-32700` parse error, `-32600` invalid request, `-32602` invalid params
- `A2A-Version` negotiation: unsupported `9.9` must yield `-32009`;
  empty header must be treated as 0.3

**task** — lifecycle per spec v1.0.0 §3.1/§4.1:
- `SendMessage` returns a `Task` or `Message`
- task ids server-generated, `contextId` present, states within the
  `TASK_STATE_*` enum
- polling reaches a terminal state; terminal tasks reject `CancelTask`
  (`-32002`) and further messages (`-32004`)
- streaming (when `capabilities.streaming`): SSE framing, first event is the
  Task, stream closes on terminal state, no `kind` discriminators

## Design notes

- **No official SDK.** A conformance tool must speak raw JSON-RPC/SSE; an SDK
  would silently normalize away the very bugs being tested for.
- **Endpoint discovery follows the spec.** The JSON-RPC endpoint is read from
  the Agent Card's `supportedInterfaces[].url` (with a base-URL fallback), not
  assumed to be a fixed path.
- **Zero dependencies.** Standard library only: `urllib`, `json`,
  `http.server` (for the in-process fixture servers used by the test suite).

## Roadmap

- [ ] REST binding (`POST /message:send`, Google AIP style) and gRPC binding probes
- [ ] Full Agent Card signature verification (JWS + RFC 8785 canonicalization)
- [ ] Declarative YAML test cases for agent-specific scenarios
- [ ] pytest plugin
- [ ] GitHub Action with PR comments

## Development

```bash
pip install -e ".[dev]"
pytest            # 19 tests; includes live in-process compliant + v0.3-legacy fixture servers
ruff check src tests && ruff format --check src tests
mypy src/a2a_test
```

The test suite spins up two real HTTP servers in-process: a spec-compliant
v1.0 fixture (must yield 0 failures) and a deliberately v0.3-dialect fixture
(must be caught with exactly the right findings) — the tool is tested against
both the spec and its own bug detector.

## License

MIT
