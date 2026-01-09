# AnyRouter OpenCode Bridge

一个专门为 [OpenCode](https://github.com/anomalyco/opencode) 和 [CherryStudio](https://cherry-ai.com) 设计的本地代理桥接工具，用于解决接入 [AnyRouter](https://anyrouter.top) (Claude Code API) 时遇到的 WAF 拦截和 TLS 指纹问题。

## 背景

AnyRouter 是一个专为 Claude Code 设计的 API Provider，具有严格的安全防护：
1.  **TLS 指纹校验**：拦截普通 Python/Node.js 的 HTTP 请求，必须使用 HTTP/2 且具备特定指纹。
2.  **严格的 Header 检查**：强制校验 `anthropic-client-name` 等客户端标识。
3.  **请求体校验**：检测请求是否包含 Claude Code 的工具定义。
4.  **仅支持 Anthropic 格式**：不支持 OpenAI `/chat/completions` 格式。

本项目通过运行一个轻量级的本地 Python 代理服务器（FastAPI + httpx/HTTP2），作为中间人进行协议清洗、格式转换和伪装，完美解决上述问题。

## 功能特性

*   ✅ **HTTP/2 支持**：使用 `httpx` 绕过 TLS 指纹检测。
*   ✅ **Header 伪装**：自动注入 Claude Code 的真实 Header（通过 mitmproxy 抓包验证）。
*   ✅ **工具注入**：对所有 Claude 模型自动注入 Claude Code 工具定义，绕过服务端检测。
*   ✅ **OpenAI 兼容**：自动将 `/chat/completions` 请求转换为 Anthropic `/messages` 格式。
*   ✅ **Body 清洗**：过滤可能导致 WAF 拦截的字段。
*   ✅ **流式透传**：完美支持 SSE (Server-Sent Events) 流式响应，打字机效果流畅。
*   ✅ **连接保持**：内置连接池和重试机制，应对上游不稳定性。
*   ✅ **配置灵活**：支持交互式配置向导、JSON 配置文件和热重载。

## 支持的客户端

| 客户端 | 支持状态 | 备注 |
|--------|----------|------|
| OpenCode | ✅ 完全支持 | 使用 `@ai-sdk/anthropic` |
| CherryStudio | ✅ 完全支持 | 使用 OpenAI 兼容模式 |
| 其他 OpenAI 兼容客户端 | ✅ 应该支持 | 通过 `/v1/chat/completions` |

## 快速开始

### 1. 下载

从 [Releases](https://github.com/Darkstarrd-dev/anyrouter-opencode-bridge/releases) 下载最新版本的 zip 包并解压，或者克隆仓库：

```bash
git clone https://github.com/Darkstarrd-dev/anyrouter-opencode-bridge.git
cd anyrouter-opencode-bridge
```

### 2. 安装依赖

需要 Python 3.8+ 环境。

```bash
pip install -r requirements.txt
```

### 3. 运行与配置

首次运行会自动进入配置向导：

```bash
python main.py
```

按提示输入：
*   **API Key**: 你的 AnyRouter API Key (`sk-...`)
*   **Proxy**: 是否使用系统代理（如 Clash/v2ray，建议开启以提高连接稳定性）

配置完成后，服务将在 `http://127.0.0.1:8765` 启动。

---

## 配置 OpenCode

在 OpenCode 的配置文件 (`~/.config/opencode/opencode.json`) 中添加或修改 Provider 配置：

```json
"anyrouter": {
  "npm": "@ai-sdk/anthropic",
  "name": "AnyRouter (via Bridge)",
  "options": {
    "baseURL": "http://127.0.0.1:8765/v1",
    "apiKey": "sk-placeholder" 
  },
  "models": {
    "claude-haiku-4-5-20251001": {
      "name": "Claude Haiku 4.5",
      "limit": { "context": 256000, "output": 128000 }
    },
    "claude-sonnet-4-5-20250929": {
      "name": "Claude Sonnet 4.5",
      "limit": { "context": 256000, "output": 128000 }
    },
    "claude-opus-4-5-20251101": {
      "name": "Claude Opus 4.5",
      "limit": { "context": 256000, "output": 128000 }
    }
  }
}
```

> **注意**：`apiKey` 在 OpenCode 配置中可以填任意值，因为真实的 Key 已由本地代理托管。

---

## 配置 CherryStudio

CherryStudio 使用 OpenAI 兼容格式，代理会自动进行格式转换。

### 配置步骤

1. 打开 CherryStudio 设置
2. 添加新的 API Provider
3. 配置如下：

| 配置项 | 值 |
|--------|-----|
| API 类型 | OpenAI 兼容 |
| API 地址 | `http://127.0.0.1:8765/v1` |
| API Key | 任意值（如 `sk-placeholder`） |
| 模型名称 | `claude-haiku-4-5-20251001` / `claude-sonnet-4-5-20250929` / `claude-opus-4-5-20251101` |

### 可用模型

在 CherryStudio 中添加以下模型：

- `claude-haiku-4-5-20251001` - 最快速度
- `claude-sonnet-4-5-20250929` - 平衡性能
- `claude-opus-4-5-20251101` - 最强能力

### 截图示例

```
API 地址: http://127.0.0.1:8765/v1
API Key:  sk-placeholder
模型:     claude-sonnet-4-5-20250929
```

---

## 高级用法

### 配置文件

设置保存在 `proxy_config.json`：

```json
{
    "api_key": "sk-...",
    "proxy_url": "http://127.0.0.1:7890",
    "use_proxy": true,
    "debug": false,
    "target_base_url": "https://anyrouter.top/v1"
}
```

### 重新配置

```bash
# 强制运行配置向导
python main.py --setup
```

### 热重载

修改配置文件后，无需重启服务：

```bash
curl -X POST http://127.0.0.1:8765/config/reload
```

### 健康检查

```bash
curl http://127.0.0.1:8765/health
```

### 开启调试模式

在 `proxy_config.json` 中设置 `"debug": true`，可以查看详细的请求日志。

---

## 常见问题

**Q: 为什么 CherryStudio 显示 404 错误？**
A: 请确保代理服务器正在运行，并且 API 地址配置为 `http://127.0.0.1:8765/v1`（注意末尾的 `/v1`）。

**Q: 为什么显示 500 错误？**
A: 通常是 AnyRouter 上游服务不稳定。代理会自动重试，如果持续失败请稍后再试。

**Q: 需要一直开着终端吗？**
A: 是的，或者使用以下方式后台运行：
- Windows: 使用 `nssm` 或 PowerShell `Start-Process`
- Linux/Mac: 使用 `nohup python main.py &` 或 `pm2`

**Q: 支持哪些模型？**
A: 支持 AnyRouter 提供的所有 Claude 模型，包括 Haiku、Sonnet 和 Opus 系列。

---

## 技术原理

1. **协议转换**：将 OpenAI `/chat/completions` 格式转换为 Anthropic `/messages` 格式
2. **Header 伪装**：注入 Claude Code 客户端的完整 Header 签名
3. **工具注入**：自动添加 17 个 Claude Code 工具定义（约 56KB）
4. **HTTP/2**：使用 httpx 的 HTTP/2 支持绕过 TLS 指纹检测

---

## 项目结构

```
anyrouter-opencode-bridge/
├── main.py                    # 代理主程序
├── claude_code_tools.json     # Claude Code 工具定义 (56KB)
├── claude_code_system.json    # Claude Code system prompt (13KB)
├── proxy_config.json          # 用户配置 (自动生成)
├── requirements.txt           # Python 依赖
└── README.md                  # 本文件
```

---

## 许可证

MIT
