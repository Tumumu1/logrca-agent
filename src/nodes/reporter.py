"""
Node 4: Report Generator
将 RCA 结果格式化为结构化的诊断报告（Markdown + JSON）
"""
from datetime import datetime
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.nodes.parser import AgentState


def generate_report(state: AgentState) -> AgentState:
    """
    生成最终的根因分析报告
    """
    anomalies = state["anomalies"]
    rca = state["rca_result"]
    parsed_logs = state["parsed_logs"]

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total_logs = len(parsed_logs)
    error_logs = len([l for l in parsed_logs if l["level"] in ("ERROR", "CRITICAL")])

    # ---- 组装 Markdown 报告 ----
    lines = []
    lines.append("# 🔍 微服务日志根因分析报告")
    lines.append(f"\n**分析时间**: {now}")
    lines.append(f"**日志总量**: {total_logs} 条 | **错误日志**: {error_logs} 条\n")

    # 执行摘要
    lines.append("---")
    lines.append("## 📋 执行摘要")
    if "error" not in rca:
        confidence_emoji = {"HIGH": "🟢", "MEDIUM": "🟡", "LOW": "🔴"}.get(rca.get("confidence", "LOW"), "⚪")
        lines.append(f"\n| 项目 | 结论 |")
        lines.append(f"|------|------|")
        lines.append(f"| 根因服务 | **{rca.get('root_cause_service', 'N/A')}** |")
        lines.append(f"| 置信度 | {confidence_emoji} {rca.get('confidence', 'N/A')} |")
        lines.append(f"| 故障传播路径 | {rca.get('propagation_path', 'N/A')} |")
    else:
        lines.append(f"\n✅ {rca['error']}")

    # 异常检测结果
    lines.append("\n---")
    lines.append("## ⚠️ 异常检测结果")
    if anomalies:
        for i, a in enumerate(anomalies, 1):
            severity_emoji = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡"}.get(a["severity"], "⚪")
            lines.append(f"\n### 异常 #{i} {severity_emoji} {a['severity']}")
            lines.append(f"- **时间段**: {a['window_start']} ~ {a['window_end']}")
            lines.append(f"- **错误率**: {a['error_rate']:.0%} ({a['total_errors']}/{a['total_logs']} 条)")
            lines.append(f"\n**受影响服务**:")
            for svc in a["affected_services"]:
                lines.append(f"  - `{svc['service']}`: {svc['error_count']} 个错误 (错误率 {svc['error_rate']:.0%})")
    else:
        lines.append("\n✅ 未检测到显著异常")

    # 根因分析
    if "error" not in rca:
        lines.append("\n---")
        lines.append("## 🎯 根因分析")
        lines.append(f"\n**根因服务**: `{rca.get('root_cause_service', 'N/A')}`")
        lines.append(f"\n**根因描述**:\n> {rca.get('root_cause_description', 'N/A')}")

        evidence = rca.get("evidence", [])
        if evidence:
            lines.append(f"\n**关键证据**:")
            for ev in evidence:
                lines.append(f"  - {ev}")

        # 修复建议
        fixes = rca.get("fix_suggestions", [])
        if fixes:
            lines.append("\n---")
            lines.append("## 🛠️ 修复建议")
            for i, fix in enumerate(fixes, 1):
                lines.append(f"{i}. {fix}")

    lines.append("\n---")
    lines.append(f"*报告由 LogRCA Agent 自动生成 | {now}*")

    report = '\n'.join(lines)
    print(f"[Reporter] 报告生成完成（{len(report)} 字符）")

    return {**state, "final_report": report}
