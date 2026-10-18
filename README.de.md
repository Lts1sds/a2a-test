# a2a-test

[![CI](https://github.com/Lts1sds/a2a-test/actions/workflows/ci.yml/badge.svg)](https://github.com/Lts1sds/a2a-test/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![Zero dependencies](https://img.shields.io/badge/dependencies-0-brightgreen.svg)](#designprinzipien)
[![A2A spec](https://img.shields.io/badge/spec-A2A%20v1.0.0-orange.svg)](https://a2a-protocol.org/latest/specification/)

[English](README.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [Español](README.es.md) | [Français](README.fr.md) | **Deutsch** | [Italiano](README.it.md) | [Русский](README.ru.md) | [Português (BR)](README.pt-BR.md)

---

**Konformitäts-Testsuite für A2A-Server (Agent2Agent-Protokoll).**
Ein einziger Befehl erzeugt einen vollständigen Konformitätsbericht gemäß der A2A-v1.0.0-Spezifikation — entwickelt für Agent-Entwickler, QA-Ingenieure und CI-Pipelines.

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

## Warum es dieses Tool gibt

Die A2A-Spezifikation hat **v1.0.0** mit Breaking Changes veröffentlicht: JSON-RPC-Methoden wurden in PascalCase umbenannt (`message/send` → `SendMessage`), der `kind`-Diskriminator wurde aus Parts und Stream-Ereignissen entfernt, und die Transport-Deklaration zog in das geordnete `supportedInterfaces`-Array um. Das Ökosystem steckt mitten in der Migration — viele Server emittieren weiterhin den v0.3-Dialekt, ohne dass ihre Autoren es wissen.

`a2a-test` beantwortet eine Frage präzise: **Ist dieser Agent eine saubere v1.0-Implementierung — und falls nicht, welche Klauseln verletzt er genau?**

| | a2a-test | offizielles `a2a-cli` | `a2a-doctor` |
|---|---|---|---|
| Zweck | Konformitätstests | Interaktiver Client | Offline-Traffic-Audit |
| Modus | Aktives Probing eines Live-Servers | Manueller Chat / manuelle Aufrufe | Wiedergabe aufgezeichneter Streams |
| CI-fähige Exit-Codes | Ja | Nein | Ja |
| v0.3-Legacy-Erkennung | Ja | — | Teilweise |

## Funktionen

- **Drei Suiten, ein Befehl** — Agent-Card-Struktur, JSON-RPC-Protokollverhalten und Task-Lebenszyklus-Semantik, alles gegen die veröffentlichte Spezifikation geprüft.
- **v0.3-Legacy-Erkennung** — markiert `preferredTransport`, `supportsExtendedAgentCard`, Methodennamen im Schrägstrich-Stil, `kind`-Diskriminatoren und weitere Pre-1.0-Verhaltensweisen, jeweils mit der exakten Migrationshinweis.
- **Rohprotokoll, null Abhängigkeiten** — implementiert JSON-RPC 2.0 über HTTP und parst SSE von Hand, ausschließlich mit der Standardbibliothek. Das offizielle SDK wird bewusst nicht verwendet, denn ein SDK würde nicht konforme Antworten stillschweigend normalisieren und die zu testenden Bugs verbergen.
- **Spezifikationstreue Endpunkt-Entdeckung** — der JSON-RPC-Endpunkt wird aus `supportedInterfaces[].url` der Agent Card gelesen (Spec §4.4.6), niemals als fester Pfad angenommen.
- **Drei Ausgabeformate** — human / TAP 14 / JSON — mit einem Exit-Code (0/1) als CI-Gate.

## Installation

```bash
pip install a2a-test            # nach PyPI-Veröffentlichung
pip install git+https://github.com/Lts1sds/a2a-test   # aus dem Quellcode
```

Benötigt Python 3.9 oder höher. Keine Laufzeit-Abhängigkeiten.

## Schnellstart

```bash
a2a-test all http://localhost:9999
```

| Befehl | Umfang |
|---|---|
| `a2a-test card <url>` | Agent Card: Discovery, Pflichtfelder, Interfaces, Skills, Signaturen, v0.3-Legacy-Felder |
| `a2a-test probe <url>` | JSON-RPC: Methodenstil, Fehlercode-Matrix, A2A-Version-Aushandlung |
| `a2a-test task <url>` | Lebenszyklus: SendMessage → Polling → Endzustand → Guards → SSE-Streaming |
| `a2a-test all <url>` | Alles zusammen |

Optionen: `--format human|tap|json`, `--timeout <Sek>`, `--task-timeout <Sek>`, `--message <Text>`.

### CI-Integration

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

Der Exit-Code ist `1`, sobald ein Check FAILt (WARN gilt nicht als Fehler), und die TAP-14-Ausgabe passt in jeden Standard-CI-Test-Reporter.

## Was geprüft wird

**`agent-card`** — *Agent Card, Spec §4.4 / §8*

- Well-Known-URI `/.well-known/agent-card.json` erreichbar und parsbar
- Pflichtfelder vorhanden: `name`, `description`, `supportedInterfaces`, `version`, `capabilities`, `defaultInputModes`, `defaultOutputModes`, `skills`
- Jedes Interface deklariert `url`, `protocolBinding` (`JSONRPC` / `GRPC` / `HTTP+JSON`) und `protocolVersion`
- Skills enthalten Pflichtfelder und eindeutige IDs
- JWS-`signatures` strukturell gültig (base64url Protected Header mit `alg`/`kid`)
- v0.3-Legacy-Felder auf oberster Ebene: `preferredTransport`, `additionalInterfaces`, `supportsExtendedAgentCard`, `url`, `security`

**`protocol`** — *JSON-RPC-Binding, Spec §9*

- Methodenstil: v1.0 PascalCase (`GetTask`) vs. v0.3 Schrägstrich-Stil (`tasks/get`)
- Fehlercode-Matrix: `-32001` TaskNotFound, `-32601` MethodNotFound, `-32700` Parse-Fehler, `-32600` ungültige Anfrage, `-32602` ungültige Parameter
- `A2A-Version`-Aushandlung: eine nicht unterstützte `9.9` muss `-32009` VersionNotSupportedError liefern; ein leerer Header muss als 0.3 interpretiert werden und den Server niemals zum Absturz bringen

**`task`** — *Task-Lebenszyklus, Spec §3.1 / §4.1*

- `SendMessage` gibt ein `Task` oder ein `Message` zurück; servergenerierte IDs; `contextId` vorhanden; Zustände innerhalb der `TASK_STATE_*`-Enumeration
- Polling erreicht einen Endzustand (`TASK_STATE_COMPLETED` / `FAILED` / `CANCELED` / `REJECTED`)
- Tasks im Endzustand lehnen `CancelTask` mit `-32002` und weitere Nachrichten mit `-32004` ab
- Streaming (wenn `capabilities.streaming`): SSE-Framing, erstes Ereignis ist der Task, der Stream schließt im Endzustand, keine `kind`-Diskriminatoren

## Designprinzipien

1. **Kein offizielles SDK.** Ein Konformitäts-Tool muss das Rohprotokoll sprechen; ein SDK würde nicht konforme Antworten verbergen.
2. **Der Spezifikation folgen, nicht Konventionen.** Endpunkt-Entdeckung, Versionsaushandlung und Fehlersemantik werden aus dem Text der v1.0.0-Spezifikation implementiert.
3. **Null Abhängigkeiten.** `urllib`, `json` und `http.server` (für die In-Process-Fixture-Server) genügen. `pip install` und los, auf jedem OS mit Python 3.9+.

## Roadmap

- [ ] REST-Binding-Sonden (`POST /message:send`, Google-AIP-Stil) und gRPC-Binding-Sonden
- [ ] Vollständige Signaturprüfung der Agent Card (JWS + RFC-8785-Kanonisierung)
- [ ] Deklarative YAML-Testfälle für agentenspezifische Szenarien
- [ ] pytest-Plugin
- [ ] GitHub Action mit PR-Kommentaren

## Entwicklung

```bash
pip install -e ".[dev]"
pytest                                   # 19 Tests
ruff check src tests && ruff format --check src tests
mypy src/a2a_test
```

Die Testsuite startet zwei echte HTTP-Server im Prozess: ein spezifikationskonformes v1.0-Fixture (muss null Fehler ergeben) und ein bewusst im v0.3-Dialekt gehaltenes Fixture (muss mit genau den richtigen Befunden erkannt werden). Das Tool wird also sowohl gegen die Spezifikation als auch gegen seinen eigenen Bug-Detektor getestet.

## Lizenz

[MIT](LICENSE)
