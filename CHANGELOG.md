# 更新日志

## 3.0 - 2026-06-09

### 新增

- 新增 `mfa.py`，用于本地完成 ZZU.Py CAS MFA 初始化。
- 新增 `tokens.py`，让统一认证 token 持久化代码更直观。
- 新增可选可信设备 ID：`ZZU_DEVICE_ID`。
- 新增加密 token 持久化：`page/data/tokens.enc`。
- 新增 CI 与单元测试，覆盖认证流程、workflow 安全约束、房间 JSON 分片、JavaScript 语法和生成/认证文件检查。
- 新增 PR 审查清单，覆盖 Secrets、workflow 权限、token 文件、房间数据和前端发布文件。

### 变更

- 更新 GitHub Actions 更新流程：运行前解密已保存 token，登录成功后刷新加密 token；如果已有 `tokens.enc` 无法解密，工作流直接失败。
- 更新 CAS 登录路径：Actions 优先尝试已保存 token；只有 token 失效并回退账密时才检查 MFA 状态，如果当前设备仍需要短信 MFA，非交互 Actions 会停止并提示重新初始化。
- 将原先的大体积房间数据脚本拆分为 `page/data/rooms/*.json`，由 `page/main.js` 按区域加载。
- 更新 Pages 发布流程：发布清单包含 `page/main.js` 和房间分片，并在上传 artifact 前移除认证文件；非 `main` 分支手动运行 Actions 不会写入 `page` 分支或部署 Pages。
- 更新 README，说明 3.0 最简教程、MFA 初始化、token 加密、page 分支持久化和验证命令。

### 移除

- 移除运行时发布路径中的 `page/room.js`。
- 移除不参与运行的 `page/README.md` 和 `page/data/.gitkeep`。
- 移除过宽 workflow 权限和旧的 workflow 清理/保活 action。

### 安全

- `tokens.json` 和 `tokens.enc` 在 `main` 分支被忽略，并会在上传 Pages artifact 前移除。
- 如果为了持久化把 `tokens.enc` 放在公开 `page` 分支，它仍可能被下载；加密密钥来自 `PASSWORD`，不要向上游 PR 提交个人 token 文件。
- Fork PR 的 CI 不依赖真实 Secrets、真实 CAS 登录或 Pages 部署。
