# 嫌疑人指标体系完整定义

> **版本**：v1.1  
> **依赖**：Phase 1（供词层级系统）、Phase 2（压力动态、反扑机制）  
> **状态**：待评审  
> **v1.1 变更**：本文所有数值均为 `config/gameplay_balance.json` 默认值，实际实现必须通过 `core.game_config` 读取，禁止在业务逻辑硬编码。

---

## 概述

每个嫌疑人拥有 **8个指标**，分为三类：

| 类别 | 指标 | 可见性 | 动态性 |
|------|------|--------|--------|
| 可见指标 | pressure（压力值） | 始终可见 | 高度动态 |
| 可见指标 | confession_level（供词层级） | 始终可见 | 阶梯升级 |
| 隐藏指标 | fear（恐惧值） | Lv.2+ 初级侧写 | 高度动态 |
| 隐藏指标 | defiance（抗压性） | Lv.10+ 高级侧写 | 中度动态 |
| 隐藏指标 | empathy_susceptibility（共情易感性） | Lv.10+ 高级侧写 | 中度动态 |
| 隐藏指标 | deception_skill（欺骗技巧） | Lv.15+ 大师侧写 | 中度动态 |
| 隐藏指标 | loyalty（忠诚度） | Lv.15+ 大师侧写 | 中度动态 |
| 隐藏指标 | credibility（可信度） | 不可见 | 低度动态 |

**核心设计原则**：
- **全维度动态变化**：5个隐藏维度都会随审讯过程动态变化，不是初始化后不变的死值
- **维度间联动**：维度之间互相影响，形成正/负反馈循环
- **反扑机制**：嫌疑人不是沙袋，会根据状态主动反击
- **主+副性格**：7种性格可组合，维度初始值由主性格(0.7) + 副性格(0.3)加权计算
- **数值配置化**：表格中的阈值、倍率、增减量和冷却值都是默认配置，调参只修改 `gameplay_balance.json`

---

## 1. pressure 压力值

### 定义

嫌疑人在审讯中承受的心理压迫程度。压力越高，嫌疑人越难以维持冷静，供词进展越快，但也会触发主动开口等不可控行为。

### 属性

| 属性 | 值 |
|------|-----|
| 值域 | 0-100（整数），硬边界不越界 |
| 可见性 | 始终可见（所有等级） |
| 初始值 | 默认20（配置基础值，所有嫌疑人相同，可调） |

### 分段效果

| 段位 | 范围 | 供词增速 | 时间动态 | LLM 行为指令 |
|------|------|---------|---------|-------------|
| 冷静 | 0-30 | 0.02/轮 | 每轮 -1（自然衰减，受floor=15保护） | 冷静从容，回答滴水不漏，主动质疑指控 |
| 紧张 | 30-70 | 0.05/轮 | 稳定（不增不减） | 有些紧张，偶有多余发言，细微前后不一致 |
| 慌乱 | 70-80 | 0.10/轮 | 每轮 +1（自然增长） | 慌乱矛盾，可能说漏嘴，辩解逻辑混乱 |
| 崩溃边缘 | 80-100 | 0.15/轮 | 每轮 +1（自然增长） | 接近崩溃，语无伦次，可能不自觉泄露 |

### 动态变化触发器

| 触发 | 变化 | 条件 |
|------|------|------|
| 出示正确证据 | +基础增量×fear系数×defiance系数 | evidence.related_suspect == suspect.name；默认基础值 physical/document/testimony = 18/12/9 |
| 证据链 | 默认+10 额外 | chain_with 关联已出示证据 |
| 施压（action=pressure） | 默认+15×soft_factor | 使用施压操作（默认每人限2次，第二次效果减半） |
| 沉默施压工具 | 默认+15 | 工具使用 |
| 威胁工具 | 默认+20 | 工具使用 |
| 多人对质工具 | 默认+20（当前嫌疑人） | 工具使用 |
| 反驳成功 | 本次增量归零 | rebuttal_believable=True |
| 共情（action=empathy） | 默认-5×empathy系数 | 共情操作（默认每人限2次，第二次效果减半） |
| 每轮动态（低段） | 默认-1/轮 | pressure < 30 |
| 每轮动态（高段） | 默认+1/轮 | pressure >= 70 |
| 反扑：挑衅 | 默认-2/轮 | fear < 15 时触发 |
| 反扑：得意回应 | 默认供词进度 -0.05 | 反驳成功时 |

### 对其他维度的影响

| 联动 | 条件 | 效果 |
|------|------|------|
| pressure→defiance | pressure > 60 | defiance 每轮 -1 |
| pressure→deception_skill | pressure > 70 | deception_skill 每轮 -2 |
| pressure→主动开口 | pressure > 70 | 每5轮概率检查（pressure/300，即23%-33%） |
| pressure→反驳 | pressure > 80 | 反驳几乎不可能成功（程序化兜底） |
| pressure→loyalty | pressure > loyalty | 多人对质时可能背叛 |

---

## 2. confession_level 供词层级

### 定义

嫌疑人供认的深度等级，是游戏的核心胜利条件。层级越高，嫌疑人透露的信息越多。

### 属性

| 属性 | 值 |
|------|-----|
| 值域 | 0-4（整数，离散层级） |
| 可见性 | 始终可见（所有等级） |
| 初始值 | 0 |

### 层级定义

| 层级 | 名称 | 描述 | LLM 指令 |
|------|------|------|---------|
| 0 | 否认 | 完全否认一切 | 坚决否认所有指控 |
| 1 | 动摇 | 情绪波动，出现紧张、回避 | 开始表现出不安，但仍然否认 |
| 2 | 部分承认 | 承认部分事实，但隐瞒关键 | 承认一些边缘事实，回避核心问题 |
| 3 | 关键突破 | 透露动机/手段/时机之一 | 泄露关键信息之一，但试图最小化 |
| 4 | 完全崩溃 | 完整供述真相 | 和盘托出所有细节 |

### 升级阈值

| 升至层级 | 最低pressure | 最低轮次 | 需要关联证据 |
|---------|-------------|---------|------------|
| 0→1 | 40 | 3 | 否 |
| 1→2 | 55 | 5 | 是 |
| 2→3 | 70 | 7 | 是 |
| 3→4 | 85 | 10 | 是 |

### 胜利条件

- confession_level >= 4 → 胜利（完全崩溃）
- secret_triggered 且 confession_level >= 3 → 完美胜利
- confession_level < 3 时 _postprocess 拦截禁止触发胜利

### 供词进度（confession_progress）

- 值域：0.0-1.0（浮点数）
- 每次有效交互增加：rate 由当前 pressure 段位决定（0.02/0.05/0.10/0.15）
- v1.5 中该值是 UI/复盘反馈指标，不作为升级硬门槛；升级以 pressure + turn_count + related_evidence 为准
- 升级瞬间视为当前层进度已完成，然后 progress 重置为 0.0

### 动态变化触发器

| 触发 | 变化 | 条件 |
|------|------|------|
| 每次有效交互 | +rate | pressure 段位决定 rate |
| 共情成功 | +0.1×empathy系数 | 共情操作 |
| 心理崩溃工具 | 直接尝试+1级 | 工具使用（先尝试正常升级，失败则强制+1） |
| 反扑：得意回应 | -0.05 | 反驳成功 |

---

## 3. fear 恐惧值

### 定义

嫌疑人对审讯员/审讯情境的畏惧程度。恐惧高时施压效果增益，恐惧低时施压效果极弱甚至触发嫌疑人反扑。**恐惧是"施压路线"的核心调控值。**

### 属性

| 属性 | 值 |
|------|-----|
| 值域 | 0-100（整数），硬边界不越界 |
| 可见性 | Lv.2+（初级心理侧写） |
| 初始值 | 由性格计算：主性格值×0.7 + 副性格值×0.3 |

### 对游戏机制的影响

```
fear_factor = fear / 50

# fear=50 → factor=1.0（正常效果）
# fear=80 → factor=1.6（施压效果+60%）
# fear=20 → factor=0.4（施压效果仅40%）
# fear<15 → 触发反扑：挑衅态度
```

施压/证据的综合压力公式：

```python
raw_delta = base × (1 + strength × 0.1) + chain_bonus  # base: physical=18, document=12, testimony=9
fear_factor = suspect.fear / 50
defiance_factor = 1.0 / (1.0 + suspect.defiance × 0.01)
raw_factor = fear_factor × defiance_factor
# 软上限：将综合系数限制在 0.3 - 1.5 之间，防止极端性格差距过大
soft_factor = max(0.3, min(1.5, raw_factor))
pressure_delta = int(raw_delta × soft_factor)
# AP消耗：施压=2AP, 出示证据=2AP, 对话=1AP
```

### fear 分段行为

| fear范围 | 行为 |
|---------|------|
| 0-14 | **挑衅态度**：嫌疑人LLM回复变为挑衅口吻，pressure每轮-2（反压制玩家） |
| 15-30 | 谨慎但不怕：施压效果低，可能试探玩家 |
| 30-70 | 正常范围：恐惧与操作正常交互 |
| 70-100 | 高度恐惧：施压效果增益，defiance加速瓦解 |

### 动态变化触发器

| 触发 | 变化 | 说明 |
|------|------|------|
| 出示正确证据 | +8 | 证据让嫌疑人害怕（与错误-10形成正向激励） |
| 出示错误证据 | -10 | 玩家暴露了判断失误 |
| 施压成功（对真凶） | +5 | 有效施压增加恐惧 |
| 施压失败（对无辜者） | -5 | 嫌疑人知道你搞错了 |
| 共情 | -10 × (empathy_susceptibility/50) | 共情降低恐惧，empathy高时效果强 |
| 对真凶共情（错误共情） | +5 | 真凶觉得你在套话，反而警惕 |
| 反驳成功 | -5 | 得逞→恐惧下降 |
| 反扑：反击质问 | +10 | 连续2次施压失败触发 |
| 每轮动态 | -1/轮 | 每轮自然冷却 |
| 被同伴出卖 | +10 | 忠诚崩塌后恐惧上升 |

### 对其他维度的影响

| 联动 | 条件 | 效果 |
|------|------|------|
| fear→defiance | fear > 70 | defiance 每轮 -2（恐惧瓦解抗压性） |
| fear→deception_skill | fear > 70 | deception_skill 每轮 -3（恐惧下破绽百出） |
| fear→empathy_susceptibility | fear > 60 | empathy 每轮 +1（恐惧打开心门） |
| fear→loyalty | fear > 70 | loyalty 每轮 -2（恐惧动摇忠诚） |
| fear→反扑 | fear < 15 | 触发挑衅态度反扑 |

---

## 4. defiance 抗压性

### 定义

嫌疑人抵抗压力的心理韧性。抗压性高时，施压/证据带来的压力增量被削弱；抗压性低时，压力容易快速堆积。**defiance 是"施压路线"的核心阻力值。**

### 属性

| 属性 | 值 |
|------|-----|
| 值域 | 5-100（整数），**最低5**，不归零（始终保留基础抗压） |
| 可见性 | Lv.10+（高级心理侧写） |
| 初始值 | 由性格计算：主性格值×0.7 + 副性格值×0.3 |

### 对游戏机制的影响

```
defiance_factor = 1.0 / (1.0 + defiance × 0.01)

# defiance=50 → factor=1/(1+0.5)=0.67（效果降至67%）
# defiance=80 → factor=1/(1+0.8)=0.56（效果降至56%）
# defiance=5  → factor=1/(1+0.05)=0.95（效果几乎不减）
# defiance=100→ factor=1/(1+1.0)=0.50（效果减半）
```

### 动态变化触发器

| 触发 | 变化 | 说明 |
|------|------|------|
| pressure > 60 时每轮 | -1 | 高压逐渐瓦解心理防线 |
| fear > 70 时每轮 | -2 | 恐惧到极点时抗压性加速崩溃 |
| 施压被反驳成功 | +3 | 成功抵抗→信心增加 |
| 连续3轮无有效施压 | +1 | 嫌疑人恢复镇定 |
| pressure < 30 时每轮 | +1 | 低压力时恢复抗压性 |
| 反扑：挑衅态度时 | +2/轮 | fear<15触发后，defiance持续回升 |

### 对其他维度的影响

| 联动 | 条件 | 效果 |
|------|------|------|
| defiance→pressure | 始终 | defiance_factor 削弱压力增量 |
| defiance→empathy_susceptibility | defiance > 70 | empathy 每轮 -1（强硬使人不易被打动） |

### 设计意图

defiance 是"可被消磨的护甲"。玩家需要先用证据/施压累积压力，压力高后 defiance 自然瓦解，形成正反馈循环。但如果施压失败（被反驳），defiance 反而上升，形成反扑。

---

## 5. empathy_susceptibility 共情易感性

### 定义

嫌疑人被情感打动、敞开心扉的倾向。共情易感性高时，共情操作效果显著（恐惧大幅下降、供词进度显著提升）；共情易感性低时，共情几乎无效。**empathy 是"共情路线"的核心调控值。**

### 属性

| 属性 | 值 |
|------|-----|
| 值域 | 0-95（整数），**最高95**，保留一点抵抗 |
| 可见性 | Lv.10+（高级心理侧写） |
| 初始值 | 由性格计算：主性格值×0.7 + 副性格值×0.3 |

### 对游戏机制的影响

```
empathy_factor = empathy_susceptibility / 50

# empathy=50 → factor=1.0（共情效果正常）
# empathy=80 → factor=1.6（共情效果+60%）
# empathy=20 → factor=0.4（共情效果仅40%）

共情效果：
  fear变化     = -10 × empathy_factor
  confession进度 = +0.1 × empathy_factor
  pressure变化 = -5 × empathy_factor（仅高empathy时微降）
```

### 动态变化触发器

| 触发 | 变化 | 说明 |
|------|------|------|
| fear > 60 时每轮 | +1 | 恐惧使人更渴望被理解 |
| 共情成功后 | +2 | 正反馈：被理解后更愿意敞开 |
| 施压成功后 | -2 | 负反馈：施压让嫌疑人关上心门 |
| defiance > 70 时每轮 | -1 | 强硬的人不容易被打动 |
| 反驳成功后 | -1 | 对抗心理让嫌疑人抗拒情感 |
| 共情对真凶（错误共情） | -3 | 真凶觉得你在套话，对共情更警惕 |

### 对其他维度的影响

| 联动 | 条件 | 效果 |
|------|------|------|
| empathy→fear | 共情操作 | fear 下降量 = 10 × (empathy/50) |
| empathy→confession | 共情操作 | 进度增量 = 0.1 × (empathy/50) |
| empathy→pressure | 共情操作 | pressure 微降 = 5 × (empathy/50) |

### 设计意图

empathy 与 defiance 形成"共情 vs 施压"的路线抉择。高 empathy 的嫌疑人适合共情路线，低 empathy 的只能走施压路线。**关键：先施压会降低 empathy（关上心门），先共情再施压效果更好。**

---

## 6. deception_skill 欺骗技巧

### 定义

嫌疑人维持谎言、成功反驳的能力。欺骗技巧高时，反驳更难被识破，高压下仍能从容撒谎；欺骗技巧低时，反驳容易失败，压力下破绽百出。

### 属性

| 属性 | 值 |
|------|-----|
| 值域 | 5-100（整数），**最低5**，不归零（保留基础撒谎能力） |
| 可见性 | Lv.15+（大师级心理侧写） |
| 初始值 | 由性格计算：主性格值×0.7 + 副性格值×0.3 |

### 对游戏机制的影响

```python
# 影响反驳可信度程序化兜底的阈值
effective_hard_threshold = 80 + int((deception_skill - 50) × 0.2)
effective_soft_threshold = 60 + int((deception_skill - 50) × 0.1)

# deception=80 → hard=86, soft=63（高压下仍可能成功反驳）
# deception=50 → hard=80, soft=60
# deception=20 → hard=74, soft=57（较早无法反驳）
# deception=5  → hard=71, soft=55.5（很快无法反驳）
```

### 动态变化触发器

| 触发 | 变化 | 说明 |
|------|------|------|
| pressure > 70 时每轮 | -2 | 高压下难以维持谎言 |
| fear > 70 时每轮 | -3 | 恐惧下破绽百出（恐惧对deception的瓦解比压力更快） |
| 反驳成功（believable=True） | +1 | 得逞更自信 |
| 反驳失败（被程序化否决） | -3 | 被识破→信心受挫 |
| 伪造证据被嫌疑人识破 | -5 | 重大打击 |
| 压力低且无操作时 | +1/3轮 | 恢复镇定后重拾欺骗技巧 |

### 对其他维度的影响

| 联动 | 条件 | 效果 |
|------|------|------|
| deception→rebuttal | 反驳判定 | 阈值 -= deception×0.2 |
| 反驳结果→deception | 成功+1，失败-3 | 自我强化/削弱循环 |

### 设计意图

deception 是"可被消磨的谎言护甲"。狡猾型嫌疑人初期反驳极难被识破，但持续施压+证据+恐惧会逐渐瓦解。一旦反驳被否决，deception 加速下降，形成"谎言崩塌"的雪球效应。

---

## 7. loyalty 忠诚度

### 定义

嫌疑人对同伙/组织的忠诚程度。忠诚度影响多人对质效果和同伴被击破后的反应。忠诚度高时，即使高压也不会出卖同伙；忠诚度低时，审讯压力超过忠诚阈值就会背叛。

### 属性

| 属性 | 值 |
|------|-----|
| 值域 | 0-100（整数），可以归零 |
| 可见性 | Lv.15+（大师级心理侧写） |
| 初始值 | 由性格计算：主性格值×0.7 + 副性格值×0.3 |

### 对游戏机制的影响

```python
# 多人对质时
if suspect.pressure > suspect.loyalty:
    # 压力超过忠诚 → 嫌疑人可能背叛同伙
    betrayal_hint = True

# 同伴被击破时
if other_suspect.confession_level >= 3:
    suspect.loyalty -= 10

if other_suspect.confession_level >= 4:
    suspect.loyalty -= 15
```

### 动态变化触发器

| 触发 | 变化 | 说明 |
|------|------|------|
| 多人对质 | -5 | 面对面压力动摇忠诚 |
| 同伴被击破（confession_level≥3） | -10 | 墙倒了 |
| 同伴完全崩溃（confession_level=4） | -15 | 信任彻底崩塌 |
| 被同伴出卖（同伴主动泄露信息） | -15 | 被出卖后忠诚无意义 |
| fear > 70 时每轮 | -2 | 恐惧动摇忠诚 |
| 被威胁 | -3 | 威胁动摇 |
| loyalty < 20 且 pressure > 50 | 每轮 -1 | 忠诚即将崩塌，加速瓦解 |

### 对其他维度的影响

| 联动 | 条件 | 效果 |
|------|------|------|
| loyalty→多人对质 | 多人对质工具 | loyalty 低 → 更容易背叛 |
| loyalty→fear | 被同伴出卖 | fear +10（崩塌后更加恐惧） |

### 设计意图

loyalty 是"群体防线的粘合剂"。主谋 loyalty 通常低（独狼），从犯 loyalty 高。多人对质的核心策略：先击破 loyalty 低的嫌疑人，再用他的供述瓦解 loyalty 高的。

---

## 8. credibility 可信度

### 定义

嫌疑人当前陈述的可信程度。影响后续反驳成功率和 LLM 行为。可信度高时，嫌疑人的反驳更容易被接受；可信度低时，嫌疑人的话被赋予更少权重。

### 属性

| 属性 | 值 |
|------|-----|
| 值域 | 0-100（整数） |
| 可见性 | 不可见（隐藏属性，心理侧写也不显示） |
| 初始值 | 50 |

### 对游戏机制的影响

```python
# credibility 影响反驳可信度的额外微调
if suspect.credibility > 70:
    effective_hard_threshold += 5  # 高可信度：反驳阈值放宽
elif suspect.credibility < 30:
    effective_hard_threshold -= 5  # 低可信度：反驳阈值收紧
```

### 动态变化触发器

| 触发 | 变化 | 说明 |
|------|------|------|
| 反驳成功（believable=True） | +10 | 成功辩解增加可信度 |
| 反驳失败（believable=False） | -5 | 被识破降低可信度 |
| 供词层级升级 | -10 | 承认事实 = 之前在撒谎 |
| 证据链形成 | -5 | 铁证面前可信度下降 |
| 主动开口暴露信息 | -8 | 不小心说漏嘴 |

### 设计意图

credibility 是"反驳路线的弹药"。狡猾型嫌疑人初始 credibility=50，如果多次反驳成功可以叠加到 70+，更难被识破。但如果被识破一次（-5），加上供词升级（-10），credibility 快速跌落，形成"信用破产"的雪球。这个指标不需要玩家看到，它是程序化判定中的一个辅助因子。

---

## 性格系统

### 7种性格的维度值

| 性格 | fear | defiance | empathy | deception | loyalty | 典型角色 |
|------|------|----------|---------|-----------|---------|---------|
| 冷静 | 30 | 70 | 30 | 60 | 50 | 主谋、幕后黑手 |
| 暴躁 | 60 | 30 | 50 | 20 | 40 | 打手、冲动型从犯 |
| 狡猾 | 40 | 50 | 20 | 80 | 30 | 会计、策划者 |
| 胆小 | 80 | 20 | 70 | 10 | 60 | 被胁迫者、旁观者 |
| 固执 | 35 | 80 | 15 | 30 | 70 | 死忠、亲信 |
| 忠诚 | 40 | 40 | 60 | 20 | 90 | 从犯、保护者 |
| 孤僻 | 45 | 60 | 10 | 50 | 20 | 独狼、知情人 |

### 主+副性格组合计算

```python
primary_weight = 0.7
secondary_weight = 0.3

dim_value = primary_dims[dim] * primary_weight + secondary_dims[dim] * secondary_weight
```

### 组合示例

| 组合 | fear | defiance | empathy | deception | loyalty | 特征描述 |
|------|------|----------|---------|-----------|---------|---------|
| 狡猾+胆小 | 52 | 41 | 35 | 59 | 39 | 表面狡猾内心恐惧，共情可能有效 |
| 冷静+狡猾 | 33 | 64 | 27 | 66 | 44 | 极难突破，需证据链+长时间施压 |
| 暴躁+固执 | 53 | 45 | 40 | 23 | 61 | 容易激怒但忠诚，施压效果一般 |
| 胆小+忠诚 | 68 | 26 | 66 | 13 | 78 | 恐惧高但忠诚也高，需先瓦解忠诚 |
| 固执+冷静 | 31 | 77 | 25 | 51 | 56 | 最难突破型，defiance极高 |
| 忠诚+胆小 | 68 | 26 | 66 | 13 | 78 | 高忠诚+高恐惧，共情后可能反水 |
| 孤僻+狡猾 | 41 | 57 | 17 | 71 | 23 | 共情几乎无效，但loyalty低可撬动 |

### Schema 扩展

```json
{
  "personality": "狡猾",
  "personality_secondary": "胆小",
  ...
}
```

缺失 `personality_secondary` 时按主性格 100% 计算（向后兼容）。

---

## 反扑机制

### 设计原则

嫌疑人不是沙袋，会根据玩家行为和自身状态主动反击。反扑不是纯惩罚，而是给玩家制造决策压力。

### 5种反扑行为

#### 反击质问

| 属性 | 值 |
|------|-----|
| 触发条件 | 连续2次施压被反驳成功 |
| 效果 | fear +10, defiance +3 |
| LLM 行为 | 嫌疑人反问："你到底有没有证据？" |
| 战术意义 | 逼迫玩家决定是否出示证据 |

#### 得意回应

| 属性 | 值 |
|------|-----|
| 触发条件 | 反驳成功（believable=True） |
| 效果 | fear -5, deception_skill +1, 供词进度 -0.05 |
| LLM 行为 | 嘲讽："你搞错了。" |
| 战术意义 | 反驳成功会削弱审讯进展 |

#### 挑衅态度

| 属性 | 值 |
|------|-----|
| 触发条件 | fear < 15 |
| 效果 | pressure 每轮 -2, defiance 每轮 +2 |
| LLM 行为 | 挑衅口吻："你奈我何？" |
| 战术意义 | fear极低时嫌疑人反压制，需用共情或正确证据恢复fear |

#### 试探玩家

| 属性 | 值 |
|------|-----|
| 触发条件 | pressure > 40 且 fear < 20 |
| 效果 | 如玩家无法出示证据 → fear -10 |
| LLM 行为 | 主动提问："你真的有证据吗？" |
| 战术意义 | 试探玩家底牌，迫使消耗证据次数 |

#### 恢复镇定

| 属性 | 值 |
|------|-----|
| 触发条件 | 连续3轮无有效施压 |
| 效果 | defiance +3, fear -5, deception_skill +2 |
| LLM 行为 | 沉默后恢复冷静姿态 |
| 战术意义 | 鼓励玩家保持攻击节奏，不要拖延 |

### 反扑检测时机

在 `submit_action` 末尾统一检查（与主动开口同位置），不在 tick 中检查（避免阻塞）。

### 新增事件类型

```python
class ProactiveEvent(TypedDict):
    type: Literal["proactive"]
    suspect_index: int
    proactive_type: str  # "counter_attack" / "gloat" / "provocation" / "probe" / "recover"
    content: str         # LLM生成的嫌疑人主动发言内容
    effects: Dict[str, int]  # {"fear": +10, "defiance": +3, ...}
```

---

## 完整推演示例

### 嫌疑人：王明，工厂会计，狡猾+胆小型

初始：fear=52, defiance=41, empathy=35, deception=59, loyalty=39, pressure=20

| 回合 | 操作 | fear | defiance | empathy | deception | loyalty | pressure | 说明 |
|------|------|------|----------|---------|-----------|---------|----------|------|
| — | 初始 | 52 | 41 | 35 | 59 | 39 | 20 | |
| 1 | 施压 | 57 | 41 | 35 | 59 | 39 | 28 | fear+5, pressure=15×(57/50)÷1.41≈12 |
| 2 | 出示正确物证 | 65 | 40 | 36 | 58 | 38 | 43 | fear+8, pressure按18基础值计算，各维度自然联动 |
| 3 | 嫌疑人反驳(失败) | 62 | 40 | 36 | **55** | 38 | 40 | deception-3(被识破) |
| 4 | 共情 | 55 | 40 | **38** | 55 | 38 | 40 | fear-7(empathy=36/50), empathy+2 |
| 5 | 出示错误证据 | **45** | 40 | 38 | 55 | 38 | 40 | fear-10(惩罚) |
| 6 | 嫌疑人反扑:挑衅 | 45 | **43** | 38 | 55 | 38 | 40 | defiance+3(连续无有效施压) |
| 7 | 施压(被反驳成功) | **55** | **46** | **36** | **56** | 38 | 40 | 反扑: fear+10, defiance+3, empathy-2, deception+1 |
| 8 | 出示正确书证(证据链) | 63 | 45 | 36 | 55 | 37 | **59** | fear+8, chain_bonus+10 |
| 9 | 空闲/聊天(1轮) | 62 | 44 | 37 | 55 | 37 | **59** | fear自然冷却, 各维度联动 |
| 10 | 多人对质 | 60 | 43 | 36 | 54 | **32** | **68** | loyalty-5, pressure+20 |

---

## 维度联动全景图

```
                    ┌──────────┐
          ┌────────→│  fear    │←────────┐
          │         └────┬─────┘         │
          │              │               │
    施压效果增益    fear>70:        fear<15:
    fear/50系数     defiance-2/轮   触发挑衅反扑
    fear>60:        deception-3/轮  pressure-2/轮
    empathy+1/轮    loyalty-2/轮    defiance+2/轮
          │              │               │
          │         ┌────┴─────┐         │
          │         │ pressure │         │
          │         └────┬─────┘         │
          │              │               │
          │    pressure>60:        出示正确证据:
          │    defiance-1/轮       fear+8
          │    pressure>70:        出示错误证据:
          │    deception-2/轮      fear-10
          │    主动开口检查        施压成功:
          │              │        fear+5
          │              │        施压失败:
          │              │        fear-5
          │         ┌────┴─────┐         │
          ├────────→│ defiance │←─────────┤
          │         └────┬─────┘         │
          │              │               │
    施压阻力系数    defiance>70:     反驳成功:
    1/(1+def×0.01)  empathy-1/轮    defiance+3
          │              │         反扑挑衅:
          │              │        defiance+2/轮
          │         ┌────┴─────┐
          ├────────→│ empathy  │
          │         └────┬─────┘
          │              │
    共情效果系数    共情成功:
    empathy/50      empathy+2
    fear>60:        施压成功:
    empathy+1/轮   empathy-2
          │
          │         ┌──────────┐
          ├────────→│deception │
          │         └────┬─────┘
          │              │
    反驳阈值调整    反驳成功:
    threshold-      deception+1
    deception×0.2   反驳失败:
    pressure>70:    deception-3
    deception-2/轮  fear>70:
                    deception-3/轮

          │         ┌──────────┐
          └────────→│ loyalty  │
                    └────┬─────┘
                         │
    多人对质判定    同伴confession≥3:
    pressure>loyalty loyalty-10
    →背叛提示       fear>70:
                    loyalty-2/轮
                    被同伴出卖:
                    loyalty-15
                    →fear+10
```

---

## gameplay_balance.json 维度动态配置

以下片段展示配置导出形状。实现时应把默认值写入 `config/gameplay_balance.json`，`core/game_config.py` 只负责加载和校验。

```python
# ──────────────────────────────────────────────
# 维度动态变化配置
# ──────────────────────────────────────────────

# 维度边界
DIMENSION_BOUNDS = {
    "fear":                  {"min": 0,   "max": 100},
    "defiance":              {"min": 5,   "max": 100},
    "empathy_susceptibility": {"min": 0,   "max": 95},
    "deception_skill":       {"min": 5,   "max": 100},
    "loyalty":               {"min": 0,   "max": 100},
    "credibility":           {"min": 0,   "max": 100},
}

# 性格维度映射
PERSONALITY_DIMENSIONS = {
    "冷静":  {"fear": 30, "defiance": 70, "empathy_susceptibility": 30, "deception_skill": 60, "loyalty": 50},
    "暴躁":  {"fear": 60, "defiance": 30, "empathy_susceptibility": 50, "deception_skill": 20, "loyalty": 40},
    "狡猾":  {"fear": 40, "defiance": 50, "empathy_susceptibility": 20, "deception_skill": 80, "loyalty": 30},
    "胆小":  {"fear": 80, "defiance": 20, "empathy_susceptibility": 70, "deception_skill": 10, "loyalty": 60},
    "固执":  {"fear": 35, "defiance": 80, "empathy_susceptibility": 15, "deception_skill": 30, "loyalty": 70},
    "忠诚":  {"fear": 40, "defiance": 40, "empathy_susceptibility": 60, "deception_skill": 20, "loyalty": 90},
    "孤僻":  {"fear": 45, "defiance": 60, "empathy_susceptibility": 10, "deception_skill": 50, "loyalty": 20},
}

# 性格组合权重
PERSONALITY_PRIMARY_WEIGHT = 0.7
PERSONALITY_SECONDARY_WEIGHT = 0.3

# 每轮维度联动（在 submit_action 末尾执行）
DIMENSION_PER_TURN_EFFECTS = {
    "pressure_gt_60": {"defiance": -1},
    "pressure_gt_70": {"deception_skill": -2},
    "fear_gt_70":     {"defiance": -2, "deception_skill": -3, "loyalty": -2},
    "fear_gt_60":     {"empathy_susceptibility": +1},
    "defiance_gt_70": {"empathy_susceptibility": -1},
    "pressure_lt_30": {"defiance": +1},
    "fear_lt_15":     {"defiance": +2},  # 挑衅反扑
}

# fear 每轮自然冷却
FEAR_PER_TURN_DECAY = -1  # 每轮 -1

# 反扑触发条件
PROACTIVE_TRIGGERS = {
    "counter_attack": {"condition": "consecutive_rebuttal_success >= 2", "effects": {"fear": +10, "defiance": +3}},
    "gloat":          {"condition": "rebuttal_believable == True", "effects": {"fear": -5, "deception_skill": +1}},
    "provocation":    {"condition": "fear < 15", "effects": {"pressure": -2, "defiance": +2}},
    "probe":          {"condition": "pressure > 40 and fear < 20", "effects": {"fear": -10}},  # 仅当无法出示证据
    "recover":        {"condition": "consecutive_idle_turns >= 3", "effects": {"defiance": +3, "fear": -5, "deception_skill": +2}},
}
```
