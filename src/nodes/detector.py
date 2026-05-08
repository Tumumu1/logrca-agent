"""
Node 2: Anomaly Detector
基于统计方法检测异常：错误率突增、日志量异常、受影响服务定位
"""
from collections import defaultdict
from datetime import timedelta
from typing import Dict, List, Any
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.nodes.parser import AgentState
from config import ANOMALY_WINDOW_MINUTES, ERROR_RATE_THRESHOLD


def detect_anomalies(state: AgentState) -> AgentState:
    """
    分析结构化日志，检测异常时间窗口和受影响服务
    """
    parsed_logs = state["parsed_logs"]
    valid_logs = [l for l in parsed_logs if l["timestamp"] is not None]

    if not valid_logs:
        return {**state, "anomalies": []}

    # ---- 1. 按时间窗口统计各服务日志量和错误数 ----
    start_time = min(l["timestamp"] for l in valid_logs)
    end_time = max(l["timestamp"] for l in valid_logs)
    window = timedelta(minutes=ANOMALY_WINDOW_MINUTES)

    # 滑动窗口统计
    windows = []
    current = start_time
    while current <= end_time:
        window_end = current + window
        window_logs = [l for l in valid_logs if current <= l["timestamp"] < window_end]

        if window_logs:
            service_stats = defaultdict(lambda: {"total": 0, "error": 0, "warn": 0, "levels": []})
            for log in window_logs:
                svc = log["service"]
                service_stats[svc]["total"] += 1
                service_stats[svc]["levels"].append(log["level"])
                if log["level"] in ("ERROR", "CRITICAL"):
                    service_stats[svc]["error"] += 1
                elif log["level"] == "WARN":
                    service_stats[svc]["warn"] += 1

            windows.append({
                "start": current,
                "end": window_end,
                "logs": window_logs,
                "service_stats": dict(service_stats),
                "total_errors": sum(s["error"] for s in service_stats.values()),
                "total_logs": len(window_logs),
            })
        current += window

    # ---- 2. 找出高错误率时间窗口 ----
    anomalies = []
    for w in windows:
        if w["total_logs"] == 0:
            continue
        error_rate = w["total_errors"] / w["total_logs"]

        if error_rate >= ERROR_RATE_THRESHOLD or w["total_errors"] >= 3:
            # 找出出错的服务
            affected_services = []
            for svc, stats in w["service_stats"].items():
                if stats["error"] > 0:
                    svc_error_rate = stats["error"] / stats["total"]
                    affected_services.append({
                        "service": svc,
                        "error_count": stats["error"],
                        "total_count": stats["total"],
                        "error_rate": round(svc_error_rate, 2),
                    })

            # 按错误数排序
            affected_services.sort(key=lambda x: x["error_count"], reverse=True)

            # 收集异常日志模板
            error_logs = [l for l in w["logs"] if l["level"] in ("ERROR", "CRITICAL", "WARN")]
            error_templates = list(set(l["template"] for l in error_logs))[:10]

            anomalies.append({
                "window_start": w["start"].strftime("%Y-%m-%d %H:%M:%S"),
                "window_end": w["end"].strftime("%Y-%m-%d %H:%M:%S"),
                "error_rate": round(error_rate, 2),
                "total_errors": w["total_errors"],
                "total_logs": w["total_logs"],
                "affected_services": affected_services,
                "error_templates": error_templates,
                "severity": "CRITICAL" if error_rate > 0.5 else "HIGH" if error_rate > 0.3 else "MEDIUM",
            })

    print(f"[Detector] 检测完成：发现 {len(anomalies)} 个异常时间窗口")
    for a in anomalies:
        print(f"  [{a['severity']}] {a['window_start']} ~ {a['window_end']} "
              f"错误率={a['error_rate']:.0%} "
              f"影响服务={[s['service'] for s in a['affected_services']]}")

    return {**state, "anomalies": anomalies}
