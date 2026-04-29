import logging

# 日志设置  level=logging.DEBUG -> 日志级别为 DEBUG
logging.basicConfig(level=logging.INFO, format="[bot] %(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)
