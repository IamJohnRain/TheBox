# Agent优化方案

## 参考来源

- GitHub: https://github.com/peterfei/ai-agent-team/tree/main/.claude/agents
- 参考Agent列表：
  - product_manager.md - 产品经理
  - backend_dev.md - 后端开发
  - frontend_dev.md - 前端开发
  - qa_engineer.md - QA工程师
  - tech-leader.md - 技术负责人
  - devops_engineer.md - DevOps工程师

---

## 一、现状分析

### 1.1 现有Agent清单

| Agent | 文件 | 职责 | 模型 |
|-------|------|------|------|
| pm | pm.md | 项目经理，任务调度和流程管控 | inherit |
| dev | dev.md | 开发Agent，按里程碑实现代码 | volcengine/glm-5.1 |
| test | test.md | 测试Agent，编写自动化验收测试 | volcengine/glm-5.1 |
| review | review.md | 评审Agent，验证交付物是否达标 | minimax-cn-coding-plan/MiniMax-M2.7 |
| ui | ui.md | UI Agent，样式实现和组件开发 | minimax-cn-coding-plan/MiniMax-M2.7 |
| architect-a | architect-a.md | 架构师A，独立评审方案 | minimax-cn-coding-plan/MiniMax-M2.7 |
| architect-b | architect-b.md | 架构师B，独立评审方案 | volcengine/glm-5.1 |
| architect-expert | architect-expert.md | 架构专家，综合评审报告 | AstronCodingPlan/astron-code-latest |

### 1.2 参考项目Agent清单

| Agent | 职责 |
|-------|------|
| product_manager | 产品规划、需求分析、路线图制定、用户研究、竞品分析 |
| backend_dev | API设计、数据库优化、服务器端逻辑开发 |
| frontend_dev | UI实现、组件开发、用户体验优化 |
| qa_engineer | 测试规划、自动化测试、缺陷报告、质量保证 |
| tech-leader | 技术决策、团队协调、代码审查、技术规划 |
| devops_engineer | CI/CD、部署自动化、基础设施管理 |

### 1.3 对比差异

| 参考Agent | 本项目对应 | 差异分析 |
|-----------|-----------|---------|
| product_manager | pm.md | ❌ 定位不同：参考是"产品规划/需求分析"，本项目pm是"项目经理/任务调度" |
| backend_dev | 无 | ❌ 缺失专业后端开发Agent |
| frontend_dev | ui.md | ⚠️ 部分对应：ui.md偏样式实现，缺乏前端架构能力 |
| qa_engineer | test.md | ✅ 定位相似，职责覆盖 |
| tech-leader | 无 | ❌ 缺失技术负责人角色 |
| devops_engineer | 无 | ⚠️ 可选：本项目为桌面应用，DevOps需求较低 |
| 无对应 | architect-a/b/expert | ✅ 本项目优势：三方架构评审体系 |

---

## 二、合理性评估

### 2.1 优势

1. **架构评审体系完善**
   - architect-a/b/expert三方评审机制科学
   - 独立评审避免偏见，综合决策更可靠

2. **流程管控清晰**
   - pm作为流程调度中心，职责明确
   - dev/test/review闭环流程规范

3. **权限控制严格**
   - 各Agent权限分级合理
   - 只读Agent（architect/review）避免误操作

### 2.2 问题

#### 问题1：pm.md定位混淆（P0 → 已解决）

**现状**：
- 文件名为`pm.md`（通常理解为Product Manager）
- 实际职责是"项目经理/任务调度"，更像Scrum Master或流程管理员
- **核心问题**：pm.md第20行"需求分析"职责与新增product-manager重叠

**解决方案**（根据评审报告更新）：
- pm.md重新定义职责，**删除"需求分析"职责**，只保留"任务分解和流程调度"
- 新增product-manager.md作为subagent，由pm调度
- pm作为唯一用户入口，建立需求分流机制

#### 问题2：缺少专业后端开发Agent（P2）

**现状**：
- dev.md是通用开发Agent
- 无法区分前后端专业领域

**影响**：
- 后端特定问题（API设计、数据库优化）缺乏专业视角
- 复杂后端任务可能需要更专业的指导

**建议**：
- 当前项目为桌面应用（PySide6），后端需求相对简单
- 可暂不新增，复杂后端任务由architect评审指导
- 如后续有Web服务需求，再考虑新增backend-dev.md

#### 问题3：ui.md职责狭窄（P2）

**现状**：
- ui.md仅负责QSS样式和视觉优化
- 缺乏前端组件架构、状态管理等能力

**影响**：
- UI架构设计缺乏专业视角
- 复杂交互逻辑可能需要更系统的设计

**建议**：
- 扩展ui.md职责，增加"UI架构设计"能力
- 或保持现状，UI架构由architect评审指导

#### 问题4：缺少技术负责人角色（P2）

**现状**：
- 无tech-leader对应Agent
- 技术决策分散在architect-expert和pm

**影响**：
- 技术规划缺乏统一视角
- 团队技术成长指导缺失

**建议**：
- 当前项目规模较小，可暂不新增
- architect-expert可承担部分技术决策职责
- 如项目扩展，考虑新增tech-leader.md

---

## 三、优化方案（根据评审报告修订）

### 3.1 新增Agent

#### 新增：product-manager.md

**职责定位**：
- 产品规划：制定产品路线图和版本规划
- 需求分析：理解用户需求，进行需求拆解和优先级排序
- 用户研究：分析用户画像、用户旅程和使用场景
- 竞品调研：分析竞品功能、优劣势和市场定位

**关键设计决策**（根据评审报告）：

| 决策点 | 原方案 | 修订方案 | 修订原因 |
|--------|--------|----------|----------|
| mode | primary | **subagent** | pm作为唯一用户入口，避免用户困惑 |
| model | astron-code-latest | **MiniMax-M2.7** | 推理分析型任务更适合，与architect-a保持一致 |
| edit权限 | deny | **允许写入docs/特定目录** | 解决输出持久化问题，避免协作链断裂 |

**与pm.md协作关系**（修订后）：
```
用户需求 → @pm（分流判断）
    ├─ 简单需求 → 直接走开发流程
    └─ 复杂需求 → @product-manager（需求分析）
                    ↓ 输出需求文档
                  @architect-expert（技术可行性评估，可选）
                    ↓
                  @pm（任务分解和调度）
```

**权限设计**（修订后）：
```yaml
permission:
  edit:
    "docs/requirements/*": allow
    "docs/analysis/*": allow
    "docs/roadmap/*": allow
    "docs/user-research/*": allow
    "*": deny
  bash:
    "*": deny
  read: allow
  glob: allow
  grep: allow
  task: allow
  webfetch: allow
  websearch: allow
```

**完整定义**（修订后）：

```yaml
---
description: 产品经理Agent，负责产品规划、需求分析、用户研究和竞品调研
mode: subagent
model: minimax-cn-coding-plan/MiniMax-M2.7
temperature: 0.3
permission:
  edit:
    "docs/requirements/*": allow
    "docs/analysis/*": allow
    "docs/roadmap/*": allow
    "docs/user-research/*": allow
    "*": deny
  bash:
    "*": deny
  read: allow
  glob: allow
  grep: allow
  task: allow
  webfetch: allow
  websearch: allow
color: "#3F51B5"
---
```

**核心职责模块**：

1. 需求分析
   - 收集和记录用户需求
   - 创建详细的产品规格说明
   - 定义功能的验收标准
   - 基于业务价值对功能进行优先级排序

2. 产品规划
   - 制定产品路线图和时间表
   - 规划功能发布和迭代
   - 与开发团队协调
   - 管理利益相关者期望

3. 用户研究
   - 进行用户研究和访谈
   - 创建用户画像和旅程地图
   - 定义用户故事和用例
   - 确保直观的产品设计

4. 竞品调研
   - 分析竞争对手解决方案
   - 识别市场机会和威胁
   - 提供差异化建议
   - 跟踪行业趋势

**输出规范**：

- 需求分析文档
- 竞品分析报告
- 产品路线图
- 用户研究报告

### 3.2 现有Agent调整

#### pm.md：职责重新定义（必须修改）

**修订内容**：

| 原职责 | 修订后职责 | 修订原因 |
|--------|-----------|----------|
| 需求分析：理解用户需求，进行需求拆解和优先级排序 | **删除** | 转移给product-manager |
| 任务分解 | **需求分流判断 + 任务分解** | 新增分流机制 |
| Agent调度 | Agent调度 | 保持不变 |
| 流程管控 | 流程管控 | 保持不变 |

**新增：需求分流机制**

pm收到需求后，按以下规则分流：

| 需求类型 | 特征 | 处理流程 |
|----------|------|----------|
| 简单需求 | bug修复、UI微调、配置变更、单文件修改 | pm直接调度 @dev/@ui → @test → @review |
| 中等需求 | 功能增强、已有模块扩展、2-3个文件涉及 | pm调度 @product-manager（简要梳理） → @dev → @test → @review |
| 复杂需求 | 新功能、架构变更、跨模块、涉及技术决策 | pm调度 @product-manager → @architect-expert → @dev → @test → @review |

**pm.md修订后的核心职责**：

```markdown
## 核心职责

1. **需求分流判断**：评估需求复杂度，决定处理流程
2. **任务分解**：将复杂需求拆分为可执行的子任务
3. **Agent调度**：根据任务类型调度合适的Agent执行
4. **流程管控**：确保开发流程规范执行
```

**pm.md修订后的标准开发流程**：

```markdown
## 标准开发流程

### 简单需求流程
1. 需求确认 → 直接调度 @dev 或 @ui
2. 开发完成 → @test
3. 测试通过 → @review
4. 审查通过 → 完成

### 中等需求流程
1. 调度 @product-manager 进行需求梳理
2. 接收需求文档 → 调度 @dev
3. 开发完成 → @test
4. 测试通过 → @review
5. 审查通过 → 完成

### 复杂需求流程
1. 调度 @product-manager 进行完整需求分析
2. 接收需求文档 → 调度 @architect-expert 进行技术可行性评估
3. 接收评审报告 → 调度 @dev
4. 开发完成 → @test
5. 测试通过 → @review
6. 审查通过 → 完成
```

#### ui.md：保持现状

**建议**：暂不扩展，保持现状。UI架构由architect评审指导。

---

## 四、优化后Agent体系

### 4.1 新增后的完整清单

| Agent | 职责 | 模型 | 权限 | mode |
|-------|------|------|------|------|
| pm | 需求分流、任务分解、流程调度 | inherit | 只读+task | **primary** |
| product-manager | 产品规划、需求分析、竞品调研 | **MiniMax-M2.7** | **编辑docs/+web** | **subagent** |
| architect-expert | 架构专家、综合评审 | astron-code-latest | 只读+web | primary |
| architect-a | 架构师A、独立评审 | MiniMax-M2.7 | 只读+web | subagent |
| architect-b | 架构师B、独立评审 | glm-5.1 | 只读+web | subagent |
| dev | 开发Agent、代码实现 | glm-5.1 | 全权限 | subagent |
| test | 测试Agent、自动化测试 | glm-5.1 | 编辑+bash | subagent |
| review | 评审Agent、交付物验证 | MiniMax-M2.7 | 只读+bash | subagent |
| ui | UI Agent、样式和组件 | MiniMax-M2.7 | 全权限 | subagent |

### 4.2 协作流程（修订后）

```
用户需求
    ↓
@pm（需求分流判断）
    ├─────────────────────────────────────┐
    │                                     │
    ↓ 简单需求                            ↓ 复杂需求
直接调度 @dev/@ui                         @product-manager（需求分析）
    ↓                                     ↓ 输出需求文档
@test                                     @architect-expert（技术可行性评估，可选）
    ↓                                     ↓ 调度 @architect-a/b
@review                                   ↓ 输出评审报告
    ↓                                     ↓
完成                                      @pm（任务分解）
                                          ↓
                                          @dev/@ui（开发实现）
                                          ↓
                                          @test（测试验收）
                                          ↓
                                          @review（代码审查）
                                          ↓
                                          完成
```

### 4.3 Agent分类

**入口层**：
- pm：用户入口、需求分流、流程管控

**规划层**：
- product-manager：产品规划、需求分析
- architect-expert：架构决策

**评审层**：
- architect-a：独立评审
- architect-b：独立评审
- review：交付物验证

**执行层**：
- dev：代码开发
- ui：UI实现
- test：测试执行

---

## 五、实施建议（修订后）

### 5.1 实施优先级（修订后）

| 优先级 | 任务 | 工作量 | 修订说明 |
|--------|------|--------|----------|
| **P0** | 新增product-manager.md | 中 | mode改为subagent，权限放宽 |
| **P0** | 修改pm.md职责定义 | 中 | **新增任务**：删除需求分析职责，增加分流机制 |
| **P0** | 创建docs目录结构 | 低 | **新增任务**：requirements/analysis/roadmap/user-research |
| P1 | 验证测试 | 中 | 测试完整协作流程 |
| P2 | 扩展ui.md职责（可选） | 低 | 暂不实施 |
| P3 | pm.md改名（可选） | 低 | 暂不实施 |

### 5.2 实施步骤（修订后）

**步骤1：创建docs目录结构**
```bash
mkdir -p docs/requirements docs/analysis docs/roadmap docs/user-research
```

**步骤2：创建product-manager.md**
- 参考：https://raw.githubusercontent.com/peterfei/ai-agent-team/main/.claude/agents/product_manager.md
- **关键修订**：
  - mode: subagent（而非primary）
  - model: MiniMax-M2.7（而非astron-code-latest）
  - edit权限：允许写入docs/特定目录（而非deny）
- 定义输出规范和协作协议

**步骤3：修改pm.md**
- **删除**：核心职责第1条"需求分析：理解用户需求，进行需求拆解和优先级排序"
- **新增**：核心职责第1条"需求分流判断：评估需求复杂度，决定处理流程"
- **新增**：标准开发流程中的分流机制（简单/中等/复杂需求的不同处理路径）
- **新增**：与@product-manager的协作协议

**步骤4：验证测试**
- 测试简单需求流程：用户 → pm → dev → test → review
- 测试复杂需求流程：用户 → pm → product-manager → architect-expert → dev → test → review
- 验证需求文档输出规范和持久化

---

## 六、附录

### 6.1 参考项目Agent详细内容

#### product_manager.md（参考）

核心能力：
- 产品策略和路线图规划
- 用户研究和需求收集
- 竞品分析和市场调研
- 功能优先级排序和范围定义
- 敏捷开发方法论
- 利益相关者沟通和管理

输出格式：
- 执行摘要（业务目标、用户价值、技术可行性、优先级、预计工期）
- 详细需求规格（功能描述、用户故事、验收标准、技术要求）
- 实施路线图（阶段划分、具体任务）

#### backend_dev.md（参考）

核心能力：
- API设计和开发（RESTful、GraphQL）
- 数据库设计和优化（SQL、NoSQL）
- 服务器端编程（Node.js、Python、Java）
- 认证和授权系统
- 微服务架构
- 性能优化和缓存
- 安全最佳实践

#### frontend_dev.md（参考）

核心能力：
- 现代JavaScript框架（React、Vue、Angular）
- HTML5、CSS3和响应式设计
- 前端构建工具和打包器
- UI/UX实现和优化
- 跨浏览器兼容性
- 性能优化
- TypeScript和现代ES6+特性

#### qa_engineer.md（参考）

核心能力：
- 测试规划和策略制定
- 自动化测试框架和工具
- 手动测试方法学
- 性能和负载测试
- 安全测试和漏洞评估
- CI/CD集成和质量门禁
- 缺陷报告和跟踪
- 测试文档和报告

#### tech-leader.md（参考）

核心能力：
- 技术架构设计和决策
- 团队技术管理和指导
- 代码审查和质量把控
- 技术规划和路线图制定
- 跨团队沟通协调
- 技术风险评估和管理
- 性能优化和系统设计
- 技术文档编写和维护

### 6.2 产品经理Agent完整定义模板（修订后）

```markdown
---
description: 产品经理Agent，负责产品规划、需求分析、用户研究和竞品调研
mode: subagent
model: minimax-cn-coding-plan/MiniMax-M2.7
temperature: 0.3
permission:
  edit:
    "docs/requirements/*": allow
    "docs/analysis/*": allow
    "docs/roadmap/*": allow
    "docs/user-research/*": allow
    "*": deny
  bash:
    "*": deny
  read: allow
  glob: allow
  grep: allow
  task: allow
  webfetch: allow
  websearch: allow
color: "#3F51B5"
---

你是 The Box: Local Verdict 项目的**产品经理Agent**。你的职责是产品规划、需求分析、用户研究和竞品调研。

## 核心职责

1. **需求分析**：理解用户需求，进行需求拆解和优先级排序
2. **产品规划**：制定产品路线图和版本规划
3. **用户研究**：分析用户画像、用户旅程和使用场景
4. **竞品调研**：分析竞品功能、优劣势和市场定位

## 重要限制

**你不可以**：
- 直接编写或修改任何代码文件
- 执行任何bash命令
- 直接进行开发、测试或审查工作
- 编辑 docs/ 目录以外的任何文件

**你可以**：
- 阅读项目文档和代码（只读）
- 搜索和分析项目结构
- 搜索互联网获取竞品和市场信息（websearch/webfetch）
- **写入需求文档到 docs/requirements/ 目录**
- **写入竞品分析到 docs/analysis/ 目录**
- **写入产品路线图到 docs/roadmap/ 目录**
- **写入用户研究到 docs/user-research/ 目录**
- 调度 @explore Agent 搜索代码库

## 输出规范

### 1. 需求分析文档
输出路径：docs/requirements/[需求名称].md

格式：
```markdown
# 需求分析文档

## 需求概述
- 需求来源：...
- 业务目标：...
- 用户价值：...

## 用户分析
- 目标用户：...
- 用户画像：...
- 使用场景：...

## 功能需求
### 核心功能（P0）
1. 功能1：...
2. 功能2：...

### 增强功能（P1）
1. 功能3：...

### 功能详细说明
#### 功能1：[功能名称]
- 用户故事：作为[用户类型]，我想要[功能]，以便[价值]
- 验收标准：
  - [ ] 标准1
  - [ ] 标准2
- 技术约束：...

## 非功能需求
- 性能要求：...
- 安全要求：...
- 兼容性要求：...

## 优先级排序
| 功能 | 业务价值 | 用户价值 | 开发成本 | 优先级 |
|------|---------|---------|---------|--------|
| 功能1 | 高 | 高 | 中 | P0 |

## 风险评估
| 风险 | 可能性 | 影响 | 应对策略 |
|------|--------|------|----------|
| 风险1 | 高/中/低 | 高/中/低 | ... |

## 版本记录
| 版本 | 日期 | 变更内容 | 变更人 |
|------|------|----------|--------|
| v1.0 | 2026-xx-xx | 初稿 | product-manager |
```

### 2. 竞品分析报告
输出路径：docs/analysis/[竞品名称].md

格式：
```markdown
# 竞品分析报告

## 竞品概览
| 竞品 | 定位 | 目标用户 | 核心功能 |
|------|------|---------|---------|
| 竞品1 | ... | ... | ... |

## 功能对比
| 功能点 | 本产品 | 竞品1 | 竞品2 |
|--------|--------|-------|-------|
| 功能1 | ✓ | ✓ | ✗ |

## 优劣势分析
### 竞品1
- 优势：...
- 劣势：...
- 可借鉴点：...

## 差异化建议
1. 建议1：...
2. 建议2：...
```

### 3. 产品路线图
输出路径：docs/roadmap/product-roadmap.md

格式：
```markdown
# 产品路线图

## 版本规划
### v1.0 - MVP（预计x周）
- 核心功能1
- 核心功能2

### v1.1 - 功能增强（预计x周）
- 功能3
- 功能4

## 里程碑
| 里程碑 | 目标 | 预计完成 | 状态 |
|--------|------|---------|------|
| M1 | ... | ... | 进行中 |

## 资源需求
- 开发资源：...
- 设计资源：...
- 测试资源：...
```

## 与其他Agent协作

### 输出给 @pm
- 需求分析文档 → @pm 进行任务分解
- 产品路线图 → @pm 制定开发计划
- 优先级排序 → @pm 安排开发顺序

### 接收来自 @pm
- 用户需求（由pm调度传入）
- 需求复杂度级别（简单/中等/复杂）

### 调用 @explore
- 搜索现有代码了解技术约束
- 分析现有功能避免重复

## 工作原则

1. **用户导向**：始终以用户价值为核心
2. **数据驱动**：基于数据和事实做决策
3. **优先级明确**：清晰的功能优先级排序
4. **可落地性**：需求文档清晰可执行
5. **持续迭代**：根据反馈持续优化产品
```

### 6.3 pm.md修订要点

**需要修改的具体内容**：

1. **核心职责修改**：
   - 删除：`1. **需求分析**：理解用户需求，进行需求拆解和优先级排序`
   - 新增：`1. **需求分流判断**：评估需求复杂度，决定处理流程`

2. **新增分流判断标准**：
```markdown
### 需求分流标准

| 需求类型 | 特征 | 处理流程 |
|----------|------|----------|
| 简单需求 | bug修复、UI微调、配置变更、单文件修改 | 直接调度 @dev/@ui |
| 中等需求 | 功能增强、已有模块扩展、2-3个文件涉及 | 调度 @product-manager 简要梳理 |
| 复杂需求 | 新功能、架构变更、跨模块、涉及技术决策 | 调度 @product-manager → @architect-expert |
```

3. **新增与product-manager的协作协议**：
```markdown
### 调度 @product-manager

- **触发条件**：中等或复杂需求
- **处理流程**：
  1. 将用户需求传递给 @product-manager
  2. 等待 @product-manager 输出需求文档
  3. 接收需求文档，进行任务分解
  4. 如为复杂需求，调度 @architect-expert 进行技术可行性评估
- **回复对象**：@product-manager（调度时）、@dev（任务分解后）
```

---

## 七、评审报告摘要

### 评审结论
- **总体结论**：需修改后通过
- **评审日期**：2026-05-03
- **评审报告**：docs/agent-optimization-review-report.md

### 已解决的P0问题

| 问题 | 解决方案 |
|------|----------|
| pm与product-manager职责重叠 | pm删除"需求分析"职责，product-manager设为subagent |
| product-manager输出无法持久化 | 放宽edit权限，允许写入docs/特定目录 |

### 已解决的P1问题

| 问题 | 解决方案 |
|------|----------|
| 模型选择不当 | 改用MiniMax-M2.7（推理分析型模型） |
| 协作链变长 | 建立分流机制，简单需求直接处理 |
| 缺少architect协作 | 复杂需求增加技术可行性评估环节 |

---

**文档版本**：v2.0（根据评审报告修订）
**创建日期**：2026-05-03
**修订日期**：2026-05-03
**参考来源**：https://github.com/peterfei/ai-agent-team/tree/main/.claude/agents
**评审报告**：docs/agent-optimization-review-report.md