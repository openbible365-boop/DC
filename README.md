# 数据收集(Data Collection)协作平台

供神学专家远程协作的资料收集、标注、审核、导出平台,产出可训练「圣经解释 AI 模型」的高质量数据集。
设计总纲见 [PROJECT_SPEC.md](PROJECT_SPEC.md)。

## 技术栈

- Django 5.1 + SQLite(开发)/ PostgreSQL(生产)
- Celery + Redis(异步任务:注释书自动拆分、音视频转录)
- HTMX + Alpine.js(轻量前端)
- uv(依赖与虚拟环境管理)

## 本地开发

```bash
# 1. 安装依赖(uv 会自动建 venv)
uv sync

# 2. 初始化数据库
uv run python manage.py migrate

# 3. 创建管理员
uv run python manage.py createsuperuser

# 4. 启动开发服务器
uv run python manage.py runserver
# 打开 http://localhost:8000/
```

### 异步任务(自动拆分等)

需要 Redis 与一个 Celery worker:

```bash
# 启动 Redis(macOS / Homebrew)
brew services start redis

# 另开一个终端,启动 worker
uv run celery -A config worker -l info
```

> 调试时若不想起 worker,可让任务同步执行:
> `export CELERY_TASK_ALWAYS_EAGER=1` 后照常运行,任务会在请求内直接跑完。

## 已实现功能

- 用户与角色权限(管理员 / 主任专家 / 协作专家 / 技术员)
- 资料收集:上传/录入、目标模型多选、状态机
- 标注工作台:经文/注释/标签/质量评分,预设标签一键加
- 审核工作流:队列(置信度配色)、通过/编辑/打回、批量通过、审核留痕
- 任务分配 + 站内通知(指派/认领/打回提醒)
- 注释书自动拆分(正则 + 书卷名对照表,异步)
- JSONL 导出(按目标模型筛选已通过条目)
- 仪表盘(数据量 / 审核进度 / 质量分布)

## 上生产前需收紧

`config/settings.py` 中的 `SECRET_KEY`、`DEBUG`、`ALLOWED_HOSTS` 目前为开发配置,
部署前应改为从环境变量读取,并切换数据库为 PostgreSQL。
