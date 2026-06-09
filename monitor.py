"""电量监控模块，负责 CAS 登录、MFA 检测和电量查询。"""
from typing import Dict, Optional
import logging

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    wait_chain,
    wait_fixed,
    retry_if_exception,
)
from zzupy.app import CASClient, ECardClient

from config import (
    ACCOUNT, PASSWORD, LIGHT_ROOM, AC_ROOM,
    ZZU_DEVICE_ID,
    RETRY_ATTEMPTS, RETRY_MULTIPLIER, INITIAL_WAIT, MAX_WAIT,
)
import tokens

logger = logging.getLogger(__name__)


class MFARequiredError(RuntimeError):
    """当前设备需要短信 MFA，自动任务不应重试。"""


def should_retry_exception(exception: BaseException) -> bool:
    """MFA 等待人工处理，重试不会改变结果。"""
    return not isinstance(exception, MFARequiredError)


def create_retry_decorator(stop_attempts: int = RETRY_ATTEMPTS, wait_strategy=None):
    """创建统一的重试装饰器。

    参数：
        stop_attempts: 最大重试次数。
        wait_strategy: 等待策略。

    返回：
        重试装饰器。
    """
    if wait_strategy is None:
        wait_strategy = wait_exponential(
            multiplier=RETRY_MULTIPLIER,
            min=INITIAL_WAIT,
            max=MAX_WAIT
        )

    return retry(
        stop=stop_after_attempt(stop_attempts),
        wait=wait_strategy,
        retry=retry_if_exception(should_retry_exception),
        reraise=True
    )


# 请求重试装饰器（带链式等待）
request_retry = create_retry_decorator(
    wait_strategy=wait_chain(
        wait_fixed(15),
        wait_fixed(30),
        wait_exponential(multiplier=1, min=45, max=120)
    )
)


class TokenManager:
    """Token 管理器，保留原有调用结构。"""

    @staticmethod
    def save(user_token: str, refresh_token: str, device_id: Optional[str] = None) -> None:
        """保存 token 到文件。"""
        tokens.save(user_token, refresh_token, device_id)

    @staticmethod
    def load() -> Optional[Dict[str, str]]:
        """从文件加载 token。"""
        return tokens.load()


class EnergyMonitor:
    """电量监控器。"""

    def __init__(self):
        self.cas_client = CASClient(ACCOUNT, PASSWORD)
        self.device_id = ZZU_DEVICE_ID
        self.get_balance = create_retry_decorator()(self._get_balance)

    def _apply_device(self, token_data: Optional[Dict[str, str]] = None) -> None:
        """设置统一认证设备 ID，优先使用环境变量，其次复用已保存的 device_id。"""
        device_id = self.device_id or (token_data or {}).get("device_id")
        if device_id:
            self.cas_client.set_device(device_id)
            logger.info("已设置统一认证设备 ID")
        else:
            logger.info("未设置 ZZU_DEVICE_ID，将使用 ZZU.Py 默认设备 ID")

    def _ensure_mfa_ready(self) -> None:
        """确认当前设备可直接登录；需要短信 MFA 时停止自动流程。"""
        try:
            if self.cas_client.mfa.is_required():
                raise MFARequiredError(
                    "当前统一认证设备需要短信 MFA，无法在 GitHub Actions 中自动完成。"
                    "请先在本地运行 mfa.py 完成一次 MFA，并将设备加入可信设备；"
                    "也可以配置已可信设备的 ZZU_DEVICE_ID。"
                )
        except Exception as e:
            if isinstance(e, MFARequiredError):
                raise
            logger.error(f"MFA 状态检测失败: {e}")
            raise

    def _login_with_saved_token(self, token_data: Dict[str, str]) -> bool:
        """优先复用已保存的 token；只有回退账密时才要求 MFA 就绪。"""
        self.cas_client.set_token(
            token_data["user_token"],
            token_data["refresh_token"]
        )
        try:
            self.cas_client.login()
        except Exception as e:
            mfa_state = getattr(self.cas_client.mfa, "state", None)
            mfa_required = getattr(self.cas_client.mfa, "required", False)
            if mfa_state and not mfa_required:
                try:
                    logger.info("检测到当前设备无需 MFA，重试 Token 登录...")
                    self.cas_client.login()
                except Exception as retry_error:
                    logger.warning(f"Token 登录重试失败: {retry_error}")
            else:
                logger.warning(f"Token 登录失败: {e}")

        if self.cas_client.logged_in:
            logger.info("Token 登录成功")
            if (
                self.cas_client.user_token != token_data.get("user_token")
                or self.cas_client.refresh_token != token_data.get("refresh_token")
            ):
                logger.info("检测到 Token 已刷新，正在保存新 Token...")
                self._save_current_token(token_data)
            return True

        logger.warning("Token 已失效，将使用账号密码登录")
        return False

    def _save_current_token(self, token_data: Optional[Dict[str, str]] = None) -> None:
        """保存当前 CAS 客户端中的 token。"""
        if not self.cas_client.user_token or not self.cas_client.refresh_token:
            logger.warning("CAS 客户端未返回完整 Token，跳过保存")
            return

        try:
            TokenManager.save(
                self.cas_client.user_token,
                self.cas_client.refresh_token,
                self.device_id or (token_data or {}).get("device_id")
            )
        except Exception as e:
            logger.error(f"保存 Token 失败: {e}")

    def _init_cas_client(self) -> bool:
        """初始化 CAS 客户端。"""
        token_data = TokenManager.load()
        self._apply_device(token_data)

        # 尝试使用已保存的 token 登录
        if token_data and token_data.get("user_token") and token_data.get("refresh_token"):
            logger.info("尝试使用已保存的 Token 登录...")
            if self._login_with_saved_token(token_data):
                return True

        self._ensure_mfa_ready()

        # 使用账号密码登录
        logger.info("使用账号密码进行 CAS 认证...")
        self.cas_client.login()

        if self.cas_client.logged_in:
            logger.info("CAS 认证成功")
            self._save_current_token(token_data)
            return True
        else:
            logger.error("CAS 认证失败")
            return False

    def _get_balance(self) -> Dict[str, float]:
        """获取电量余额。"""
        if not self._init_cas_client():
            raise Exception("CAS 认证失败，无法获取电量信息")

        logger.info("创建一卡通客户端...")
        with ECardClient(self.cas_client) as ecard:
            ecard.login()
            logger.info("一卡通登录成功")

            logger.info("获取电量余额...")
            light_balance = ecard.get_remaining_energy(room=LIGHT_ROOM)
            ac_balance = ecard.get_remaining_energy(room=AC_ROOM)

            logger.info(f"照明: {light_balance} 度, 空调: {ac_balance} 度")

            return {
                "light_Balance": light_balance,
                "ac_Balance": ac_balance
            }
