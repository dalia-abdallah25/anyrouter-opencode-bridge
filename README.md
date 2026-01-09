# AnyRouter OpenCode Bridge

一个专门为 [OpenCode](https://github.com/google/opencode) 设计的本地代理桥接工具，用于解决接入 [AnyRouter](https://anyrouter.top) (Claude Code API) 时遇到的 WAF 拦截和 TLS 指纹问题。

## 背景

AnyRouter 是一个专为 Claude Code 设计的 API Provider，具有严格的安全防护：
1.  **TLS 指纹校验**：拦截普通 Python/Node.js 的 HTTP 请求，必须使用 HTTP/2 且具备特定指纹。
2.  **严格的 Header 检查**：强制校验 `anthropic-client-name` 等客户端标识。
3.  **OpenCode 兼容性**：OpenCode 原生 SDK 无法完全模拟 Claude Code 的请求特征，导致被 WAF (阿里云) 拦截。

本项目通过运行一个轻量级的本地 Python 代理服务器（FastAPI + httpx/HTTP2），作为中间人进行协议清洗和伪装，完美解决上述问题。

## 功能特性

*   ✅ **HTTP/2 支持**：使用 `httpx` 绕过 TLS 指纹检测。
*   ✅ **Header 伪装**：自动注入 Claude Code 的真实 Header（通过 mitmproxy 抓包验证）。
*   ✅ **工具注入**：对 Sonnet/Opus 模型自动注入 Claude Code 工具定义，绕过服务端检测。
*   ✅ **Body 清洗**：过滤 OpenCode 可能发送的 OpenAI 专有字段，防止 WAF 拦截。
*   ✅ **流式透传**：完美支持 SSE (Server-Sent Events) 流式响应，打字机效果流畅。
*   ✅ **连接保持**：内置连接池和重试机制，应对上游不稳定性。
*   ✅ **配置灵活**：支持交互式配置向导、JSON 配置文件和热重载。

## 快速开始

### 1. 安装依赖

需要 Python 3.8+ 环境。

```bash
git clone https://github.com/YOUR_USERNAME/anyrouter-opencode-bridge.git
cd anyrouter-opencode-bridge
pip install -r requirements.txt
```

### 2. 运行与配置

首次运行会自动进入配置向导：

```bash
python main.py
```

按提示输入：
*   **API Key**: 你的 AnyRouter API Key (`sk-...`)
*   **Proxy**: 是否使用系统代理（如 Clash/v2ray，建议开启以提高连接稳定性）

配置完成后，服务将在 `http://127.0.0.1:8765` 启动。

### 3. 配置 OpenCode

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
      "name": "claude-haiku-4-5-20251001",
      "limit": { "context": 256000, "output": 128000 }
    },
    "claude-sonnet-4-5-20250929": {
      "name": "claude-sonnet-4-5-20250929",
      "limit": { "context": 256000, "output": 128000 }
    },
    "claude-opus-4-5-20251101": {
      "name": "claude-opus-4-5-20251101",
      "limit": { "context": 256000, "output": 128000 }
    }
  }
}
```

> **注意**：`apiKey` 在 OpenCode 配置中可以填任意值，因为真实的 Key 已由本地代理托管（当然填写真实的也没问题，代理会优先使用配置文件中的）。

## 高级用法

### 配置文件

设置保存在 `proxy_config.json`：

```json
{
    "api_key": "sk-...",
    "proxy_url": "http://127.0.0.1:7890",
    "use_proxy": true,
    "debug": false
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

## 常见问题

**Q: 为什么 OpenCode 里显示 Unknown Error?**
A: 请检查代理控制台日志。如果是 500/502/520 错误，通常是 AnyRouter 上游不稳定，代理会自动重试，但有时需要手动重试。

**Q: 需要一直开着终端吗？**
A: 是的，或者使用 `nohup` / `pm2` / `nssm` (Windows) 将其作为后台服务运行。

## 许可证

MIT
