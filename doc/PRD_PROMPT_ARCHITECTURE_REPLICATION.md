# PromptGo Prompt 架构复现 PRD

## 1. 文档目标

本文档用于在其他项目中复现 PromptGo 的 Prompt 生成架构，覆盖：

- 苏格拉底式多轮澄清生成 Prompt
- 多提示词框架（Standard / XML Structured / LangGPT / CO-STAR）
- Auto 自动场景选择（Scenario + Personality + Template）
- Prompt 管理与二次优化

同时，本文档区分了当前代码的真实实现状态（As-Is）与建议复现目标（To-Be）。

## 2. 背景与问题

目标用户输入通常是模糊任务描述。单次生成 Prompt 往往存在：

- 目标不清晰
- 输出格式不可控
- 安全边界不明确
- 不同任务缺少场景化 Prompt 结构

因此需要一个系统：先澄清、再生成、再可迭代优化，并支持任务场景自动路由。

## 3. 产品目标

### 3.1 北极星目标

把「模糊想法」转化为「可直接执行的高质量 Prompt」。

### 3.2 子目标

1. 对话中 3-5 轮内完成需求澄清
2. 支持 4 种框架输出
3. 支持 Auto 推荐场景配置
4. 支持历史复用与二次优化
5. 支持基础 RAG 知识增强（提示工程知识库）

## 4. 用户画像与核心场景

### 4.1 用户画像

- 开发者：需要代码类 Prompt，强调结构化和可执行
- 运营/客服：需要合规、语气稳定的业务 Prompt
- 内容创作者：需要风格化、受众导向 Prompt
- 分析/研究者：需要证据链与结构化输出 Prompt
- 教学者：需要循序渐进、可解释 Prompt

### 4.2 核心场景

1. 新建会话，输入初始需求，系统追问并最终生成 Prompt
2. 生成后继续“优化 Prompt”
3. 复用历史 Prompt 进行编辑
4. 查看框架模板和系统提示词

## 5. 功能需求

## 5.1 会话式 Prompt 生成

- 用户输入 `initial_idea`
- 系统多轮提问（question + options + custom）
- 达到轮次或信息充分后输出：
  - `prompt`（结构化字段）
  - `raw_text`（可直接使用文本）
  - `tags`

## 5.2 框架输出能力

支持 4 种框架：

1. `standard`
2. `structured`（XML）
3. `langgpt`
4. `costar`

框架切换应影响最终 `raw_text` 的组织结构。

## 5.3 Prompt 二次优化

- 已完成会话允许 `refine`
- 用户输入“调整意图”
- 系统返回更新后的结构化 Prompt + raw text

## 5.4 Auto 自动选择

### 需求定义

- 根据用户输入自动推断：
  - `scenario`
  - `personality`
  - `template`

### 场景集

- `code_assistant`
- `customer_service`
- `content_writer`
- `analyst`
- `educator`
- `general`
- `auto`（模式位，不是最终业务场景）

### 自动选择策略

- 关键词规则匹配 + 置信度判断
- 低置信度回退 `general`

## 5.5 设置与配置中心

- Prompt 配置选项接口
- 场景/人设/模板预览
- 骨架预览（不调用 LLM）

## 5.6 历史管理

- 会话历史列表
- Prompt 历史列表
- 删除会话 / 删除 Prompt

## 5.7 RAG（可选增强）

- 内置语料索引
- 语义检索
- 检索结果作为参考上下文注入

## 6. As-Is（当前代码真实状态）

## 6.1 已实现

1. 苏格拉底多轮会话生成链路（后端主链路）
2. 4 种框架模板落地在 `SocraticEngine`
3. Prompt 二次优化 `refine`
4. 换思路 `rethink`
5. Prompt/会话历史存储
6. Auto 所需配置数据与分类接口存在（`/api/config/*`）
7. Prompt 设置弹窗和场景人设模板 UI 存在

## 6.2 未完全打通

1. 前端选择的 `scenario/personality/verbosity` 未进入会话生成主链路
2. 前端目前只把 `template` 同步为 `promptFramework` 并传后端
3. `PromptAssembler`、`SkillLoader`、`MemoryManager`、`CitationRules` 已实现但未接入会话主流程
4. `classify-intent` 接口已实现但前端未在开始会话时调用

## 7. To-Be（复现目标，建议实现）

## 7.1 必须项（MVP）

1. 会话澄清 + 4 框架生成
2. Auto 分类并将结果注入会话配置
3. 场景/人设/模板可显式 override
4. Prompt 历史 + refine

## 7.2 增强项（Phase 2）

1. 接入 PromptAssembler 三层拼装（场景层/人设层/模板层）
2. 接入 verbosity 控制
3. 接入技能注入、记忆注入、引用规范注入
4. 与 RAG 检索策略联动（首轮检索 + 生成前增强检索）

## 8. 关键业务流程（目标版）

1. 用户输入初始需求
2. 若模式为 `auto`：
   - 调用 `classify-intent`
   - 得到 `scenario/personality/template`
3. 组装会话配置并创建会话
4. 进入多轮澄清
5. 按所选模板输出最终 Prompt
6. 用户可继续 refine
7. 保存到历史

## 9. 验收标准

## 9.1 功能验收

1. 4 种模板输出结构明显不同
2. Auto 能正确把“代码/客服/创作/分析/教学”分类到目标场景
3. 手动设置可覆盖 Auto 结果
4. refine 后能更新 Prompt 并持久化

## 9.2 质量验收

1. 生成成功率 >= 99%
2. 首轮响应时间（不含外部模型波动）<= 2s
3. Auto 分类平均耗时 <= 100ms（规则法）

## 10. 非功能要求

- 可观测：记录分类结果、模板选择、会话轮次
- 可扩展：场景/人设/模板配置化（JSON）
- 可维护：模板与业务逻辑分离
- 安全：注入内容必须视为不可信上下文

## 11. 复现交付物

在新项目落地时，最少应包含：

1. Prompt 配置 JSON（场景/人设/模板/兼容矩阵）
2. Intent 分类器
3. 会话式澄清引擎
4. 框架模板渲染器
5. 会话与 Prompt 持久化
6. 前端设置面板 + 历史面板

