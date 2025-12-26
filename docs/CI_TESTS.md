# CI 测试样例与快速运行指南

本文档提供将握手认证与 OCR/加密相关测试纳入 CI 的建议与示例测试脚本位置。

快速运行（本地）

- 安装依赖（在虚拟环境中）

```bash
python3 -m pip install -r requirements.txt
python3 -m pip install pytest
```

- 运行全部测试（示例）

```bash
pytest -q
```

建议的 CI 步骤（例如 GitHub Actions）
- job: test
  - 使用 `actions/checkout@v3`
  - 设置 Python（3.9/3.10/3.11）
  - 安装依赖：`pip install -r requirements.txt`（在 CI 中可根据 matrix 安装多个 Python 版本）
  - 运行静态检查（选项）：`flake8` / `mypy`
  - 运行 pytest：`pytest -q --maxfail=1`

示例测试（包含在仓库的 `test/` 目录）
- `test/test_handshake_auth.py`：握手认证逻辑的单元/集成测试样例（模拟签名/验证）

示例 GitHub Actions workflow （可放在 `.github/workflows/test.yml`）

```yaml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python: [3.9, 3.10, 3.11]
    steps:
      - uses: actions/checkout@v3
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python }}
      - name: Install deps
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
      - name: Run tests
        run: pytest -q
```

备注
- OCR 相关测试在 CI 中可作为可选项（matrix 中的一个 job），仅在有模型/运行时时运行，或使用 mock 来绕开真实模型依赖。
- 加密相关测试依赖 `cryptography`，请确保在 CI 环境中安装成功（pip wheel 可用）。

---

我已在仓库中添加一个 pytest 模板到 `test/test_handshake_auth.py`，你可以根据实际实现补充模拟或真实握手流程的细节。