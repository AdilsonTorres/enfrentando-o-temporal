import asyncio
import logging
from dotenv import load_dotenv

load_dotenv("../.env")

from temporalio.client import Client
from temporalio.worker import Worker

from activities.device import (
    get_interface_state,
    set_interface_state,
    validate_interface_state,
    rollback_interface_state,
)
from activities.notify import send_message
from shared.telegram_approval_bot import telegram_polling_loop
from workflow import InterfaceAdminStateWorkflow

logging.basicConfig(level=logging.INFO)


async def main():
    client = await Client.connect("localhost:7233")

    worker = Worker(
        client,
        task_queue="interface-ops-queue",
        workflows=[InterfaceAdminStateWorkflow],
        activities=[
            get_interface_state,
            set_interface_state,
            validate_interface_state,
            rollback_interface_state,
            send_message,
        ],
    )

    print("Worker Interface Admin-State iniciado. Aguardando tarefas... (Ctrl+C para parar)")
    await asyncio.gather(
        worker.run(),
        telegram_polling_loop(client),
    )


if __name__ == "__main__":
    asyncio.run(main())
