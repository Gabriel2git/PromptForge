# PromptForge API / LLM Call Flow Explain

## 1) 目的
本文说明当前代码的真实调用链，重点回答：
- 前端如何调用后端 API
- 后端哪些接口会调用 LLM，哪些不会
- `generate_next_turn` 的重试与回退触发条件
- 最终 Prompt 在什么时机生成

## 2) 代码入口（当前实际路径）
- 前端交互与 API 调用：`frontend/assets/app.js`
- 后端会话路由：`backend/app/routers/conversations.py`
- LLM 调用封装：`backend/app/services/llm_service.py`
- 本地回退问题引擎：`backend/app/services/socratic_engine.py`
- Prompt 结构化生成：`backend/app/services/prompt_generator.py`

## 3) 前后端主链路

### 3.1 新建会话
1. 前端调用 `POST /api/conversations`
2. 后端 `create_conversation(...)`：
   - 解析会话配置（scenario/personality/template/framework）
   - 调 `_build_assistant_turn(...)`
3. `_build_assistant_turn(...)`：
   - 优先调用 `llm_service.generate_next_turn(...)`
   - LLM 成功：返回 `assistant_turn.turn_source = "llm"`
   - LLM 失败：回退 `socratic_engine.next_assistant_turn(...)`，并返回
     - `assistant_turn.turn_source = "fallback"`
     - `assistant_turn.fallback_reason = parse_error | network_error | timeout | disabled`
4. 路由始终返回：
   - `assistant_message`（兼容旧前端）
   - `assistant_turn`（主交互载体）

### 3.2 继续对话
1. 前端调用 `POST /api/conversations/{id}/messages`
2. 后端先写入用户消息
3. 若已达到生成条件（`should_generate(...) == True`）：进入最终 Prompt 生成
4. 若未达到：再次走 `_build_assistant_turn(...)`，返回下一轮问题和 3 个选项

### 3.3 换个角度（rethink）
1. 前端调用 `POST /api/conversations/{id}/rethink`
2. 后端同样走 `_build_assistant_turn(...)`（与 create/messages 一致）
3. 返回结构与普通追问一致，保证 `assistant_turn` 始终存在

## 4) LLM 重试与回退策略（关键）

实现位置：`backend/app/services/llm_service.py::DeepSeekClient.generate_next_turn`

### 4.1 重试策略
- 最多重试 2 次（总尝试 3 次）
- 退避时间：约 `0.3s`、`0.6s`

### 4.2 严格 JSON 解析
- 先尝试直接按 JSON 解析
- 支持 ` ```json ... ``` ` 包裹内容
- 若模型返回混杂文本，尝试提取首尾 `{...}` JSON 对象
- 仍无法解析则判定 `parse_error`

### 4.3 失败类型分类
- `disabled`：未配置 API Key
- `timeout`：请求超时
- `network_error`：HTTP/网络请求失败或响应结构非法
- `parse_error`：模型文本无法解析为约定 JSON

### 4.4 回退行为
当重试耗尽仍失败时，路由层回退到本地 `socratic_engine.next_assistant_turn(...)`，并显式返回：
- `assistant_turn.turn_source = "fallback"`
- `assistant_turn.fallback_reason = <上面的失败类型>`

这意味着“继续可用”，但不再黑盒。

## 5) 本地回退不再固定题库

实现位置：`backend/app/services/socratic_engine.py`

- 回退问题和选项会根据三要素变化：
  - `scenario`
  - `turn`
  - `initial_idea` 关键词
- 仍保持交互契约不变：
  - 固定 3 个选项
  - `allow_custom = true`
  - `custom_label = "自定义输入"`

## 6) 哪些接口会调用 LLM

会调用 LLM：
- `POST /api/conversations`（首轮问题）
- `POST /api/conversations/{id}/messages`（继续追问；以及达成条件时生成结构化 Prompt）
- `POST /api/conversations/{id}/rethink`（换角度追问）
- `POST /api/conversations/{id}/refine`（基于已有 Prompt 做改写）

不会调用 LLM（数据库或配置类接口）：
- `GET /api/conversations`
- `GET /api/conversations/{id}`
- `DELETE /api/conversations/{id}`
- `PUT /api/conversations/{id}/prompt`
- `GET /api/settings`
- `PUT /api/settings`

## 7) 最终 Prompt 生成时机

最终 Prompt 不是在新建会话时生成，而是在 `messages` 路由内满足以下之一时触发：
- 用户回答轮次达到 `max_turns`
- 用户显式 `force_generate = true`

触发后流程：
1. 本地 `build_prompt(...)` 先给出可用结构
2. 若 LLM 可用，尝试 `generate_structured_prompt(...)` 增强
3. 最终经过 `apply_profile_to_prompt(...)` 合并配置并落库

## 8) 前端可观测状态

前端 `frontend/assets/app.js` 会读取：
- `assistant_turn.turn_source`
- `assistant_turn.fallback_reason`

当处于 `fallback` 时，选项区显示“当前为回退模式：xxx原因”，便于排查“为什么看起来像模板化”。
