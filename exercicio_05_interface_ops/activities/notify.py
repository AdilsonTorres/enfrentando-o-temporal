import os
import asyncio
import requests
from temporalio import activity

@activity.defn
async def send_message(message: str) -> dict:
    """Envia uma notificação via Telegram Bot."""
    try:
        bot_token = os.getenv("BOT_TOKEN", "")
        chat_id = os.getenv("CHAT_ID", "")
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = {"chat_id": chat_id, "text": message}
        response = await asyncio.to_thread(requests.post, url, json=data)
        response.raise_for_status()
        return {"status": True}
    except Exception as e:
        activity.logger.error(f"[ERRO] Telegram: {e}")
        raise
