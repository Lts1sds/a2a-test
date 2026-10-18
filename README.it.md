# a2a-test

[![CI](https://github.com/Lts1sds/a2a-test/actions/workflows/ci.yml/badge.svg)](https://github.com/Lts1sds/a2a-test/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![Zero dependencies](https://img.shields.io/badge/dependencies-0-brightgreen.svg)](#principi-di-progetto)
[![A2A spec](https://img.shields.io/badge/spec-A2A%20v1.0.0-orange.svg)](https://a2a-protocol.org/latest/specification/)

[English](README.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [Español](README.es.md) | [Français](README.fr.md) | [Deutsch](README.de.md) | **Italiano** | [Русский](README.ru.md) | [Português (BR)](README.pt-BR.md)

---

**Suite di test di conformità per server del protocollo A2A (Agent2Agent).**
Un solo comando produce un report di conformità completo secondo la specifica A2A v1.0.0 — pensato per sviluppatori di agenti, ingegneri QA e pipeline CI.

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

## Perché esiste

Il protocollo A2A ha rilasciato la versione **v1.0.0** con modifiche di rottura: i metodi JSON-RPC sono stati rinominati in PascalCase (`message/send` → `SendMessage`), il discriminatore `kind` è stato rimosso dai Part e dagli eventi di stream, e la dichiarazione dei trasporti è migrata nell'array ordinato `supportedInterfaces`. L'ecosistema è in piena migrazione — molti server emettono ancora il dialetto v0.3 all'insaputa dei loro autori.

`a2a-test` risponde con precisione a una domanda: **questo agente è un'implementazione v1.0 pulita e, se no, quali clausole viola esattamente?**

| | a2a-test | `a2a-cli` ufficiale | `a2a-doctor` |
|---|---|---|---|
| Scopo | Test di conformità | Client interattivo | Audit del traffico offline |
| Modalità | Sondaggio attivo di un server live | Chat manuale / chiamate manuali | Riproduzione di flussi registrati |
| Codici di uscita adatti al CI | Sì | No | Sì |
| Rilevamento del legacy v0.3 | Sì | — | Parziale |

## Caratteristiche

- **Quattro suite, un comando** — struttura dell'Agent Card, comportamento del protocollo JSON-RPC, semantica del ciclo di vita dei task e binding REST (HTTP+JSON), tutto validato contro la specifica pubblicata.
- **Rilevamento del legacy v0.3** — segnala `preferredTransport`, `supportsExtendedAgentCard`, nomi di metodi con barra, discriminatori `kind` e altri comportamenti pre-1.0, con la nota di migrazione esatta per ciascuno.
- **Sonde del binding REST** — quando l'Agent Card dichiara un'interfaccia `HTTP+JSON`, `POST /message:send`, i percorsi dei task in stile Google AIP, i corpi di errore `google.rpc.Status`, la paginazione di `ListTasks` e lo streaming SSE vengono verificati secondo la spec §11.
- **Protocollo puro, zero dipendenze** — implementa JSON-RPC 2.0 su HTTP e analizza SSE a mano usando solo la libreria standard. L'SDK ufficiale non viene usato deliberatamente: un SDK normalizzerebbe silenziosamente le risposte non conformi, nascondendo i bug da testare.
- **Scoperta dell'endpoint fedele alla specifica** — l'endpoint JSON-RPC viene letto da `supportedInterfaces[].url` dell'Agent Card (spec §4.4.6), mai assunto come percorso fisso.
- **Tre formati di output** — human / TAP 14 / JSON — con un codice di uscita (0/1) che funge da gate per il CI.
- **GitHub Action** — utilizzabile direttamente come `uses: Lts1sds/a2a-test@v0.2.0` in qualsiasi workflow.

## Installazione

```bash
pip install a2a-test            # dopo la pubblicazione su PyPI
pip install git+https://github.com/Lts1sds/a2a-test   # dai sorgenti
```

Richiede Python 3.9 o successivo. Nessuna dipendenza a runtime.

## Inizio rapido

```bash
a2a-test all http://localhost:9999
```

| Comando | Ambito |
|---|---|
| `a2a-test card <url>` | Agent Card: discovery, campi obbligatori, interfacce, skill, firme, campi legacy v0.3 |
| `a2a-test probe <url>` | JSON-RPC: stile dei metodi, matrice dei codici di errore, negoziazione A2A-Version |
| `a2a-test task <url>` | Ciclo di vita: SendMessage → polling → stato terminale → guardie → streaming SSE |
| `a2a-test rest <url>` | Binding REST: `message:send`, percorsi dei task, errori `google.rpc.Status`, paginazione, SSE |
| `a2a-test all <url>` | Tutto quanto sopra |

Opzioni: `--format human|tap|json`, `--timeout <sec>`, `--task-timeout <sec>`, `--message <testo>`.

### Integrazione CI

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

Oppure usa direttamente la GitHub Action pacchettizzata:

```yaml
      - uses: Lts1sds/a2a-test@v0.2.0
        with:
          url: https://staging.example.com
          command: all
          format: tap
```

Il codice di uscita è `1` se un controllo FALLISCE (WARN non conta come fallimento), e l'output TAP 14 si collega a qualsiasi reporter di test CI standard.

## Cosa viene verificato

**`agent-card`** — *Agent Card, spec §4.4 / §8*

- L'URI well-known `/.well-known/agent-card.json` è raggiungibile e analizzabile
- Campi obbligatori presenti: `name`, `description`, `supportedInterfaces`, `version`, `capabilities`, `defaultInputModes`, `defaultOutputModes`, `skills`
- Ogni interfaccia dichiara `url`, `protocolBinding` (`JSONRPC` / `GRPC` / `HTTP+JSON`) e `protocolVersion`
- Le skill contengono i campi obbligatori e id univoci
- Le `signatures` JWS sono strutturalmente valide (header protetto base64url con `alg`/`kid`)
- Campi legacy v0.3 di primo livello: `preferredTransport`, `additionalInterfaces`, `supportsExtendedAgentCard`, `url`, `security`

**`protocol`** — *Binding JSON-RPC, spec §9*

- Stile dei metodi: PascalCase v1.0 (`GetTask`) vs stile con barra v0.3 (`tasks/get`)
- Matrice dei codici di errore: `-32001` TaskNotFound, `-32601` MethodNotFound, `-32700` errore di parsing, `-32600` richiesta non valida, `-32602` parametri non validi
- Negoziazione `A2A-Version`: una versione non supportata `9.9` deve produrre `-32009` VersionNotSupportedError; un header vuoto deve essere interpretato come 0.3 e non deve mai mandare in crash il server

**`task`** — *Ciclo di vita dei task, spec §3.1 / §4.1*

- `SendMessage` restituisce un `Task` o un `Message`; id generati dal server; `contextId` presente; stati entro l'enumerazione `TASK_STATE_*`
- Il polling raggiunge uno stato terminale (`TASK_STATE_COMPLETED` / `FAILED` / `CANCELED` / `REJECTED`)
- I task in stato terminale rifiutano `CancelTask` con `-32002` e messaggi ulteriori con `-32004`
- Streaming (quando `capabilities.streaming`): framing SSE, primo evento è il Task, lo stream si chiude allo stato terminale, nessun discriminatore `kind`

**`rest`** — *Binding HTTP+JSON, spec §11* (eseguito quando l'Agent Card dichiara un'interfaccia `HTTP+JSON`)

- `POST /message:send` risponde 200 con un oggetto `task`/`message` e `Content-Type: application/a2a+json`
- Id di task sconosciuti: `GET /tasks/{id}` e `POST /tasks/{id}:cancel` restituiscono 404 con un corpo `google.rpc.Status` (`code: 5`, `details[].reason: TASK_NOT_FOUND`)
- `GET /tasks` restituisce la busta `ListTasksResponse` con `nextPageToken` / `pageSize` / `totalSize`
- Una `A2A-Version` non supportata viene rifiutata con HTTP 400 (problem+json della spec §6.4)
- `POST /message:stream` (quando `capabilities.streaming`) risponde in SSE con eventi Task / statusUpdate non incapsulati

## Principi di progetto

1. **Nessun SDK ufficiale.** Uno strumento di conformità deve parlare il protocollo puro; un SDK maschere le risposte non conformi.
2. **Seguire la specifica, non le convenzioni.** Scoperta dell'endpoint, negoziazione della versione e semantica degli errori sono implementate dal testo della specifica v1.0.0.
3. **Zero dipendenze.** `urllib`, `json` e `http.server` (per i server fixture in-process) sono sufficienti. `pip install` e via, su qualsiasi OS con Python 3.9+.

## Roadmap

- [x] Sonde del binding REST (`POST /message:send`, stile Google AIP) — *v0.2.0*
- [x] GitHub Action — *v0.2.0*
- [ ] Sonde del binding gRPC
- [ ] Verifica completa delle firme dell'Agent Card (JWS + canonizzazione RFC 8785)
- [ ] Casi di test YAML dichiarativi per scenari specifici dell'agente
- [ ] Plugin pytest

## Sviluppo

```bash
pip install -e ".[dev]"
pytest                                   # 24 test
ruff check src tests && ruff format --check src tests
mypy src/a2a_test
```

La suite di test avvia due veri server HTTP in-process: un fixture conforme alla specifica v1.0 (deve dare zero errori) e un fixture deliberatamente in dialetto v0.3 (deve essere colto con esattezza). Lo strumento è quindi testato sia contro la specifica sia contro il proprio rilevatore di bug.

## Licenza

[MIT](LICENSE)
