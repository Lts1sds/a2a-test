# a2a-test

[![CI](https://github.com/Lts1sds/a2a-test/actions/workflows/ci.yml/badge.svg)](https://github.com/Lts1sds/a2a-test/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![Zero dependencies](https://img.shields.io/badge/dependencies-0-brightgreen.svg)](#設計原則)
[![A2A spec](https://img.shields.io/badge/spec-A2A%20v1.0.0-orange.svg)](https://a2a-protocol.org/latest/specification/)

[English](README.md) | [简体中文](README.zh-CN.md) | **日本語** | [한국어](README.ko.md) | [Español](README.es.md) | [Français](README.fr.md) | [Deutsch](README.de.md) | [Italiano](README.it.md) | [Русский](README.ru.md) | [Português (BR)](README.pt-BR.md)

---

**A2A（Agent2Agent）プロトコルサーバー向けコンフォーマンステストスイート。**
1 コマンドで A2A v1.0.0 仕様に準拠した完全なレポートを生成します。エージェント開発者、QA エンジニア、CI パイプライン向け。

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

## なぜ必要なのか

A2A プロトコルの **v1.0.0** には破壊的変更が含まれています。JSON-RPC メソッド名が PascalCase に変更（`message/send` → `SendMessage`）、Part とストリームイベントの `kind` 判別子が削除、トランスポート宣言が順序付き `supportedInterfaces` 配列へ移行しました。エコシステムは移行途中であり、多くのサーバーが作者の知らないうちに v0.3 方言を出力し続けています。

`a2a-test` は 1 つの問いに正確に答えます。**このエージェントはクリーンな v1.0 実装か？そうでない場合、どの条項に違反しているか？**

| | a2a-test | 公式 `a2a-cli` | `a2a-doctor` |
|---|---|---|---|
| 位置づけ | コンフォーマンステスト | 対話型クライアント | オフライントラフィック監査 |
| モード | ライブサーバーへの能動的プローブ | 手動チャット / 手動呼び出し | 録画済みトラフィックの再生 |
| CI 対応の終了コード | あり | なし | あり |
| v0.3 レガシー検出 | あり | — | 部分 |

## 特徴

- **3 つのスイート、1 コマンド**——Agent Card 構造、JSON-RPC プロトコル動作、タスクライフサイクルセマンティクスを公開仕様に照らして検証。
- **v0.3 レガシー検出**——`preferredTransport`、`supportsExtendedAgentCard`、スラッシュ形式メソッド名、`kind` 判別子などの pre-1.0 挙動を検出し、各項目の正確な移行ノートを提示。
- **生プロトコル、依存ゼロ**——標準ライブラリのみで JSON-RPC 2.0 over HTTP を実装し、SSE を手動解析。公式 SDK はあえて使用しません。SDK は非準拠レスポンスを黙って正規化し、テスト対象のバグを覆い隠すためです。
- **仕様に忠実なエンドポイント発見**——JSON-RPC エンドポイントは Agent Card の `supportedInterfaces[].url` から読み取ります（仕様 §4.4.6）。固定パスを前提にしません。
- **3 つの出力形式**——human / TAP 14 / JSON。終了コード（0/1）はそのまま CI ゲートになります。

## インストール

```bash
pip install a2a-test            # PyPI 公開後
pip install git+https://github.com/Lts1sds/a2a-test   # ソースから
```

Python 3.9 以降が必要。ランタイム依存はありません。

## クイックスタート

```bash
a2a-test all http://localhost:9999
```

| コマンド | 範囲 |
|---|---|
| `a2a-test card <url>` | Agent Card：発見、必須フィールド、interfaces、skills、署名、v0.3 レガシーフィールド |
| `a2a-test probe <url>` | JSON-RPC：メソッドスタイル、エラーコードマトリクス、A2A-Version ネゴシエーション |
| `a2a-test task <url>` | ライフサイクル：SendMessage → ポーリング → 終了状態 → ガード → SSE ストリーミング |
| `a2a-test all <url>` | 上記すべて |

オプション：`--format human|tap|json`、`--timeout <秒>`、`--task-timeout <秒>`、`--message <テキスト>`。

### CI 統合

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

いずれかのチェックが FAIL すると終了コードは `1`（WARN は失敗扱いにしない）。TAP 14 出力は任意の標準 CI テストレポーターに接続できます。

## 検査項目

**`agent-card`** — *Agent Card、仕様 §4.4 / §8*

- well-known URI `/.well-known/agent-card.json` が到達可能かつ解析可能
- 必須フィールドが揃っている：`name`、`description`、`supportedInterfaces`、`version`、`capabilities`、`defaultInputModes`、`defaultOutputModes`、`skills`
- 各 interface が `url`、`protocolBinding`（`JSONRPC` / `GRPC` / `HTTP+JSON`）、`protocolVersion` を宣言
- skills に必須フィールドがあり id が一意
- JWS `signatures` が構造的に有効（`alg`/`kid` を含む base64url protected header）
- v0.3 レガシートップレベルフィールド：`preferredTransport`、`additionalInterfaces`、`supportsExtendedAgentCard`、`url`、`security`

**`protocol`** — *JSON-RPC バインディング、仕様 §9*

- メソッドスタイル：v1.0 PascalCase（`GetTask`）vs v0.3 スラッシュ形式（`tasks/get`）
- エラーコードマトリクス：`-32001` TaskNotFound、`-32601` MethodNotFound、`-32700` パースエラー、`-32600` 無効リクエスト、`-32602` 無効パラメータ
- `A2A-Version` ネゴシエーション：未対応の `9.9` には `-32009` VersionNotSupportedError が必須。空ヘッダーは 0.3 として解釈され、サーバーをクラッシュさせてはならない

**`task`** — *タスクライフサイクル、仕様 §3.1 / §4.1*

- `SendMessage` が `Task` または `Message` を返す。id はサーバー生成。`contextId` が存在。状態は `TASK_STATE_*` 列挙内
- ポーリングで終了状態に到達（`TASK_STATE_COMPLETED` / `FAILED` / `CANCELED` / `REJECTED`）
- 終了状態のタスクは `CancelTask`（`-32002`）と追加メッセージ（`-32004`）を拒否
- ストリーミング（`capabilities.streaming` が真の場合）：SSE フレーミング、先頭イベントが Task、終了状態でストリームを閉じる、`kind` 判別子なし

## 設計原則

1. **公式 SDK 不使用。** コンフォーマンスツールは生のワイヤープロトコルを話す必要がある。SDK は非準拠レスポンスを覆い隠す。
2. **慣例ではなく仕様に従う。** エンドポイント発見、バージョンネゴシエーション、エラーセマンティクスは v1.0.0 仕様本文に基づき実装。
3. **依存ゼロ。** `urllib`、`json`、`http.server`（インプロセスフィクスチャサーバー用）で十分。あらゆる OS、Python 3.9+ で `pip install` するだけ。

## ロードマップ

- [ ] REST バインディングプローブ（`POST /message:send`、Google AIP スタイル）と gRPC バインディングプローブ
- [ ] Agent Card 署名の完全検証（JWS + RFC 8785 正規化）
- [ ] エージェント固有シナリオ向け宣言型 YAML テストケース
- [ ] pytest プラグイン
- [ ] PR コメント付き GitHub Action

## 開発

```bash
pip install -e ".[dev]"
pytest                                   # 19 テスト
ruff check src tests && ruff format --check src tests
mypy src/a2a_test
```

テストスイートはインプロセスで 2 つの実 HTTP サーバーを起動します。仕様準拠の v1.0 フィクスチャ（ゼロ失敗が必須）と、意図的に v0.3 方言を使用するフィクスチャ（正確な検出が必須）です。ツールは仕様に対しても、自身のバグ検出能力に対してもテストされています。

## ライセンス

[MIT](LICENSE)
