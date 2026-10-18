# a2a-test

[![CI](https://github.com/Lts1sds/a2a-test/actions/workflows/ci.yml/badge.svg)](https://github.com/Lts1sds/a2a-test/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![Zero dependencies](https://img.shields.io/badge/dependencies-0-brightgreen.svg)](#принципы-проектирования)
[![A2A spec](https://img.shields.io/badge/spec-A2A%20v1.0.0-orange.svg)](https://a2a-protocol.org/latest/specification/)

[English](README.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [Español](README.es.md) | [Français](README.fr.md) | [Deutsch](README.de.md) | [Italiano](README.it.md) | **Русский** | [Português (BR)](README.pt-BR.md)

---

**Набор тестов соответствия для серверов протокола A2A (Agent2Agent).**
Одна команда формирует полный отчёт о соответствии спецификации A2A v1.0.0 — для разработчиков агентов, QA-инженеров и CI-конвейеров.

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

## Зачем это нужно

Спецификация A2A выпустила версию **v1.0.0** с ломающими изменениями: методы JSON-RPC переименованы в PascalCase (`message/send` → `SendMessage`), дискриминатор `kind` удалён из Part и событий потока, объявление транспортов перенесено в упорядоченный массив `supportedInterfaces`. Экосистема находится в середине миграции — многие серверы по-прежнему выдают диалект v0.3, не зная об этом.

`a2a-test` точно отвечает на один вопрос: **является ли этот агент чистой реализацией v1.0, а если нет — какие именно пункты он нарушает?**

| | a2a-test | официальный `a2a-cli` | `a2a-doctor` |
|---|---|---|---|
| Назначение | Тесты соответствия | Интерактивный клиент | Офлайн-аудит трафика |
| Режим | Активное зондирование живого сервера | Ручной чат / ручные вызовы | Воспроизведение записанных потоков |
| CI-совместимые коды выхода | Да | Нет | Да |
| Обнаружение legacy v0.3 | Да | — | Частично |

## Возможности

- **Три набора, одна команда** — структура Agent Card, поведение протокола JSON-RPC и семантика жизненного цикла задач — всё проверяется по опубликованной спецификации.
- **Обнаружение legacy v0.3** — помечает `preferredTransport`, `supportsExtendedAgentCard`, имена методов через слэш, дискриминаторы `kind` и другие поведения pre-1.0 с точной пометкой о миграции для каждого.
- **Чистый протокол, ноль зависимостей** — реализует JSON-RPC 2.0 поверх HTTP и разбирает SSE вручную, используя только стандартную библиотеку. Официальный SDK намеренно не используется: SDK молча нормализует несоответствующие ответы и скрывает проверяемые ошибки.
- **Обнаружение endpoint по спецификации** — JSON-RPC endpoint читается из `supportedInterfaces[].url` Agent Card (спец. §4.4.6), а не предполагается фиксированным путём.
- **Три формата вывода** — human / TAP 14 / JSON — с кодом выхода (0/1), работающим как CI-гейт.

## Установка

```bash
pip install a2a-test            # после публикации на PyPI
pip install git+https://github.com/Lts1sds/a2a-test   # из исходников
```

Требуется Python 3.9 или новее. Никаких зависимостей времени выполнения.

## Быстрый старт

```bash
a2a-test all http://localhost:9999
```

| Команда | Область |
|---|---|
| `a2a-test card <url>` | Agent Card: обнаружение, обязательные поля, интерфейсы, skills, подписи, legacy-поля v0.3 |
| `a2a-test probe <url>` | JSON-RPC: стиль методов, матрица кодов ошибок, согласование A2A-Version |
| `a2a-test task <url>` | Жизненный цикл: SendMessage → опрос → терминальное состояние → защиты → SSE-стриминг |
| `a2a-test all <url>` | Всё перечисленное |

Опции: `--format human|tap|json`, `--timeout <сек>`, `--task-timeout <сек>`, `--message <текст>`.

### Интеграция с CI

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

Код выхода равен `1`, если хоть одна проверка провалена (WARN не считается провалом), а вывод TAP 14 подключается к любому стандартному CI-репортеру.

## Что проверяется

**`agent-card`** — *Agent Card, спец. §4.4 / §8*

- Well-known URI `/.well-known/agent-card.json` доступен и разбирается
- Обязательные поля на месте: `name`, `description`, `supportedInterfaces`, `version`, `capabilities`, `defaultInputModes`, `defaultOutputModes`, `skills`
- Каждый интерфейс объявляет `url`, `protocolBinding` (`JSONRPC` / `GRPC` / `HTTP+JSON`) и `protocolVersion`
- Skills содержат обязательные поля и уникальные id
- JWS-`signatures` структурно валидны (base64url protected header с `alg`/`kid`)
- Legacy-поля v0.3 верхнего уровня: `preferredTransport`, `additionalInterfaces`, `supportsExtendedAgentCard`, `url`, `security`

**`protocol`** — *JSON-RPC-биндинг, спец. §9*

- Стиль методов: v1.0 PascalCase (`GetTask`) против v0.3 через слэш (`tasks/get`)
- Матрица кодов ошибок: `-32001` TaskNotFound, `-32601` MethodNotFound, `-32700` ошибка разбора, `-32600` некорректный запрос, `-32602` некорректные параметры
- Согласование `A2A-Version`: неподдерживаемая `9.9` должна давать `-32009` VersionNotSupportedError; пустой заголовок должен трактоваться как 0.3 и не должен ронять сервер

**`task`** — *Жизненный цикл задач, спец. §3.1 / §4.1*

- `SendMessage` возвращает `Task` или `Message`; id генерируются сервером; `contextId` присутствует; состояния в пределах перечисления `TASK_STATE_*`
- Опрос достигает терминального состояния (`TASK_STATE_COMPLETED` / `FAILED` / `CANCELED` / `REJECTED`)
- Задачи в терминальном состоянии отклоняют `CancelTask` с `-32002` и дальнейшие сообщения с `-32004`
- Стриминг (при `capabilities.streaming`): SSE-фрейминг, первое событие — Task, поток закрывается на терминальном состоянии, без дискриминаторов `kind`

## Принципы проектирования

1. **Без официального SDK.** Инструмент проверки соответствия должен говорить по чистому протоколу; SDK маскирует несоответствующие ответы.
2. **Следовать спецификации, а не привычкам.** Обнаружение endpoint, согласование версий и семантика ошибок реализованы по тексту спецификации v1.0.0.
3. **Ноль зависимостей.** `urllib`, `json` и `http.server` (для внутрипроцессных фикстур-серверов) достаточно. `pip install` — и в путь, на любой ОС с Python 3.9+.

## Планы

- [ ] Зонды REST-биндинга (`POST /message:send`, стиль Google AIP) и gRPC-биндинга
- [ ] Полная проверка подписей Agent Card (JWS + канонизация RFC 8785)
- [ ] Декларативные YAML-тесты для сценариев конкретных агентов
- [ ] Плагин pytest
- [ ] GitHub Action с комментариями в PR

## Разработка

```bash
pip install -e ".[dev]"
pytest                                   # 19 тестов
ruff check src tests && ruff format --check src tests
mypy src/a2a_test
```

Набор тестов поднимает два настоящих HTTP-сервера в процессе: фикстур, соответствующий спецификации v1.0 (должен давать ноль провалов), и фикстур, намеренно говорящий на диалекте v0.3 (должен быть точно распознан). Инструмент проверяется и против спецификации, и против собственного детектора ошибок.

## Лицензия

[MIT](LICENSE)
