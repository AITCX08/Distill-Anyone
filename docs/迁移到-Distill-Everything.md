# 迁移到 Distill-Everything

本文记录产品从 `Distill-Anyone` 迁移到 `Distill-Everything` 的兼容边界，供已有使用者更新仓库地址、环境变量和本地启动方式。

## 名称映射

| 原名称 | 新名称 |
| --- | --- |
| `Distill-Anyone` | `Distill-Everything` |
| `distill-anyone-dashboard` | `distill-everything-dashboard` |
| `DISTILL_ANYONE_PYTHON` | `DISTILL_EVERYTHING_PYTHON` |
| `https://github.com/AITCX08/Distill-Anyone.git` | `https://github.com/AITCX08/Distill-Everything.git` |

更新既有克隆库的远端地址：

```powershell
git remote set-url origin https://github.com/AITCX08/Distill-Everything.git
```

## 保留的兼容边界

- 现有 Conda 环境若仍以旧名称创建，可以继续使用；不要为了改名而移动或重命名已经可用的环境。
- 新脚本和自动化配置应使用 `DISTILL_EVERYTHING_PYTHON` 指向项目解释器。
- `src` 包名和既有 `src.*` 导入保持不变。
- 已有的 `data`、`output`、浏览器 profile 与任务状态是本地私有内容；迁移仓库时不应提交、复制到 issue，或重新生成它们。

## Dashboard 与测试

- Windows 的隐藏 Dashboard 启动方式及后台 pytest 运行器，是 Codex Desktop Windows 场景下避免终端弹窗和进程管理不稳定的约束，不是 macOS 用户的通用命令。
- macOS 使用前台命令启动本地 Dashboard：`python main.py dashboard --port 8765 --no-open`。
- 无论平台，Dashboard 仅监听 `127.0.0.1`；健康检查为 `http://127.0.0.1:8765/api/v1/health`。

完整的支持状态、平台限制与故障排查请阅读：[平台支持与故障排查](./平台支持与故障排查.md)。
