import asyncio
import os
import uuid
from dotenv import load_dotenv
from temporalio.client import Client

from workflow import MultiBannerWorkflow, MultiBannerInput, DeviceTarget

load_dotenv("../../.env")

DEVICE_01 = os.getenv("DEVICE_01", "192.168.100.101")  # Arista router-01
DEVICE_03 = os.getenv("DEVICE_03", "192.168.100.103")  # Nokia srl-01

BANNER = "Acesso restrito. Este equipamento é monitorado."


async def main():
    client = await Client.connect("localhost:7233")

    devices = [
        DeviceTarget(ip=DEVICE_01, device_type="eos"),
        DeviceTarget(ip=DEVICE_03, device_type="srl"),
    ]

    print(f"Aplicando banner em {len(devices)} devices em paralelo:")
    for d in devices:
        print(f"  - {d.ip} ({d.device_type.upper()})")
    print()

    result = await client.execute_workflow(
        MultiBannerWorkflow.run,
        MultiBannerInput(devices=devices, banner_text=BANNER),
        id=f"banner-paralelo-{uuid.uuid4().hex[:8]}",
        task_queue="paralelo-queue",
    )

    print(f"\n=== Resultado ===")
    print(f"  Sucesso : {result['success']}")
    print(f"  Falhas  : {result['failed']}")
    print(f"\nHistórico: http://localhost:8080")


if __name__ == "__main__":
    asyncio.run(main())
