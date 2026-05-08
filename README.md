# LogRCA Agent 🔍

> 面向微服务的日志智能根因定位系统  
> 基于 LangGraph + DeepSeek + ReAct 构建

## 项目架构

```
用户输入日志
    ↓
[Node 1] Log Parser        解析日志 → 结构化数据
    ↓
[Node 2] Anomaly Detector  统计分析 → 定位异常时间窗口 & 受影响服务
    ↓
[Node 3] RCA Reasoner      ReAct 推理 → LLM 主动调用工具分析根因
    ↓
[Node 4] Report Generator  生成结构化诊断报告
    ↓
Gradio 界面展示
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 API Key

方式一：在 Gradio 界面直接输入（推荐）

方式二：设置环境变量
```bash
# Windows
set DEEPSEEK_API_KEY=sk-your-key-here

# Mac/Linux
export DEEPSEEK_API_KEY=sk-your-key-here
```

获取 DeepSeek API Key：https://platform.deepseek.com

### 3. 启动界面

```bash
python app.py
```

浏览器打开 http://localhost:7860

### 4. 命令行运行（无界面）

```bash
python graph.py
```

## 日志格式

支持标准格式：
```
2024-01-15 10:00:01 INFO  [service-name] log message here
2024-01-15 10:00:02 ERROR [service-name] something went wrong reason=xxx
```

## ReAct 工具说明

| 工具 | 功能 |
|------|------|
| `search_logs` | 按服务/级别/关键词搜索日志 |
| `get_service_call_graph` | 查询服务上下游调用关系 |
| `analyze_error_timeline` | 展示服务错误时间线 |
| `compare_error_patterns` | 对比异常前后日志模式变化 |
| `lookup_knowledge_base` | 检索历史故障知识库 |

## 项目结构

```
logrca-agent/
├── app.py                    # Gradio 启动入口
├── graph.py                  # LangGraph 主图
├── config.py                 # 配置文件
├── requirements.txt
├── data/
│   ├── sample_logs/          # 示例日志
│   └── knowledge_base.json   # 历史故障知识库
└── src/
    ├── nodes/
    │   ├── parser.py         # Node1: 日志解析
    │   ├── detector.py       # Node2: 异常检测
    │   ├── reasoner.py       # Node3: RCA 推理
    │   └── reporter.py       # Node4: 报告生成
    └── tools/
        └── rca_tools.py      # ReAct 工具集
```
