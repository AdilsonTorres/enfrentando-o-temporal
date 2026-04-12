import asyncio
import logging
from dotenv import load_dotenv
from temporalio.client import Client
from temporalio.worker import Worker

from activities.device import apply_banner
from workflow import MultiBannerWorkflow

load_dotenv("../../.env")
logging.basicConfig(level=logging.INFO)


async def main():
    client = await Client.connect("localhost:7233")

    worker = Worker(
        client,
        task_queue="paralelo-queue",
        workflows=[MultiBannerWorkflow],
        activities=[apply_banner],
    )

    print("Worker Paralelo iniciado. (Ctrl+C para parar)")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
