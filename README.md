# ZZU Electricity Monitor

郑州大学宿舍电量监控系统

当前版本：**3.0**

## 功能特性

- 定时自动获取照明/空调电量
- 低电量多渠道通知 (20+ 渠道)
- 现代化前端，支持深色模式
- 内置房间查询器，快速查找房间编号
- 统一认证 MFA Token/可信设备方案，适配 GitHub Actions 非交互运行
- AES-256-GCM 加密存储
- GitHub Actions 全自动运行

## 3.0 发布要点

3.0 主要面向学校统一认证 MFA 变更、前端资源体积和上游可审查性：

- **认证链路**：新增 `mfa.py`、`tokens.py`、`ZZU_DEVICE_ID`、`TOKEN_ENCRYPTION_KEY`，Actions 优先复用加密 token；token 失效回退账密时再要求可信设备/MFA 就绪。
- **失败闭合**：`tokens.enc` 存在但无法解密时，工作流会直接失败，避免静默回退到需要短信验证码的账密登录。
- **前端资源**：移除内嵌大体积 `page/room.js`，改为 `page/data/rooms/*.json` 按区域懒加载。
- **发布隔离**：工作流会在上传 Pages artifact 前移除 `tokens.json` 和 `tokens.enc`；只有 `main` 分支会写入 `page` 分支和部署 Pages。
- **审查证据**：新增 CI 与单元测试，覆盖 MFA/token 关键路径、workflow 安全约束、房间 JSON 分片契约和前端语法。

发布 3.0 前建议至少确认：

```bash
python -m py_compile config.py monitor.py tokens.py mfa.py main.py crypto.py storage.py notify.py markdown.py tests/test_auth_flow.py tests/test_workflow_guards.py tests/test_room_data_contract.py
python -m unittest discover -s tests
node --check page/main.js
git diff --check
```

完整变更见 [CHANGELOG.md](CHANGELOG.md)。

## 3.0 最简教程

已经会用本项目的用户，可以只按这一版做：

1. 更新依赖到 3.0 代码后，在 GitHub Secrets 配置 `ACCOUNT`、`PASSWORD`、`LIGHT_ROOM`、`AC_ROOM`。
2. 推荐额外配置 `TOKEN_ENCRYPTION_KEY`，并保持本地和 GitHub Secrets 一致；需要固定可信设备时再配置 `ZZU_DEVICE_ID`。
3. 本地设置同一组环境变量后运行 `python mfa.py`，按提示输入短信验证码，生成 `page/data/tokens.json`。
4. 运行 `python crypto.py encrypt`，生成 `page/data/tokens.enc`；不要提交 `tokens.json`。
5. 将 `tokens.enc` 放到 `page` 分支的 `data/` 目录，用于后续 Actions 读取和刷新。
6. GitHub Pages 选择 **GitHub Actions** 作为部署源，在 Actions 里手动运行 `Update`，正式发布选择 `main` 分支。

上游维护者测试 3.0 时，可以手动运行 `Update` 并选择 `test` 分支。`test` 分支会跑认证和脚本，但不会写入 `page` 分支，也不会部署 Pages。

## 快速开始

### 第一步：Fork 仓库

点击右上角 Fork 按钮，将本仓库复制到你的账号下。

### 第二步：配置 Secrets

进入你 Fork 的仓库，点击 **Settings** → **Secrets and variables** → **Actions** → **New repository secret**，添加以下必填配置：

| 变量名 | 说明 | 示例 |
|--------|------|------|
| `ACCOUNT` | 郑州大学统一认证账号 | 学号 |
| `PASSWORD` | 统一认证密码 | 你的密码 |
| `LIGHT_ROOM` | 照明电量房间号 | 使用内置房间查询器获取 |
| `AC_ROOM` | 空调电量房间号 | 使用内置房间查询器获取 |

可选配置：

| 变量名 | 说明 | 示例 |
|--------|------|------|
| `ZZU_DEVICE_ID` | 统一认证 MFA 可信设备 ID，不填则使用 ZZU.Py 默认 deviceId | 已在安全中心设为可信的 deviceId |
| `TOKEN_ENCRYPTION_KEY` | `tokens.enc` 独立加密密钥，不填则兼容使用 `PASSWORD` | 建议使用长随机字符串 |

**获取房间号：**

1. 访问 [宿舍电量监控](https://elykia093.github.io/ZZU-Electricity-Monitor/)
2. 点击导航栏 **"房间查询"** 按钮
3. 依次选择区域、建筑、单元、房间号
4. 复制显示的照明和空调房间编号
5. 分别配置到 `LIGHT_ROOM` 和 `AC_ROOM`

支持主校区、北校区、东校区、南校区、护理学院、洛阳校区。

### 第三步：配置 GitHub Pages

进入你 Fork 的仓库，点击 **Settings** → **Pages**：

1. 在 **Source** 部分，将构建和部署源从 **"Deploy from a branch"** 改为 **"GitHub Actions"**
2. 保存设置

这样配置后，GitHub Actions 会自动将生成的页面部署到 GitHub Pages，你就可以通过 `https://你的用户名.github.io/ZZU-Electricity-Monitor/` 访问电量监控页面了。

### 第四步：启用 Actions

进入 **Actions** 页面，点击 **I understand my workflows, go ahead and enable them** 启用工作流。

**定时触发方式（二选一）：**

- **方式一：GitHub Actions 定时**（简单，但可能有 10-60 分钟延迟）

  编辑 `.github/workflows/static.yml`，取消注释 schedule 部分：
  ```yaml
  on:
    schedule:
      - cron: '0 16,20,0,4,8,12 * * *'  # UTC 时间，对应北京 0,4,8,12,16,20 点
    workflow_dispatch:
  ```

- **方式二：精确定时触发**（推荐，无延迟）

  参考下方 [精确定时触发（可选）](#精确定时触发可选) 配置。

你也可以点击 **Run workflow** 手动触发运行。

上游维护者如果要先在 `test` 分支验证 Actions，可以在 Actions 页面手动运行 `Update` 并选择 `test` 分支。该分支会执行安装依赖、解密 token、运行脚本和重新加密等步骤，但发布步骤只允许 `main` 分支执行，因此不会推送 `page` 分支，也不会部署 GitHub Pages。正式发布时再在 `main` 分支运行即可。

### 第五步：完成 MFA Token 初始化（推荐）

学校统一认证在 2026-06-02 左右新增了手机号短信验证。项目已适配 `ZZU.Py >= 7.2.1` 的 MFA 流程，但 GitHub Actions 不能交互输入短信验证码。

推荐做法：

1. 在本地设置 `ACCOUNT`、`PASSWORD`，建议设置稳定的 `ZZU_DEVICE_ID` 和长随机 `TOKEN_ENCRYPTION_KEY`
2. 运行 `python mfa.py`
3. 按提示输入短信验证码，生成 `page/data/tokens.json`
4. 运行 `python crypto.py encrypt` 生成 `page/data/tokens.enc`；如已设置 `TOKEN_ENCRYPTION_KEY`，后续 Actions 也必须使用同一个值
5. 将设备在统一认证安全中心设置为可信设备
6. 将同一个 `ZZU_DEVICE_ID` 和 `TOKEN_ENCRYPTION_KEY` 配置到 GitHub Secrets；如果本地不设置 `ZZU_DEVICE_ID`，Actions 也会使用 ZZU.Py 默认 deviceId

首次启用 MFA 时，需要让工作流能读到 `tokens.enc`：

- 推荐：将 `page/data/tokens.enc` 放到 `page` 分支的 `data/` 目录
- 如果只维护自己的私有 fork，可以临时强制添加 `page/data/tokens.enc` 到 `main` 并手动运行一次工作流；公开仓库不建议这样做，因为删除后历史记录中仍会保留该认证材料
- 不要提交 `page/data/tokens.json`

`tokens.enc` 虽然是加密文件，但仍是个人认证材料，默认已被 `.gitignore` 忽略。公开仓库的 `page` 分支密文仍可能被他人下载，因此建议使用独立的高强度 `TOKEN_ENCRYPTION_KEY`，不要只依赖统一认证密码。上游维护时不要接收 fork PR 中的个人 `tokens.enc`。

如果 `page` 分支中存在 `tokens.enc`，但 `TOKEN_ENCRYPTION_KEY` 或 `PASSWORD` 无法解密它，工作流会在解密步骤直接失败。此时请确认本地加密和 GitHub Secrets 使用的是同一个密钥，或重新运行 `python mfa.py` 与 `python crypto.py encrypt` 生成新的 `tokens.enc`。

工作流会在上传 GitHub Pages artifact 前移除 `tokens.json` 和 `tokens.enc`，避免认证文件直接出现在部署出来的网站目录中；`page` 分支中的 `tokens.enc` 仅用于后续 Actions 读取和刷新。

后续 Actions 会优先复用已加密保存的 token；即使当前设备仍提示 MFA，也会先尝试 token 登录。只有 token 失效并需要回退到账密登录时，如果当前设备仍要求短信 MFA，脚本才会停止并提示重新完成本地 MFA 初始化。

GitHub Actions 每次 runner 机器可能不同，但 ZZU.Py 传给统一认证的 `deviceId` 是稳定的：不设置时默认为 `ZZU.Py`，设置后使用 `ZZU_DEVICE_ID`。学校认证系统是否真正放行可信设备仍以统一认证 MFA 判断结果为准。

### 第六步：配置通知渠道（可选）

至少配置一个通知渠道以接收电量提醒。推荐使用 Telegram，无发送次数限制。

## 通知渠道配置

### Telegram（推荐）

每次运行都会发送通知，无发送次数限制。

| 变量名 | 说明 | 必填 |
|--------|------|------|
| `TELEGRAM_BOT_TOKEN` | Bot Token，从 @BotFather 获取 | 是 |
| `TELEGRAM_CHAT_ID` | Chat ID，从 @userinfobot 获取 | 是 |

**获取方法：**
1. 在 Telegram 搜索 @BotFather，发送 `/newbot` 创建机器人，获取 Token
2. 搜索 @userinfobot，发送任意消息获取你的 Chat ID
3. 给你创建的机器人发送一条消息（激活对话）

### Server酱

仅在电量不足时发送，节约每日 5 条的免费额度。

| 变量名 | 说明 | 必填 |
|--------|------|------|
| `SERVERCHAN_KEY` | SendKey，从 sct.ftqq.com 获取 | 是 |
| `SERVERCHAN_KEY2` | 备用 SendKey | 否 |
| `SERVERCHAN_KEY3` | 备用 SendKey | 否 |

### 邮件通知

仅在电量不足时发送。

| 变量名 | 说明 | 必填 |
|--------|------|------|
| `EMAIL` | 邮箱地址（发送和接收） | 是 |
| `SMTP_CODE` | SMTP 授权码（非邮箱密码） | 是 |
| `SMTP_SERVER` | SMTP 服务器地址 | 是 |

**常用 SMTP 服务器：**
- QQ邮箱：`smtp.qq.com`
- 163邮箱：`smtp.163.com`
- Gmail：`smtp.gmail.com`

### Bark（iOS）

| 变量名 | 说明 | 必填 |
|--------|------|------|
| `BARK_KEY` | Bark 推送密钥 | 是 |
| `BARK_URL` | 自建服务器地址 | 否 |

### 钉钉机器人

| 变量名 | 说明 | 必填 |
|--------|------|------|
| `DINGTALK_WEBHOOK` | 机器人 Webhook 地址 | 是 |
| `DINGTALK_SECRET` | 加签密钥 | 否 |

### 飞书机器人

| 变量名 | 说明 | 必填 |
|--------|------|------|
| `FEISHU_WEBHOOK` | 机器人 Webhook 地址 | 是 |
| `FEISHU_SECRET` | 加签密钥 | 否 |

### 企业微信

| 变量名 | 说明 | 必填 |
|--------|------|------|
| `WECOM_CORP_ID` | 企业 ID | 是 |
| `WECOM_AGENT_ID` | 应用 AgentId | 是 |
| `WECOM_SECRET` | 应用 Secret | 是 |
| `WECOM_TOUSER` | 接收用户，默认 @all | 否 |

### PushPlus

| 变量名 | 说明 | 必填 |
|--------|------|------|
| `PUSHPLUS_TOKEN` | 推送 Token | 是 |

### go-cqhttp

| 变量名 | 说明 | 必填 |
|--------|------|------|
| `GOCQHTTP_URL` | go-cqhttp 服务地址 | 是 |
| `GOCQHTTP_TOKEN` | 访问令牌 | 否 |
| `GOCQHTTP_TARGET` | 目标 QQ 号 | 是 |

### Gotify

| 变量名 | 说明 | 必填 |
|--------|------|------|
| `GOTIFY_URL` | Gotify 服务器地址 | 是 |
| `GOTIFY_TOKEN` | 应用 Token | 是 |

### iGot

| 变量名 | 说明 | 必填 |
|--------|------|------|
| `IGOT_KEY` | iGot 推送密钥 | 是 |

### PushDeer

| 变量名 | 说明 | 必填 |
|--------|------|------|
| `PUSHDEER_KEY` | PushDeer 推送密钥 | 是 |

### Synology Chat

| 变量名 | 说明 | 必填 |
|--------|------|------|
| `SYNOLOGY_CHAT_URL` | Synology Chat 服务器地址 | 是 |
| `SYNOLOGY_CHAT_TOKEN` | Incoming Webhook Token | 是 |

### Qmsg酱

| 变量名 | 说明 | 必填 |
|--------|------|------|
| `QMSG_KEY` | Qmsg 密钥 | 是 |
| `QMSG_QQ` | 指定接收的 QQ 号 | 否 |

### 智能微秘书

| 变量名 | 说明 | 必填 |
|--------|------|------|
| `AIBOTK_KEY` | API Key | 是 |
| `AIBOTK_TARGET` | 目标用户或群 | 是 |

### PushMe

| 变量名 | 说明 | 必填 |
|--------|------|------|
| `PUSHME_KEY` | PushMe 推送密钥 | 是 |

### Chronocat

| 变量名 | 说明 | 必填 |
|--------|------|------|
| `CHRONOCAT_URL` | Chronocat 服务地址 | 是 |
| `CHRONOCAT_TOKEN` | 访问令牌 | 否 |
| `CHRONOCAT_TARGET` | 目标 QQ 号 | 是 |

### ntfy

| 变量名 | 说明 | 必填 |
|--------|------|------|
| `NTFY_TOPIC` | ntfy 主题名称 | 是 |
| `NTFY_URL` | 自建服务器地址 | 否 |
| `NTFY_TOKEN` | 访问令牌 | 否 |

### 自定义 Webhook

| 变量名 | 说明 | 必填 |
|--------|------|------|
| `WEBHOOK_URL` | Webhook 地址 | 是 |
| `WEBHOOK_METHOD` | 请求方法，默认 POST | 否 |
| `WEBHOOK_HEADERS` | 请求头，JSON 格式 | 否 |
| `WEBHOOK_BODY_TEMPLATE` | 请求体模板，支持 `{{title}}` 和 `{{content}}` 占位符 | 否 |

## 通知逻辑

| 渠道 | 触发条件 | 说明 |
|------|----------|------|
| Telegram | 每次运行 | 无发送限制，推荐作为主要通知渠道 |
| 其他渠道 | 仅低电量 | 电量低于 10 度时发送，避免频繁打扰 |

## 通知示例

**电量充足时（仅 Telegram 收到）：**
```
🏠宿舍电量通报🏠

💡 照明剩余电量：125.0 度（充足）
❄️ 空调剩余电量：80.0 度（偏低）

当前电量充足，请保持关注。
```

**电量不足时（所有渠道都会收到）：**
```
⚠️宿舍电量预警⚠️

💡 照明剩余电量：8.5 度（警告）
❄️ 空调剩余电量：5.0 度（警告）

⚠️ 电量不足，请尽快充电！
```

## 项目结构

```
ZZU-Electricity-Monitor/
├── main.py              # 主程序入口，获取电量、通知并写入数据
├── mfa.py               # 本地 MFA 认证与 Token 初始化脚本
├── monitor.py           # 电量监控模块，含 ZZU.Py CAS 登录流程
├── tokens.py            # 统一认证 Token 文件读写模块
├── notify.py            # 通知模块，支持 20+ 通知渠道
├── storage.py           # 数据存储模块，管理电量历史记录
├── crypto.py            # Token 文件加密模块，AES-256-GCM 加密
├── config.py            # 配置模块，环境变量读取
├── markdown.py          # GitHub Actions Step Summary 生成
├── requirements.txt     # Python 依赖
├── CHANGELOG.md         # 版本变更记录
├── .github/workflows/
│   ├── static.yml       # 定时/手动更新电量并发布 Pages
│   ├── redeploy.yml     # 仅重新发布当前 page 数据
│   └── ci.yml           # PR/主分支验证
└── page/                # 前端页面
    ├── index.html       # 主页面，数据可视化
    ├── style.css        # 样式文件，支持深色模式
    ├── main.js          # 主要 JavaScript 逻辑
    ├── data/rooms/      # 按区域拆分的房间查询器数据
    └── data/            # 电量数据与 token 密文（page 分支持久化）
```

## 分支说明

| 分支 | 用途 | 说明 |
|------|------|------|
| `main` | 源代码 | Python 后端、GitHub Actions 工作流、前端模板 |
| `page` | 持久化分支 | GitHub Pages 静态资源快照、电量数据、加密令牌 |

**为什么分两个分支？**

- **数据持久化**：电量数据存储在 `page` 分支，代码更新不会丢失历史数据
- **独立部署**：前端资源与后端代码分离，`main` 分支工作流从 `page/` 上传 GitHub Pages artifact，并同步 `page` 分支作为持久化快照
- **认证文件隔离**：加密令牌 (`tokens.enc`) 仅用于 `page` 分支持久化，部署到 Pages 前会从网站产物移除
- **快速加载**：`page` 分支仅包含静态资源，访问速度更快

## 技术栈

- **Python 3.14** - 主程序语言
- **ZZU.Py >= 7.2.1** - 郑州大学统一认证 API 封装，支持 MFA
- **ECharts 6.0** - 数据可视化图表
- **GitHub Actions** - CI/CD 自动化
- **GitHub Pages** - 静态页面托管
- **AES-256-GCM** - 数据加密

## 常见问题

### 如何获取房间号？

**方法一：内置房间查询器（推荐）**

1. 访问 [宿舍电量监控](https://elykia093.github.io/ZZU-Electricity-Monitor/)
2. 点击导航栏 **"房间查询"** 按钮
3. 依次选择区域、建筑、单元、房间号
4. 复制显示的房间编号

**方法二：手动查表**

参考教程：[郑州大学宿舍电量监控：ZZU-Electricity-Monitor](https://blog.elykia.cn/posts/22)

### 为什么没有收到通知？

1. 检查 Secrets 配置是否正确
2. 检查 Actions 是否启用
3. 查看 Actions 运行日志排查错误

### 为什么 Actions 运行失败？

常见原因及解决方法：

1. **账号密码或 MFA 问题**：检查 `ACCOUNT`、`PASSWORD`、`ZZU_DEVICE_ID`、`TOKEN_ENCRYPTION_KEY`，必要时重新运行 `python mfa.py`
2. **房间号错误**：使用房间查询器重新获取正确的房间编号
3. **网络问题**：GitHub Actions 偶尔会有网络波动，可以手动重新运行
4. **page 分支不存在**：首次运行会自动创建，无需担心

### 如何查看电量历史数据？

访问你的 GitHub Pages 页面（`https://你的用户名.github.io/ZZU-Electricity-Monitor/`），页面会显示：
- 实时电量数据
- 7天电量变化趋势图
- 历史记录表格

### 如何修改运行频率？

编辑 `.github/workflows/static.yml` 文件中的 cron 表达式：

```yaml
schedule:
  - cron: '0 16,20,0,4,8,12 * * *'  # UTC 时间，对应北京时间 0,4,8,12,16,20 点
```

### 精确定时触发（可选）

GitHub Actions 定时任务存在延迟，如需精确定时可使用以下任一平台：

| 平台 | 免费额度 | 自托管 | 特点 |
|------|----------|--------|------|
| [Zapier](https://zapier.com) | 100 次 | ❌ | 行业标杆，生态最成熟 |
| [Make](https://make.com) | 1,000 次 | ❌ | 托管方案中最慷慨 |
| [n8n](https://n8n.io) | 无限制 | ✅ | 完全自由，1000+ 集成 |
| [IFTTT](https://ifttt.com) | 无限基础 | ❌ | 适合智能家居，限2个Applet |
| [Power Automate](https://make.powerautomate.com) | 750 次 | ❌ | Office 365深度集成 |
| [OttoKit](https://ottokit.com) | 250 次 | ❌ | 小企业友好 |
| [Pipedream](https://pipedream.com) | 100 次 | ❌ | 开发者友好，支持代码 |
| [Pabbly Connect](https://www.pabbly.com/connect) | 100 次 | ❌ | 含高级功能 |
| [Integrately](https://integrately.com) | 100 次 | ❌ | 预制食谱 |
| [Activepieces](https://www.activepieces.com) | 无限制 | ✅ | 开源，现代界面 |
| [Huginn](https://github.com/huginn/huginn) | 无限制 | ✅ | 代理式，Ruby |
| [Node-RED](https://nodered.org) | 无限制 | ✅ | IoT 专注 |

**通用配置步骤（以 Make 为例）：**

1. **创建 GitHub Token**
   - GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
   - 勾选 `repo` 和 `workflow` 权限，生成并保存 Token

2. **配置 Make**
   - 注册 Make，创建新 Scenario
   - 触发器选择 **Webhooks** → **Custom webhook**，保存后获得 webhook URL
   - 添加 **HTTP** 模块：
     - URL: `https://api.github.com/repos/你的用户名/ZZU-Electricity-Monitor/actions/workflows/static.yml/dispatches`
     - Method: `POST`
     - Headers:
       - `Content-Type` = `application/json`
       - `Authorization` = `Bearer 你的GitHubToken`
       - `Accept` = `application/vnd.github.v3+json`
     - Body: `{"ref":"main"}`

3. **配置定时**
   - 点击 Webhooks 模块右侧的时钟图标
   - 选择 **不激活**，点击 **添加定时器**
   - 勾选 **高级调度**
   - 添加 6 个时间段：
     - **Item 1**: 从 `00:00` 至 `00:01`
     - **Item 2**: 从 `04:00` 至 `04:01`
     - **Item 3**: 从 `08:00` 至 `08:01`
     - **Item 4**: 从 `12:00` 至 `12:01`
     - **Item 5**: 从 `16:00` 至 `16:01`
     - **Item 6**: 从 `20:00` 至 `20:01`
   - 时区选择 `Asia/Shanghai`

配置完成后，Make 会在精确时间触发 GitHub Actions，无延迟。

### 如何修改电量阈值？

编辑 `config.py` 文件：

```python
THRESHOLD = 10.0           # 低电量警告阈值
EXCELLENT_THRESHOLD = 100.0  # 充足电量阈值
```

## 致谢

- [ZZU.Py](https://github.com/Illustar0/ZZU.Py)
- [ZZU-Electricity](https://github.com/TorCroft/ZZU-Electricity)

## License

[MIT License](LICENSE)
