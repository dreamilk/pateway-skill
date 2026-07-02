---
name: pateway-dashboard
description: Query PatewayAI console data (balance/quota, API keys usage, usage logs, service modes, supported models) via the web API — no browser needed.
---

# PatewayAI Dashboard API Skill

用 PatewayAI Web API 查询控制台数据：账户额度、API Key 列表、每个 Key 的服务模式/月用量、全局用量趋势、调用明细、服务模式支持的模型，以及“某个 API Key 支持哪些模型”。无需浏览器。

## 安装

```bash
git clone https://github.com/dreamilk/pateway-skill.git
mkdir -p ~/.hermes/skills/devops/pateway-dashboard
cp -r pateway-skill/* ~/.hermes/skills/devops/pateway-dashboard/
```

或作为 Hermes skill 源安装时，将本仓库内容放到 `~/.hermes/skills/devops/pateway-dashboard/`。

## 配置凭证

脚本不会在仓库中硬编码账号密码。请设置环境变量：

```bash
export PATEWAY_EMAIL='your-email@example.com'
export PATEWAY_PASSWORD='your-password'
```

可选变量：

```bash
export PATEWAY_API_BASE='https://web.pateway.ai/api/v1'
export PATEWAY_TOKEN_FILE="$HOME/.hermes/cache/pateway_token.json"
```

## 使用方式

```bash
python scripts/pateway_api.py <subcommand>
```

子命令：

| 命令 | 用途 |
|------|------|
| `balance` | 账户额度摘要：可用额度、本月消费、累计奖励 |
| `keys` | API Key 列表：名称、状态、服务模式、月限额、本月用量 |
| `usage [24h\|7d\|30d]` | 全局用量统计 + 趋势：花费、请求数、输入/输出 tokens |
| `logs [--page N] [--size M]` | 使用明细：时间、Key、服务模式、模型、tokens、费用 |
| `modes` | 服务模式列表 + 每个 modeId 支持的模型 |
| `key-models` | 每个 API Key 继承其服务模式后支持的模型列表 |
| `all` | 一键显示 balance / keys / modes / key-models / usage / logs |

## 示例

```bash
python scripts/pateway_api.py balance
python scripts/pateway_api.py keys
python scripts/pateway_api.py usage 24h
python scripts/pateway_api.py logs --page 1 --size 20
python scripts/pateway_api.py modes
python scripts/pateway_api.py key-models
python scripts/pateway_api.py all
```

## API 端点

| 端点 | 方法 | 返回数据 |
|------|------|---------|
| `/auth/login` | POST | `{token, inviteCode}` |
| `/balance/summary` | GET | `{availableBalance, monthlySpending, totalGiftEarned}` |
| `/user/api-keys` | GET | 每个 key：`{apiKeyName, apiKey, status, serviceModeId, serviceModeTagZh, monthUsage, ...}` |
| `/usage/summary?period=24h\|7d\|30d` | GET | `{cards: {totalCost, inputTokens, outputTokens, requestCount}, trend: [...]}` |
| `/usage/details?page=N&pageSize=M` | GET | `{list: [{eventTime, keyName, model, serviceModeTagZh, totalTokens, totalCost, ...}]}` |
| `/service-modes/options` | GET | `{list: [{serviceModeId, tagZh, isDefault, modelNames, ...}]}` |

## 注意事项

- 认证使用 `x-token` header，脚本会自动登录并缓存 token。
- 密码使用 RSA-OAEP (SHA-256) 客户端加密后传输。
- Token 默认缓存 6 天。
- 请求间隔 ≥1.5s 防限流，遇 429 自动指数退避重试。
- 401 自动重新登录并重试一次。
- 不要提交真实 Pateway 邮箱、密码或 token。