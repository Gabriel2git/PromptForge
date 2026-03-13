# PromptForge MVP

基于 PRD 实现的前后端 MVP，包含：
- 苏格拉底式多轮问答（3-5 轮，可直接生成）
- 结构化提示词生成
- 提示词预览/编辑/保存/复制
- 历史会话记录（SQLite）

## 目录

- `backend/` FastAPI + SQLite API
- `frontend/` 纯静态前端页面（由后端托管）
- `data/prompt_forge.db` 本地数据库（运行时自动生成）

## DeepSeek 配置

- 在 `backend/.env` 中配置 `DEEPSEEK_API_KEY`
- 可选参数：`DEEPSEEK_BASE_URL`、`DEEPSEEK_MODEL`、`DEEPSEEK_TIMEOUT_SECONDS`
- 示例见：`backend/.env.example`

## 启动

1. 安装依赖

```bash
python -m pip install -r backend/requirements.txt
```

2. 启动服务

```bash
cd backend
python -m uvicorn app.main:app --reload --port 8000
```

3. 打开浏览器访问

- <http://127.0.0.1:8000>

## 主要 API

- `POST /api/conversations` 创建会话
- `POST /api/conversations/{id}/messages` 发送回答并推进问答
- `GET /api/conversations` 获取历史会话
- `GET /api/conversations/{id}` 获取会话详情
- `PUT /api/conversations/{id}/prompt` 保存编辑后的提示词
