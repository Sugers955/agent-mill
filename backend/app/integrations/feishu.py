"""飞书机器人集成 — 接收群消息，调用数字员工回复。"""
from __future__ import annotations
import hashlib
import hmac
import time
import logging
import httpx
import base64
import json

logger = logging.getLogger(__name__)


class FeishuBot:
    """飞书自定义机器人。"""

    def __init__(self, webhook: str, secret: str = ""):
        self.webhook = webhook
        self.secret = secret

    def _gen_sign(self) -> tuple[str, str]:
        """生成签名。"""
        if not self.secret:
            return "", ""
        timestamp = str(int(time.time()))
        string_to_sign = f"{timestamp}\n{self.secret}"
        hmac_code = hmac.HMAC(
            self.secret.encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha256
        ).digest()
        sign = base64.b64encode(hmac_code).decode("utf-8")
        return timestamp, sign

    async def send_text(self, content: str) -> dict:
        """发送文本消息。"""
        payload: dict = {"msg_type": "text", "content": {"text": content}}
        return await self._post(payload)

    async def send_interactive(self, title: str, content: str) -> dict:
        """发送富文本消息。"""
        payload = {
            "msg_type": "interactive",
            "card": {
                "header": {"title": {"tag": "plain_text", "content": title}},
                "elements": [{"tag": "markdown", "content": content}],
            },
        }
        return await self._post(payload)

    async def _post(self, payload: dict) -> dict:
        url = self.webhook
        if self.secret:
            timestamp, sign = self._gen_sign()
            payload["timestamp"] = timestamp
            payload["sign"] = sign
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=payload)
            return resp.json()

    @staticmethod
    def parse_callback(data: dict) -> dict | None:
        """解析飞书回调数据。

        飞书机器人事件格式 (v2):
        {
            "schema": "2.0",
            "header": {"event_type": "im.message.receive_v1", ...},
            "event": {
                "message": {
                    "message_type": "text",
                    "content": "{\"text\":\"@_user_1 消息内容\"}",
                    "chat_id": "xxx",
                    "message_id": "xxx",
                },
                "sender": {"sender_id": {"open_id": "xxx"}, "sender_type": "user"}
            }
        }
        """
        header = data.get("header", {})
        event_type = header.get("event_type", "")
        if event_type != "im.message.receive_v1":
            return None

        event = data.get("event", {})
        message = event.get("message", {})
        sender = event.get("sender", {})

        msg_type = message.get("message_type", "")
        if msg_type != "text":
            return None

        try:
            content_obj = json.loads(message.get("content", "{}"))
            text = content_obj.get("text", "").strip()
        except (json.JSONDecodeError, AttributeError):
            text = ""

        # 去除 @机器人 前缀
        if text.startswith("@"):
            parts = text.split(" ", 1)
            text = parts[1] if len(parts) > 1 else ""

        return {
            "text": text,
            "sender_id": sender.get("sender_id", {}).get("open_id", ""),
            "chat_id": message.get("chat_id", ""),
            "message_id": message.get("message_id", ""),
        }
