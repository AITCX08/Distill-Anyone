# 本地后台测试（Windows）

`run-pytest-background.cmd` 在后台运行 pytest，并将输出写入
`.local-artifacts/test-runs/latest.log`；退出状态写入
`.local-artifacts/test-runs/latest.exitcode`。该目录已被 Git 忽略。

当调用方不能打开控制台窗口或持有 pytest 输出管道时，请从既有的非交互控制台通过
`start /b` 启动脚本：

```cmd
cmd /d /c start "" /b scripts\run-pytest-background.cmd tests\distillation\test_engine.py -q
```

脚本优先读取 `DISTILL_EVERYTHING_PYTHON`，其次使用仓库中的
`.venv\Scripts\python.exe`，最后使用 `PATH` 上的 `python`。例如，在已选择项目解释器的
CMD 会话中：

```cmd
set "DISTILL_EVERYTHING_PYTHON=<path-to-project-python>"
cmd /d /c start "" /b scripts\run-pytest-background.cmd -q
```

在认定测试成功前，必须读取 `latest.exitcode`。pytest 未安装或测试失败都会产生非零
退出码，并记录在日志中。
