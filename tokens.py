"""CAS 认证 token 持久化模块"""
import json
import logging
from os import makedirs, path
from typing import Dict, Optional

from config import TOKEN_FILE
from storage import get_cst_time

logger = logging.getLogger(__name__)


def save(user_token: str, refresh_token: str, device_id: Optional[str] = None) -> None:
    """保存 token 到文件。"""
    try:
        token_data = {
            "user_token": user_token,
            "refresh_token": refresh_token,
            "saved_at": get_cst_time(),
        }
        if device_id:
            token_data["device_id"] = device_id

        dir_path = path.dirname(TOKEN_FILE)
        if dir_path and not path.exists(dir_path):
            makedirs(dir_path, exist_ok=True)

        with open(TOKEN_FILE, "w", encoding="utf-8") as f:
            json.dump(token_data, f, ensure_ascii=False, indent=2)

        logger.info(f"Token 已保存: {TOKEN_FILE}")
    except Exception as e:
        logger.error(f"保存 Token 失败: {e}")
        raise


def load() -> Optional[Dict[str, str]]:
    """从文件加载 token。"""
    try:
        if not path.exists(TOKEN_FILE):
            logger.info("Token 文件不存在，将使用账号密码登录")
            return None

        with open(TOKEN_FILE, "r", encoding="utf-8") as f:
            token_data = json.load(f)

        logger.info(f"Token 加载成功，保存时间: {token_data.get('saved_at', '未知')}")
        return token_data

    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.warning(f"读取 Token 文件失败: {e}")
        return None
