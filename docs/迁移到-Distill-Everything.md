# 迁移到 Distill-Everything

本文记录 2026-08-11 完成的产品与本地目录迁移，供已有用户更新克隆地址、启动器和自动化脚本。

## 名称与路径映射

| 原名称或路径 | 新名称或路径 |
| --- | --- |
| `Distill-Anyone` | `Distill-Everything` |
| `distill-anyone-dashboard` | `distill-everything-dashboard` |
| `DISTILL_ANYONE_PYTHON` | `DISTILL_EVERYTHING_PYTHON` |
| `C:\Users\Administrator\Desktop\Vibe\Distill-Anyone` | `C:\Users\Administrator\Desktop\Vibe\Distill-Everything` |
| `C:\Users\Administrator\Desktop\Vibe\Distill-Anyone-dashboard-runtime` | `C:\Users\Administrator\Desktop\Vibe\Distill-Everything-dashboard-runtime` |
| `https://github.com/AITCX08/Distill-Anyone.git` | `https://github.com/AITCX08/Distill-Everything.git` |

## 保留不变的内容

- Conda 环境路径 `C:\Coding\Anaconda\envs\Distill-Anyone` 暂不重命名，避免破坏已安装的依赖与现有本机配置。
- 新版环境变量 `DISTILL_EVERYTHING_PYTHON` 可以继续指向该环境中的 `python.exe`。
- 项目内的 `src` Python 包名不变，现有 `src.*` 导入无需调整。
- 主项目目录内的 `data`、`output` 与本机 `.local-artifacts` 已随目录整体迁移；既有任务和交付文件不应重新下载或重新生成。

## GitHub 与旧链接

仓库的规范地址已改为：

```text
https://github.com/AITCX08/Distill-Everything
```

GitHub 会将旧仓库链接重定向到新地址，但新的 clone、remote、文档链接和自动化配置必须使用新地址。已有本地仓库可执行：

```powershell
git remote set-url origin https://github.com/AITCX08/Distill-Everything.git
```

## 无窗口启动 Dashboard

本机 Dashboard 使用新的运行工作树与隐藏启动器，不会打开 CMD 窗口：

```powershell
Start-Process -FilePath 'C:\Coding\Anaconda\envs\Distill-Anyone\pythonw.exe' `
  -ArgumentList 'C:\Users\Administrator\Desktop\Vibe\Distill-Everything-dashboard-runtime\.local-artifacts\start_dashboard_8765.pyw' `
  -WorkingDirectory 'C:\Users\Administrator\Desktop\Vibe\Distill-Everything-dashboard-runtime' `
  -WindowStyle Hidden
```

启动后访问 `http://127.0.0.1:8765/`。健康检查地址为 `http://127.0.0.1:8765/api/v1/health`。

## 后台测试

不要在 Codex 桌面端直接运行 `pytest` 或 `python -m pytest`。需要 Python 测试时，使用项目的后台运行器，并通过退出码和日志判断结果：

```powershell
$env:DISTILL_EVERYTHING_PYTHON = 'C:\Coding\Anaconda\envs\Distill-Anyone\python.exe'
cmd /d /c start "" /b scripts\run-pytest-background.cmd tests\dashboard\test_sse.py -q
Get-Content .local-artifacts\test-runs\latest.exitcode
Get-Content .local-artifacts\test-runs\latest.log
```

`start /b` 不会创建可见的 CMD 窗口。前端测试与构建仍通过固定的 `C:\Coding\node\node.exe` 直接执行。
