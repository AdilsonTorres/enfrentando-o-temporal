"""
Exercício 1 — Workflow Básico

Uso:
  python run.py                  # Arista router-01 (padrão)
  python run.py --nokia          # Nokia srl-01
  python run.py --device 192.168.100.102 --device-type eos
"""

import asyncio
import os
import sys
from dotenv import load_dotenv
from temporalio.client import Client, WorkflowFailureError

from workflow import DeviceInfoWorkflow, DeviceInfoInput

load_dotenv("../.env")

DEVICE_01 = os.getenv("DEVICE_01", "192.168.100.101")  # Arista router-01
DEVICE_03 = os.getenv("DEVICE_03", "192.168.100.103")  # Nokia srl-01


async def _aguardar_com_status(handle) -> None:
    """Imprime uma linha de status a cada 6s enquanto o workflow executa."""
    elapsed = 0
    while True:
        await asyncio.sleep(6)
        elapsed += 6
        print(f"  ... aguardando ({elapsed}s) — retries automáticos em andamento", flush=True)


async def main():
    # Opções de linha de comando simples
    nokia_mode = "--nokia" in sys.argv
    device_ip = DEVICE_03 if nokia_mode else DEVICE_01
    device_type = "srl" if nokia_mode else "eos"

    # Permite sobrescrever via --device e --device-type
    if "--device" in sys.argv:
        idx = sys.argv.index("--device")
        device_ip = sys.argv[idx + 1]
    if "--device-type" in sys.argv:
        idx = sys.argv.index("--device-type")
        device_type = sys.argv[idx + 1]

    client = await Client.connect("localhost:7233")

    handle = await client.start_workflow(
        DeviceInfoWorkflow.run,
        DeviceInfoInput(device_ip=device_ip, device_type=device_type),
        id=f"device-info-{device_type}-{device_ip.split('.')[-1]}",
        task_queue="device-info-queue",
    )

    print(f"Workflow iniciado : {handle.id}")
    print(f"Device            : {device_ip} ({device_type.upper()})")
    print(f"Temporal UI       : http://localhost:8080")
    print()

    status_task = asyncio.create_task(_aguardar_com_status(handle))

    try:
        result = await handle.result()
        status_task.cancel()

        print("\n=== Resultado ===")
        print(f"  Hostname  : {result['data']['hostname']}")
        print(f"  OS Version: {result['data']['os_version']}")
        print(f"  Uptime    : {result['data']['uptime']}s")
        print(f"  Interfaces: {', '.join(result['data']['interfaces'])}")
        print(f"\nHistórico completo: http://localhost:8080")

    except WorkflowFailureError as e:
        status_task.cancel()

        # Desempacota a cadeia de exceções para exibir a causa raiz
        cause = e.cause
        while cause is not None and getattr(cause, "cause", None) is not None:
            cause = cause.cause

        print(f"\n[FALHA] O workflow falhou após todas as tentativas de retry.")
        print(f"  Workflow ID : {handle.id}")
        print(f"  Causa       : {cause}")
        print(f"\nHistórico completo: http://localhost:8080")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
