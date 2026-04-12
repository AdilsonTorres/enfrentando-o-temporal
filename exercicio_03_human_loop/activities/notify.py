import os
import asyncio
import requests
from temporalio import activity

@activity.defn
async def send_message(message: str, workflow_id: str = "") -> dict:
    """
    Envia uma notificação via Telegram Bot.

    Se workflow_id for fornecido, adiciona botões inline ✅ Aprovar / ❌ Rejeitar
    à mensagem (usado pela notificação de aprovação do Ex03).
    """
    try:
        bot_token = os.getenv("BOT_TOKEN", "")
        chat_id = os.getenv("CHAT_ID", "")
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data: dict = {"chat_id": chat_id, "text": message}
        if workflow_id:
            data["reply_markup"] = {
                "inline_keyboard": [[
                    {"text": "✅ Aprovar", "callback_data": f"approve:{workflow_id}"},
                    {"text": "❌ Rejeitar", "callback_data": f"reject:{workflow_id}"},
                ]]
            }
        response = await asyncio.to_thread(requests.post, url, json=data)
        response.raise_for_status()
        return {"status": True}
    except Exception as e:
        activity.logger.error(f"[ERRO] Telegram: {e}")
        raise
