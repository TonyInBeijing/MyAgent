# MyAgent

基于 FastAPI 的智能体服务。当前是项目骨架，只提供一个示例接口。

## 项目结构

```text
src/myagent/
├── __init__.py
├── __main__.py          # python -m myagent
├── main.py              # 应用工厂与启动入口
└── api/
    └── routes.py        # HTTP 路由
```

## 快速开始

```bash
conda activate my-agent
pip install -e .
myagent
```

服务默认监听 `http://127.0.0.1:8000`。

## 示例接口

```bash
curl http://127.0.0.1:8000/api/v1/hello
```

```json
{"message": "Hello from MyAgent"}
```

交互文档：<http://127.0.0.1:8000/docs>
