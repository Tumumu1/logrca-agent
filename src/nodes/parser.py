"""
Node 1: Log Parser
将原始日志文本解析为结构化数据，提取时间戳、服务名、日志级别、消息模板
"""
import re
from datetime import datetime
from typing import TypedDict, List, Dict, Any


# ========== 状态定义（整个 Agent 的共享状态）==========
class AgentState(TypedDict):
    raw_logs: str                          # 原始日志文本
    parsed_logs: List[Dict[str, Any]]      # 解析后的结构化日志
    anomalies: List[Dict[str, Any]]        # 检测到的异常
    rca_result: Dict[str, Any]             # 根因分析结果
    final_report: str                      # 最终报告


# ========== 日志解析正则 ==========
LOG_PATTERN = re.compile(
    r'(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+'
    r'(?P<level>INFO|WARN|ERROR|CRITICAL|DEBUG)\s+'
    r'\[(?P<service>[^\]]+)\]\s+'
    r'(?P<message>.+)'
)

# 变量替换模式（将具体值替换为占位符，提取模板）
VARIABLE_PATTERNS = [
    (re.compile(r'\b\d+\.\d+\.\d+\.\d+\b'), '<IP>'),           # IP地址
    (re.compile(r'\borderId=\S+'), 'orderId=<ID>'),             # orderId
    (re.compile(r'\buserId=\S+'), 'userId=<ID>'),               # userId
    (re.compile(r'\bproductId=\S+'), 'productId=<ID>'),         # productId
    (re.compile(r'\bamount=[\d.]+'), 'amount=<NUM>'),           # 金额
    (re.compile(r'\blatency=\d+ms'), 'latency=<NUM>ms'),       # 延迟
    (re.compile(r'\bactiveConn=\d+'), 'activeConn=<NUM>'),     # 连接数
    (re.compile(r'\bwaitingRequests=\d+'), 'waitingRequests=<NUM>'),
    (re.compile(r'\bretryCount=\d+'), 'retryCount=<NUM>'),
    (re.compile(r'\b\d{5,}\b'), '<NUM>'),                       # 长数字
]


def extract_template(message: str) -> str:
    """从日志消息中提取模板（去除变量值）"""
    template = message
    for pattern, placeholder in VARIABLE_PATTERNS:
        template = pattern.sub(placeholder, template)
    return template.strip()


def parse_logs(state: AgentState) -> AgentState:
    """
    解析原始日志文本，返回结构化日志列表
    """
    raw_logs = state["raw_logs"]
    parsed = []

    for line in raw_logs.strip().split('\n'):
        line = line.strip()
        if not line:
            continue

        match = LOG_PATTERN.match(line)
        if match:
            data = match.groupdict()
            parsed.append({
                "timestamp": datetime.strptime(data["timestamp"], "%Y-%m-%d %H:%M:%S"),
                "timestamp_str": data["timestamp"],
                "level": data["level"],
                "service": data["service"],
                "message": data["message"],
                "template": extract_template(data["message"]),
                "raw": line,
            })
        else:
            # 无法解析的行，保留原始内容
            parsed.append({
                "timestamp": None,
                "timestamp_str": "",
                "level": "UNKNOWN",
                "service": "unknown",
                "message": line,
                "template": line,
                "raw": line,
            })

    print(f"[Parser] 解析完成：共 {len(parsed)} 条日志")
    return {**state, "parsed_logs": parsed}
