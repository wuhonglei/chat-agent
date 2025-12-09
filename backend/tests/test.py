from loguru import logger

# ✅ 推荐：记录元数据和摘要
logger.info(
    f"Chat request received: "
    f"conversation_id={1}, "
    f"client_ip={2}, "
    f"message_length={3}"  # 只记录长度，不记录内容
)
