# 剧情脚本目录

此目录存放剧情模式的 JSON 脚本文件。

## 文件命名规范

- 文件名使用小写字母 + 连字符：`missing-father.json`
- 每个文件是一个完整的剧情（包含所有章节和结局）

## 脚本结构

脚本 JSON 必须符合 `schemas/story.py` 中定义的 STORY_SCHEMA，且每个 `scripted` 章节的 `case_data` 必须符合 `core/case_generator.py` 中的 `CASE_SCHEMA`。

详见 [`docs/gameplay-optimization/dual-mode.md`](../docs/gameplay-optimization/dual-mode.md) 第4章。

## 可用剧情

| 文件 | 标题 | 章节数 | 结局数 | 状态 |
|------|------|--------|--------|------|
| `missing_father.json` | 寻找失踪父亲 | 5 | 4 | ✅ 可用 |
| `test_story.json` | 测试剧情 | 2 | 2 | ✅ 测试用 |

## 章节编写指南

### scripted 类型（固定剧本）

1. 按 `CASE_SCHEMA` 编写完整的 `case_data`（可参考 `tests/fixtures/mock_cases/simple.json`）
2. 编写 `narrative` 的 `opening`、`closing_win`、`closing_partial`、`closing_fail`
3. 定义 `branch.conditions`，使用声明式条件格式
4. 如需收敛，设置 `merge_to` 指向目标章节

### generated 类型（LLM约束生成）

1. 编写 `case_constraints`：`theme`、`suspect_count`、`must_include`、`difficulty`
2. 系统会根据约束调用 LLM 生成符合 CASE_SCHEMA 的案件
3. 建议优先使用 scripted 类型，generated 仅用于填充章节

### 分支设计原则

- **漏斗式收敛**：分支后 1-2 章内回归主线，通过 `merge_to` 声明
- **3级结果**：`win` / `partial` / `fail`，通过 `min_confession` / `min_evidence` 细化
- **最后一个条件为兜底**：只有 `next` 字段，无需条件匹配
