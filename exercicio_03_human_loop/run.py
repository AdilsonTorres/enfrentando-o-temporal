"""
Exercício 3 — Human-in-the-Loop: Aprovação antes de aplicar mudança

Uso:
  # 1. Disparar o workflow (ele pausa e aguarda aprovação)
  python run.py                             # Arista router-01
  python run.py --nokia                     # Nokia srl-01

  # 2. Em outro terminal: aprovar a mudança
  python run.py --approve <workflow-id>

  # 3. Ou rejeitar com um motivo
  python run.py --reject <workflow-id> "Motivo da rejeição"

  # 4. Consultar o status atual (sem modificar nada)
  python run.py --status <workflow-id>

Nomes de interface:
  Arista EOS   : Ethernet1 (padrão)
  Nokia SR Linux: ethernet-1/1 (padrão com --nokia)
"""

import asyncio
import os
import sys
import uuid
from dotenv import load_dotenv
from temporalio.client import Client

from workflow import InterfaceChangeApprovalWorkflow, InterfaceChangeInput

load_dotenv("../.env")

DEVICE_01 = os.getenv("DEVICE_01", "192.168.100.101")  # Arista router-01
DEVICE_03 = os.getenv("DEVICE_03", "192.168.100.103")  # Nokia srl-01


async def main():
    client = await Client.connect("localhost:7233")
    args = sys.argv[1:]

    # --- Aprovar ---
    if args and args[0] == "--approve":
        workflow_id = args[1]
        handle = client.get_workflow_handle(workflow_id)
        await handle.signal(InterfaceChangeApprovalWorkflow.approve)
        print(f"[OK] Sinal de aprovação enviado para '{workflow_id}'")
        return

    # --- Rejeitar ---
    if args and args[0] == "--reject":
        workflow_id = args[1]
        reason = args[2] if len(args) > 2 else "sem motivo informado"
        handle = client.get_workflow_handle(workflow_id)
        await handle.signal(InterfaceChangeApprovalWorkflow.reject, reason)
        print(f"[OK] Sinal de rejeição enviado para '{workflow_id}': {reason}")
        return

    # --- Consultar status ---
    if args and args[0] == "--status":
        workflow_id = args[1]
        handle = client.get_workflow_handle(workflow_id)
        status = await handle.query(InterfaceChangeApprovalWorkflow.current_status)
        print(f"Status de '{workflow_id}': {status}")
        return

    # --- Disparar novo workflow ---
    nokia_mode = "--nokia" in args
    device_ip = DEVICE_03 if nokia_mode else DEVICE_01
    device_type = "srl" if nokia_mode else "eos"

    # Nomes de interface diferem por vendor
    interface = "ethernet-1/1" if nokia_mode else "Ethernet1"
    new_description = "uplink-to-router-01" if nokia_mode else "uplink-to-srl-01"

    workflow_id = f"approval-{uuid.uuid4().hex[:8]}"

    print(f"Disparando workflow: {workflow_id}")
    print(f"Device   : {device_ip} ({device_type.upper()})")
    print(f"Interface: {interface}")
    print(f"Nova desc: '{new_description}'")
    print()
    print("O workflow vai pausar e aguardar sua aprovação.")
    print("→ Use os botões ✅ Aprovar / ❌ Rejeitar no Telegram, ou:")
    print(f"  python run.py --approve {workflow_id}")
    print()

    result = await client.execute_workflow(
        InterfaceChangeApprovalWorkflow.run,
        InterfaceChangeInput(
            device_ip=device_ip,
            interface=interface,
            new_description=new_description,
            workflow_id=workflow_id,
            device_type=device_type,
        ),
        id=workflow_id,
        task_queue="approval-queue",
    )

    print(f"\n=== Resultado ===")
    print(f"  Status: {result['status']}")
    if result["status"] == "success":
        print(f"  Interface: {result['interface']}")
        print(f"  Descrição: {result['description']}")
    elif result["status"] == "rejected":
        print(f"  Motivo: {result.get('reason', 'N/A')}")
    print(f"\nHistórico completo: http://localhost:8080")


if __name__ == "__main__":
    asyncio.run(main())
