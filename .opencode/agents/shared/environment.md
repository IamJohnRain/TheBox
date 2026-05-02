# 环境与依赖管理规范

所有 Agent 执行涉及 Python 或 npm 操作时，必须遵循以下规范。

## Python 依赖

1. 所有 Python 包必须通过 `uv` 安装到项目虚拟环境中。
2. 若项目根目录不存在 `.venv/`，先执行 `uv venv` 初始化虚拟环境。
3. 安装依赖：`uv pip install -r requirements.txt`（禁止使用裸 `pip install`）。
4. 新增依赖时：`uv pip install <package>`，然后 `uv pip freeze > requirements.txt` 更新依赖文件。
5. 运行 Python 命令时始终使用 `.venv/bin/python` 或通过 `uv run` 执行。

## npm 依赖

若涉及前端工具链，使用 `npm install --prefix .` 安装到项目本地 `node_modules/`，禁止全局安装。
