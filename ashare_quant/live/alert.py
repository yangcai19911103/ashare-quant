"""告警通道：企业微信 / 钉钉 / 邮件。"""
from __future__ import annotations

import json
import smtplib
from email.mime.text import MIMEText
from typing import Any

from ashare_quant.config import get
from ashare_quant.logging_setup import logger


def _http_post(url: str, payload: dict, timeout: float = 5.0) -> bool:
    try:
        import urllib.request
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"告警 POST 失败 {url}: {exc}")
        return False


def send_wechat_work(content: str, mentioned_list: list[str] | None = None) -> bool:
    """企业微信群机器人。"""
    if not get("live.alert.enabled", False):
        return False
    url = get("live.alert.wechat_work_webhook")
    if not url:
        return False
    payload = {"msgtype": "text",
               "text": {"content": content, "mentioned_list": mentioned_list or []}}
    return _http_post(url, payload)


def send_dingtalk(content: str, at_mobiles: list[str] | None = None) -> bool:
    if not get("live.alert.enabled", False):
        return False
    url = get("live.alert.dingtalk_webhook")
    if not url:
        return False
    payload = {"msgtype": "text",
               "text": {"content": content},
               "at": {"atMobiles": at_mobiles or [], "isAtAll": False}}
    return _http_post(url, payload)


def send_email(subject: str, body: str) -> bool:
    if not get("live.alert.enabled", False):
        return False
    cfg = get("live.alert.email", {}) or {}
    if not cfg.get("smtp_server"):
        return False
    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = cfg["sender"]
        msg["To"] = ", ".join(cfg.get("receivers", []))
        with smtplib.SMTP_SSL(cfg["smtp_server"], cfg.get("smtp_port", 465)) as s:
            s.login(cfg["sender"], cfg["password"])
            s.send_message(msg)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error(f"邮件发送失败：{exc}")
        return False


def alert(level: str, title: str, message: str, **payload: Any) -> None:
    """统一入口：根据 level 自动选择通道。"""
    msg = f"[{level}] {title}\n{message}"
    if payload:
        msg += f"\n{payload}"
    logger.info(f"ALERT: {msg}")
    send_wechat_work(msg)
    send_dingtalk(msg)
    if level == "CRITICAL":
        send_email(f"[CRITICAL] {title}", msg)
