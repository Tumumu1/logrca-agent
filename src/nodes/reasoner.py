"""
Node 3: RCA Reasoner
使用 ReAct 模式，让 LLM 通过调用工具主动分析日志，定位根因
"""
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from src.nodes.parser import AgentState
from langchain_core.messages import HumanMessage
from src.tools.rca_tools import ALL_TOOLS, init_tools
from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL, KNOWLEDGE_BASE_PATH, MAX_REACT_ITERATIONS


def load_knowledge_base():
    try:
        with open(KNOWLEDGE_BASE_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []


# ReAct Prompt 模板
RCA_PROMPT_TEMPLATE = """你是一个专业的微服务系统故障根因分析专家。

你有以下工具可以调用：
{tools}

工具名称列表：{tool_names}

分析任务：
{input}

分析要求：
1. 首先查看异常时间段内各服务的错误日志
2. 分析服务调用链，判断故障传播路径
3. 对比异常前后的日志模式变化
4. 检索知识库寻找相似历史故障
5. 综合以上信息，得出根因结论

请按照以下格式进行推理：

Thought: 我需要分析什么
Action: 工具名称
Action Input: 工具输入参数
Observation: 工具返回结果
... (可以重复多次 Thought/Action/Observation)
Thought: 我现在知道最终答案了
Final Answer: 
{{
  "root_cause_service": "根因服务名",
  "root_cause_description": "根因描述",
  "evidence": ["证据1", "证据2", "证据3"],
  "propagation_path": "故障传播路径描述",
  "confidence": "HIGH/MEDIUM/LOW",
  "fix_suggestions": ["修复建议1", "修复建议2"]
}}

{agent_scratchpad}"""


def run_rca(state: AgentState) -> AgentState:
    """
    对检测到的异常执行根因分析
    """
    parsed_logs = state["parsed_logs"]
    anomalies = state["anomalies"]

    if not anomalies:
        return {**state, "rca_result": {"error": "未检测到异常，无需根因分析"}}

    # 初始化工具数据源
    kb_entries = load_knowledge_base()
    init_tools(parsed_logs, kb_entries)

    # 初始化 DeepSeek LLM
    # llm = ChatOpenAI(
    #     api_key=DEEPSEEK_API_KEY,
    #     base_url=DEEPSEEK_BASE_URL,
    #     model=DEEPSEEK_MODEL,
    #     temperature=0.1,
    # )
    llm = ChatOpenAI(
        api_key="sk-a520795f6ff341f39fb59995de0b0254",
        base_url="https://api.deepseek.com",
        model="deepseek-chat",
        temperature=0.1,
    )
    # 绑定工具
    llm_with_tools = llm.bind_tools(ALL_TOOLS)

    # 构建任务描述
    main_anomaly = anomalies[0]
    affected = main_anomaly["affected_services"]
    error_templates = main_anomaly["error_templates"]

    task_description = f"""
检测到以下异常情况，请进行根因分析：

异常时间段: {main_anomaly['window_start']} ~ {main_anomaly['window_end']}
严重程度: {main_anomaly['severity']}
错误率: {main_anomaly['error_rate']:.0%}（共{main_anomaly['total_logs']}条日志中有{main_anomaly['total_errors']}条错误）

受影响的服务（按错误数排序）:
{chr(10).join(f"  - {s['service']}: {s['error_count']}个错误，错误率{s['error_rate']:.0%}" for s in affected)}

观察到的错误日志模板（样本）:
{chr(10).join(f"  • {t}" for t in error_templates[:5])}

请调用工具进行深入分析，找出根因。
"""

    print(f"[RCA Reasoner] 开始根因分析...")
    print(f"  分析目标: {[s['service'] for s in affected]}")

    # 使用简化的 ReAct 循环（手动实现，避免 hub 依赖问题）
    rca_result = _run_react_loop(llm, task_description, parsed_logs, kb_entries)

    return {**state, "rca_result": rca_result}


def _run_react_loop(llm, task: str, parsed_logs: list, kb_entries: list) -> dict:
    """
    手动实现 ReAct 循环，避免外部 hub 依赖
    """
    from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

    # 工具名到函数的映射
    tool_map = {t.name: t for t in ALL_TOOLS}

    system_prompt = """你是一个微服务系统故障根因分析专家。请通过调用工具分析日志，定位根因。

分析策略：
1. 先用 analyze_error_timeline 查看出错服务的时间线
2. 用 get_service_call_graph 分析调用链
3. 用 compare_error_patterns 对比异常前后变化
4. 用 lookup_knowledge_base 检索相似故障
5. 综合分析，输出结论

最终答案必须是如下 JSON 格式（用 ```json ``` 包裹）：
```json
{
  "root_cause_service": "根因服务名",
  "root_cause_description": "根因的详细描述",
  "evidence": ["关键证据1", "关键证据2", "关键证据3"],
  "propagation_path": "故障传播路径，如 A→B→C",
  "confidence": "HIGH",
  "fix_suggestions": ["立即修复建议", "长期优化建议"]
}
```"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": task}
    ]

    llm_with_tools = llm.bind_tools(ALL_TOOLS)

    for iteration in range(MAX_REACT_ITERATIONS):
        print(f"  [ReAct 第{iteration+1}轮]", end=" ")
        response = llm_with_tools.invoke(messages)

        # 检查是否有工具调用
        if hasattr(response, 'tool_calls') and response.tool_calls:
            tool_calls = response.tool_calls
            print(f"调用工具: {[tc['name'] for tc in tool_calls]}")

            # 添加 AI 消息
            messages.append({"role": "assistant", "content": response.content or "",
                              "tool_calls": [{"id": tc["id"], "type": "function",
                                              "function": {"name": tc["name"],
                                                           "arguments": json.dumps(tc["args"])}}
                                             for tc in tool_calls]})

            # 执行每个工具
            for tc in tool_calls:
                tool_name = tc["name"]
                tool_args = tc["args"]
                tool_id = tc["id"]

                if tool_name in tool_map:
                    try:
                        # 提取第一个参数值
                        arg_val = list(tool_args.values())[0] if tool_args else ""
                        result = tool_map[tool_name].invoke(arg_val)
                    except Exception as e:
                        result = f"工具调用出错: {e}"
                else:
                    result = f"未知工具: {tool_name}"

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_id,
                    "content": str(result)
                })
        else:
            # 没有工具调用，LLM 给出了最终答案
            print("生成最终答案")
            content = response.content or ""

            # 解析 JSON 结果
            import re
            json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    pass

            # fallback：返回原始文本
            return {
                "root_cause_service": "未能确定",
                "root_cause_description": content,
                "evidence": [],
                "propagation_path": "分析未完成",
                "confidence": "LOW",
                "fix_suggestions": []
            }

    return {
        "root_cause_service": "分析超时",
        "root_cause_description": "超过最大迭代次数，请检查日志后手动分析",
        "evidence": [],
        "propagation_path": "",
        "confidence": "LOW",
        "fix_suggestions": []
    }
