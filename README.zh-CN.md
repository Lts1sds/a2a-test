# a2a-test

[![CI](https://github.com/Lts1sds/a2a-test/actions/workflows/ci.yml/badge.svg)](https://github.com/Lts1sds/a2a-test/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![Zero dependencies](https://img.shields.io/badge/dependencies-0-brightgreen.svg)](#设计原则)
[![A2A spec](https://img.shields.io/badge/spec-A2A%20v1.0.0-orange.svg)](https://a2a-protocol.org/latest/specification/)

[English](README.md) | **简体中文** | [日本語](README.ja.md) | [한국어](README.ko.md) | [Español](README.es.md) | [Français](README.fr.md) | [Deutsch](README.de.md) | [Italiano](README.it.md) | [Русский](README.ru.md) | [Português (BR)](README.pt-BR.md)

---

**A2A（Agent2Agent）协议服务器的合规性测试套件。**
一条命令即可依据 A2A v1.0.0 规范生成完整的合规报告——面向 Agent 开发者、QA 工程师与 CI 流水线。

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

## 为什么需要它

A2A 协议发布的 **v1.0.0** 包含多项破坏性变更：JSON-RPC 方法名改为 PascalCase（`message/send` → `SendMessage`）、Part 与流式事件中的 `kind` 判别器被移除、传输声明迁移至有序的 `supportedInterfaces` 数组。整个生态正处于迁移之中——大量服务器仍在输出 v0.3 方言，而其作者并不知情。

`a2a-test` 精确回答一个问题：**这个 Agent 是否是干净的 v1.0 实现？如果不是，具体违反了哪些条款？**

| | a2a-test | 官方 `a2a-cli` | `a2a-doctor` |
|---|---|---|---|
| 定位 | 合规性测试 | 交互式客户端 | 离线流量审计 |
| 模式 | 主动探测在线服务器 | 人工对话 / 手动调用 | 回放已录制流量 |
| CI 友好退出码 | 是 | 否 | 是 |
| v0.3 遗留检测 | 是 | — | 部分 |

## 特性

- **三套测试组，一条命令**——Agent Card 结构、JSON-RPC 协议行为、任务生命周期语义，全部对照已发布规范校验。
- **v0.3 遗留检测**——标记 `preferredTransport`、`supportsExtendedAgentCard`、斜杠风格方法名、`kind` 判别器等 pre-1.0 行为，并附每项的精确迁移说明。
- **裸协议、零依赖**——仅用标准库手写 JSON-RPC 2.0 over HTTP 并手工解析 SSE。刻意不使用官方 SDK——SDK 会悄悄修正不合规响应，掩盖被测的 bug。
- **遵循规范的端点发现**——JSON-RPC 端点从 Agent Card 的 `supportedInterfaces[].url` 读取（规范 §4.4.6），绝不假设为固定路径。
- **三种输出格式**——human / TAP 14 / JSON，退出码（0/1）可直接作为 CI 门禁。

## 安装

```bash
pip install a2a-test            # PyPI 发布后
pip install git+https://github.com/Lts1sds/a2a-test   # 从源码
```

要求 Python 3.9 及以上，无任何运行时依赖。

## 快速开始

```bash
a2a-test all http://localhost:9999
```

| 命令 | 范围 |
|---|---|
| `a2a-test card <url>` | Agent Card：发现、必填字段、interfaces、skills、签名、v0.3 遗留字段 |
| `a2a-test probe <url>` | JSON-RPC：方法风格、错误码矩阵、A2A-Version 协商 |
| `a2a-test task <url>` | 生命周期：SendMessage → 轮询 → 终态 → 守卫 → SSE 流式 |
| `a2a-test all <url>` | 以上全部 |

选项：`--format human|tap|json`、`--timeout <秒>`、`--task-timeout <秒>`、`--message <文本>`。

### CI 集成

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

任一检查 FAIL 时退出码为 `1`（WARN 不算失败），TAP 14 输出可接入任何标准 CI 测试报告器。

## 检查项

**`agent-card`** — *Agent Card，规范 §4.4 / §8*

- well-known URI `/.well-known/agent-card.json` 可达且可解析
- 必填字段齐全：`name`、`description`、`supportedInterfaces`、`version`、`capabilities`、`defaultInputModes`、`defaultOutputModes`、`skills`
- 每个 interface 声明 `url`、`protocolBinding`（`JSONRPC` / `GRPC` / `HTTP+JSON`）、`protocolVersion`
- skills 含必填字段且 id 唯一
- JWS `signatures` 结构合法（base64url protected header 含 `alg`/`kid`）
- v0.3 遗留顶层字段：`preferredTransport`、`additionalInterfaces`、`supportsExtendedAgentCard`、`url`、`security`

**`protocol`** — *JSON-RPC 绑定，规范 §9*

- 方法风格：v1.0 PascalCase（`GetTask`）vs v0.3 斜杠风格（`tasks/get`）
- 错误码矩阵：`-32001` TaskNotFound、`-32601` MethodNotFound、`-32700` 解析错误、`-32600` 无效请求、`-32602` 无效参数
- `A2A-Version` 协商：不支持的 `9.9` 必须返回 `-32009` VersionNotSupportedError；空 header 必须按 0.3 解释，绝不能令服务器崩溃

**`task`** — *任务生命周期，规范 §3.1 / §4.1*

- `SendMessage` 返回 `Task` 或 `Message`；id 由服务器生成；`contextId` 存在；状态在 `TASK_STATE_*` 枚举内
- 轮询到达终态（`TASK_STATE_COMPLETED` / `FAILED` / `CANCELED` / `REJECTED`）
- 终态任务拒绝 `CancelTask`（`-32002`）与后续消息（`-32004`）
- 流式（当 `capabilities.streaming` 为真）：SSE 帧格式、首事件为 Task、终态关闭流、无 `kind` 判别器

## 设计原则

1. **不使用官方 SDK。** 合规工具必须说裸协议；SDK 会掩盖不合规响应。
2. **遵循规范而非惯例。** 端点发现、版本协商、错误语义均按 v1.0.0 规范文本实现。
3. **零依赖。** `urllib`、`json` 与 `http.server`（用于进程内夹具服务器）足矣。任何 OS、Python 3.9+，`pip install` 即用。

## 路线图

- [ ] REST 绑定探针（`POST /message:send`，Google AIP 风格）与 gRPC 绑定探针
- [ ] Agent Card 签名完整验证（JWS + RFC 8785 规范化）
- [ ] 面向 Agent 特定场景的声明式 YAML 测试用例
- [ ] pytest 插件
- [ ] 带 PR 评论的 GitHub Action

## 开发

```bash
pip install -e ".[dev]"
pytest                                   # 19 项测试
ruff check src tests && ruff format --check src tests
mypy src/a2a_test
```

测试套件在进程内启动两个真实 HTTP 服务器：一个规范合规的 v1.0 夹具（必须零失败）、一个故意使用 v0.3 方言的夹具（必须被精准抓出全部问题）——工具既对照规范测试，也对照自身的 bug 检测能力测试。

## 许可证

[MIT](LICENSE)
