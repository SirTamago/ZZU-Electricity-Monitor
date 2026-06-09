"""本地 MFA 初始化脚本，只负责认证并保存 CAS token。"""
import logging
import sys

from config import ACCOUNT, PASSWORD, ZZU_DEVICE_ID, get_missing_required_env
import tokens
from zzupy.app import CASClient


logger = logging.getLogger(__name__)


def configure_logging() -> None:
    """配置脚本运行时日志。"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def main() -> int:
    """执行本地 MFA 初始化流程。"""
    missing_vars = get_missing_required_env(("ACCOUNT", "PASSWORD"))
    if missing_vars:
        logger.error("缺少必要的环境变量: %s", ", ".join(missing_vars))
        return 1

    cas = CASClient(ACCOUNT, PASSWORD)
    try:
        if ZZU_DEVICE_ID:
            cas.set_device(ZZU_DEVICE_ID)
            logger.info("使用已配置的 ZZU_DEVICE_ID")
        else:
            logger.info("使用 ZZU.Py 默认 deviceId")

        if cas.mfa.is_required():
            logger.info("当前设备需要 MFA，正在发送短信验证码...")
            cas.mfa.send_sms()
            code = input("请输入短信验证码: ").strip()
            if not code:
                logger.error("短信验证码为空")
                return 1
            cas.mfa.verify_sms(code)
            logger.info("MFA 验证成功")
        else:
            logger.info("当前设备无需 MFA")

        cas.login()
        if not cas.logged_in or not cas.user_token or not cas.refresh_token:
            logger.error("CAS 登录失败：未返回 token")
            return 1

        tokens.save(cas.user_token, cas.refresh_token, ZZU_DEVICE_ID)
        logger.info("Token 已保存。请运行 python crypto.py encrypt 后，将 tokens.enc 放到 page 分支。")
        logger.info("如统一认证提示可信设备，请在安全中心将当前设备设为可信。")
        return 0
    finally:
        if hasattr(cas, "close"):
            cas.close()


if __name__ == "__main__":
    configure_logging()
    sys.exit(main())
