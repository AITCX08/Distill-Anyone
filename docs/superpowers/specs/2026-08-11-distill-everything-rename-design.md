# Distill-Everything 全量改名与本地迁移设计

## 目标

将项目从 **Distill-Anyone** 统一迁移为 **Distill-Everything**：GitHub 仓库、本地代码根目录、数据目录、产物目录、Dashboard、CLI、脚本、环境变量与活跃文档均使用新名称，同时保留现有 Conda 环境 `<existing-conda-env>` 不变。

## 范围与非目标

### 纳入范围

- GitHub 仓库从 `AITCX08/Distill-Anyone` 改名为 `AITCX08/Distill-Everything`，本地 `origin` 同步更新。
- 主工作树改为 `<workspace>/Distill-Everything`；Dashboard 运行工作树改为 `<workspace>/Distill-Everything-dashboard-runtime`。
- 将 `data` 与 `output` 移至新的主工作树，保留其全部任务、登录凭据、缓存状态和已交付产物。
- 所有运行时产品标识改为 `Distill-Everything`，机器可读标识改为 `distill-everything` 或 `DISTILL_EVERYTHING_*`。
- Dashboard 静态资源、隐藏启动器和文档同步更新。

### 不纳入范围

- 不重命名 Python 顶层包 `src`；它是内部模块根，不是产品公开名称，重命名会制造无收益的导入兼容风险。
- 不移动或重建 Conda 环境；继续使用 `<existing-conda-env>`。
- 不编辑历史设计/计划中描述旧版本事实的内容；仅在本迁移文档中建立旧名映射，避免篡改历史记录。

## 命名约定

| 用途 | 旧值 | 新值 |
| --- | --- | --- |
| 产品展示名 | `Distill-Anyone` | `Distill-Everything` |
| GitHub 仓库 | `AITCX08/Distill-Anyone` | `AITCX08/Distill-Everything` |
| Node 包名 | `distill-anyone-dashboard` | `distill-everything-dashboard` |
| Python 环境变量 | `DISTILL_ANYONE_PYTHON` | `DISTILL_EVERYTHING_PYTHON` |
| 主目录 | `...\Distill-Anyone` | `...\Distill-Everything` |
| Dashboard 工作树 | `...\Distill-Anyone-dashboard-runtime` | `...\Distill-Everything-dashboard-runtime` |
| 数据目录 | `...\Distill-Anyone\data` | `...\Distill-Everything\data` |
| 产物目录 | `...\Distill-Anyone\output` | `...\Distill-Everything\output` |

## 迁移架构

迁移分为三个受控阶段：先冻结运行时并完成可回退的路径移动，再更新仓库与代码标识，最后重建并启动 Dashboard。路径移动只在目标路径为空且源路径完整时执行；`data` 和 `output` 使用同卷原子移动，不复制、不删除、不重建。

```mermaid
flowchart LR
  A[停止 Dashboard] --> B[检查源/目标路径]
  B --> C[移动主工作树、运行工作树、data、output]
  C --> D[更新 GitHub 仓库与 origin]
  D --> E[更新代码、脚本、文档与静态资源]
  E --> F[重建 Dashboard]
  F --> G[启动隐藏 pythonw 服务]
  G --> H[健康检查、任务/产物校验]
```

## 数据完整性与回退

- 移动前记录每个源路径是否存在、目标路径是否存在，以及 `data` 中任务状态文件和 `output` 中产物数量。
- 任何目标目录已存在、源目录缺失、Dashboard 未停止或迁移后关键路径不可读时，立即停止后续步骤。
- GitHub 改名会保留 GitHub 自动重定向；本地仍显式设置新 `origin`，不依赖重定向。
- 若本地路径迁移后启动校验失败，在未进行新任务写入前将目录移动回旧路径，并恢复旧启动器路径；不删除任何数据。

## 运行时行为

新的隐藏启动器继续使用 `pythonw.exe`，以避免可见 CMD 窗口：

- `DATA_DIR` 指向新的 `...\Distill-Everything\data`。
- `OUTPUT_DIR` 指向新的 `...\Distill-Everything\output`。
- 仅解释器路径保留 `...\envs\Distill-Anyone\pythonw.exe`。
- Dashboard 仍绑定 `127.0.0.1:8765`，启动后以健康端点和 SSE 快照验证数据读取。

## 验收标准

1. GitHub 新仓库地址可访问，本地 `origin` 指向新地址。
2. 两个本地工作树、`data`、`output` 均位于新路径，旧路径不再作为运行位置。
3. Dashboard 在 `http://127.0.0.1:8765` 健康可用，能读取已有的 8 集任务、标题、BV 号、完成时间和产物目录。
4. CLI 帮助、Dashboard 页面标题、README、Node 包名和脚本环境变量均显示新名称。
5. Conda 环境路径保持原样，未创建或删除 Python 环境。

## 历史名称映射

旧名称 `Distill-Anyone` 在 GitHub 的自动重定向、既有提交历史和未迁移的外部引用中仍可能出现；这不代表运行时仍使用旧项目路径。所有新说明、脚本与发布入口只使用 `Distill-Everything`。
