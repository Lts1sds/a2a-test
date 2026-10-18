# a2a-test

[![CI](https://github.com/Lts1sds/a2a-test/actions/workflows/ci.yml/badge.svg)](https://github.com/Lts1sds/a2a-test/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![Zero dependencies](https://img.shields.io/badge/dependencies-0-brightgreen.svg)](#princípios-de-design)
[![A2A spec](https://img.shields.io/badge/spec-A2A%20v1.0.0-orange.svg)](https://a2a-protocol.org/latest/specification/)

[English](README.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [Español](README.es.md) | [Français](README.fr.md) | [Deutsch](README.de.md) | [Italiano](README.it.md) | [Русский](README.ru.md) | **Português (BR)**

---

**Suíte de testes de conformidade para servidores do protocolo A2A (Agent2Agent).**
Um único comando gera um relatório completo de conformidade com a especificação A2A v1.0.0 — projetado para desenvolvedores de agentes, engenheiros de QA e pipelines de CI.

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

## Por que existe

O protocolo A2A lançou a versão **v1.0.0** com mudanças de ruptura: os métodos JSON-RPC foram renomeados para PascalCase (`message/send` → `SendMessage`), o discriminador `kind` foi removido dos Parts e dos eventos de stream, e a declaração de transportes migrou para o array ordenado `supportedInterfaces`. O ecossistema está no meio da migração — muitos servidores ainda emitem o dialeto v0.3 sem que seus autores saibam.

O `a2a-test` responde com precisão a uma pergunta: **este agente é uma implementação v1.0 limpa e, se não, quais cláusulas ele viola exatamente?**

| | a2a-test | `a2a-cli` oficial | `a2a-doctor` |
|---|---|---|---|
| Propósito | Testes de conformidade | Cliente interativo | Auditoria de tráfego offline |
| Modo | Sondagem ativa de um servidor ativo | Chat manual / chamadas manuais | Reprodução de fluxos gravados |
| Códigos de saída amigáveis ao CI | Sim | Não | Sim |
| Detecção de legado v0.3 | Sim | — | Parcial |

## Recursos

- **Quatro suítes, um comando** — estrutura do Agent Card, comportamento do protocolo JSON-RPC, semântica do ciclo de vida das tarefas e binding REST (HTTP+JSON), tudo validado contra a especificação publicada.
- **Detecção de legado v0.3** — sinaliza `preferredTransport`, `supportsExtendedAgentCard`, nomes de métodos com barra, discriminadores `kind` e outros comportamentos pre-1.0, com a nota exata de migração para cada um.
- **Sondas do binding REST** — quando o Agent Card declara uma interface `HTTP+JSON`, `POST /message:send`, os caminhos de tarefas no estilo Google AIP, os corpos de erro `google.rpc.Status`, a paginação de `ListTasks` e o streaming SSE são verificados conforme a spec §11.
- **Protocolo puro, zero dependências** — implementa JSON-RPC 2.0 sobre HTTP e analisa SSE manualmente usando apenas a biblioteca padrão. O SDK oficial não é usado de propósito: um SDK normalizaria silenciosamente respostas não conformes, escondendo exatamente os bugs que se quer testar.
- **Descoberta de endpoint fiel à especificação** — o endpoint JSON-RPC é lido do `supportedInterfaces[].url` do Agent Card (spec §4.4.6), nunca assumido como caminho fixo.
- **Três formatos de saída** — human / TAP 14 / JSON — com código de saída (0/1) que serve de gate para CI.
- **GitHub Action** — utilizável diretamente como `uses: Lts1sds/a2a-test@v0.2.0` em qualquer workflow.

## Instalação

```bash
pip install a2a-test            # após publicação no PyPI
pip install git+https://github.com/Lts1sds/a2a-test   # a partir do código-fonte
```

Requer Python 3.9 ou superior. Nenhuma dependência em tempo de execução.

## Início rápido

```bash
a2a-test all http://localhost:9999
```

| Comando | Escopo |
|---|---|
| `a2a-test card <url>` | Agent Card: descoberta, campos obrigatórios, interfaces, skills, assinaturas, campos legados v0.3 |
| `a2a-test probe <url>` | JSON-RPC: estilo de métodos, matriz de códigos de erro, negociação de A2A-Version |
| `a2a-test task <url>` | Ciclo de vida: SendMessage → polling → estado terminal → guardas → streaming SSE |
| `a2a-test rest <url>` | Binding REST: `message:send`, caminhos de tarefas, erros `google.rpc.Status`, paginação, SSE |
| `a2a-test all <url>` | Tudo acima |

Opções: `--format human|tap|json`, `--timeout <seg>`, `--task-timeout <seg>`, `--message <texto>`.

### Integração com CI

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

Ou use diretamente a GitHub Action empacotada:

```yaml
      - uses: Lts1sds/a2a-test@v0.2.0
        with:
          url: https://staging.example.com
          command: all
          format: tap
```

O código de saída é `1` se qualquer verificação FALHAR (WARN não conta como falha), e a saída TAP 14 se conecta a qualquer reporter de testes de CI padrão.

## O que é verificado

**`agent-card`** — *Agent Card, spec §4.4 / §8*

- URI well-known `/.well-known/agent-card.json` acessível e analisável
- Campos obrigatórios presentes: `name`, `description`, `supportedInterfaces`, `version`, `capabilities`, `defaultInputModes`, `defaultOutputModes`, `skills`
- Cada interface declara `url`, `protocolBinding` (`JSONRPC` / `GRPC` / `HTTP+JSON`) e `protocolVersion`
- Skills contêm campos obrigatórios e ids únicos
- Assinaturas JWS estruturalmente válidas (cabeçalho protegido base64url com `alg`/`kid`)
- Campos legados v0.3 de nível superior: `preferredTransport`, `additionalInterfaces`, `supportsExtendedAgentCard`, `url`, `security`

**`protocol`** — *Binding JSON-RPC, spec §9*

- Estilo de métodos: PascalCase v1.0 (`GetTask`) vs estilo com barra v0.3 (`tasks/get`)
- Matriz de códigos de erro: `-32001` TaskNotFound, `-32601` MethodNotFound, `-32700` erro de análise, `-32600` requisição inválida, `-32602` parâmetros inválidos
- Negociação de `A2A-Version`: uma versão não suportada `9.9` deve produzir `-32009` VersionNotSupportedError; um cabeçalho vazio deve ser interpretado como 0.3 e nunca derrubar o servidor

**`task`** — *Ciclo de vida das tarefas, spec §3.1 / §4.1*

- `SendMessage` retorna um `Task` ou um `Message`; ids gerados pelo servidor; `contextId` presente; estados dentro do enum `TASK_STATE_*`
- O polling atinge um estado terminal (`TASK_STATE_COMPLETED` / `FAILED` / `CANCELED` / `REJECTED`)
- Tarefas em estado terminal rejeitam `CancelTask` com `-32002` e mensagens adicionais com `-32004`
- Streaming (quando `capabilities.streaming`): enquadramento SSE, primeiro evento é o Task, o fluxo fecha no estado terminal, sem discriminadores `kind`

**`rest`** — *Binding HTTP+JSON, spec §11* (executado quando o Agent Card declara uma interface `HTTP+JSON`)

- `POST /message:send` responde 200 com um objeto `task`/`message` e `Content-Type: application/a2a+json`
- Ids de tarefa desconhecidos: `GET /tasks/{id}` e `POST /tasks/{id}:cancel` retornam 404 com um corpo `google.rpc.Status` (`code: 5`, `details[].reason: TASK_NOT_FOUND`)
- `GET /tasks` retorna o envelope `ListTasksResponse` com `nextPageToken` / `pageSize` / `totalSize`
- Uma `A2A-Version` não suportada é rejeitada com HTTP 400 (problem+json da spec §6.4)
- `POST /message:stream` (quando `capabilities.streaming`) responde em SSE com eventos Task / statusUpdate sem envoltório

## Princípios de design

1. **Sem SDK oficial.** Uma ferramenta de conformidade precisa falar o protocolo puro; um SDK esconderia respostas não conformes.
2. **Seguir a especificação, não convenções.** Descoberta de endpoint, negociação de versão e semântica de erros são implementadas a partir do texto da especificação v1.0.0.
3. **Zero dependências.** `urllib`, `json` e `http.server` (para os servidores de fixture em processo) são suficientes. `pip install` e pronto, em qualquer SO com Python 3.9+.

## Roteiro

- [x] Sondas do binding REST (`POST /message:send`, estilo Google AIP) — *v0.2.0*
- [x] GitHub Action — *v0.2.0*
- [ ] Sondas do binding gRPC
- [ ] Verificação completa de assinaturas do Agent Card (JWS + canonização RFC 8785)
- [ ] Casos de teste YAML declarativos para cenários específicos de cada agente
- [ ] Plugin pytest

## Desenvolvimento

```bash
pip install -e ".[dev]"
pytest                                   # 24 testes
ruff check src tests && ruff format --check src tests
mypy src/a2a_test
```

A suíte de testes sobe dois servidores HTTP reais em processo: uma fixture conforme com a especificação v1.0 (deve dar zero falhas) e uma fixture deliberadamente no dialeto v0.3 (deve ser detectada com precisão). A ferramenta é testada tanto contra a especificação quanto contra o seu próprio detector de bugs.

## Licença

[MIT](LICENSE)
