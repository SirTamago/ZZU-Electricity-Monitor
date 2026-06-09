"""通知模块，负责按电量状态分发日常通知和低电量报警。"""
import json
import logging
import smtplib
from email.mime.text import MIMEText
from typing import Dict, Optional, Callable
from urllib.parse import urlencode

import requests
from tenacity import (
    retry,
    stop_after_attempt,
    wait_chain,
    wait_fixed,
    wait_exponential,
    retry_if_exception_type,
)

from config import (
    THRESHOLD,
    EXCELLENT_THRESHOLD,
    RETRY_ATTEMPTS,
    # 通知渠道配置
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    SERVERCHAN_KEYS,
    EMAIL,
    SMTP_CODE,
    SMTP_SERVER,
    BARK_URL,
    BARK_KEY,
    DINGTALK_WEBHOOK,
    DINGTALK_SECRET,
    FEISHU_WEBHOOK,
    FEISHU_SECRET,
    GOCQHTTP_URL,
    GOCQHTTP_TOKEN,
    GOCQHTTP_TARGET,
    GOTIFY_URL,
    GOTIFY_TOKEN,
    IGOT_KEY,
    PUSHDEER_KEY,
    SYNOLOGY_CHAT_URL,
    SYNOLOGY_CHAT_TOKEN,
    PUSHPLUS_TOKEN,
    WECOM_CORP_ID,
    WECOM_AGENT_ID,
    WECOM_SECRET,
    WECOM_TOUSER,
    QMSG_KEY,
    QMSG_QQ,
    AIBOTK_KEY,
    AIBOTK_TARGET,
    PUSHME_KEY,
    CHRONOCAT_URL,
    CHRONOCAT_TOKEN,
    CHRONOCAT_TARGET,
    NTFY_URL,
    NTFY_TOPIC,
    NTFY_TOKEN,
    WEBHOOK_URL,
    WEBHOOK_METHOD,
    WEBHOOK_HEADERS,
    WEBHOOK_BODY_TEMPLATE,
)

logger = logging.getLogger(__name__)

# 请求重试装饰器
request_retry = retry(
    stop=stop_after_attempt(RETRY_ATTEMPTS),
    wait=wait_chain(
        wait_fixed(15),
        wait_fixed(30),
        wait_exponential(multiplier=1, min=45, max=120),
    ),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)


def get_status(balance: float) -> str:
    """获取电量状态描述"""
    if balance > EXCELLENT_THRESHOLD:
        return "充足"
    elif balance > THRESHOLD:
        return "偏低"
    else:
        return "不足"


def format_balance_report(
    light_balance: float, ac_balance: float, escape_markdown: bool = False
) -> str:
    """格式化电量报告。

    参数：
        light_balance: 照明电量。
        ac_balance: 空调电量。
        escape_markdown: 是否转义 Markdown 特殊字符，用于 Telegram。

    返回：
        格式化后的报告字符串。
    """
    light_status = get_status(light_balance)
    ac_status = get_status(ac_balance)

    light_str = str(light_balance)
    ac_str = str(ac_balance)

    if escape_markdown:
        light_str = light_str.replace(".", "\\.")
        ac_str = ac_str.replace(".", "\\.")

    return (
        f"💡 照明剩余电量：{light_str} 度（{light_status}）\n"
        f"❄️ 空调剩余电量：{ac_str} 度（{ac_status}）\n\n"
    )


def is_low_energy(balances: Dict[str, float]) -> bool:
    """判断是否低电量"""
    return balances["light_Balance"] <= THRESHOLD or balances["ac_Balance"] <= THRESHOLD


# 通知渠道实现


@request_retry
def send_telegram(title: str, content: str) -> bool:
    """Telegram 通知"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.debug("未配置 Telegram 参数，跳过")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": f"*{title}*\n\n{content}",
        "parse_mode": "MarkdownV2",
    }
    response = requests.post(url, data=payload, timeout=10)
    result = response.json()

    if not result.get("ok"):
        raise requests.exceptions.RequestException(result.get("description"))
    logger.info("Telegram 通知发送成功")
    return True


@request_retry
def send_serverchan(title: str, content: str) -> bool:
    """Server酱 通知"""
    if not SERVERCHAN_KEYS:
        logger.debug("未配置 SERVERCHAN_KEYS，跳过")
        return False

    success = False
    for key in SERVERCHAN_KEYS.split(","):
        key = key.strip()
        if not key:
            continue

        url = f"https://sctapi.ftqq.com/{key}.send"
        payload = {"title": title, "desp": content}
        response = requests.post(url, data=payload, timeout=10)

        try:
            result = response.json()
            if result.get("code") == 0:
                logger.info(f"Server酱 通知发送成功 (key: {key[:8]}...)")
                success = True
            else:
                logger.warning(f"Server酱 发送失败: {result.get('message')}")
        except ValueError:
            logger.error(f"Server酱 返回非 JSON: {response.text}")

    return success


@request_retry
def send_email(title: str, content: str) -> bool:
    """邮件通知"""
    if not all([EMAIL, SMTP_CODE, SMTP_SERVER]):
        logger.debug("邮件配置不完整，跳过")
        return False

    msg = MIMEText(content, "plain", "utf-8")
    msg["Subject"] = title
    msg["From"] = EMAIL
    msg["To"] = EMAIL

    client = smtplib.SMTP_SSL(SMTP_SERVER, smtplib.SMTP_SSL_PORT)
    client.login(EMAIL, SMTP_CODE)
    client.sendmail(EMAIL, EMAIL, msg.as_string())
    client.quit()
    logger.info("邮件通知发送成功")
    return True


@request_retry
def send_bark(title: str, content: str) -> bool:
    """Bark 通知 (iOS)"""
    if not BARK_KEY:
        logger.debug("未配置 BARK_KEY，跳过")
        return False

    base_url = BARK_URL or "https://api.day.app"
    url = f"{base_url}/{BARK_KEY}/{title}/{content}"
    response = requests.get(url, timeout=10)
    result = response.json()

    if result.get("code") == 200:
        logger.info("Bark 通知发送成功")
        return True
    else:
        raise requests.exceptions.RequestException(result.get("message"))


@request_retry
def send_dingtalk(title: str, content: str) -> bool:
    """钉钉机器人通知"""
    if not DINGTALK_WEBHOOK:
        logger.debug("未配置 DINGTALK_WEBHOOK，跳过")
        return False

    url = DINGTALK_WEBHOOK
    if DINGTALK_SECRET:
        import time
        import hmac
        import hashlib
        import base64

        timestamp = str(round(time.time() * 1000))
        secret_enc = DINGTALK_SECRET.encode("utf-8")
        string_to_sign = f"{timestamp}\n{DINGTALK_SECRET}"
        hmac_code = hmac.new(
            secret_enc, string_to_sign.encode("utf-8"), digestmod=hashlib.sha256
        ).digest()
        sign = base64.b64encode(hmac_code).decode("utf-8")
        url = f"{url}&timestamp={timestamp}&sign={sign}"

    payload = {"msgtype": "text", "text": {"content": f"{title}\n\n{content}"}}
    response = requests.post(url, json=payload, timeout=10)
    result = response.json()

    if result.get("errcode") == 0:
        logger.info("钉钉通知发送成功")
        return True
    else:
        raise requests.exceptions.RequestException(result.get("errmsg"))


@request_retry
def send_feishu(title: str, content: str) -> bool:
    """飞书机器人通知"""
    if not FEISHU_WEBHOOK:
        logger.debug("未配置 FEISHU_WEBHOOK，跳过")
        return False

    url = FEISHU_WEBHOOK
    if FEISHU_SECRET:
        import time
        import hmac
        import hashlib
        import base64

        timestamp = str(int(time.time()))
        string_to_sign = f"{timestamp}\n{FEISHU_SECRET}"
        hmac_code = hmac.new(
            string_to_sign.encode("utf-8"), digestmod=hashlib.sha256
        ).digest()
        sign = base64.b64encode(hmac_code).decode("utf-8")
        payload = {
            "timestamp": timestamp,
            "sign": sign,
            "msg_type": "text",
            "content": {"text": f"{title}\n\n{content}"},
        }
    else:
        payload = {"msg_type": "text", "content": {"text": f"{title}\n\n{content}"}}

    response = requests.post(url, json=payload, timeout=10)
    result = response.json()

    if result.get("code") == 0:
        logger.info("飞书通知发送成功")
        return True
    else:
        raise requests.exceptions.RequestException(result.get("msg"))


@request_retry
def send_gocqhttp(title: str, content: str) -> bool:
    """go-cqhttp 通知"""
    if not GOCQHTTP_URL or not GOCQHTTP_TARGET:
        logger.debug("未配置 go-cqhttp 参数，跳过")
        return False

    url = f"{GOCQHTTP_URL}/send_private_msg"
    headers = {}
    if GOCQHTTP_TOKEN:
        headers["Authorization"] = f"Bearer {GOCQHTTP_TOKEN}"

    payload = {"user_id": GOCQHTTP_TARGET, "message": f"{title}\n\n{content}"}
    response = requests.post(url, json=payload, headers=headers, timeout=10)
    result = response.json()

    if result.get("status") == "ok":
        logger.info("go-cqhttp 通知发送成功")
        return True
    else:
        raise requests.exceptions.RequestException(result.get("message"))


@request_retry
def send_gotify(title: str, content: str) -> bool:
    """Gotify 通知"""
    if not GOTIFY_URL or not GOTIFY_TOKEN:
        logger.debug("未配置 Gotify 参数，跳过")
        return False

    url = f"{GOTIFY_URL}/message"
    headers = {"X-Gotify-Key": GOTIFY_TOKEN}
    payload = {"title": title, "message": content, "priority": 5}
    response = requests.post(url, json=payload, headers=headers, timeout=10)

    if response.status_code == 200:
        logger.info("Gotify 通知发送成功")
        return True
    else:
        raise requests.exceptions.RequestException(response.text)


@request_retry
def send_igot(title: str, content: str) -> bool:
    """iGot 通知"""
    if not IGOT_KEY:
        logger.debug("未配置 IGOT_KEY，跳过")
        return False

    url = f"https://push.hellyw.com/{IGOT_KEY}"
    payload = {"title": title, "content": content}
    response = requests.post(url, json=payload, timeout=10)
    result = response.json()

    if result.get("ret") == 0:
        logger.info("iGot 通知发送成功")
        return True
    else:
        raise requests.exceptions.RequestException(result.get("errMsg"))


@request_retry
def send_pushdeer(title: str, content: str) -> bool:
    """PushDeer 通知"""
    if not PUSHDEER_KEY:
        logger.debug("未配置 PUSHDEER_KEY，跳过")
        return False

    url = "https://api2.pushdeer.com/message/push"
    payload = {"pushkey": PUSHDEER_KEY, "text": title, "desp": content, "type": "text"}
    response = requests.post(url, data=payload, timeout=10)
    result = response.json()

    if result.get("code") == 0:
        logger.info("PushDeer 通知发送成功")
        return True
    else:
        raise requests.exceptions.RequestException(result.get("error"))


@request_retry
def send_synology_chat(title: str, content: str) -> bool:
    """Synology Chat 通知"""
    if not SYNOLOGY_CHAT_URL or not SYNOLOGY_CHAT_TOKEN:
        logger.debug("未配置 Synology Chat 参数，跳过")
        return False

    url = f"{SYNOLOGY_CHAT_URL}?api=SYNO.Chat.External&method=incoming&version=2&token={SYNOLOGY_CHAT_TOKEN}"
    payload = {"payload": json.dumps({"text": f"{title}\n\n{content}"})}
    response = requests.post(url, data=payload, timeout=10)
    result = response.json()

    if result.get("success"):
        logger.info("Synology Chat 通知发送成功")
        return True
    else:
        raise requests.exceptions.RequestException(str(result))


@request_retry
def send_pushplus(title: str, content: str) -> bool:
    """PushPlus 通知"""
    if not PUSHPLUS_TOKEN:
        logger.debug("未配置 PUSHPLUS_TOKEN，跳过")
        return False

    url = "https://www.pushplus.plus/send"
    payload = {"token": PUSHPLUS_TOKEN, "title": title, "content": content}
    response = requests.post(url, json=payload, timeout=10)
    result = response.json()

    if result.get("code") == 200:
        logger.info("PushPlus 通知发送成功")
        return True
    else:
        raise requests.exceptions.RequestException(result.get("msg"))


@request_retry
def send_wecom(title: str, content: str) -> bool:
    """企业微信通知"""
    if not all([WECOM_CORP_ID, WECOM_AGENT_ID, WECOM_SECRET]):
        logger.debug("企业微信配置不完整，跳过")
        return False

    # 获取 access_token
    token_url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={WECOM_CORP_ID}&corpsecret={WECOM_SECRET}"
    token_response = requests.get(token_url, timeout=10)
    token_result = token_response.json()

    if token_result.get("errcode") != 0:
        raise requests.exceptions.RequestException(token_result.get("errmsg"))

    access_token = token_result["access_token"]

    # 发送消息
    send_url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={access_token}"
    payload = {
        "touser": WECOM_TOUSER or "@all",
        "msgtype": "text",
        "agentid": WECOM_AGENT_ID,
        "text": {"content": f"{title}\n\n{content}"},
    }
    response = requests.post(send_url, json=payload, timeout=10)
    result = response.json()

    if result.get("errcode") == 0:
        logger.info("企业微信通知发送成功")
        return True
    else:
        raise requests.exceptions.RequestException(result.get("errmsg"))


@request_retry
def send_qmsg(title: str, content: str) -> bool:
    """Qmsg酱 通知"""
    if not QMSG_KEY:
        logger.debug("未配置 QMSG_KEY，跳过")
        return False

    url = f"https://qmsg.zendee.cn/send/{QMSG_KEY}"
    payload = {"msg": f"{title}\n\n{content}"}
    if QMSG_QQ:
        payload["qq"] = QMSG_QQ

    response = requests.post(url, data=payload, timeout=10)
    result = response.json()

    if result.get("code") == 0:
        logger.info("Qmsg酱 通知发送成功")
        return True
    else:
        raise requests.exceptions.RequestException(result.get("reason"))


@request_retry
def send_aibotk(title: str, content: str) -> bool:
    """智能微秘书 (Aibotk) 通知"""
    if not AIBOTK_KEY or not AIBOTK_TARGET:
        logger.debug("未配置智能微秘书参数，跳过")
        return False

    url = "https://api-bot.aibotk.com/openapi/v1/chat/send"
    headers = {"Authorization": f"Bearer {AIBOTK_KEY}"}
    payload = {"to": AIBOTK_TARGET, "type": 1, "content": f"{title}\n\n{content}"}
    response = requests.post(url, json=payload, headers=headers, timeout=10)
    result = response.json()

    if result.get("code") == 0:
        logger.info("智能微秘书通知发送成功")
        return True
    else:
        raise requests.exceptions.RequestException(result.get("message"))


@request_retry
def send_pushme(title: str, content: str) -> bool:
    """PushMe 通知"""
    if not PUSHME_KEY:
        logger.debug("未配置 PUSHME_KEY，跳过")
        return False

    url = "https://push.i-i.me/"
    payload = {"push_key": PUSHME_KEY, "title": title, "content": content}
    response = requests.post(url, data=payload, timeout=10)

    if response.text == "success":
        logger.info("PushMe 通知发送成功")
        return True
    else:
        raise requests.exceptions.RequestException(response.text)


@request_retry
def send_chronocat(title: str, content: str) -> bool:
    """Chronocat 通知"""
    if not CHRONOCAT_URL or not CHRONOCAT_TARGET:
        logger.debug("未配置 Chronocat 参数，跳过")
        return False

    url = f"{CHRONOCAT_URL}/api/message/send"
    headers = {"Content-Type": "application/json"}
    if CHRONOCAT_TOKEN:
        headers["Authorization"] = f"Bearer {CHRONOCAT_TOKEN}"

    payload = {
        "peer": {"chatType": 1, "peerUin": CHRONOCAT_TARGET},
        "elements": [{"elementType": 1, "textElement": {"content": f"{title}\n\n{content}"}}],
    }
    response = requests.post(url, json=payload, headers=headers, timeout=10)

    if response.status_code == 200:
        logger.info("Chronocat 通知发送成功")
        return True
    else:
        raise requests.exceptions.RequestException(response.text)


@request_retry
def send_ntfy(title: str, content: str) -> bool:
    """ntfy 通知"""
    if not NTFY_TOPIC:
        logger.debug("未配置 NTFY_TOPIC，跳过")
        return False

    base_url = NTFY_URL or "https://ntfy.sh"
    url = f"{base_url}/{NTFY_TOPIC}"
    headers = {"Title": title}
    if NTFY_TOKEN:
        headers["Authorization"] = f"Bearer {NTFY_TOKEN}"

    response = requests.post(url, data=content.encode("utf-8"), headers=headers, timeout=10)

    if response.status_code == 200:
        logger.info("ntfy 通知发送成功")
        return True
    else:
        raise requests.exceptions.RequestException(response.text)


@request_retry
def send_webhook(title: str, content: str) -> bool:
    """自定义 Webhook 通知"""
    if not WEBHOOK_URL:
        logger.debug("未配置 WEBHOOK_URL，跳过")
        return False

    method = (WEBHOOK_METHOD or "POST").upper()
    headers = json.loads(WEBHOOK_HEADERS) if WEBHOOK_HEADERS else {}

    if WEBHOOK_BODY_TEMPLATE:
        body = WEBHOOK_BODY_TEMPLATE.replace("{{title}}", title).replace(
            "{{content}}", content
        )
        data = json.loads(body)
    else:
        data = {"title": title, "content": content}

    if method == "GET":
        response = requests.get(WEBHOOK_URL, params=data, headers=headers, timeout=10)
    else:
        response = requests.post(WEBHOOK_URL, json=data, headers=headers, timeout=10)

    if response.status_code in [200, 201, 204]:
        logger.info("Webhook 通知发送成功")
        return True
    else:
        raise requests.exceptions.RequestException(response.text)


# 通知调度

# 所有通知渠道 (除 Telegram 外)
ALERT_CHANNELS: list[tuple[str, Callable[[str, str], bool]]] = [
    ("Server酱", send_serverchan),
    ("邮件", send_email),
    ("Bark", send_bark),
    ("钉钉", send_dingtalk),
    ("飞书", send_feishu),
    ("go-cqhttp", send_gocqhttp),
    ("Gotify", send_gotify),
    ("iGot", send_igot),
    ("PushDeer", send_pushdeer),
    ("Synology Chat", send_synology_chat),
    ("PushPlus", send_pushplus),
    ("企业微信", send_wecom),
    ("Qmsg酱", send_qmsg),
    ("智能微秘书", send_aibotk),
    ("PushMe", send_pushme),
    ("Chronocat", send_chronocat),
    ("ntfy", send_ntfy),
    ("Webhook", send_webhook),
]


def send_alert(title: str, content: str) -> None:
    """向所有已配置渠道发送报警通知。

    参数：
        title: 通知标题。
        content: 普通文本格式的通知内容。
    """
    logger.info("发送报警通知到所有渠道...")

    # Telegram (使用 Markdown 转义)
    try:
        telegram_content = content.replace(".", "\\.")
        send_telegram(title, telegram_content)
    except Exception as e:
        logger.error(f"Telegram 通知失败: {e}")

    # 其他渠道
    for name, func in ALERT_CHANNELS:
        try:
            func(title, content)
        except Exception as e:
            logger.error(f"{name} 通知失败: {e}")


def send_daily(title: str, content: str) -> None:
    """向 Telegram 发送日常通知。

    参数：
        title: 通知标题。
        content: 普通文本格式的通知内容。
    """
    logger.info("发送日常通知到 Telegram...")
    try:
        telegram_content = content.replace(".", "\\.")
        send_telegram(title, telegram_content)
    except Exception as e:
        logger.error(f"Telegram 通知失败: {e}")


def notify(balances: Dict[str, float]) -> None:
    """根据电量状态发送通知。

    参数：
        balances: 电量数据，包含 light_Balance 和 ac_Balance。
    """
    low_energy = is_low_energy(balances)
    title = "⚠️宿舍电量预警⚠️" if low_energy else "🏠宿舍电量通报🏠"
    content = format_balance_report(balances["light_Balance"], balances["ac_Balance"])

    if low_energy:
        content += "⚠️ 电量不足，请尽快充电！"
        send_alert(title, content)
    else:
        content += "当前电量充足，请保持关注。"
        send_daily(title, content)
