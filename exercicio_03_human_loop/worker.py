import asyncio
import logging
from dotenv import load_dotenv

load_dotenv("../.env")

from temporalio.client import Client
from temporalio.worker import Worker

from activities.device import get_interface_description, apply_interface_description
from activities.notify import send_message
from shared.telegram_approval_bot import telegram_polling_loop
from workflow import InterfaceChangeApprovalWorkflow

logging.basicConfig(level=logging.INFO)


async def main():
    client = await Client.connect("localhost:7233")

    worker = Worker(
        client,
        task_queue="approval-queue",
        workflows=[InterfaceChangeApprovalWorkflow],
        activities=[
            get_interface_description,
            apply_interface_description,
            send_message,
        ],
    )

    print("Worker Human-in-the-Loop iniciado. Aguardando tarefas... (Ctrl+C para parar)")
    await asyncio.gather(
        worker.run(),
        telegram_polling_loop(client),
    )


if __name__ == "__main__":
    asyncio.run(main())
