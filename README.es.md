# a2a-test

[![CI](https://github.com/Lts1sds/a2a-test/actions/workflows/ci.yml/badge.svg)](https://github.com/Lts1sds/a2a-test/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![Zero dependencies](https://img.shields.io/badge/dependencies-0-brightgreen.svg)](#principios-de-diseño)
[![A2A spec](https://img.shields.io/badge/spec-A2A%20v1.0.0-orange.svg)](https://a2a-protocol.org/latest/specification/)

[English](README.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | **Español** | [Français](README.fr.md) | [Deutsch](README.de.md) | [Italiano](README.it.md) | [Русский](README.ru.md) | [Português (BR)](README.pt-BR.md)

---

**Suite de pruebas de conformidad para servidores del protocolo A2A (Agent2Agent).**
Un solo comando genera un informe completo de cumplimiento según la especificación A2A v1.0.0 — diseñado para desarrolladores de agentes, ingenieros de QA y pipelines de CI.

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

## Por qué existe

La versión **v1.0.0** del protocolo A2A incluye cambios de ruptura: los métodos JSON-RPC pasaron a PascalCase (`message/send` → `SendMessage`), se eliminó el discriminador `kind` de los Parts y de los eventos de flujo, y la declaración de transporte se trasladó al array ordenado `supportedInterfaces`. El ecosistema está en plena migración — muchos servidores siguen emitiendo el dialecto v0.3 sin que sus autores lo sepan.

`a2a-test` responde con precisión a una pregunta: **¿es este agente una implementación limpia de v1.0 y, si no, qué cláusulas viola exactamente?**

| | a2a-test | `a2a-cli` oficial | `a2a-doctor` |
|---|---|---|---|
| Propósito | Pruebas de conformidad | Cliente interactivo | Auditoría de tráfico offline |
| Modo | Sondeo activo de un servidor en vivo | Chat manual / llamadas manuales | Reproducción de flujos grabados |
| Códigos de salida aptos para CI | Sí | No | Sí |
| Detección de legado v0.3 | Sí | — | Parcial |

## Características

- **Tres suites, un comando** — estructura del Agent Card, comportamiento del protocolo JSON-RPC y semántica del ciclo de vida de las tareas, todo validado contra la especificación publicada.
- **Detección de legado v0.3** — señala `preferredTransport`, `supportsExtendedAgentCard`, nombres de método con barras, discriminadores `kind` y otros comportamientos pre-1.0, con la nota de migración exacta para cada uno.
- **Protocolo puro, cero dependencias** — implementa JSON-RPC 2.0 sobre HTTP y analiza SSE a mano usando solo la biblioteca estándar. No se usa el SDK oficial, porque un SDK normalizaría silenciosamente los errores que se están probando.
- **Descubrimiento de endpoint fiel a la especificación** — el endpoint JSON-RPC se lee del `supportedInterfaces[].url` del Agent Card (spec §4.4.6), nunca se asume una ruta fija.
- **Tres formatos de salida** — human / TAP 14 / JSON — con un código de salida (0/1) que actúa como compuerta de CI.

## Instalación

```bash
pip install a2a-test            # tras publicarse en PyPI
pip install git+https://github.com/Lts1sds/a2a-test   # desde el código fuente
```

Requiere Python 3.9 o superior. Sin dependencias en tiempo de ejecución.

## Inicio rápido

```bash
a2a-test all http://localhost:9999
```

| Comando | Alcance |
|---|---|
| `a2a-test card <url>` | Agent Card: descubrimiento, campos obligatorios, interfaces, skills, firmas, campos legados v0.3 |
| `a2a-test probe <url>` | JSON-RPC: estilo de métodos, matriz de códigos de error, negociación de A2A-Version |
| `a2a-test task <url>` | Ciclo de vida: SendMessage → sondeo → estado terminal → guardas → streaming SSE |
| `a2a-test all <url>` | Todo lo anterior |

Opciones: `--format human|tap|json`, `--timeout <seg>`, `--task-timeout <seg>`, `--message <texto>`.

### Integración con CI

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

El código de salida es `1` si cualquier verificación FALLA (WARN no cuenta como fallo), y la salida TAP 14 se conecta a cualquier reportador de pruebas de CI estándar.

## Qué se verifica

**`agent-card`** — *Agent Card, spec §4.4 / §8*

- URI well-known `/.well-known/agent-card.json` accesible y analizable
- Campos obligatorios presentes: `name`, `description`, `supportedInterfaces`, `version`, `capabilities`, `defaultInputModes`, `defaultOutputModes`, `skills`
- Cada interface declara `url`, `protocolBinding` (`JSONRPC` / `GRPC` / `HTTP+JSON`) y `protocolVersion`
- Los skills contienen los campos obligatorios e ids únicos
- Firmas JWS estructuralmente válidas (cabecera protegida base64url con `alg`/`kid`)
- Campos legados v0.3 de nivel superior: `preferredTransport`, `additionalInterfaces`, `supportsExtendedAgentCard`, `url`, `security`

**`protocol`** — *Binding JSON-RPC, spec §9*

- Estilo de métodos: PascalCase v1.0 (`GetTask`) vs estilo con barras v0.3 (`tasks/get`)
- Matriz de códigos de error: `-32001` TaskNotFound, `-32601` MethodNotFound, `-32700` error de análisis, `-32600` solicitud inválida, `-32602` parámetros inválidos
- Negociación de `A2A-Version`: una versión no soportada `9.9` debe producir `-32009` VersionNotSupportedError; una cabecera vacía debe interpretarse como 0.3 y nunca debe bloquear el servidor

**`task`** — *Ciclo de vida de las tareas, spec §3.1 / §4.1*

- `SendMessage` devuelve un `Task` o un `Message`; ids generados por el servidor; `contextId` presente; estados dentro del enum `TASK_STATE_*`
- El sondeo alcanza un estado terminal (`TASK_STATE_COMPLETED` / `FAILED` / `CANCELED` / `REJECTED`)
- Las tareas en estado terminal rechazan `CancelTask` con `-32002` y mensajes adicionales con `-32004`
- Streaming (cuando `capabilities.streaming`): enmarcado SSE, primer evento es el Task, el flujo se cierra en el estado terminal, sin discriminadores `kind`

## Principios de diseño

1. **Sin SDK oficial.** Una herramienta de conformidad debe hablar el protocolo puro; un SDK ocultaría las respuestas no conformes.
2. **Seguir la especificación, no las convenciones.** El descubrimiento de endpoints, la negociación de versión y la semántica de errores se implementan según el texto de la especificación v1.0.0.
3. **Cero dependencias.** `urllib`, `json` y `http.server` (para los servidores de fixture en proceso) son suficientes. `pip install` y listo, en cualquier SO con Python 3.9+.

## Hoja de ruta

- [ ] Sondas del binding REST (`POST /message:send`, estilo Google AIP) y del binding gRPC
- [ ] Verificación completa de firmas del Agent Card (JWS + canonización RFC 8785)
- [ ] Casos de prueba YAML declarativos para escenarios específicos de cada agente
- [ ] Plugin de pytest
- [ ] GitHub Action con comentarios en PRs

## Desarrollo

```bash
pip install -e ".[dev]"
pytest                                   # 19 pruebas
ruff check src tests && ruff format --check src tests
mypy src/a2a_test
```

La suite de pruebas levanta dos servidores HTTP reales en proceso: un fixture conforme a la especificación v1.0 (debe dar cero fallos) y un fixture deliberadamente en dialecto v0.3 (debe ser detectado con exactitud). La herramienta se prueba tanto contra la especificación como contra su propio detector de errores.

## Licencia

[MIT](LICENSE)
