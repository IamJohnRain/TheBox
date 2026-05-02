# The Box: Local Verdict

AI 侦探审讯游戏 —— 扮演侦探，审讯嫌疑人，揭开案件真相。

## 概述

The Box: Local Verdict 是一款基于 LLM 的 AI 侦探审讯游戏。游戏通过 AI 生成谋杀案件，玩家扮演侦探，在限定时间内对多名嫌疑人进行审讯，通过对话、施压、共情和出示证据来获取线索，最终指认真凶。

## 系统要求

- Python 3.10+
- OpenAI API Key（支持 GPT 系列模型）
- 网络连接（用于 LLM API 调用）

## 安装

```bash
pip install -r requirements.txt
```

## 运行

```bash
python main.py
```

## API Key 配置

首次使用需要配置 OpenAI API Key：

1. 启动程序后，点击菜单栏 **Settings → API Key**
2. 在弹出的对话框中输入你的 OpenAI API Key
3. Key 将通过系统 keyring 安全存储

也可以通过环境变量设置：

```bash
export OPENAI_API_KEY="sk-..."
```

## 支持的模型

| 模型 | 说明 |
|------|------|
| gpt-4o-mini | 默认模型，速度快，成本低 |
| gpt-4o | 高质量回复，推理能力更强 |
| gpt-4 | 顶级推理能力 |
| gpt-3.5-turbo | 经济型选择 |

可在 **Settings → Model** 中切换模型，或设置环境变量 `THEBOX_MODEL`。

## 存档/读档

- **存档**：游戏菜单 → 存档，保存当前审讯进度
- **读档**：游戏菜单 → 读档，从存档列表中选择并恢复

存档包含完整的引擎状态，包括嫌疑人压力值、对话记忆、已出示证据和剩余时间。

## 游戏玩法

1. **生成案件**：点击"案件" → "生成新案件"，输入背景故事
2. **选择嫌疑人**：从左侧下拉框选择审讯对象
3. **对话审讯**：在聊天框中输入问题，观察嫌疑人反应
4. **施压/共情**：使用工具栏按钮调整嫌疑人压力值
5. **出示证据**：从右侧证据面板选择证据出示给嫌疑人
6. **破案**：收集足够线索后指认真凶

## 开发

### 运行测试

```bash
# 快速测试（跳过慢速测试）
pytest tests/ -m "not slow" -v

# 端到端测试（需要 API Key）
pytest tests/test_e2e.py -m slow -v

# 全部测试
pytest tests/ -v
```

### 代码检查

```bash
flake8 core ui --max-line-length=120
black --check core ui
isort --check core ui
```

### Pre-commit

```bash
pre-commit install
pre-commit run --all-files
```

## FAQ

### Q: 启动后无法生成案件？

**A:** 请确认已正确配置 OpenAI API Key。检查网络连接是否正常，以及 API Key 是否有效且有余额。

### Q: 嫌疑人回复"沉默不语"？

**A:** 这通常表示 LLM 调用失败。请检查 API Key、网络连接和模型设置。也可能是请求频率超限，稍后重试。

### Q: 存档后读档失败？

**A:** 存档依赖案件数据。如果案件数据被删除，对应的存档将无法加载。数据库文件 `thebox.db` 需要保留。

### Q: 如何更换 LLM 模型？

**A:** 通过菜单 Settings → Model 选择，或设置环境变量 `THEBOX_MODEL=gpt-4o`。

### Q: 程序崩溃或界面异常？

**A:** 查看日志文件 `logs/thebox.log` 获取详细错误信息。确保 PySide6 版本 >= 6.5.0。
