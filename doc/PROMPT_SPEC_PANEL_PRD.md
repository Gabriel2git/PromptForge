# PromptForge PRD: Prompt Spec Panel (v1)

## 1. Background

Current PromptForge stores two tracks after generation:
- Structured prompt object (`role/task/input_spec/constraints/output_format/...`)
- Rendered `raw_text`

But the UI only shows `raw_text`. Users cannot directly see:
- What key requirement slots are already captured
- Where to edit at field level versus full-text level
- Why the system generated the current prompt

This creates a trust and reuse gap for the core value proposition: requirement clarification before generation.

## 2. Product Goal

Expose the structured prompt object to users as a readable "Prompt Spec Panel", while keeping the current copy-ready raw text workflow.

Primary outcome:
- Improve explainability and controllability of generated prompts

North-star for this feature:
- Increase first-pass usability confidence without increasing editing friction

## 3. Target Users

- Novice AI users: need to understand "what was captured" from clarification
- Frequent users: need quick partial edits and reusable structure
- Review/collaboration users: need to inspect constraints, output format, and failure handling explicitly

## 4. Scope (v1)

### In Scope

- Add dual-view tabs in Prompt pane:
  - `结构化面板` (Prompt Spec)
  - `Raw Text`
- Render key slots from structured object:
  - `角色定义`, `任务目标`, `输入/场景`, `限制条件`, `输出形式`, `缺失处理`
- Show slot coverage summary (`结构化槽位覆盖: x/5`)
- Keep existing raw text edit/save/copy flow unchanged
- Keep backend contract unchanged (reuse existing `generated_prompt` object)

### Out of Scope

- Field-level editing of structured slots
- Per-slot regeneration
- Version diff/annotation between structured snapshots
- Collaboration permissions

## 5. Information Architecture

Prompt pane layout:
1. View tabs (`结构化面板` / `Raw Text`)
2. Empty state (when no generated prompt)
3. Spec panel (coverage + slot cards)
4. Raw panel (`readonly` + edit mode textarea)
5. Actions (`编辑`, `保存`, `复制`)

Behavior rules:
- If structured object exists, default to `结构化面板`
- If only raw text exists, default to `Raw Text`
- Entering edit mode always switches to `Raw Text`

## 6. Data Contract

Input from backend (already available):
- `generated_prompt` object including:
  - `role`
  - `task`
  - `input_spec.description`
  - `constraints[]`
  - `output_format`
  - `error_handling`
  - `raw_text`

Frontend derived model:
- `currentPromptStruct`: nullable object
- `currentPrompt`: string
- `promptView`: `spec | raw`
- `coverage`: count of populated essential slots

## 7. Interaction Details

- `结构化面板`:
  - Render cards for non-empty fields only
  - Coverage based on essential slots:
    - `goal`, `audience`, `constraints`, `output`, `fallback`
- `Raw Text`:
  - Existing read/edit/save/copy behavior preserved
- No prompt available:
  - Tabs hidden
  - Empty state shown
  - Copy/Edit/Save hidden

## 8. Success Metrics

Primary:
- `Spec panel open rate` after generation
- `Raw-only edit rate` decrease without reducing copy rate

Secondary:
- Time from generation to first copy
- Save rate of prompts with at least one refinement

Guardrails:
- No increase in generation completion drop-off
- No regression in current copy/save flows

## 9. Risks and Mitigations

- Risk: UI complexity increase for novice users
  - Mitigation: default concise cards + keep raw flow unchanged
- Risk: Inconsistent data between spec and raw text after manual edits
  - Mitigation (v1): explicit product behavior "raw edit updates text track only"; defer bidirectional sync to v2

## 10. Acceptance Criteria (v1)

- User can switch between `结构化面板` and `Raw Text`
- Structured cards render correctly for completed conversations
- Coverage summary updates with structured payload presence
- Existing edit/save/copy raw workflow works as before
- Empty state works with no prompt generated
