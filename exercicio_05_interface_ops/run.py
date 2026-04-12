"""
Exercício 5 — SAGA + Human-in-the-Loop: Admin-State de Interface

Combina o padrão SAGA (ex02) com aprovação humana (ex03):
  1. O workflow lê o estado atual da interface
  2. Envia notificação pedindo aprovação
  3. Aguarda o sinal do operador (approve/reject)
  4. Se aprovado: aplica e valida; rollback automático se a validação falhar

Uso:
  # Disparar o workflow (pausa aguardando aprovação)
  python run.py                              # Arista: Ethernet1 → down
  python run.py --up                         # Arista: Ethernet1 → up
  python run.py --nokia                      # Nokia: ethernet-1/1 → down
  python run.py --nokia --up                 # Nokia: ethernet-1/1 → up

  # Aprovar ou rejeitar (em outro terminal)
  python run.py --approve <workflow-id>
  python run.py --reject  <workflow-id> "Motivo da rejeição"

  # Consultar status
  python run.py --status <workflow-id>

Nomes de interface:
  Arista EOS    : Ethernet1 (padrão)
  Nokia SR Linux: ethernet-1/1 (padrão com --nokia)
"""

import asyncio
import os
import sys
import uuid
from dotenv import load_dotenv
from temporalio.client import Client

from workflow import InterfaceAdminStateWorkflow, InterfaceAdminStateInput

load_dotenv("../.env")

DEVICE_01 = os.getenv("DEVICE_01", "192.168.100.101")  # Arista router-01
DEVICE_03 = os.getenv("DEVICE_03", "192.168.100.103")  # Nokia srl-01


async def main():
    client = await Client.connect("localhost:7233")
    args = sys.argv[1:]

    # --- Aprovar ---
    if args and args[0] == "--approve":
        wf_id = args[1]
        handle = client.get_workflow_handle(wf_id)
        await handle.signal(InterfaceAdminStateWorkflow.approve)
        print(f"[OK] Sinal de aprovação enviado para '{wf_id}'")
        return

    # --- Rejeitar ---
    if args and args[0] == "--reject":
        wf_id = args[1]
        reason = args[2] if len(args) > 2 else "sem motivo informado"
        handle = client.get_workflow_handle(wf_id)
        await handle.signal(InterfaceAdminStateWorkflow.reject, reason)
        print(f"[OK] Sinal de rejeição enviado para '{wf_id}': {reason}")
        return

    # --- Consultar status ---
    if args and args[0] == "--status":
        wf_id = args[1]
        handle = client.get_workflow_handle(wf_id)
        status = await handle.query(InterfaceAdminStateWorkflow.current_status)
        print(f"Status de '{wf_id}': {status}")
        return

    # --- Disparar novo workflow ---
    nokia_mode = "--nokia" in args
    up_mode = "--up" in args

    device_ip = DEVICE_03 if nokia_mode else DEVICE_01
    device_type = "srl" if nokia_mode else "eos"
    interface = "ethernet-1/1" if nokia_mode else "Ethernet1"
    new_state = "up" if up_mode else "down"

    wf_id = f"interface-ops-{uuid.uuid4().hex[:8]}"

    print(f"Disparando workflow: {wf_id}")
    print(f"Device   : {device_ip} ({device_type.upper()})")
    print(f"Interface: {interface}")
    print(f"Operação : admin-state → '{new_state}'")
    print()
    print("O workflow vai pausar e aguardar sua aprovação.")
    print("Em outro terminal, execute:")
    print(f"  python run.py --approve {wf_id}")
    print()

    result = await client.execute_workflow(
        InterfaceAdminStateWorkflow.run,
        InterfaceAdminStateInput(
            device_ip=device_ip,
            interface=interface,
            new_state=new_state,
            workflow_id=wf_id,
            device_type=device_type,
        ),
        id=wf_id,
        task_queue="interface-ops-queue",
    )

    print("\n=== Resultado ===")
    print(f"  Status   : {result['status']}")
    if result["status"] == "success":
        print(f"  Interface: {result['interface']}")
        print(f"  Estado   : {result['final_state']}")
    elif result["status"] == "rejected":
        print(f"  Motivo   : {result.get('reason', 'N/A')}")
    elif result["status"] == "rollback":
        print(f"  Erro     : {result.get('error', 'N/A')}")
    print(f"\nHistórico completo: http://localhost:8080")


if __name__ == "__main__":
    asyncio.run(main())
