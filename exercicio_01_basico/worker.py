import asyncio
import logging
from dotenv import load_dotenv
from temporalio.client import Client
from temporalio.worker import Worker

from activities import get_device_info
from workflow import DeviceInfoWorkflow

load_dotenv("../.env")
logging.basicConfig(level=logging.INFO)


async def main():
    client = await Client.connect("localhost:7233")

    worker = Worker(
        client,
        task_queue="device-info-queue",
        workflows=[DeviceInfoWorkflow],
        activities=[get_device_info],
    )

    print("Worker iniciado. Aguardando tarefas... (Ctrl+C para parar)")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
