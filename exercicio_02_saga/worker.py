import asyncio
import logging
from dotenv import load_dotenv

load_dotenv("../.env")

from temporalio.client import Client
from temporalio.worker import Worker

from activities.device import (
    get_current_hostname,
    apply_hostname,
    validate_hostname,
    rollback_hostname,
)
from activities.notify import send_message
from workflow import ChangeHostnameSagaWorkflow
logging.basicConfig(level=logging.INFO)


async def main():
    client = await Client.connect("localhost:7233")

    worker = Worker(
        client,
        task_queue="saga-queue",
        workflows=[ChangeHostnameSagaWorkflow],
        activities=[
            get_current_hostname,
            apply_hostname,
            validate_hostname,
            rollback_hostname,
            send_message,
        ],
    )

    print("Worker SAGA iniciado. Aguardando tarefas... (Ctrl+C para parar)")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
