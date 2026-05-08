"""
Gradio 交互界面
提供日志上传/粘贴、一键分析、报告展示功能
"""
import gradio as gr
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from graph import run_analysis

# 加载示例日志
SAMPLE_LOG_PATH = os.path.join(os.path.dirname(__file__), "data", "sample_logs", "microservice_logs.txt")

def load_sample_logs():
    try:
        with open(SAMPLE_LOG_PATH, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception:
        return ""


def analyze(log_text: str, api_key: str):
    """分析入口函数"""
    if not log_text.strip():
        return "❌ 请输入或上传日志内容", "", ""

    if not api_key.strip():
        api_key = "你的deepseek api key"

    # 注入 API Key
    os.environ["DEEPSEEK_API_KEY"] = api_key.strip()

    # 动态更新 config
    import config
    config.DEEPSEEK_API_KEY = api_key.strip()

    try:
        result = run_analysis(log_text)

        # 异常摘要
        anomalies = result.get("anomalies", [])
        if anomalies:
            anomaly_summary = "\n".join([
                f"[{a['severity']}] {a['window_start']} ~ {a['window_end']} | "
                f"错误率 {a['error_rate']:.0%} | "
                f"影响服务: {', '.join(s['service'] for s in a['affected_services'])}"
                for a in anomalies
            ])
        else:
            anomaly_summary = "✅ 未检测到异常"

        # RCA 结论
        rca = result.get("rca_result", {})
        if rca and "error" not in rca:
            rca_summary = (
                f"根因服务: {rca.get('root_cause_service', 'N/A')}\n"
                f"置信度: {rca.get('confidence', 'N/A')}\n"
                f"描述: {rca.get('root_cause_description', 'N/A')}\n\n"
                f"传播路径: {rca.get('propagation_path', 'N/A')}"
            )
        else:
            rca_summary = rca.get("error", "分析未完成")

        report = result.get("final_report", "报告生成失败")
        return anomaly_summary, rca_summary, report

    except Exception as e:
        import traceback
        err = traceback.format_exc()
        return f"❌ 分析出错: {e}", "", err


def upload_file(file):
    """处理文件上传"""
    if file is None:
        return ""
    try:
        with open(file.name, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"文件读取失败: {e}"


# ========== Gradio UI ==========
with gr.Blocks(
    title="LogRCA Agent — 微服务日志根因分析",
    theme=gr.themes.Soft(primary_hue="blue"),
    css="""
    .header { text-align: center; padding: 20px 0; }
    .header h1 { font-size: 2em; margin-bottom: 5px; }
    .result-box { font-family: 'Courier New', monospace; font-size: 13px; }
    """
) as demo:

    gr.HTML("""
    <div class="header">
        <h1>🔍 LogRCA Agent</h1>
        <p>微服务日志智能根因定位系统 | 基于 LangGraph + DeepSeek</p>
    </div>
    """)

    with gr.Row():
        # 左侧输入区
        with gr.Column(scale=1):
            gr.Markdown("### ⚙️ 配置")
            api_key_input = gr.Textbox(
                label="DeepSeek API Key",
                placeholder="sk-xxxxxxxxxxxx",
                type="password",
                info="从 platform.deepseek.com 获取"
            )

            gr.Markdown("### 📄 日志输入")
            log_input = gr.Textbox(
                label="原始日志（粘贴或上传）",
                placeholder="2024-01-15 10:00:01 INFO [order-service] ...",
                lines=15,
                max_lines=30,
            )

            with gr.Row():
                upload_btn = gr.UploadButton("📂 上传日志文件", file_types=[".txt", ".log"])
                sample_btn = gr.Button("📋 加载示例日志", variant="secondary")

            analyze_btn = gr.Button("🚀 开始分析", variant="primary", size="lg")

        # 右侧输出区
        with gr.Column(scale=1):
            gr.Markdown("### ⚠️ 异常检测结果")
            anomaly_output = gr.Textbox(
                label="",
                lines=5,
                interactive=False,
                elem_classes=["result-box"]
            )

            gr.Markdown("### 🎯 根因分析结论")
            rca_output = gr.Textbox(
                label="",
                lines=6,
                interactive=False,
                elem_classes=["result-box"]
            )

    gr.Markdown("### 📊 完整分析报告")
    report_output = gr.Markdown(label="", value="*分析结果将在此显示...*")

    # 事件绑定
    upload_btn.upload(upload_file, inputs=[upload_btn], outputs=[log_input])
    sample_btn.click(load_sample_logs, outputs=[log_input])
    analyze_btn.click(
        analyze,
        inputs=[log_input, api_key_input],
        outputs=[anomaly_output, rca_output, report_output]
    )

    gr.Markdown("""
    ---
    **使用说明**: 粘贴日志 → 输入 API Key → 点击分析 | 支持标准格式: `时间 级别 [服务名] 消息`
    """)


if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        inbrowser=True,
    )
