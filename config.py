import os

# ========== LLM 配置 ==========
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "your-deepseek-api-key-here")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"

# ========== 路径配置 ==========
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
SAMPLE_LOGS_DIR = os.path.join(DATA_DIR, "sample_logs")
KNOWLEDGE_BASE_PATH = os.path.join(DATA_DIR, "knowledge_base.json")
CHROMA_DB_PATH = os.path.join(DATA_DIR, "chroma_db")

# ========== Agent 配置 ==========
MAX_REACT_ITERATIONS = 16       # ReAct 最大迭代次数
ANOMALY_WINDOW_MINUTES = 5     # 异常检测时间窗口（分钟）
ERROR_RATE_THRESHOLD = 0.3     # 错误率告警阈值（30%）

# ========== 服务调用图（模拟微服务依赖关系）==========
SERVICE_CALL_GRAPH = {
    "api-gateway": ["order-service", "payment-service", "user-service", "inventory-service"],
    "order-service": ["payment-service", "inventory-service", "database-service", "notification-service"],
    "payment-service": ["database-service"],
    "inventory-service": ["database-service"],
    "user-service": ["database-service"],
    "notification-service": ["database-service"],
    "database-service": [],
}
