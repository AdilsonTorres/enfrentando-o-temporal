"""
shared/telegram_approval_bot.py

Bot de aprovação Telegram reutilizável para exercícios com Human-in-the-Loop.

Processa cliques nos botões ✅ Aprovar / ❌ Rejeitar enviando os Signals
`approve` e `reject` ao workflow Temporal correspondente.

Uso nos workers:
    from shared.telegram_approval_bot import telegram_polling_loop
    await asyncio.gather(worker.run(), telegram_polling_loop(client))
"""

import asyncio
import os
import requests


def _bot_token() -> str:
    return os.getenv("BOT_TOKEN", "")


def _telegram(method: str, **kwargs) -> dict:
    resp = requests.post(
        f"https://api.telegram.org/bot{_bot_token()}/{method}",
        json=kwargs,
        timeout=10,
    )
    return resp.json()


async def _handle_callback(client, cb: dict) -> None:
    """Processa um clique de botão inline do Telegram."""
    query_id = cb["id"]
    data = cb.get("data", "")
    user = cb.get("from", {}).get("first_name", "operador")
    chat_id = cb["message"]["chat"]["id"]
    msg_id = cb["message"]["message_id"]

    # Confirma o clique imediatamente (remove spinner do Telegram)
    _telegram("answerCallbackQuery", callback_query_id=query_id, text="Processando...")

    # Remove os botões (evita cliques duplos)
    _telegram("editMessageReplyMarkup", chat_id=chat_id, message_id=msg_id, reply_markup={})

    if data.startswith("approve:"):
        wf_id = data.split(":", 1)[1]
        await client.get_workflow_handle(wf_id).signal("approve")
        print(f"✅ {user} aprovou workflow '{wf_id}'")

    elif data.startswith("reject:"):
        wf_id = data.split(":", 1)[1]
        await client.get_workflow_handle(wf_id).signal("reject", f"Rejeitado por {user} via Telegram")
        print(f"❌ {user} rejeitou workflow '{wf_id}'")

    else:
        print(f"⚠️  callback desconhecido: {data!r}")


async def telegram_polling_loop(client) -> None:
    """
    Long-polling loop para eventos callback_query do Telegram.

    Pode ser embutido em qualquer worker via asyncio.gather():
        await asyncio.gather(worker.run(), telegram_polling_loop(client))

    Se BOT_TOKEN não estiver configurado, encerra silenciosamente.
    """
    token = _bot_token()
    if not token:
        print("⚠️  BOT_TOKEN não configurado — botões do Telegram desativados.")
        return

    print("🤖 Bot de aprovação ativo (aguardando botões do Telegram...)")
    offset = 0
    while True:
        try:
            resp = await asyncio.to_thread(
                requests.get,
                f"https://api.telegram.org/bot{token}/getUpdates",
                params={
                    "timeout": 30,
                    "offset": offset,
                    "allowed_updates": ["callback_query"],
                },
                timeout=35,
            )
            for update in resp.json().get("result", []):
                offset = update["update_id"] + 1
                if "callback_query" in update:
                    await _handle_callback(client, update["callback_query"])
        except requests.exceptions.RequestException as e:
            print(f"⚠️  Erro de rede (Telegram): {e} — retentando em 5s...")
            await asyncio.sleep(5)
        except Exception as e:
            print(f"⚠️  Erro inesperado (Telegram): {e} — retentando em 5s...")
            await asyncio.sleep(5)
