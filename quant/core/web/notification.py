"""Signal push notification service (DingTalk/WeChat webhook)."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import yaml

ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = ROOT / "config" / "web.yaml"


class NotificationConfig:
    """Notification configuration."""

    def __init__(self):
        self.dingtalk_webhook: str = ""
        self.wechat_webhook: str = ""
        self.enabled: bool = False
        self.notify_on_buy: bool = True
        self.notify_on_sell: bool = True
        self.min_score: float = 0.0
        self._load_config()

    def _load_config(self):
        """Load configuration from web.yaml."""
        if not CONFIG_PATH.exists():
            return

        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}

            notification = config.get("notification", {})
            self.dingtalk_webhook = notification.get("dingtalk_webhook", "")
            self.wechat_webhook = notification.get("wechat_webhook", "")
            self.enabled = notification.get("enabled", False)
            self.notify_on_buy = notification.get("notify_on_buy", True)
            self.notify_on_sell = notification.get("notify_on_sell", True)
            self.min_score = notification.get("min_score", 0.0)
        except Exception:
            pass


class SignalNotifier:
    """Send signal notifications via DingTalk/WeChat webhook."""

    def __init__(self):
        self.config = NotificationConfig()

    async def notify_signals(self, signals: list[dict[str, Any]], trade_date: str) -> dict[str, bool]:
        """Send notifications for signals."""
        if not self.config.enabled:
            return {"dingtalk": False, "wechat": False, "reason": "disabled"}

        # Filter signals
        filtered = []
        for signal in signals:
            signal_type = signal.get("signal_type", "")
            score = signal.get("score", 0) or 0

            if signal_type == "BUY" and not self.config.notify_on_buy:
                continue
            if signal_type == "SELL" and not self.config.notify_on_sell:
                continue
            if score < self.config.min_score:
                continue

            filtered.append(signal)

        if not filtered:
            return {"dingtalk": False, "wechat": False, "reason": "no_signals"}

        # Build message
        message = self._build_message(filtered, trade_date)

        # Send notifications
        results = {}

        if self.config.dingtalk_webhook:
            results["dingtalk"] = await self._send_dingtalk(message)

        if self.config.wechat_webhook:
            results["wechat"] = await self._send_wechat(message)

        return results

    def _build_message(self, signals: list[dict[str, Any]], trade_date: str) -> str:
        """Build notification message."""
        buy_signals = [s for s in signals if s.get("signal_type") == "BUY"]
        sell_signals = [s for s in signals if s.get("signal_type") == "SELL"]

        lines = [
            f"📊 量化交易信号 ({trade_date})",
            "",
        ]

        if buy_signals:
            lines.append(f"🟢 买入信号 ({len(buy_signals)}只)")
            lines.append("-" * 30)
            for s in buy_signals[:10]:  # Limit to 10
                name = s.get("name", s.get("ts_code", ""))
                price = s.get("price", 0)
                score = s.get("score", 0)
                lines.append(f"  {name} ¥{price:.2f} 评分{score:.4f}")
            if len(buy_signals) > 10:
                lines.append(f"  ... 还有 {len(buy_signals) - 10} 只")
            lines.append("")

        if sell_signals:
            lines.append(f"🔴 卖出信号 ({len(sell_signals)}只)")
            lines.append("-" * 30)
            for s in sell_signals[:10]:
                name = s.get("name", s.get("ts_code", ""))
                price = s.get("price", 0)
                score = s.get("score", 0)
                lines.append(f"  {name} ¥{price:.2f} 评分{score:.4f}")
            if len(sell_signals) > 10:
                lines.append(f"  ... 还有 {len(sell_signals) - 10} 只")
            lines.append("")

        lines.append(f"共 {len(signals)} 个信号")
        lines.append(f"时间: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M')}")

        return "\n".join(lines)

    async def _send_dingtalk(self, message: str) -> bool:
        """Send message via DingTalk webhook."""
        try:
            async with httpx.AsyncClient() as client:
                payload = {
                    "msgtype": "text",
                    "text": {"content": message},
                }
                response = await client.post(
                    self.config.dingtalk_webhook,
                    json=payload,
                    timeout=10,
                )
                return response.status_code == 200
        except Exception as e:
            print(f"DingTalk notification failed: {e}")
            return False

    async def _send_wechat(self, message: str) -> bool:
        """Send message via WeChat Work webhook."""
        try:
            async with httpx.AsyncClient() as client:
                payload = {
                    "msgtype": "text",
                    "text": {"content": message},
                }
                response = await client.post(
                    self.config.wechat_webhook,
                    json=payload,
                    timeout=10,
                )
                return response.status_code == 200
        except Exception as e:
            print(f"WeChat notification failed: {e}")
            return False


# Global notifier instance
notifier = SignalNotifier()
