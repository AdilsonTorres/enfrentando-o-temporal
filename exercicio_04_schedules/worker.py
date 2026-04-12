import asyncio
import logging
from dotenv import load_dotenv

load_dotenv("../.env")

from temporalio.client import Client
from temporalio.worker import Worker

from activities.compliance import check_device_compliance
from activities.notify import send_message
from workflow import ComplianceCheckWorkflow
logging.basicConfig(level=logging.INFO)


async def main():
    client = await Client.connect("localhost:7233")

    worker = Worker(
        client,
        task_queue="compliance-queue",
        workflows=[ComplianceCheckWorkflow],
        activities=[check_device_compliance, send_message],
    )

    print("Worker Compliance iniciado. Aguardando tarefas... (Ctrl+C para parar)")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
