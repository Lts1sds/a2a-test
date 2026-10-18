# a2a-test

[![CI](https://github.com/Lts1sds/a2a-test/actions/workflows/ci.yml/badge.svg)](https://github.com/Lts1sds/a2a-test/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![Zero dependencies](https://img.shields.io/badge/dependencies-0-brightgreen.svg)](#설계-원칙)
[![A2A spec](https://img.shields.io/badge/spec-A2A%20v1.0.0-orange.svg)](https://a2a-protocol.org/latest/specification/)

[English](README.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md) | **한국어** | [Español](README.es.md) | [Français](README.fr.md) | [Deutsch](README.de.md) | [Italiano](README.it.md) | [Русский](README.ru.md) | [Português (BR)](README.pt-BR.md)

---

**A2A (Agent2Agent) 프로토콜 서버를 위한 컨포먼스 테스트 스위트.**
한 번의 명령으로 A2A v1.0.0 사양에 대한 전체 준수 보고서를 생성합니다. 에이전트 개발자, QA 엔지니어, CI 파이프라인을 위해 설계되었습니다.

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

## 왜 필요한가

A2A 프로토콜의 **v1.0.0**에는 파괴적 변경이 포함되어 있습니다. JSON-RPC 메서드 이름이 PascalCase로 변경(`message/send` → `SendMessage`)되고, Part와 스트림 이벤트의 `kind` 판별자가 제거되었으며, 트랜스포트 선언이 순서가 있는 `supportedInterfaces` 배열로 이동했습니다. 생태계는 마이그레이션 중간에 있으며, 많은 서버가 작성자도 모르는 사이에 v0.3 방언을 계속 출력하고 있습니다.

`a2a-test`는 하나의 질문에 정확하게 답합니다. **이 에이전트가 깨끗한 v1.0 구현인가? 그렇지 않다면 정확히 어떤 조항을 위반하는가?**

| | a2a-test | 공식 `a2a-cli` | `a2a-doctor` |
|---|---|---|---|
| 위치 | 컨포먼스 테스트 | 대화형 클라이언트 | 오프라인 트래픽 감사 |
| 모드 | 라이브 서버에 대한 능동적 프로빙 | 수동 채팅 / 수동 호출 | 기록된 트래픽 재생 |
| CI 친화적 종료 코드 | 있음 | 없음 | 있음 |
| v0.3 레거시 감지 | 있음 | — | 부분적 |

## 특징

- **세 가지 스위트, 한 번의 명령** — Agent Card 구조, JSON-RPC 프로토콜 동작, 태스크 라이프사이클 시맨틱을 게시된 사양에 따라 검증합니다.
- **v0.3 레거시 감지** — `preferredTransport`, `supportsExtendedAgentCard`, 슬래시 스타일 메서드 이름, `kind` 판별자 등 pre-1.0 동작을 감지하고 각 항목의 정확한 마이그레이션 노트를 제공합니다.
- **원시 프로토콜, 의존성 없음** — 표준 라이브러리만으로 JSON-RPC 2.0 over HTTP를 구현하고 SSE를 직접 파싱합니다. 공식 SDK는 의도적으로 사용하지 않습니다. SDK가 비준수 응답을 조용히 정규화하여 테스트 대상 버그를 가릴 수 있기 때문입니다.
- **사양에 정확한 엔드포인트 발견** — JSON-RPC 엔드포인트는 Agent Card의 `supportedInterfaces[].url`에서 읽습니다(사양 §4.4.6). 고정 경로를 가정하지 않습니다.
- **세 가지 출력 형식** — human / TAP 14 / JSON, 종료 코드(0/1)는 그대로 CI 게이트가 됩니다.

## 설치

```bash
pip install a2a-test            # PyPI 게시 후
pip install git+https://github.com/Lts1sds/a2a-test   # 소스에서
```

Python 3.9 이상이 필요하며 런타임 의존성은 없습니다.

## 빠른 시작

```bash
a2a-test all http://localhost:9999
```

| 명령 | 범위 |
|---|---|
| `a2a-test card <url>` | Agent Card: 발견, 필수 필드, interfaces, skills, 서명, v0.3 레거시 필드 |
| `a2a-test probe <url>` | JSON-RPC: 메서드 스타일, 오류 코드 매트릭스, A2A-Version 협상 |
| `a2a-test task <url>` | 라이프사이클: SendMessage → 폴링 → 종료 상태 → 가드 → SSE 스트리밍 |
| `a2a-test all <url>` | 위의 모든 것 |

옵션: `--format human|tap|json`, `--timeout <초>`, `--task-timeout <초>`, `--message <텍스트>`.

### CI 통합

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

어떤 검사든 FAIL이면 종료 코드는 `1`입니다(WARN은 실패로 간주하지 않음). TAP 14 출력은 표준 CI 테스트 리포터에 연결할 수 있습니다.

## 검사 항목

**`agent-card`** — *Agent Card, 사양 §4.4 / §8*

- well-known URI `/.well-known/agent-card.json` 도달 가능 및 파싱 가능
- 필수 필드 존재: `name`, `description`, `supportedInterfaces`, `version`, `capabilities`, `defaultInputModes`, `defaultOutputModes`, `skills`
- 각 interface가 `url`, `protocolBinding`(`JSONRPC` / `GRPC` / `HTTP+JSON`), `protocolVersion` 선언
- skills에 필수 필드와 고유 id 존재
- JWS `signatures`가 구조적으로 유효(`alg`/`kid` 포함 base64url protected header)
- v0.3 레거시 최상위 필드: `preferredTransport`, `additionalInterfaces`, `supportsExtendedAgentCard`, `url`, `security`

**`protocol`** — *JSON-RPC 바인딩, 사양 §9*

- 메서드 스타일: v1.0 PascalCase(`GetTask`) vs v0.3 슬래시 스타일(`tasks/get`)
- 오류 코드 매트릭스: `-32001` TaskNotFound, `-32601` MethodNotFound, `-32700` 파싱 오류, `-32600` 잘못된 요청, `-32602` 잘못된 매개변수
- `A2A-Version` 협상: 지원되지 않는 `9.9`는 `-32009` VersionNotSupportedError를 반환해야 하며, 빈 헤더는 0.3으로 해석되어야 하고 서버를 크래시시켜서는 안 됩니다

**`task`** — *태스크 라이프사이클, 사양 §3.1 / §4.1*

- `SendMessage`가 `Task` 또는 `Message` 반환. id는 서버 생성. `contextId` 존재. 상태는 `TASK_STATE_*` 열거형 내
- 폴링이 종료 상태에 도달(`TASK_STATE_COMPLETED` / `FAILED` / `CANCELED` / `REJECTED`)
- 종료 상태 태스크는 `CancelTask`(`-32002`)와 추가 메시지(`-32004`)를 거부
- 스트리밍(`capabilities.streaming`이 참일 때): SSE 프레이밍, 첫 이벤트는 Task, 종료 상태에서 스트림 종료, `kind` 판별자 없음

## 설계 원칙

1. **공식 SDK 미사용.** 컨포먼스 도구는 원시 와이어 프로토콜을 사용해야 합니다. SDK는 비준수 응답을 가립니다.
2. **관례가 아닌 사양을 따름.** 엔드포인트 발견, 버전 협상, 오류 시맨틱은 v1.0.0 사양 본문에 따라 구현됩니다.
3. **의존성 없음.** `urllib`, `json`, `http.server`(인프로세스 픽스처 서버용)면 충분합니다. 모든 OS, Python 3.9+에서 `pip install`로 바로 사용.

## 로드맵

- [ ] REST 바인딩 프로브(`POST /message:send`, Google AIP 스타일) 및 gRPC 바인딩 프로브
- [ ] Agent Card 서명 완전 검증(JWS + RFC 8785 정규화)
- [ ] 에이전트별 시나리오를 위한 선언적 YAML 테스트 케이스
- [ ] pytest 플러그인
- [ ] PR 코멘트가 있는 GitHub Action

## 개발

```bash
pip install -e ".[dev]"
pytest                                   # 19 테스트
ruff check src tests && ruff format --check src tests
mypy src/a2a_test
```

테스트 스위트는 인프로세스에서 두 개의 실제 HTTP 서버를 시작합니다. 사양 준수 v1.0 픽스처(0 실패여야 함)와 의도적으로 v0.3 방언을 사용하는 픽스처(정확히 감지되어야 함)입니다. 이 도구는 사양과 자체 버그 감지 능력 모두에 대해 테스트됩니다.

## 라이선스

[MIT](LICENSE)
