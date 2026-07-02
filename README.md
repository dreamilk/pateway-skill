# pateway-skill

用命令行查询 PatewayAI 控制台数据的轻量工具 / 可复用 Agent 技能。

适用于 Codex、Claude Code、Cursor、Hermes 等 Agent，也可以作为独立 CLI 使用；不绑定特定 Agent 框架。

它可以查询：

- 账户余额 / 可用额度
- API Key 列表、服务模式、本月用量
- 24h / 7d / 30d 用量汇总
- 详细调用日志
- 服务模式支持的模型
- 每个 API Key 继承服务模式后支持哪些模型

> 说明：这个仓库本身是一个可独立运行的 CLI 工具，也可以作为 Hermes Agent 的 skill 使用。很多用户使用 Codex、Claude Code、Claude Desktop、Cursor 等 Agent，所以推荐直接把下面的“安装提示词”复制给你的 Agent，让它自动安装和验证。

---

## 方式一：复制给 Agent 的安装提示词（推荐）

把下面这段话直接复制给你的 Agent（Codex / Claude Code / Claude / Cursor / Hermes 都可以）：

```text
请帮我安装并配置 pateway-skill：

仓库地址：https://github.com/dreamilk/pateway-skill

要求：
1. clone 这个仓库到本地合适目录；
2. 安装 Python 依赖 cryptography（如果环境是 PEP668，请用 venv/uv，不要破坏系统 Python）；
3. 不要把任何 Pateway 邮箱、密码、token 写入仓库或提交；
4. 让我提供或自行读取环境变量 PATEWAY_EMAIL 和 PATEWAY_PASSWORD；
5. 运行 `python scripts/pateway_api.py balance` 验证能查询余额；
6. 运行 `python scripts/pateway_api.py keys` 验证能查询 API Key；
7. 如果当前环境是 Hermes Agent，请把它安装为 Hermes skill：复制到 `~/.hermes/skills/devops/pateway-dashboard/`，然后提示我在新会话或 `/skill pateway-dashboard` 后使用；
8. 如果当前环境不是 Hermes，也请保留 CLI 用法，并把常用命令写入当前项目的 AGENTS.md / CLAUDE.md / README 本地说明中，方便以后复用。

安装完成后，请告诉我：安装路径、验证结果、如何查询余额/用量/key/日志。
```

---

## 方式二：手动安装为 Hermes skill

```bash
git clone https://github.com/dreamilk/pateway-skill.git
mkdir -p ~/.hermes/skills/devops/pateway-dashboard
cp -r pateway-skill/* ~/.hermes/skills/devops/pateway-dashboard/
```

在 Hermes 中加载：

```text
/skill pateway-dashboard
```

之后可让 Hermes 帮你查：

```text
查一下 Pateway 还剩多少额度
查一下最近24小时 token 用量
查一下有哪些 key 在用
查一下 gpt-5.5 是不是经济模式
```

---

## 方式三：作为独立 CLI 使用

```bash
git clone https://github.com/dreamilk/pateway-skill.git
cd pateway-skill
python -m pip install -r requirements.txt
```

如果系统 Python 是 PEP668 保护环境，推荐：

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
```

或使用 uv：

```bash
uv venv
. .venv/bin/activate
uv pip install -r requirements.txt
```

---

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

---

## 常用命令

```bash
# 查账户额度
python scripts/pateway_api.py balance

# 查所有 API Key：状态、服务模式、本月用量
python scripts/pateway_api.py keys

# 查最近 24 小时用量
python scripts/pateway_api.py usage 24h

# 查最近 7 天用量
python scripts/pateway_api.py usage 7d

# 查最近调用明细
python scripts/pateway_api.py logs --page 1 --size 20

# 查服务模式支持哪些模型
python scripts/pateway_api.py modes

# 查每个 API Key 支持哪些模型
python scripts/pateway_api.py key-models

# 一次性输出全部信息
python scripts/pateway_api.py all
```

---

## 输出示例

以下是虚构示例，非真实账户数据：

```text
Available Quota:    $123.45
Monthly Spending:   $6.78
Total Rewards:      $200
```

```text
Key Name             Status     Mode         Limit          Used/Month
--------------------------------------------------------------------------
economy-key          active     经济模式      No limit     $       1.23
default-key          active     默认          No limit     $       0.45
```

---

## 安全注意事项

- 不要提交真实 `PATEWAY_EMAIL` / `PATEWAY_PASSWORD`。
- 不要提交 token 缓存文件。
- 登录 token 默认缓存到 `~/.hermes/cache/pateway_token.json`，权限会设置为 `0600`。
- 如果你把本工具交给 Agent 安装，要求它先检查仓库中是否包含敏感信息，再提交或同步。

---

## API 能力

| 端点 | 方法 | 用途 |
|------|------|------|
| `/auth/login` | POST | 登录并获取 token |
| `/balance/summary` | GET | 账户余额 / 可用额度 |
| `/user/api-keys` | GET | API Key 列表和用量 |
| `/usage/summary?period=24h\|7d\|30d` | GET | 用量汇总 |
| `/usage/details?page=N&pageSize=M` | GET | 调用明细 |
| `/service-modes/options` | GET | 服务模式和支持模型 |

---

## License

MIT
