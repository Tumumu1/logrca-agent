"""
ReAct Agent 工具集
LLM 可调用这些工具来主动查询日志、分析调用链、检索知识库
"""
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from langchain.tools import tool
from config import SERVICE_CALL_GRAPH, KNOWLEDGE_BASE_PATH

# ========== 全局日志存储（由 reasoner 注入）==========
_parsed_logs = []
_kb_entries = []


def init_tools(parsed_logs: list, kb_entries: list):
    """初始化工具的数据源"""
    global _parsed_logs, _kb_entries
    _parsed_logs = parsed_logs
    _kb_entries = kb_entries


@tool
def search_logs(query: str) -> str:
    """
    搜索日志记录。
    输入格式: "service=<服务名> level=<日志级别> keyword=<关键词>"
    例如: "service=database-service level=ERROR keyword=connection"
    任意参数可省略。
    """
    params = {}
    for part in query.split():
        if '=' in part:
            k, v = part.split('=', 1)
            params[k.strip()] = v.strip()

    results = _parsed_logs
    if 'service' in params:
        results = [l for l in results if params['service'].lower() in l['service'].lower()]
    if 'level' in params:
        results = [l for l in results if l['level'] == params['level'].upper()]
    if 'keyword' in params:
        kw = params['keyword'].lower()
        results = [l for l in results if kw in l['message'].lower()]

    if not results:
        return "未找到匹配的日志记录"

    # 返回最多15条
    output = []
    for l in results[:15]:
        output.append(f"[{l['timestamp_str']}] [{l['level']}] [{l['service']}] {l['message']}")
    if len(results) > 15:
        output.append(f"... 共 {len(results)} 条，只显示前15条")
    return '\n'.join(output)


@tool
def get_service_call_graph(service_name: str) -> str:
    """
    获取指定服务的上下游调用关系。
    输入: 服务名称，如 "payment-service"
    返回: 该服务依赖哪些服务（下游），以及哪些服务依赖它（上游）
    """
    service_name = service_name.strip()

    # 查找下游依赖
    downstream = SERVICE_CALL_GRAPH.get(service_name, None)
    if downstream is None:
        # 尝试模糊匹配
        for svc in SERVICE_CALL_GRAPH:
            if service_name.lower() in svc.lower():
                downstream = SERVICE_CALL_GRAPH[svc]
                service_name = svc
                break

    if downstream is None:
        return f"未找到服务 '{service_name}'，已知服务: {list(SERVICE_CALL_GRAPH.keys())}"

    # 查找上游（谁调用了这个服务）
    upstream = [svc for svc, deps in SERVICE_CALL_GRAPH.items() if service_name in deps]

    result = [f"服务: {service_name}"]
    result.append(f"  ↓ 依赖的下游服务: {downstream if downstream else '无（叶子节点）'}")
    result.append(f"  ↑ 被以下上游服务调用: {upstream if upstream else '无（根节点）'}")

    if not downstream:
        result.append("  ⚠️ 该服务是叶子节点（基础服务），若它故障将影响所有上游服务")

    return '\n'.join(result)


@tool
def analyze_error_timeline(service_name: str) -> str:
    """
    分析指定服务的错误时间线，展示错误如何随时间演变。
    输入: 服务名称，如 "database-service"
    """
    service_logs = [l for l in _parsed_logs
                    if service_name.lower() in l['service'].lower()
                    and l['timestamp'] is not None]

    if not service_logs:
        return f"未找到服务 '{service_name}' 的日志"

    service_logs.sort(key=lambda x: x['timestamp'])

    timeline = []
    for log in service_logs:
        if log['level'] in ('ERROR', 'CRITICAL', 'WARN'):
            timeline.append(f"[{log['timestamp_str']}] [{log['level']}] {log['message']}")

    if not timeline:
        return f"服务 '{service_name}' 在此时间段内无异常日志"

    return f"服务 '{service_name}' 异常时间线（共{len(timeline)}条）:\n" + '\n'.join(timeline[:20])


@tool
def compare_error_patterns(service_name: str) -> str:
    """
    对比指定服务在异常前后的日志模板频率变化，识别突增的错误模式。
    输入: 服务名称，如 "payment-service"
    """
    service_logs = [l for l in _parsed_logs
                    if service_name.lower() in l['service'].lower()
                    and l['timestamp'] is not None]

    if not service_logs:
        return f"未找到服务 '{service_name}' 的日志"

    service_logs.sort(key=lambda x: x['timestamp'])

    # 以中间时间点为界
    mid = len(service_logs) // 2
    before = service_logs[:mid]
    after = service_logs[mid:]

    def count_templates(logs):
        counts = {}
        for l in logs:
            t = l['template']
            counts[t] = counts.get(t, 0) + 1
        return counts

    before_counts = count_templates(before)
    after_counts = count_templates(after)

    # 找出新增或激增的模板
    changes = []
    all_templates = set(list(before_counts.keys()) + list(after_counts.keys()))
    for tmpl in all_templates:
        b = before_counts.get(tmpl, 0)
        a = after_counts.get(tmpl, 0)
        if a > b and (b == 0 or a / b > 2):
            changes.append((tmpl, b, a))

    if not changes:
        return f"服务 '{service_name}' 前后日志模式无显著变化"

    changes.sort(key=lambda x: x[2] - x[1], reverse=True)
    result = [f"服务 '{service_name}' 异常后新增/激增的日志模式:"]
    for tmpl, before_cnt, after_cnt in changes[:8]:
        result.append(f"  [{'+' if before_cnt == 0 else '↑'}] 前:{before_cnt}次 → 后:{after_cnt}次 | {tmpl[:100]}")
    return '\n'.join(result)


@tool
def lookup_knowledge_base(keywords: str) -> str:
    """
    检索历史故障知识库，查找相似的根因案例。
    输入: 关键词，如 "connection pool exhausted database timeout"
    """
    if not _kb_entries:
        return "知识库为空"

    kw_list = keywords.lower().split()
    scored = []
    for entry in _kb_entries:
        score = 0
        text = (entry.get('title', '') + ' ' +
                ' '.join(entry.get('symptoms', [])) + ' ' +
                entry.get('root_cause', '') + ' ' +
                ' '.join(entry.get('tags', []))).lower()
        for kw in kw_list:
            if kw in text:
                score += 1
        if score > 0:
            scored.append((score, entry))

    if not scored:
        return "未找到相似的历史故障案例"

    scored.sort(key=lambda x: x[0], reverse=True)
    results = []
    for score, entry in scored[:2]:
        results.append(
            f"【{entry['id']}】{entry['title']} (匹配度:{score})\n"
            f"  根因: {entry['root_cause']}\n"
            f"  修复方案: {entry['fix']}"
        )
    return '\n\n'.join(results)


# 工具列表（供 LangGraph 注册）
ALL_TOOLS = [search_logs, get_service_call_graph, analyze_error_timeline,
             compare_error_patterns, lookup_knowledge_base]
