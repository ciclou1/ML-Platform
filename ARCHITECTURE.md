# 架构说明

本项目是单机部署的 AI 数据标注、数据版本、模型训练、评估和边缘推理平台。
本文档描述整体分层、模块边界与关键流程，帮助新成员快速定位代码。

## 技术栈

- 后端：FastAPI + SQLAlchemy (Async) + Alembic + PostgreSQL
- 前端：Vue 3 + Vite + TypeScript + Element Plus + Pinia + Vue Router
- 存储：本地 `storage/` 目录（数据集、导出物、任务产物、模型权重等）
- 运行时：后端进程内子进程执行训练/评估/预处理 worker

## 顶层目录

```text
backend/
  app/
    core/           跨模块基础设施（认证、日志、存储、runner、指标、工作流引擎）
    db/             SQLAlchemy engine/session（Postgres）
    frameworks/     算法框架适配层（当前为 yolov8 trainer/evaluator/predictor）
    models/         所有 SQLAlchemy ORM 模型
    repositories/   数据访问层（按实体组织的查询封装）
    routers/        FastAPI 路由（HTTP 入口）
    schemas/        Pydantic 请求/响应模型
    services/       业务逻辑层
    runners/        独立 worker 进程入口（训练/评估/预处理/视频抽帧/算法包/工作流）
    utils/          通用工具（bbox、图像、文件名清理等）
  alembic/          数据库迁移
  scripts/          运维脚本（种子数据、节点代理等）
  tests/            后端测试
frontend/
  src/
    api/            后端接口封装（axios）
    components/     通用组件（布局、上传等）
    composables/    组合式逻辑（标注工作台、画布、任务进度等）
    config/         菜单、权限点配置
    router/         路由（含登录守卫、404）
    stores/         Pinia 状态（auth、dataset、annotationDraft、tags、app、loading）
    types/          领域类型定义
    views/          页面视图
    styles/         全局样式
```

## 分层原则

### 后端

- **Router → Service → Repository → Model**：路由只做参数校验与响应组装；
  业务逻辑在 Service；SQL 查询集中在 Repository。
- **框架适配层不访问数据库**：`frameworks/yolov8/` 只处理模型文件与训练/评估/推理，
  通过 runner 子进程运行，与主进程隔离。
- **任务 worker 独立于数据库**：`runners/*_worker.py` 通过 `storage/tasks/{id}/`
  下的 config / progress / result / stdout / stderr 文件与主进程通信，
  worker 不直接读写数据库，避免长任务占用连接。
- **存储路径集中管理**：所有运行时路径必须通过 `app/core/storage/paths.py`
  的 `StoragePaths` 生成，禁止业务代码手拼路径。
- **认证**：`core/auth_middleware.py` 全局强制 JWT（白名单除外），并旁路写审计日志；
  权限点在 `core/security.py` 定义，Router 通过 `deps.require_permission` 校验。

### 前端

- **api/ → stores / views**：页面在 `onMounted` 中调用接口加载数据，
  跨页面共享状态（用户、数据集列表、标注草稿）放入 Pinia store。
- **路由守卫**：`router/index.ts` 的 `beforeEach` 校验 token，未登录跳转 `/login`；
  带 `meta.public` 的路由（登录页）放行。
- **请求封装**：`api/request.ts` 统一注入 `Authorization` 头、401 自动登出、
  全局加载指示（见 `stores/loading.ts` 与 `App.vue` 顶部进度条）。
- **404**：根布局下新增 `:pathMatch(.*)*` 兜底路由指向 `views/error/NotFound.vue`。

## 关键流程

### 数据导入

1. 前端上传 ZIP → `/api/v1/upload/dataset` 流式落盘（分块写入，避免 OOM）。
2. `services/dataset_import.py` 解压并探测 YOLO 结构（splits/classes/data.yaml）。
3. 前端确认结构 → 写 `data.yaml`、图片落库为 `Image` 记录。

### 训练

1. 数据集版本 → YOLO 导出（生成 `data.yaml` + 划分统计）。
2. 创建训练任务（必须选择成功的导出记录）→ `TaskService.start_task` 组装 config。
3. `core/runner/process.py` 以子进程启动 `runners/train_worker.py`，
   worker 将进度写入 progress 文件、日志写入 stdout/stderr。
4. 前端通过 WebSocket（`/api/v1/ws/tasks/{id}`）或轮询读取进度与结果。

### 模型评估 / 推理

- 评估：`services/evaluation.py` 创建评估任务，worker 加载 best.pt 计算 mAP 等指标。
- 推理：`frameworks/yolov8/predictor.py` 对上传图片执行检测，结果回传。

## 数据库

- 迁移：`alembic upgrade head`（本地与容器启动时都会执行）。
- 表结构：数据集、图片、标注、标签、批次/质检、模型、任务、用户/角色/审计日志、
  数据集版本/导出、视频、算法包、边缘节点、工作流等。
- OLAP：~~Doris~~ 连接已移除（当前无 OLAP 需求），全部使用 PostgreSQL。

## 测试

- 后端：`uv run --extra dev python -m pytest tests -q`，覆盖算法、模型契约、
  路由/Service 注册、worker 与种子脚本契约，均不依赖外部服务。
- 前端：`pnpm test`（vitest）与 `pnpm build`（vue-tsc + vite）。
- CI：`.github/workflows/ci.yml` 在 push/PR 时执行两端测试与构建。

## 部署

单机部署见 README「Docker 部署」：`docker compose --env-file .env up -d --build`。
容器内执行 `alembic upgrade head`，前端通过 Nginx 反代后端 `/api`。
