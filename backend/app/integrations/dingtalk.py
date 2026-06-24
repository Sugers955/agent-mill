"""钉钉机器人集成 — 接收群消息，调用数字员工回复。"""
from __future__ import annotations
import hashlib
import hmac
import base64
import time
import logging
import httpx
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)


class DingTalkBot:
    """钉钉自定义机器人。"""

    def __init__(self, webhook: str, secret: str = ""):
        self.webhook = webhook
        self.secret = secret

    def _sign(self) -> tuple[str, str]:
        """计算签名（若配置了 secret）。"""
        if not self.secret:
            return "", ""
        timestamp = str(round(time.time() * 1000))
        string_to_sign = f"{timestamp}\n{self.secret}"
        hmac_code = hmac.HMAC(
            self.secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        sign = quote_plus(base64.b64encode(hmac_code))
        return timestamp, sign

    async def send_text(self, content: str, at_mobiles: list[str] | None = None) -> dict:
        """发送文本消息到群。"""
        payload: dict = {"msgtype": "text", "text": {"content": content}}
        if at_mobiles:
            payload["at"] = {"atMobiles": at_mobiles, "isAtAll": False}
        return await self._post(payload)

    async def send_markdown(self, title: str, text: str) -> dict:
        """发送 Markdown 消息到群。"""
        payload = {"msgtype": "markdown", "markdown": {"title": title, "text": text}}
        return await self._post(payload)

    async def _post(self, payload: dict) -> dict:
        url = self.webhook
        if self.secret:
            timestamp, sign = self._sign()
            url = f"{self.webhook}&timestamp={timestamp}&sign={sign}"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=payload)
            return resp.json()

    @staticmethod
    def parse_callback(data: dict) -> dict | None:
        """解析钉钉回调数据，提取消息内容。

        钉钉机器人回调格式:
        {
            "msgtype": "text",
            "text": {"content": "@机器人 消息内容"},
            "senderNick": "张三",
            "senderStaffId": "xxx",
            "conversationId": "xxx",
            "conversationType": "1",  # 1=单聊 2=群聊
            "msgId": "xxx",
            "senderCorpId": "xxx",
        }
        """
        msgtype = data.get("msgtype")
        if msgtype == "text":
            content = data.get("text", {}).get("content", "").strip()
            # 去除 @机器人 前缀
            if content.startswith("@"):
                parts = content.split(" ", 1)
                content = parts[1] if len(parts) > 1 else ""
            return {
                "text": content,
                "sender_nick": data.get("senderNick", ""),
                "sender_id": data.get("senderStaffId", ""),
                "conversation_id": data.get("conversationId", ""),
                "conversation_type": data.get("conversationType", ""),
                "msg_id": data.get("msgId", ""),
            }
        return None
