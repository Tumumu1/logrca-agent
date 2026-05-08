"""
LangGraph 主图
将 4 个节点串联成完整的分析流水线
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from langgraph.graph import StateGraph, END
from src.nodes.parser import AgentState, parse_logs
from src.nodes.detector import detect_anomalies
from src.nodes.reasoner import run_rca
from src.nodes.reporter import generate_report


def build_graph() -> StateGraph:
    """构建并编译 LangGraph 分析流水线"""

    # 创建状态图
    graph = StateGraph(AgentState)

    # 注册节点
    graph.add_node("parse_logs", parse_logs)
    graph.add_node("detect_anomalies", detect_anomalies)
    graph.add_node("run_rca", run_rca)
    graph.add_node("generate_report", generate_report)

    # 连接边（线性流水线）
    graph.set_entry_point("parse_logs")
    graph.add_edge("parse_logs", "detect_anomalies")
    graph.add_edge("detect_anomalies", "run_rca")
    graph.add_edge("run_rca", "generate_report")
    graph.add_edge("generate_report", END)

    return graph.compile()


def run_analysis(log_text: str) -> dict:
    """
    运行完整分析流水线
    :param log_text: 原始日志文本
    :return: 最终状态（包含报告）
    """
    app = build_graph()

    initial_state: AgentState = {
        "raw_logs": log_text,
        "parsed_logs": [],
        "anomalies": [],
        "rca_result": {},
        "final_report": "",
    }

    print("=" * 50)
    print("🚀 LogRCA Agent 启动")
    print("=" * 50)

    final_state = app.invoke(initial_state)

    print("=" * 50)
    print("✅ 分析完成")
    print("=" * 50)

    return final_state


if __name__ == "__main__":
    # 命令行测试
    sample_log_path = os.path.join(os.path.dirname(__file__), "data", "sample_logs", "microservice_logs.txt")
    with open(sample_log_path, 'r', encoding='utf-8') as f:
        logs = f.read()

    result = run_analysis(logs)
    print("\n" + result["final_report"])
