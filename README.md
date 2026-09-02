# AI Platform

本项目是单机部署的 AI 数据标注、数据版本、模型训练、评估和边缘推理平台。

- 后端：FastAPI、SQLAlchemy Async、Alembic、PostgreSQL
- 前端：Vue 3、Vite、TypeScript、Element Plus、Vue Flow
- 存储：本地 `storage/` 目录
- 运行时：Windows 本地开发使用 Python 3.12、uv、pnpm；PostgreSQL 使用 Docker Compose

## 功能概览

### 数据与标注

- 数据集、标签、图片和视频样本管理
- 视频上传、抽帧和帧图像落库
- bbox、多边形、旋转框、关键点和图级分类标注
- 标注导出、数据集版本冻结、自动 train/val/test 划分
- 图像侧预置位纠偏：相位相关估计偏移后批量修正标注坐标

### 模型与评估

- 模型权重导入、下载、训练产物导出和模型谱系
- 训练任务、日志、进度、取消和断点续训
- YOLO detect、segment、OBB、pose、classify 任务推断
- 评估任务、分类别指标、F-beta、加权指标和自定义算法包指标
- 模型推理工作区

### 算法与边缘

- 算法 ZIP 导入、发布、弃用、下载和本地子进程推理
- 边缘节点注册、心跳、部署、远程推理和结果回传
- 发电机、水轮机、主变图像检测模板种子脚本

### 时序组态

- Vue Flow 拖拽编辑器
- CSV 上传和子进程工作流执行
- 50+ CSV 算子，支持筛选、排序、去重、字段处理和聚合
- 节点连线、删除、保存、重新加载和任务结果展示

## 目录结构

```text
backend/                 FastAPI 服务、迁移、worker 和测试
frontend/                Vue 单页应用
storage/                 运行时数据，不提交到 Git
  datasets/              数据集文件
  exports/               数据版本导出物
  tasks/                 worker 配置、日志、结果
  runs/                  训练和评估产物
  models/                已导入和训练产出模型
  packages/              算法包版本
  workflows/             CSV 工作流输入
```

所有运行时路径必须通过 `backend/app/core/storage/paths.py` 的 `StoragePaths` 生成。

## 本地启动

### 前置条件

- Python 3.12
- Node.js 20+ 与 pnpm 9+
- Docker Desktop
- Windows PowerShell

本地 PyTorch 使用 CPU wheel，避免部分 Windows CUDA wheel 的 `c10.dll` 初始化问题。GPU 训练需要单独维护兼容的 CUDA PyTorch 运行时或容器环境。

### 1. 启动 PostgreSQL

```powershell
docker compose up -d postgres
```

### 2. 启动后端

```powershell
cd backend
Copy-Item .env.example .env
uv sync --extra dev
uv run alembic upgrade head
uv run python run.py
```

后端地址：`http://127.0.0.1:8000`

- 健康检查：`/api/v1/health`
- OpenAPI：`/docs`

Windows 下请使用 `run.py` 启动。它会设置与 psycopg Async 兼容的事件循环策略。

### 3. 启动前端

```powershell
cd frontend
pnpm install
pnpm dev
```

默认前端地址：`http://127.0.0.1:5173`

开发环境请求始终通过 Vite 的 `/api` 代理访问后端。不要在 `frontend/.env.development` 中配置直连后端地址。

## 训练输入流程

训练任务不直接使用原始 ZIP 或数据集目录，而是使用成功的数据版本导出记录。

1. 在“数据集管理”导入图片或视频帧，并完成标签与标注。
2. 在“数据集版本 / 导出记录”创建版本。
3. 推荐选择“按比例自动划分”，至少生成 `train` 和 `val`。
4. 发起 YOLO 导出，等待导出状态为 `success`。
5. 在“模型管理”导入预训练权重。
6. 在“训练任务”选择“训练输入数据”中的成功导出记录。选择导出后，所属数据集和版本会自动同步。

检测训练需要 YOLO bbox 标签。图像分类训练需要图级分类标注和分类模型权重。未标注图片可参与数据集版本，但会降低训练有效样本比例。

## 常用接口

```text
GET/POST    /api/v1/datasets
GET/POST    /api/v1/dataset-versions
GET/POST    /api/v1/dataset-exports
GET/POST    /api/v1/models
GET/POST    /api/v1/tasks

GET/POST    /api/v1/images/{id}/annotations
POST        /api/v1/images/{id}/preset-alignment/estimate
POST        /api/v1/images/{id}/preset-alignment/apply

GET/POST    /api/v1/videos
POST        /api/v1/evaluation/run
GET/POST    /api/v1/algorithm-packages
GET/POST    /api/v1/nodes
GET/POST    /api/v1/workflows
```

## 算法模板与节点代理

创建行业模板：

```powershell
cd backend
uv run python scripts/seed_equipment_templates.py
```

启动边缘节点代理：

```powershell
cd backend
uv run python scripts/node_agent.py --base http://127.0.0.1:8000/api/v1 --node-id <node-id> --token <token>
```

## 测试与检查

```powershell
cd backend
uv run --extra dev python -m pytest tests -q

cd ../frontend
pnpm test
pnpm build
```

后端测试覆盖核心算法、模型表结构、Router、Service、worker 和模板契约。前端测试覆盖 API 基地址与 Vite 代理选择。

## Docker 部署

```bash
docker compose --env-file .env up -d --build
```

容器访问地址：

- 前端：`http://localhost:18080`
- 后端：`http://localhost:18000`

容器启动时会执行 `alembic upgrade head`。生产环境应通过根目录 `.env` 设置 PostgreSQL 密码、CORS 来源和存储配置。

## 当前约束

- 数据库迁移当前版本：`0010`
- 训练、评估和推理是独立业务链路
- framework 适配层不访问数据库
- 运行期文件不提交到 Git
- GPU 训练、分割和 OBB 的真实端到端验证需要兼容的 CUDA 运行时与权重
