"""
Exercício 2 — SAGA: Configuração com Rollback Automático

Para demonstrar o rollback, você pode:
  1. Passar --force-fail → hostname inválido → validação falha → rollback automático
  2. Desligar a interface de gerência do device entre apply e validate

Execute:
  python run.py                          # Arista router-01, mudança com sucesso
  python run.py --force-fail             # Arista router-01, força rollback
  python run.py --nokia                  # Nokia srl-01, mudança com sucesso
  python run.py --nokia --force-fail     # Nokia srl-01, força rollback
"""

import asyncio
import os
import sys
import uuid
from dotenv import load_dotenv
from temporalio.client import Client

from workflow import ChangeHostnameSagaWorkflow, ChangeHostnameInput

load_dotenv("../.env")

DEVICE_01 = os.getenv("DEVICE_01", "192.168.100.101")  # Arista router-01
DEVICE_03 = os.getenv("DEVICE_03", "192.168.100.103")  # Nokia srl-01


async def main():
    nokia_mode = "--nokia" in sys.argv
    force_fail = "--force-fail" in sys.argv

    device_ip = DEVICE_03 if nokia_mode else DEVICE_01
    device_type = "srl" if nokia_mode else "eos"

    if "--device" in sys.argv:
        idx = sys.argv.index("--device")
        device_ip = sys.argv[idx + 1]
    if "--device-type" in sys.argv:
        idx = sys.argv.index("--device-type")
        device_type = sys.argv[idx + 1]

    suffix = "srl-01-new" if device_type == "srl" else "router-01-new"
    new_hostname = suffix
    if force_fail:
        print(f"[MODO FALHA] Apply será executado (device muda), depois falha simulada → rollback SAGA")
    else:
        print(f"[MODO NORMAL] Alterando hostname para '{new_hostname}'")

    print(f"Device : {device_ip} ({device_type.upper()})")

    client = await Client.connect("localhost:7233")
    workflow_id = f"saga-hostname-{uuid.uuid4().hex[:8]}"

    result = await client.execute_workflow(
        ChangeHostnameSagaWorkflow.run,
        ChangeHostnameInput(device_ip=device_ip, new_hostname=new_hostname, device_type=device_type, force_fail=force_fail),
        id=workflow_id,
        task_queue="saga-queue",
    )

    print(f"\n=== Resultado ===")
    print(f"  Status : {result['status']}")
    print(f"  Device : {result['device']}")
    if result["status"] == "success":
        print(f"  Hostname: {result['hostname']}")
    else:
        print(f"  Erro   : {result.get('error', 'N/A')}")
    print(f"\nVeja o histórico completo no Temporal UI: http://localhost:8080")


if __name__ == "__main__":
    asyncio.run(main())
