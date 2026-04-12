"""
telegram_bot.py — Bot de aprovação standalone (opcional)

O bot de aprovação já está embutido no worker.py. Este script existe para
uso standalone caso queira rodá-lo como processo separado.

Uso:
  python telegram_bot.py
"""

import asyncio
import os

from dotenv import load_dotenv
from temporalio.client import Client

# Carrega .env do projeto principal
_here = os.path.dirname(os.path.abspath(__file__))
load_dotenv(dotenv_path=os.path.join(_here, "../.env"))

from shared.telegram_approval_bot import telegram_polling_loop

TEMPORAL_ADDRESS = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")


async def main() -> None:
    client = await Client.connect(TEMPORAL_ADDRESS)
    print(f"🤖 Bot de aprovação iniciado (Temporal: {TEMPORAL_ADDRESS})")
    await telegram_polling_loop(client)


if __name__ == "__main__":
    asyncio.run(main())
