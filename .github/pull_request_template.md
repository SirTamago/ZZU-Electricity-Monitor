## 变更说明

- 变更目的：
- 影响范围：
- 是否涉及 GitHub Actions / 认证 / Token / 通知 / 前端资源：

## 提交者自检

- [ ] 没有提交账号、密码、短信验证码、token、cookie、webhook secret 或完整环境变量值
- [ ] 没有提交 `page/data/tokens.json`、`page/data/tokens.enc`、`__pycache__/`、`*.pyc` 等本地生成或个人认证文件
- [ ] 如果改了认证链路，已说明 `ACCOUNT`、`PASSWORD`、`ZZU_DEVICE_ID`、`TOKEN_ENCRYPTION_KEY`、`tokens.enc` 的兼容方式
- [ ] 如果改了 workflow，已说明触发条件、权限、Secrets 使用、token 文件剔除和 Pages 发布影响
- [ ] 如果改了房间数据，已说明数据来源，并验证照明/空调房间编号仍能匹配
- [ ] 如果改了前端资源，已确认 `page/main.js`、`page/style.css`、`page/data/rooms/*.json` 会被发布到 `page` 分支
- [ ] 如果面向 3.0 发布，已更新 `README.md` 和 `CHANGELOG.md`

## 建议验证

- [ ] `python -m py_compile config.py monitor.py tokens.py mfa.py main.py crypto.py storage.py notify.py markdown.py tests/test_auth_flow.py tests/test_workflow_guards.py tests/test_room_data_contract.py`
- [ ] `python -m unittest discover -s tests`
- [ ] `node --check page/main.js`
- [ ] workflow YAML 可解析
- [ ] `git diff --check`
- [ ] 搜索确认无凭据残留
- [ ] PR CI 通过，且没有依赖 Secrets、真实登录或 Pages 部署

## 维护者重点复核

- `.github/workflows/*.yml`：禁止 fork PR 获取 Secrets，避免 `pull_request_target`、过宽 `permissions`、不可信脚本执行
- `requirements.txt`：核对新增或升级依赖是否必要，避免供应链风险
- `monitor.py` / `mfa.py` / `tokens.py` / `crypto.py`：核对 MFA、token 保存、加密、日志脱敏和失败路径
- `notify.py` / `config.py`：核对 webhook、邮件、机器人密钥不会被日志或错误输出泄露
- `page/index.html` / `page/main.js` / `page/data/rooms/`：核对外部脚本、房间数据加载、缓存和部署清单
