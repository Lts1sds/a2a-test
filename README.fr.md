# a2a-test

[![CI](https://github.com/Lts1sds/a2a-test/actions/workflows/ci.yml/badge.svg)](https://github.com/Lts1sds/a2a-test/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![Zero dependencies](https://img.shields.io/badge/dependencies-0-brightgreen.svg)](#principes-de-conception)
[![A2A spec](https://img.shields.io/badge/spec-A2A%20v1.0.0-orange.svg)](https://a2a-protocol.org/latest/specification/)

[English](README.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [Español](README.es.md) | **Français** | [Deutsch](README.de.md) | [Italiano](README.it.md) | [Русский](README.ru.md) | [Português (BR)](README.pt-BR.md)

---

**Suite de tests de conformité pour les serveurs du protocole A2A (Agent2Agent).**
Une seule commande produit un rapport de conformité complet selon la spécification A2A v1.0.0 — conçu pour les développeurs d'agents, les ingénieurs QA et les pipelines CI.

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

## Pourquoi cet outil

La spécification A2A a publié sa version **v1.0.0** avec des changements cassants : les méthodes JSON-RPC ont été renommées en PascalCase (`message/send` → `SendMessage`), le discriminateur `kind` a été supprimé des Parts et des événements de flux, et la déclaration des transports a migré vers le tableau ordonné `supportedInterfaces`. L'écosystème est en pleine migration — de nombreux serveurs émettent encore le dialecte v0.3 sans que leurs auteurs le sachent.

`a2a-test` répond précisément à une question : **cet agent est-il une implémentation v1.0 propre, et sinon, quelles clauses viole-t-il exactement ?**

| | a2a-test | `a2a-cli` officiel | `a2a-doctor` |
|---|---|---|---|
| Vocation | Tests de conformité | Client interactif | Audit de trafic hors ligne |
| Mode | Sondage actif d'un serveur en ligne | Chat manuel / appels manuels | Relecture de flux enregistrés |
| Codes de sortie compatibles CI | Oui | Non | Oui |
| Détection de l'héritage v0.3 | Oui | — | Partielle |

## Fonctionnalités

- **Quatre suites, une commande** — structure de l'Agent Card, comportement du protocole JSON-RPC, sémantique du cycle de vie des tâches et binding REST (HTTP+JSON), le tout validé par rapport à la spécification publiée.
- **Détection de l'héritage v0.3** — signale `preferredTransport`, `supportsExtendedAgentCard`, les noms de méthodes à barres obliques, les discriminateurs `kind` et autres comportements pré-1.0, avec la note de migration exacte pour chacun.
- **Sondes du binding REST** — quand l'Agent Card déclare une interface `HTTP+JSON`, `POST /message:send`, les chemins de tâches au style Google AIP, les corps d'erreur `google.rpc.Status`, la pagination `ListTasks` et le streaming SSE sont vérifiés selon la spec §11.
- **Protocole brut, zéro dépendance** — implémente JSON-RPC 2.0 sur HTTP et analyse le SSE à la main, uniquement avec la bibliothèque standard. Le SDK officiel n'est volontairement pas utilisé : un SDK normaliserait silencieusement les réponses non conformes et masquerait les bugs testés.
- **Découverte du endpoint fidèle à la spécification** — le endpoint JSON-RPC est lu depuis `supportedInterfaces[].url` de l'Agent Card (spec §4.4.6), jamais supposé être un chemin fixe.
- **Trois formats de sortie** — human / TAP 14 / JSON — avec un code de sortie (0/1) qui sert de garde-fou CI.
- **GitHub Action** — utilisable directement via `uses: Lts1sds/a2a-test@v0.2.0` dans n'importe quel workflow.

## Installation

```bash
pip install a2a-test            # après publication sur PyPI
pip install git+https://github.com/Lts1sds/a2a-test   # depuis les sources
```

Nécessite Python 3.9 ou supérieur. Aucune dépendance à l'exécution.

## Démarrage rapide

```bash
a2a-test all http://localhost:9999
```

| Commande | Périmètre |
|---|---|
| `a2a-test card <url>` | Agent Card : découverte, champs requis, interfaces, skills, signatures, champs hérités v0.3 |
| `a2a-test probe <url>` | JSON-RPC : style des méthodes, matrice des codes d'erreur, négociation A2A-Version |
| `a2a-test task <url>` | Cycle de vie : SendMessage → polling → état terminal → gardes → streaming SSE |
| `a2a-test rest <url>` | Binding REST : `message:send`, chemins de tâches, erreurs `google.rpc.Status`, pagination, SSE |
| `a2a-test all <url>` | Tout ce qui précède |

Options : `--format human|tap|json`, `--timeout <sec>`, `--task-timeout <sec>`, `--message <texte>`.

### Intégration CI

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

Ou utilisez directement la GitHub Action empaquetée :

```yaml
      - uses: Lts1sds/a2a-test@v0.2.0
        with:
          url: https://staging.example.com
          command: all
          format: tap
```

Le code de sortie est `1` si un test échoue (WARN n'est pas un échec), et la sortie TAP 14 se branche sur n'importe quel reporter de tests CI standard.

## Ce qui est vérifié

**`agent-card`** — *Agent Card, spec §4.4 / §8*

- L'URI well-known `/.well-known/agent-card.json` est accessible et analysable
- Champs requis présents : `name`, `description`, `supportedInterfaces`, `version`, `capabilities`, `defaultInputModes`, `defaultOutputModes`, `skills`
- Chaque interface déclare `url`, `protocolBinding` (`JSONRPC` / `GRPC` / `HTTP+JSON`) et `protocolVersion`
- Les skills comportent les champs requis et des ids uniques
- Les `signatures` JWS sont structurellement valides (en-tête protégé base64url avec `alg`/`kid`)
- Champs hérités v0.3 de premier niveau : `preferredTransport`, `additionalInterfaces`, `supportsExtendedAgentCard`, `url`, `security`

**`protocol`** — *Binding JSON-RPC, spec §9*

- Style des méthodes : PascalCase v1.0 (`GetTask`) vs style à barres v0.3 (`tasks/get`)
- Matrice des codes d'erreur : `-32001` TaskNotFound, `-32601` MethodNotFound, `-32700` erreur d'analyse, `-32600` requête invalide, `-32602` paramètres invalides
- Négociation `A2A-Version` : une version non supportée `9.9` doit produire `-32009` VersionNotSupportedError ; un en-tête vide doit être interprété comme 0.3 et ne jamais faire planter le serveur

**`task`** — *Cycle de vie des tâches, spec §3.1 / §4.1*

- `SendMessage` renvoie un `Task` ou un `Message` ; ids générés par le serveur ; `contextId` présent ; états dans l'énumération `TASK_STATE_*`
- Le polling atteint un état terminal (`TASK_STATE_COMPLETED` / `FAILED` / `CANCELED` / `REJECTED`)
- Les tâches en état terminal rejettent `CancelTask` avec `-32002` et les messages suivants avec `-32004`
- Streaming (quand `capabilities.streaming`) : cadrage SSE, premier événement = le Task, fermeture du flux à l'état terminal, aucun discriminateur `kind`

**`rest`** — *Binding HTTP+JSON, spec §11* (exécuté quand l'Agent Card déclare une interface `HTTP+JSON`)

- `POST /message:send` répond 200 avec un objet `task`/`message` et `Content-Type: application/a2a+json`
- Ids de tâche inconnus : `GET /tasks/{id}` et `POST /tasks/{id}:cancel` renvoient 404 avec un corps `google.rpc.Status` (`code: 5`, `details[].reason: TASK_NOT_FOUND`)
- `GET /tasks` renvoie l'enveloppe `ListTasksResponse` avec `nextPageToken` / `pageSize` / `totalSize`
- Une `A2A-Version` non supportée est rejetée avec HTTP 400 (problem+json de la spec §6.4)
- `POST /message:stream` (quand `capabilities.streaming`) répond en SSE avec des événements Task / statusUpdate non enveloppés

## Principes de conception

1. **Pas de SDK officiel.** Un outil de conformité doit parler le protocole brut ; un SDK masquerait les réponses non conformes.
2. **Suivre la spécification, pas les conventions.** La découverte du endpoint, la négociation de version et la sémantique des erreurs sont implémentées depuis le texte de la spécification v1.0.0.
3. **Zéro dépendance.** `urllib`, `json` et `http.server` (pour les serveurs de fixture in-process) suffisent. `pip install` et c'est parti, sur tout OS avec Python 3.9+.

## Feuille de route

- [x] Sondes du binding REST (`POST /message:send`, style Google AIP) — *v0.2.0*
- [x] GitHub Action — *v0.2.0*
- [ ] Sondes du binding gRPC
- [ ] Vérification complète des signatures de l'Agent Card (JWS + canonisation RFC 8785)
- [ ] Cas de test YAML déclaratifs pour les scénarios propres à chaque agent
- [ ] Plugin pytest

## Développement

```bash
pip install -e ".[dev]"
pytest                                   # 24 tests
ruff check src tests && ruff format --check src tests
mypy src/a2a_test
```

La suite de tests démarre deux vrais serveurs HTTP in-process : un fixture conforme v1.0 (doit donner zéro échec) et un fixture volontairement en dialecte v0.3 (doit être détecté avec exactitude). L'outil est donc testé à la fois contre la spécification et contre son propre détecteur de bugs.

## Licence

[MIT](LICENSE)
